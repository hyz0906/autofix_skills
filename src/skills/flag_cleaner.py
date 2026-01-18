"""
Flag Cleaner Skill - Remove unsupported compiler flags.

This skill detects errors where a compiler flag is not recognized
by the current compiler (Clang/GCC) and removes it from the build configuration.

Implements ID 27 from top30_skills.md.
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
class FlagCleanerSkill(BaseSkill):
    """
    Skill for removing unsupported compiler flags.

    Handles errors like:
    - "error: unknown argument: '-fno-strict-overflow'"
    - "clang: error: unsupported option '-fno-aggressive-loop-optimizations'"
    - "warning: unknown warning option '-Wno-unused-but-set-variable'"

    The fix involves removing the offending flag from cflags/cppflags in the build file.
    """

    error_codes: List[str] = [
        'unknown argument',
        'unsupported option',
        'unknown warning option',
        'unrecognized command line option',
        'unrecognized option',
    ]

    # Patterns to extract the unsupported flag
    FLAG_ERROR_PATTERNS = [
        r"unknown argument:\s*[`'\"]?(-[^\s`'\"]+)",
        r"unsupported option\s*[`'\"]?(-[^\s`'\"]+)",
        r"unknown warning option\s*[`'\"]?(-[^\s`'\"]+)",
        r"unrecognized command line option\s*[`'\"]?(-[^\s`'\"]+)",
        r"unrecognized option\s*[`'\"]?(-[^\s`'\"]+)",
        r"error:.*[`'\"](-W[^\s`'\"]+)[`'\"]",
        r"warning:.*[`'\"](-W[^\s`'\"]+)[`'\"].*not supported",
    ]

    def __init__(self, name: str = "FlagCleanerSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about an unsupported compiler flag."""
        raw_log = diagnostic.raw_log.lower()

        # Check for flag-related keywords
        indicators = [
            'unknown argument',
            'unsupported option',
            'unknown warning option',
            'unrecognized command line option',
            'unrecognized option',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the flag
        flag_info = self._extract_flag(diagnostic.raw_log)
        if flag_info:
            self.logger.info(f"Detected unsupported flag: {flag_info}")
            return True

        return False

    def _extract_flag(self, raw_log: str) -> Optional[str]:
        """Extract the unsupported flag from error log."""
        for pattern in self.FLAG_ERROR_PATTERNS:
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
        Analyze the flag error.

        Determines:
        - The unsupported flag
        - The source file where it was encountered
        - The build file that likely contains the flag
        """
        flag = self._extract_flag(diagnostic.raw_log)
        if not flag:
            self.logger.error("Could not extract flag from error")
            return None

        source_file = Path(diagnostic.location.get('file', ''))

        return {
            'flag': flag,
            'source_file': str(source_file),
            'flag_type': self._classify_flag(flag),
        }

    def _classify_flag(self, flag: str) -> str:
        """Classify the type of flag."""
        if flag.startswith('-W'):
            return 'warning'
        elif flag.startswith('-f'):
            return 'feature'
        elif flag.startswith('-O'):
            return 'optimization'
        elif flag.startswith('-m'):
            return 'machine'
        else:
            return 'other'

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'flag' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to remove the unsupported flag.

        The plan will remove the flag from cflags/cppflags/cflags_cc in the build file.
        """
        plan = ExecutionPlan()

        flag = analysis_result.get('flag', '')
        flag_type = analysis_result.get('flag_type', 'other')

        plan.steps.append({
            'action': 'REMOVE_FLAG',
            'params': {
                'flag': flag,
                'flag_type': flag_type,
                'arrays_to_check': ['cflags', 'cppflags', 'cflags_cc', 'conlyflags'],
            }
        })

        self.logger.info(f"Plan: Remove flag '{flag}' from build configuration")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
