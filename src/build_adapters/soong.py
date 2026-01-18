"""
Soong Build Adapter - Implementation for Android.bp files.

This module provides the concrete adapter for Soong build system,
used in AOSP (Android Open Source Project).

As per design.md Section 2.3.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter, ModuleInfo
from src.build_adapters.parser import parse_android_bp, ParsedModule
from src.utils.logger import get_logger


class SoongAdapter(IBuildAdapter):
    """
    Build adapter for Soong (Android.bp) files.

    Android.bp files use a Blueprint syntax. This adapter parses
    and modifies these files while preserving comments and formatting
    as much as possible.
    """

    BUILD_FILE_NAME = 'Android.bp'

    def __init__(self, root_dir: Path):
        super().__init__(root_dir)
        self.logger = get_logger(__name__)
        self._parsed_cache: Dict[Path, List[ParsedModule]] = {}

    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the Android.bp file that governs a given source file.

        Searches upward from the source file's directory.
        """
        current_dir = source_file.parent if source_file.is_file() else source_file

        while current_dir >= self.root_dir:
            build_file = current_dir / self.BUILD_FILE_NAME
            if build_file.exists():
                self.logger.debug(f"Found Android.bp at {build_file}")
                return build_file
            current_dir = current_dir.parent

        self.logger.warning(f"No Android.bp found for {source_file}")
        return None

    def _parse_build_file(self, build_file: Path) -> List[ParsedModule]:
        """Parse an Android.bp file using the robust parser, with caching."""
        if build_file in self._parsed_cache:
            return self._parsed_cache[build_file]

        try:
            content = build_file.read_text()
            modules = parse_android_bp(content)
            self._parsed_cache[build_file] = modules
            return modules
        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return []

    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse an Android.bp file and extract module information.

        Uses the robust BlueprintParser for parsing.
        """
        build_file = self.find_build_file(file_path)
        if not build_file:
            return None

        try:
            modules = self._parse_build_file(build_file)

            if not modules:
                self.logger.warning(f"No modules found in {build_file}")
                return None

            # Return the first module
            module = modules[0]

            # Extract dependencies from properties
            deps: List[str] = []
            deps.extend(module.properties.get('shared_libs', []))
            deps.extend(module.properties.get('static_libs', []))
            deps.extend(module.properties.get('header_libs', []))

            includes: List[str] = []
            includes.extend(module.properties.get('include_dirs', []))
            includes.extend(module.properties.get('local_include_dirs', []))

            sources = module.properties.get('srcs', [])

            return ModuleInfo(
                name=module.name,
                path=build_file,
                module_type=module.module_type,
                dependencies=deps,
                include_dirs=includes,
                sources=sources
            )

        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return None

    def _extract_module_block(self, content: str, module_name: str) -> Optional[str]:
        """Extract the content block for a specific module."""
        pattern = rf'(\w+)\s*\{{\s*name:\s*"{re.escape(module_name)}"'
        match = re.search(pattern, content)
        if not match:
            return None

        # Find matching braces
        start = match.start()
        brace_count = 0
        end = start

        for i, char in enumerate(content[start:], start=start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        return content[start:end]

    def _extract_list_field(self, content: str, field_name: str) -> List[str]:
        """Extract a list field from module content."""
        pattern = rf'{field_name}:\s*\[(.*?)\]'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return []

        list_content = match.group(1)
        return re.findall(r'"([^"]+)"', list_content)

    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'shared_library'
    ) -> bool:
        """
        Add a dependency to an Android.bp module.

        Maps dep_type to the appropriate field:
        - shared_library -> shared_libs
        - static_library -> static_libs
        - header -> header_libs
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            self.logger.error(f"Could not find Android.bp for module {target_module}")
            return False

        # Map dependency type to field name
        field_map = {
            'shared_library': 'shared_libs',
            'static_library': 'static_libs',
            'header': 'header_libs',
        }
        field_name = field_map.get(dep_type, 'shared_libs')

        try:
            content = build_file.read_text()

            # Find the module block
            module_content = self._extract_module_block(content, target_module)
            if not module_content:
                self.logger.error(f"Module {target_module} not found in {build_file}")
                return False

            module_start = content.find(module_content)
            module_end = module_start + len(module_content)

            # Check if the field exists
            field_pattern = rf'{field_name}:\s*\['
            field_match = re.search(field_pattern, module_content)

            if field_match:
                # Add to existing field
                insert_pos = module_start + field_match.end()
                new_content = (
                    content[:insert_pos] +
                    f'\n        "{dep_name}",' +
                    content[insert_pos:]
                )
            else:
                # Find position to insert new field (after name:)
                name_pattern = rf'name:\s*"{re.escape(target_module)}"'
                name_match = re.search(name_pattern, module_content)
                if name_match:
                    insert_pos = module_start + name_match.end()
                    # Find the end of the line
                    line_end = content.find('\n', insert_pos)
                    if line_end == -1:
                        line_end = insert_pos

                    new_content = (
                        content[:line_end] +
                        f',\n    {field_name}: [\n        "{dep_name}",\n    ]' +
                        content[line_end:]
                    )
                else:
                    self.logger.error("Could not find insertion point")
                    return False

            build_file.write_text(new_content)
            self.logger.info(f"Added {dep_type} {dep_name} to {target_module}")
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
        Modify the include_dirs for an Android.bp module.
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            module_content = self._extract_module_block(content, target_module)
            if not module_content:
                return False

            module_start = content.find(module_content)

            if action == 'add':
                # Check if include_dirs exists
                field_pattern = r'include_dirs:\s*\['
                field_match = re.search(field_pattern, module_content)

                if field_match:
                    insert_pos = module_start + field_match.end()
                    new_content = (
                        content[:insert_pos] +
                        f'\n        "{path}",' +
                        content[insert_pos:]
                    )
                else:
                    # Find name field and insert after
                    name_pattern = rf'name:\s*"{re.escape(target_module)}"'
                    name_match = re.search(name_pattern, module_content)
                    if name_match:
                        line_end = content.find('\n', module_start + name_match.end())
                        new_content = (
                            content[:line_end] +
                            f',\n    include_dirs: [\n        "{path}",\n    ]' +
                            content[line_end:]
                        )
                    else:
                        return False

                build_file.write_text(new_content)
                self.logger.info(f"Added include path {path} to {target_module}")
                return True

            elif action == 'remove':
                path_pattern = rf',?\s*"{re.escape(path)}"'
                new_content = re.sub(path_pattern, '', content)
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
        Update cflags for an Android.bp module.
        """
        build_file = self._find_build_file_for_module(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()
            module_content = self._extract_module_block(content, target_module)
            if not module_content:
                return False

            module_start = content.find(module_content)

            if action == 'add':
                flags_str = ',\n        '.join(f'"{f}"' for f in flags)

                cflags_pattern = r'cflags:\s*\['
                cflags_match = re.search(cflags_pattern, module_content)

                if cflags_match:
                    insert_pos = module_start + cflags_match.end()
                    new_content = (
                        content[:insert_pos] +
                        f'\n        {flags_str},' +
                        content[insert_pos:]
                    )
                else:
                    name_pattern = rf'name:\s*"{re.escape(target_module)}"'
                    name_match = re.search(name_pattern, module_content)
                    if name_match:
                        line_end = content.find('\n', module_start + name_match.end())
                        new_content = (
                            content[:line_end] +
                            f',\n    cflags: [\n        {flags_str},\n    ]' +
                            content[line_end:]
                        )
                    else:
                        return False

                build_file.write_text(new_content)
                self.logger.info(f"Added cflags {flags} to {target_module}")
                return True

        except Exception as e:
            self.logger.error(f"Error updating cflags: {e}")
            return False

        return False

    def _find_build_file_for_module(self, module_name: str) -> Optional[Path]:
        """
        Find the Android.bp file containing a specific module.
        """
        for build_file in self.root_dir.rglob(self.BUILD_FILE_NAME):
            try:
                content = build_file.read_text()
                if f'name: "{module_name}"' in content:
                    return build_file
            except Exception:
                continue

        return None
