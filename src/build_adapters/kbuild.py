"""
Kbuild Build Adapter - Implementation for Linux Kernel Makefiles.

This module provides the adapter for the Kbuild build system
used in the Linux Kernel.

As per top30_skills.md - Wave 2.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter, ModuleInfo
from src.utils.logger import get_logger


class KbuildAdapter(IBuildAdapter):
    """
    Build adapter for Kbuild (Makefile/Kbuild) files in Linux Kernel.

    Kbuild files use a special Makefile syntax with obj-y, obj-m,
    ccflags-y, and similar variables.
    """

    BUILD_FILE_NAMES = ['Kbuild', 'Makefile']

    def __init__(self, root_dir: Path):
        super().__init__(root_dir)
        self.logger = get_logger(__name__)

    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the Kbuild or Makefile that governs a given source file.

        Searches upward from the source file's directory.
        """
        current_dir = source_file.parent if source_file.is_file() else source_file

        while current_dir >= self.root_dir:
            for name in self.BUILD_FILE_NAMES:
                build_file = current_dir / name
                if build_file.exists():
                    self.logger.debug(f"Found {name} at {build_file}")
                    return build_file
            current_dir = current_dir.parent

        self.logger.warning(f"No Kbuild/Makefile found for {source_file}")
        return None

    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a Kbuild/Makefile and extract module information.

        Extracts obj-y, obj-m, ccflags-y, and other common variables.
        """
        build_file = self.find_build_file(file_path)
        if not build_file:
            return None

        try:
            content = build_file.read_text()

            # Extract the module name from directory
            module_name = build_file.parent.name

            # Parse obj-y and obj-m entries
            sources = self._extract_obj_list(content, 'obj-y')
            sources += self._extract_obj_list(content, 'obj-m')

            # Parse ccflags
            cflags = self._extract_variable(content, 'ccflags-y')

            return ModuleInfo(
                name=module_name,
                path=build_file,
                module_type='kbuild',
                sources=sources,
                properties={'ccflags-y': cflags}
            )

        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return None

    def _extract_obj_list(self, content: str, var_name: str) -> List[str]:
        """Extract object file list from a Makefile variable."""
        objects = []

        # Match patterns like: obj-y += foo.o bar.o
        # or: obj-$(CONFIG_FOO) += baz.o
        pattern = rf'{re.escape(var_name)}\s*[\+:]?=\s*(.+?)(?:\n|\\)'
        matches = re.findall(pattern, content, re.MULTILINE)

        for match in matches:
            # Extract .o files
            obj_files = re.findall(r'(\w+\.o)', match)
            objects.extend(obj_files)

        return objects

    def _extract_variable(self, content: str, var_name: str) -> List[str]:
        """Extract values from a Makefile variable."""
        values = []

        pattern = rf'{re.escape(var_name)}\s*[\+:]?=\s*(.+?)(?:\n|\\)'
        matches = re.findall(pattern, content, re.MULTILINE)

        for match in matches:
            # Split by whitespace
            parts = match.strip().split()
            values.extend(parts)

        return values

    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'obj'
    ) -> bool:
        """
        Add an object dependency to a Kbuild file.

        For Kbuild, dependencies are typically added to obj-y.
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            self.logger.error(f"Could not find Kbuild for module {target_module}")
            return False

        try:
            content = build_file.read_text()

            # Check if obj-y exists
            if 'obj-y' in content:
                # Append to existing obj-y
                pattern = r'(obj-y\s*[\+:]?=.*?)(\n)'
                replacement = rf'\1 {dep_name}.o\2'
                new_content = re.sub(pattern, replacement, content, count=1)
            else:
                # Add new obj-y line
                new_content = content + f'\nobj-y += {dep_name}.o\n'

            build_file.write_text(new_content)
            self.logger.info(f"Added {dep_name}.o to obj-y in {build_file}")
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
        Modify the include path (ccflags-y) for a Kbuild module.
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            include_flag = f'-I$(srctree)/{path}'

            if action == 'add':
                if 'ccflags-y' in content:
                    # Append to existing ccflags-y
                    pattern = r'(ccflags-y\s*[\+:]?=.*?)(\n)'
                    replacement = rf'\1 {include_flag}\2'
                    new_content = re.sub(pattern, replacement, content, count=1)
                else:
                    # Add new ccflags-y line
                    new_content = content + f'\nccflags-y += {include_flag}\n'

                build_file.write_text(new_content)
                self.logger.info(f"Added include path {path} to {build_file}")
                return True

            elif action == 'remove':
                pattern = rf'\s*{re.escape(include_flag)}'
                new_content = re.sub(pattern, '', content)
                build_file.write_text(new_content)
                self.logger.info(f"Removed include path {path} from {build_file}")
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
        Update ccflags-y for a Kbuild module.
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            flags_str = ' '.join(flags)

            if action == 'add':
                if 'ccflags-y' in content:
                    pattern = r'(ccflags-y\s*[\+:]?=.*?)(\n)'
                    replacement = rf'\1 {flags_str}\2'
                    new_content = re.sub(pattern, replacement, content, count=1)
                else:
                    new_content = content + f'\nccflags-y += {flags_str}\n'

                build_file.write_text(new_content)
                self.logger.info(f"Added cflags {flags} to {build_file}")
                return True

            elif action == 'remove':
                for flag in flags:
                    pattern = rf'\s*{re.escape(flag)}'
                    content = re.sub(pattern, '', content)
                build_file.write_text(content)
                self.logger.info(f"Removed cflags {flags} from {build_file}")
                return True

        except Exception as e:
            self.logger.error(f"Error updating cflags: {e}")
            return False

        return False

    def _find_build_file_for_module(self, module_name: str) -> Optional[Path]:
        """Find the Kbuild file for a module by searching the directory tree."""
        for name in self.BUILD_FILE_NAMES:
            for build_file in self.root_dir.rglob(name):
                if build_file.parent.name == module_name:
                    return build_file
                # Also check if module_name appears in the file
                try:
                    if module_name in build_file.read_text():
                        return build_file
                except Exception:
                    continue

        return None
