"""
Build Adapters - Abstract interface for build system manipulation.

This module defines the IBuildAdapter abstract base class, which provides
a unified interface for reading and modifying build configuration files
across different build systems (Soong, GN, CMake, etc.).

As per design.md Section 2.3.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModuleInfo:
    """
    Information about a build module.

    Attributes:
        name: The module name.
        path: Path to the build file defining this module.
        module_type: Type of module (e.g., 'cc_library', 'executable').
        dependencies: List of dependency module names.
        include_dirs: List of include directories.
        sources: List of source files.
        properties: Additional module properties.
    """
    name: str
    path: Path
    module_type: str
    dependencies: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


class IBuildAdapter(ABC):
    """
    Abstract base class for build system adapters.

    Each concrete adapter (Soong, GN, etc.) must implement these methods
    to provide a unified interface for build file manipulation.

    As per design.md Section 2.3:
    - get_module_info: Parse build file and extract module attributes
    - inject_dependency: Add static_libs or deps
    - modify_include_path: Modify include_dirs or public_configs
    """

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def get_module_info(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a build file and extract module information.

        Args:
            file_path: Path to the source file (not the build file).
                      The adapter should locate the corresponding build file.

        Returns:
            ModuleInfo object or None if module not found.
        """
        pass

    @abstractmethod
    def find_build_file(self, source_file: Path) -> Optional[Path]:
        """
        Find the build file that governs a given source file.

        Args:
            source_file: Path to a source file.

        Returns:
            Path to the build file, or None if not found.
        """
        pass

    @abstractmethod
    def inject_dependency(
        self,
        target_module: str,
        dep_name: str,
        dep_type: str = 'shared_library'
    ) -> bool:
        """
        Add a dependency to a module.

        Args:
            target_module: The name of the module to modify.
            dep_name: The dependency to add.
            dep_type: Type of dependency ('shared_library', 'static_library', 'header').

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def modify_include_path(
        self,
        target_module: str,
        path: str,
        action: str = 'add'
    ) -> bool:
        """
        Modify the include paths for a module.

        Args:
            target_module: The name of the module to modify.
            path: The include path to add or remove.
            action: Either 'add' or 'remove'.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def update_cflags(
        self,
        target_module: str,
        flags: List[str],
        action: str = 'add'
    ) -> bool:
        """
        Update compiler flags for a module.

        Args:
            target_module: The name of the module to modify.
            flags: The flags to add or remove.
            action: Either 'add' or 'remove'.

        Returns:
            True if successful, False otherwise.
        """
        pass

    def dry_run(self, operations: List[Dict[str, Any]]) -> str:
        """
        Perform a dry-run and return the expected diff.

        As per design.md Section 6.2.

        Args:
            operations: List of operations to simulate.

        Returns:
            A string representation of the expected changes (diff format).
        """
        # Default implementation returns a simple summary
        lines = ["Dry-run summary:"]
        for op in operations:
            lines.append(f"  - {op.get('action', 'unknown')}: {op.get('params', {})}")
        return '\n'.join(lines)
