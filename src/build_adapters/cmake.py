"""
CMake Build Adapter - Implementation for CMakeLists.txt files.

This module provides the adapter for the CMake build system.

As per top30_skills.md - Wave 2.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter, ModuleInfo
from src.utils.logger import get_logger


class CMakeAdapter(IBuildAdapter):
    """
    Build adapter for CMake (CMakeLists.txt) files.

    CMake uses a declarative syntax with commands like
    add_executable, add_library, target_include_directories, etc.
    """

    BUILD_FILE_NAME = 'CMakeLists.txt'

    def __init__(self, root_dir: Path):
        super().__init__(root_dir)
        self.logger = get_logger(__name__)

    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the CMakeLists.txt that governs a given source file.

        Searches upward from the source file's directory.
        """
        current_dir = source_file.parent if source_file.is_file() else source_file

        while current_dir >= self.root_dir:
            build_file = current_dir / self.BUILD_FILE_NAME
            if build_file.exists():
                self.logger.debug(f"Found CMakeLists.txt at {build_file}")
                return build_file
            current_dir = current_dir.parent

        self.logger.warning(f"No CMakeLists.txt found for {source_file}")
        return None

    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a CMakeLists.txt and extract target information.

        Extracts add_executable, add_library, and related commands.
        """
        build_file = self.find_build_file(file_path)
        if not build_file:
            return None

        try:
            content = build_file.read_text()

            # Extract target definitions
            targets = self._extract_targets(content)

            if not targets:
                self.logger.warning(f"No targets found in {build_file}")
                return None

            # Return the first target
            target_name, target_type, sources = targets[0]

            return ModuleInfo(
                name=target_name,
                path=build_file,
                module_type=target_type,
                sources=sources
            )

        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return None

    def _extract_targets(self, content: str) -> List[tuple]:
        """Extract target definitions from CMakeLists.txt."""
        targets = []

        # Pattern for add_executable and add_library
        patterns = [
            (r'add_executable\s*\(\s*(\w+)\s+([^)]+)\)', 'executable'),
            (r'add_library\s*\(\s*(\w+)\s+(?:STATIC|SHARED|MODULE)?\s*([^)]+)\)', 'library'),
        ]

        for pattern, target_type in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                target_name = match[0]
                sources_str = match[1] if len(match) > 1 else ''
                sources = re.findall(r'[\w./]+\.\w+', sources_str)
                targets.append((target_name, target_type, sources))

        return targets

    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'library'
    ) -> bool:
        """
        Add a dependency to a CMake target.

        Uses target_link_libraries() command.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            self.logger.error(f"Could not find CMakeLists.txt for target {target_module}")
            return False

        try:
            content = build_file.read_text()

            # Check if target_link_libraries exists for this target
            pattern = rf'target_link_libraries\s*\(\s*{re.escape(target_module)}'
            if re.search(pattern, content, re.IGNORECASE):
                # Append to existing target_link_libraries
                pattern = rf'(target_link_libraries\s*\(\s*{re.escape(target_module)}[^)]*?)(\))'
                replacement = rf'\1 {dep_name}\2'
                new_content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            else:
                # Add new target_link_libraries after target definition
                target_pattern = rf'(add_(?:executable|library)\s*\(\s*{re.escape(target_module)}[^)]*\))'
                replacement = rf'\1\ntarget_link_libraries({target_module} {dep_name})'
                new_content = re.sub(target_pattern, replacement, content, count=1, flags=re.IGNORECASE)

            build_file.write_text(new_content)
            self.logger.info(f"Added dependency {dep_name} to {target_module}")
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
        Modify include directories for a CMake target.

        Uses target_include_directories() or include_directories().
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()

            if action == 'add':
                # Check if target_include_directories exists
                pattern = rf'target_include_directories\s*\(\s*{re.escape(target_module)}'
                if re.search(pattern, content, re.IGNORECASE):
                    # Append to existing
                    pattern = rf'(target_include_directories\s*\(\s*{re.escape(target_module)}[^)]*?)(\))'
                    replacement = rf'\1\n    {path}\2'
                    new_content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
                else:
                    # Add new target_include_directories after target definition
                    target_pattern = rf'(add_(?:executable|library)\s*\(\s*{re.escape(target_module)}[^)]*\))'
                    replacement = rf'\1\ntarget_include_directories({target_module} PRIVATE {path})'
                    new_content = re.sub(target_pattern, replacement, content, count=1, flags=re.IGNORECASE)

                build_file.write_text(new_content)
                self.logger.info(f"Added include path {path} to {target_module}")
                return True

            elif action == 'remove':
                pattern = rf'\s*{re.escape(path)}'
                new_content = re.sub(pattern, '', content)
                build_file.write_text(new_content)
                self.logger.info(f"Removed include path {path} from {target_module}")
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
        Update compile options for a CMake target.

        Uses target_compile_options().
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            flags_str = ' '.join(flags)

            if action == 'add':
                # Check if target_compile_options exists
                pattern = rf'target_compile_options\s*\(\s*{re.escape(target_module)}'
                if re.search(pattern, content, re.IGNORECASE):
                    pattern = rf'(target_compile_options\s*\(\s*{re.escape(target_module)}[^)]*?)(\))'
                    replacement = rf'\1 {flags_str}\2'
                    new_content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
                else:
                    target_pattern = rf'(add_(?:executable|library)\s*\(\s*{re.escape(target_module)}[^)]*\))'
                    replacement = rf'\1\ntarget_compile_options({target_module} PRIVATE {flags_str})'
                    new_content = re.sub(target_pattern, replacement, content, count=1, flags=re.IGNORECASE)

                build_file.write_text(new_content)
                self.logger.info(f"Added cflags {flags} to {target_module}")
                return True

            elif action == 'remove':
                for flag in flags:
                    pattern = rf'\s*{re.escape(flag)}'
                    content = re.sub(pattern, '', content)
                build_file.write_text(content)
                self.logger.info(f"Removed cflags {flags} from {target_module}")
                return True

        except Exception as e:
            self.logger.error(f"Error updating cflags: {e}")
            return False

        return False

    def _find_build_file_for_target(self, target_name: str) -> Optional[Path]:
        """Find the CMakeLists.txt containing a specific target."""
        for build_file in self.root_dir.rglob(self.BUILD_FILE_NAME):
            try:
                content = build_file.read_text()
                if re.search(rf'add_(?:executable|library)\s*\(\s*{re.escape(target_name)}', content, re.IGNORECASE):
                    return build_file
            except Exception:
                continue

        return None
