"""
Version Guard Skill - Fix kernel version compatibility issues.

This skill detects kernel API version conflicts and suggests
adding LINUX_VERSION_CODE guards.

Implements ID 23 from top30_skills.md.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    register_skill,
)
from src.utils.logger import get_logger


@register_skill
class VersionGuardSkill(BaseSkill):
    """
    Skill for fixing kernel version compatibility issues.

    Handles errors like:
    - "implicit declaration of function 'new_api_func'"
    - "too many arguments to function 'old_api_func'"
    - API changes between kernel versions

    The fix involves adding version guards like:
    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
    """

    error_codes: List[str] = [
        'implicit declaration',
        'too many arguments',
        'too few arguments',
    ]

    # Known kernel API changes (API -> version introduced)
    KERNEL_API_VERSIONS = {
        'ktime_get_coarse_real_ts64': (5, 3, 0),
        'devm_platform_ioremap_resource': (5, 0, 0),
        'dma_alloc_attrs': (4, 8, 0),
        'class_create_with_module': (6, 4, 0),
        'timer_setup': (4, 15, 0),
        'setup_timer': (4, 15, 0),  # Deprecated
    }

    # Patterns to extract API information
    VERSION_PATTERNS = [
        r"implicit declaration of function\s*[`'\"]?(\w+)",
        r"too (?:many|few) arguments to function\s*[`'\"]?(\w+)",
        r"[`'\"]?(\w+)[`'\"]?\s+has incompatible type",
    ]

    def __init__(self, name: str = "VersionGuardSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about kernel version compatibility."""
        raw_log = diagnostic.raw_log.lower()

        # Check for kernel/C related errors
        indicators = [
            'implicit declaration',
            'too many arguments',
            'too few arguments',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Check if it's in kernel code (Kbuild)
        source_file = diagnostic.location.get('file', '')
        is_kernel = any(x in source_file.lower() for x in [
            'driver', 'kernel', 'module', '.ko'
        ]) or diagnostic.build_system == 'kbuild'

        if not is_kernel:
            return False

        # Try to extract API info
        info = self._extract_api_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected version-sensitive API: {info}")
            return True

        return False

    def _extract_api_info(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """Extract the API function from error log."""
        for pattern in self.VERSION_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                func_name = match.group(1)
                version = self.KERNEL_API_VERSIONS.get(func_name)
                return {
                    'function': func_name,
                    'version': version,
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the version compatibility error."""
        info = self._extract_api_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)
        func_name = info['function']
        version = info['version']

        version_guard = None
        if version:
            version_guard = (
                f'#if LINUX_VERSION_CODE >= KERNEL_VERSION({version[0]}, {version[1]}, {version[2]})'
            )

        return {
            'function': func_name,
            'version': version,
            'source_file': str(source_file),
            'line': line,
            'version_guard': version_guard,
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to add version guard."""
        plan = ExecutionPlan()

        func_name = analysis_result.get('function', '')
        version_guard = analysis_result.get('version_guard')
        source_file = analysis_result.get('source_file', '')
        line = analysis_result.get('line', 1)

        if version_guard:
            plan.steps.append({
                'action': 'ADD_VERSION_GUARD',
                'params': {
                    'source_file': source_file,
                    'line': line,
                    'guard_start': version_guard,
                    'guard_end': '#endif',
                }
            })
            self.logger.info(f"Plan: Add version guard for '{func_name}'")
        else:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'function': func_name,
                    'suggestion': f"Check kernel version requirements for '{func_name}'",
                }
            })

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
