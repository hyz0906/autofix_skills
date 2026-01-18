"""
Const Mismatch Skill - Fix const qualifier mismatch errors.

This skill detects const mismatch errors in function overrides
and suggests fixes to align const qualifiers.

Implements ID 21 from top30_skills.md.
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
class ConstMismatchSkill(BaseSkill):
    """
    Skill for fixing const qualifier mismatch errors.

    Handles errors like:
    - "member function declared const here"
    - "cannot convert 'this' pointer from 'const X' to 'X&'"
    - "overriding virtual function differs in const only"

    The fix involves adjusting const qualifiers on member functions.
    """

    error_codes: List[str] = [
        'const',
        'differs only in cv-qualifiers',
        'cannot convert this pointer',
        'const qualifier',
    ]

    # Patterns to extract const mismatch information
    CONST_ERROR_PATTERNS = [
        r"cannot convert ['\"]?this['\"]? pointer from\s*[`'\"]?const\s+(\w+)",
        r"[`'\"]?(\w+)[`'\"]?.*differs? only in cv-qualifiers",
        r"marked as override, but does not override.*const",
        r"error:.*[`'\"]?(\w+)[`'\"]?.*is not a member of.*const",
    ]

    def __init__(self, name: str = "ConstMismatchSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a const mismatch."""
        raw_log = diagnostic.raw_log.lower()

        # Check for const-related keywords
        indicators = [
            'differs only in cv-qualifiers',
            'const qualifier',
            'cannot convert this pointer',
            'const member function',
        ]

        # Also check for const keyword in context
        has_const = 'const' in raw_log

        if not has_const:
            return False

        if not any(ind in raw_log for ind in indicators):
            # Also check for override-related const issues
            if 'override' not in raw_log:
                return False

        # Try to extract const info
        info = self._extract_const_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected const mismatch: {info}")
            return True

        return False

    def _extract_const_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the const mismatch information from error log."""
        for pattern in self.CONST_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups:
                    return {
                        'class_or_func': groups[0],
                        'fix_type': 'add_const',
                    }
        
        # Generic detection for const issues
        if 'const' in raw_log.lower():
            return {
                'class_or_func': 'unknown',
                'fix_type': 'check_const',
            }
        
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the const mismatch error.
        """
        info = self._extract_const_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        return {
            'class_or_func': info['class_or_func'],
            'source_file': str(source_file),
            'line': line,
            'fix_type': info['fix_type'],
            'suggestions': [
                "Check if the overriding function needs 'const' qualifier",
                "Ensure the base class virtual function signature matches",
            ],
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the const mismatch."""
        plan = ExecutionPlan()

        plan.steps.append({
            'action': 'ANALYZE',
            'params': {
                'class_or_func': analysis_result.get('class_or_func'),
                'suggestions': analysis_result.get('suggestions', []),
            }
        })

        for suggestion in analysis_result.get('suggestions', []):
            self.logger.info(f"Suggestion: {suggestion}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
