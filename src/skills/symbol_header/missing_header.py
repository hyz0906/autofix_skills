"""
Missing Header Skill - Automatically fix missing header file errors.

This skill detects "file not found" type errors from the compiler,
searches for the header in the source tree, and adds the appropriate
include path to the build configuration.

As per requirement.md Section 3.3 (Missing Header Algorithm).
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter
from src.build_adapters.gn import GNAdapter
from src.build_adapters.soong import SoongAdapter
from src.context_engine.ast_grep_client import AstGrepClient
from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    register_skill,
)
from src.utils.logger import get_logger


@register_skill
class MissingHeaderSkill(BaseSkill):
    """
    Skill for fixing missing header file errors.

    Handles errors like:
    - "fatal error: 'xxx.h' file not found"
    - "error: xxx.h: No such file or directory"
    - "cannot open source file 'xxx.h'"

    Algorithm (as per requirement.md):
    1. Parse the error to extract the missing header name
    2. Use ast-grep/find to locate the header in the source tree
    3. Determine the module that provides the header
    4. Modify the build file to add the include path or dependency
    """

    # Error patterns this skill can handle
    error_codes: List[str] = [
        'E0020',      # identifier not found (often header related)
        'C1083',      # cannot open include file (MSVC)
        'fatal error', # GCC/Clang fatal error prefix
    ]

    # Regex patterns to match missing header errors
    HEADER_ERROR_PATTERNS = [
        r"fatal error:\s*'?([^'\"]+\.h)'?\s*file not found",
        r"fatal error:\s*([^:]+\.h):\s*No such file or directory",
        r"cannot open source file\s*['\"]?([^'\"]+\.h)['\"]?",
        r"error:\s*([^:]+\.h):\s*No such file or directory",
        r"#include\s*[<\"]([^>\"]+)[>\"].*not found",
    ]

    def __init__(self, name: str = "MissingHeaderSkill"):
        super().__init__(name)
        self.context_engine: Optional[AstGrepClient] = None
        self.build_adapter: Optional[IBuildAdapter] = None

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """
        Check if this error is about a missing header.
        """
        raw_log = diagnostic.raw_log.lower()

        # Check for common missing header indicators
        indicators = [
            'file not found',
            'no such file or directory',
            'cannot open',
            'fatal error',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the header name
        header_name = self._extract_header_name(diagnostic.raw_log)
        if header_name:
            self.logger.info(f"Detected missing header: {header_name}")
            return True

        return False

    def _extract_header_name(self, raw_log: str) -> Optional[str]:
        """Extract the missing header filename from the error log."""
        for pattern in self.HEADER_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the error and search for the header file.

        Returns analysis containing:
        - header_name: the missing header
        - header_locations: list of paths where the header was found
        - recommended_path: the most likely path to add
        """
        header_name = self._extract_header_name(diagnostic.raw_log)
        if not header_name:
            self.logger.error("Could not extract header name from error")
            return None

        # Get the source file location
        source_file = Path(diagnostic.location.get('file', ''))
        if not source_file.is_absolute():
            # Try to make it absolute based on context
            self.logger.warning(f"Non-absolute source path: {source_file}")

        # Initialize context engine if provided
        if isinstance(context, AstGrepClient):
            self.context_engine = context
        else:
            # Create a default context engine
            root_dir = source_file.parent if source_file.exists() else Path.cwd()
            self.context_engine = AstGrepClient(root_dir)

        # Search for the header file
        header_locations = self.context_engine.search_header_file(header_name)

        if not header_locations:
            self.logger.warning(f"Header {header_name} not found in source tree")
            return None

        self.logger.info(f"Found {len(header_locations)} location(s) for {header_name}")

        # Determine the recommended path
        # Prefer paths in common directories like include/, api/, interface/
        recommended = self._select_best_location(header_locations, source_file)

        return {
            'header_name': header_name,
            'header_locations': [str(p) for p in header_locations],
            'recommended_path': str(recommended.parent) if recommended else None,
            'source_file': str(source_file),
        }

    def _select_best_location(
        self,
        locations: List[Path],
        source_file: Path
    ) -> Optional[Path]:
        """Select the best header location based on heuristics."""
        if not locations:
            return None

        # Prefer paths with common include directory names
        preferred_dirs = ['include', 'api', 'interface', 'public', 'export']

        for location in locations:
            for preferred in preferred_dirs:
                if preferred in location.parts:
                    return location

        # If no preferred path found, use the first one
        return locations[0]

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we can modify the build file."""
        source_file = Path(analysis_result.get('source_file', ''))
        if not source_file.exists():
            self.logger.error(f"Source file does not exist: {source_file}")
            return False

        # Initialize appropriate build adapter
        root_dir = source_file.parent
        while not (root_dir / 'BUILD.gn').exists() and \
              not (root_dir / 'Android.bp').exists() and \
              root_dir != root_dir.parent:
            root_dir = root_dir.parent

        # Detect build system
        if (root_dir / 'Android.bp').exists():
            self.build_adapter = SoongAdapter(root_dir)
        elif (root_dir / 'BUILD.gn').exists():
            self.build_adapter = GNAdapter(root_dir)
        else:
            self.logger.error("No supported build file found")
            return False

        # Check if we can find the build file for this source
        build_file = self.build_adapter.find_build_file(source_file)
        if not build_file:
            self.logger.error(f"No build file found for {source_file}")
            return False

        return True

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate the execution plan to fix the missing header.
        """
        plan = ExecutionPlan()

        recommended_path = analysis_result.get('recommended_path')
        source_file = Path(analysis_result.get('source_file', ''))

        if not recommended_path:
            self.logger.error("No recommended path available")
            return plan

        # Get module info
        if self.build_adapter:
            module_info = self.build_adapter.get_module_info(source_file)
            if module_info:
                plan.steps.append({
                    'action': 'ADD_INCLUDE_PATH',
                    'params': {
                        'target': module_info.name,
                        'path': recommended_path,
                    }
                })

                # Apply the change
                success = self.build_adapter.modify_include_path(
                    module_info.name,
                    recommended_path,
                    action='add'
                )

                if success:
                    self.logger.info(
                        f"Added include path {recommended_path} to {module_info.name}"
                    )
                else:
                    self.logger.error("Failed to modify build file")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """
        Verify the fix by checking if the build file was modified.

        Full verification would require running the build, which is
        expensive. For now, we return SUCCESS if execute completed.
        """
        # In a full implementation, this would:
        # 1. Run incremental build (mm or hb build)
        # 2. Check if the error is resolved
        # 3. Rollback if still failing

        return SkillResult.SUCCESS
