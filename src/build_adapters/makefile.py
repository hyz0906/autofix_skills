"""
Generic Makefile Adapter - Implementation for standard Makefiles.

This module provides the adapter for generic Makefile-based projects
(not Kbuild-specific).

As per top30_skills.md - Wave 2.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter, ModuleInfo
from src.utils.logger import get_logger


class MakefileAdapter(IBuildAdapter):
    """
    Build adapter for generic Makefiles.

    This adapter handles standard Makefile syntax with variables
    like CFLAGS, CPPFLAGS, LDFLAGS, INCLUDES, SRCS, OBJS, etc.
    """

    BUILD_FILE_NAMES = ['Makefile', 'makefile', 'GNUmakefile']

    def __init__(self, root_dir: Path):
        super().__init__(root_dir)
        self.logger = get_logger(__name__)

    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the Makefile that governs a given source file.

        Searches upward from the source file's directory.
        """
        current_dir = source_file.parent if source_file.is_file() else source_file

        while current_dir >= self.root_dir:
            for name in self.BUILD_FILE_NAMES:
                build_file = current_dir / name
                if build_file.exists():
                    self.logger.debug(f"Found Makefile at {build_file}")
                    return build_file
            current_dir = current_dir.parent

        self.logger.warning(f"No Makefile found for {source_file}")
        return None

    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a Makefile and extract target/module information.

        Extracts common variables like TARGET, SRCS, OBJS, etc.
        """
        build_file = self.find_build_file(file_path)
        if not build_file:
            return None

        try:
            content = build_file.read_text()

            # Try to find the main target name
            target_name = self._extract_main_target(content, build_file)

            # Parse sources
            sources = self._extract_variable_list(content, 'SRCS')
            if not sources:
                sources = self._extract_variable_list(content, 'SOURCES')
            if not sources:
                sources = self._extract_variable_list(content, 'SRC')

            # Parse includes
            includes = self._extract_include_dirs(content)

            # Parse CFLAGS
            cflags = self._extract_variable_list(content, 'CFLAGS')

            return ModuleInfo(
                name=target_name,
                path=build_file,
                module_type='makefile',
                sources=sources,
                include_dirs=includes,
                properties={'cflags': cflags}
            )

        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return None

    def _extract_main_target(self, content: str, build_file: Path) -> str:
        """Extract the main target name from a Makefile."""
        # Try TARGET variable
        match = re.search(r'TARGET\s*[:+]?=\s*(\S+)', content)
        if match:
            return match.group(1)

        # Try PROGRAM variable
        match = re.search(r'PROGRAM\s*[:+]?=\s*(\S+)', content)
        if match:
            return match.group(1)

        # Try first target that isn't .PHONY or all
        match = re.search(r'^([a-zA-Z_]\w*):', content, re.MULTILINE)
        if match and match.group(1) not in ['all', 'clean', 'install', 'test']:
            return match.group(1)

        # Default to directory name
        return build_file.parent.name

    def _extract_variable_list(self, content: str, var_name: str) -> List[str]:
        """Extract a list of values from a Makefile variable."""
        values = []

        # Match both := and = assignments, including +=
        pattern = rf'{re.escape(var_name)}\s*[:+]?=\s*(.+?)(?:\n(?!\t)|$)'
        matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            # Handle line continuations
            match = match.replace('\\\n', ' ')
            # Split by whitespace
            parts = match.strip().split()
            values.extend(parts)

        return values

    def _extract_include_dirs(self, content: str) -> List[str]:
        """Extract include directories from CFLAGS/CPPFLAGS/INCLUDES."""
        includes = []

        # Check INCLUDES variable
        includes.extend(self._extract_variable_list(content, 'INCLUDES'))
        includes.extend(self._extract_variable_list(content, 'INCLUDE_DIRS'))

        # Extract -I flags from CFLAGS/CPPFLAGS
        for var in ['CFLAGS', 'CPPFLAGS']:
            flags = self._extract_variable_list(content, var)
            for flag in flags:
                if flag.startswith('-I'):
                    includes.append(flag[2:])

        return includes

    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'lib'
    ) -> bool:
        """
        Add a library dependency to a Makefile.

        Adds to LDFLAGS or LIBS variable.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            self.logger.error(f"Could not find Makefile for target {target_module}")
            return False

        try:
            content = build_file.read_text()

            # Format the library flag
            if dep_name.startswith('-l'):
                lib_flag = dep_name
            else:
                lib_flag = f'-l{dep_name}'

            if 'LDFLAGS' in content or 'LIBS' in content:
                # Append to existing LDFLAGS or LIBS
                for var in ['LDFLAGS', 'LIBS']:
                    pattern = rf'({var}\s*[:+]?=.*?)(\n)'
                    if re.search(pattern, content):
                        replacement = rf'\1 {lib_flag}\2'
                        content = re.sub(pattern, replacement, content, count=1)
                        break
            else:
                # Add new LDFLAGS line
                content = content + f'\nLDFLAGS += {lib_flag}\n'

            build_file.write_text(content)
            self.logger.info(f"Added library {lib_flag} to {build_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error injecting dependency: {e}")
            return False

    def modify_include_path(
        self,
        target_module: str,
        path: str,
        action: str = 'add'
    ) -> bool:
        """
        Modify include paths in a Makefile.

        Adds -I flags to CFLAGS or INCLUDES.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            include_flag = f'-I{path}'

            if action == 'add':
                # Try to add to INCLUDES first, then CFLAGS
                for var in ['INCLUDES', 'CFLAGS', 'CPPFLAGS']:
                    pattern = rf'({var}\s*[:+]?=.*?)(\n)'
                    if re.search(pattern, content):
                        replacement = rf'\1 {include_flag}\2'
                        content = re.sub(pattern, replacement, content, count=1)
                        build_file.write_text(content)
                        self.logger.info(f"Added include path {path} to {var}")
                        return True

                # If no variable exists, add INCLUDES
                content = content + f'\nINCLUDES += {include_flag}\n'
                build_file.write_text(content)
                self.logger.info(f"Added new INCLUDES with {path}")
                return True

            elif action == 'remove':
                pattern = rf'\s*{re.escape(include_flag)}'
                new_content = re.sub(pattern, '', content)
                build_file.write_text(new_content)
                self.logger.info(f"Removed include path {path}")
                return True

        except Exception as e:
            self.logger.error(f"Error modifying include path: {e}")
            return False

        return False

    def update_cflags(
        self,
        target_module: str,
        flags: List[str],
        action: str = 'add'
    ) -> bool:
        """
        Update CFLAGS in a Makefile.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            flags_str = ' '.join(flags)

            if action == 'add':
                if 'CFLAGS' in content:
                    pattern = r'(CFLAGS\s*[:+]?=.*?)(\n)'
                    replacement = rf'\1 {flags_str}\2'
                    new_content = re.sub(pattern, replacement, content, count=1)
                else:
                    new_content = content + f'\nCFLAGS += {flags_str}\n'

                build_file.write_text(new_content)
                self.logger.info(f"Added cflags {flags}")
                return True

            elif action == 'remove':
                for flag in flags:
                    pattern = rf'\s*{re.escape(flag)}'
                    content = re.sub(pattern, '', content)
                build_file.write_text(content)
                self.logger.info(f"Removed cflags {flags}")
                return True

        except Exception as e:
            self.logger.error(f"Error updating cflags: {e}")
            return False

        return False

    def _find_build_file_for_target(self, target_name: str) -> Optional[Path]:
        """Find the Makefile containing a specific target."""
        for name in self.BUILD_FILE_NAMES:
            for build_file in self.root_dir.rglob(name):
                try:
                    content = build_file.read_text()
                    # Check if target is mentioned
                    if target_name in content:
                        return build_file
                except Exception:
                    continue

        return None
