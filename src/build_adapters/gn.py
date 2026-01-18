"""
GN Build Adapter - Implementation for BUILD.gn files.

This module provides the concrete adapter for GN build system,
commonly used in OpenHarmony and Chromium-based projects.

As per design.md Section 2.3.
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter, ModuleInfo
from src.build_adapters.parser import parse_build_gn, ParsedModule
from src.utils.logger import get_logger


class GNAdapter(IBuildAdapter):
    """
    Build adapter for GN (BUILD.gn) files.

    GN is used by OpenHarmony and other projects. This adapter
    provides methods to read and modify BUILD.gn files while
    preserving formatting.
    """

    BUILD_FILE_NAME = 'BUILD.gn'

    def __init__(self, root_dir: Path):
        super().__init__(root_dir)
        self.logger = get_logger(__name__)
        self._parsed_cache: Dict[Path, List[ParsedModule]] = {}

    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the BUILD.gn file that governs a given source file.

        Searches upward from the source file's directory.
        """
        current_dir = source_file.parent if source_file.is_file() else source_file

        while current_dir >= self.root_dir:
            build_file = current_dir / self.BUILD_FILE_NAME
            if build_file.exists():
                self.logger.debug(f"Found BUILD.gn at {build_file}")
                return build_file
            current_dir = current_dir.parent

        self.logger.warning(f"No BUILD.gn found for {source_file}")
        return None

    def _parse_build_file(self, build_file: Path) -> List[ParsedModule]:
        """Parse a BUILD.gn file using the robust parser, with caching."""
        if build_file in self._parsed_cache:
            return self._parsed_cache[build_file]

        try:
            content = build_file.read_text()
            targets = parse_build_gn(content)
            self._parsed_cache[build_file] = targets
            return targets
        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return []

    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a BUILD.gn file and extract module information.

        Uses the robust GNParser for parsing.
        """
        build_file = self.find_build_file(file_path)
        if not build_file:
            return None

        try:
            targets = self._parse_build_file(build_file)

            if not targets:
                self.logger.warning(f"No targets found in {build_file}")
                return None

            # For simplicity, return the first target
            target = targets[0]

            # Extract from parsed properties
            deps = target.properties.get('deps', [])
            if not isinstance(deps, list):
                deps = []

            includes = target.properties.get('include_dirs', [])
            if not isinstance(includes, list):
                includes = []

            sources = target.properties.get('sources', [])
            if not isinstance(sources, list):
                sources = []

            return ModuleInfo(
                name=target.name,
                path=build_file,
                module_type=target.module_type,
                dependencies=deps,
                include_dirs=includes,
                sources=sources
            )

        except Exception as e:
            self.logger.error(f"Error parsing {build_file}: {e}")
            return None

    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'shared_library'
    ) -> bool:
        """
        Add a dependency to a GN target.

        For GN, dependencies are added to the 'deps' array.
        """
        # Find the BUILD.gn file containing the target
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            self.logger.error(f"Could not find BUILD.gn for target {target_module}")
            return False

        try:
            content = build_file.read_text()

            # Find the target block
            target_pattern = rf'(\w+)\s*\(\s*"{re.escape(target_module)}"\s*\)\s*\{{'
            match = re.search(target_pattern, content)
            if not match:
                self.logger.error(f"Target {target_module} not found in {build_file}")
                return False

            # Find the deps array within the target
            # This is a simplified approach; production code needs proper parsing
            target_start = match.end()

            # Check if deps already exists
            deps_pattern = r'deps\s*=\s*\['
            deps_match = re.search(deps_pattern, content[target_start:])

            if deps_match:
                # Add to existing deps array
                insert_pos = target_start + deps_match.end()
                new_content = (
                    content[:insert_pos] +
                    f'\n    "{dep_name}",' +
                    content[insert_pos:]
                )
            else:
                # Create new deps array (insert after opening brace)
                new_content = (
                    content[:target_start] +
                    f'\n  deps = [\n    "{dep_name}",\n  ]' +
                    content[target_start:]
                )

            build_file.write_text(new_content)
            self._format_file(build_file)

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
        Modify the include_dirs for a GN target.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()

            target_pattern = rf'(\w+)\s*\(\s*"{re.escape(target_module)}"\s*\)\s*\{{'
            match = re.search(target_pattern, content)
            if not match:
                return False

            target_start = match.end()

            if action == 'add':
                # Check if include_dirs exists
                include_pattern = r'include_dirs\s*=\s*\['
                include_match = re.search(include_pattern, content[target_start:])

                if include_match:
                    insert_pos = target_start + include_match.end()
                    new_content = (
                        content[:insert_pos] +
                        f'\n    "{path}",' +
                        content[insert_pos:]
                    )
                else:
                    new_content = (
                        content[:target_start] +
                        f'\n  include_dirs = [\n    "{path}",\n  ]' +
                        content[target_start:]
                    )

                build_file.write_text(new_content)
                self._format_file(build_file)
                self.logger.info(f"Added include path {path} to {target_module}")
                return True

            elif action == 'remove':
                # Remove the path from include_dirs
                path_pattern = rf',?\s*"{re.escape(path)}"'
                new_content = re.sub(path_pattern, '', content)
                build_file.write_text(new_content)
                self._format_file(build_file)
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
        Update cflags for a GN target.

        In GN, flags are typically set via cflags, cflags_cc, etc.
        """
        build_file = self._find_build_file_for_target(target_module)
        if not build_file:
            return False

        try:
            content = build_file.read_text()

            target_pattern = rf'(\w+)\s*\(\s*"{re.escape(target_module)}"\s*\)\s*\{{'
            match = re.search(target_pattern, content)
            if not match:
                return False

            target_start = match.end()

            if action == 'add':
                flags_str = ', '.join(f'"{f}"' for f in flags)

                cflags_pattern = r'cflags\s*=\s*\['
                cflags_match = re.search(cflags_pattern, content[target_start:])

                if cflags_match:
                    insert_pos = target_start + cflags_match.end()
                    new_content = (
                        content[:insert_pos] +
                        f'\n    {flags_str},' +
                        content[insert_pos:]
                    )
                else:
                    new_content = (
                        content[:target_start] +
                        f'\n  cflags = [\n    {flags_str},\n  ]' +
                        content[target_start:]
                    )

                build_file.write_text(new_content)
                self._format_file(build_file)
                self.logger.info(f"Added cflags {flags} to {target_module}")
                return True

        except Exception as e:
            self.logger.error(f"Error updating cflags: {e}")
            return False

        return False

    def _find_build_file_for_target(self, target_name: str) -> Optional[Path]:
        """
        Find the BUILD.gn file containing a specific target.

        This is a simplified implementation that searches common locations.
        """
        # For now, search the entire root directory
        # In production, you'd want to use GN's desc command or maintain an index
        for build_file in self.root_dir.rglob(self.BUILD_FILE_NAME):
            try:
                content = build_file.read_text()
                if f'"{target_name}"' in content:
                    return build_file
            except Exception:
                continue

        return None

    def _format_file(self, file_path: Path) -> bool:
        """
        Format a BUILD.gn file using gn format.

        As per design.md Section 2.3.
        """
        try:
            subprocess.run(
                ['gn', 'format', str(file_path)],
                capture_output=True,
                check=True
            )
            self.logger.debug(f"Formatted {file_path}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"gn format failed for {file_path}: {e}")
            return False
        except FileNotFoundError:
            self.logger.warning("gn binary not found, skipping format")
            return False
