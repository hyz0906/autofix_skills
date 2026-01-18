"""
Type Conversion Skill - Fix type conversion errors.

This skill detects type mismatch and conversion errors
and suggests appropriate casts.

Implements ID 20 from top30_skills.md.
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
class TypeConversionSkill(BaseSkill):
    """
    Skill for fixing type conversion errors.

    Handles errors like:
    - "cannot convert 'int*' to 'void*'"
    - "invalid conversion from 'const char*' to 'char*'"
    - "incompatible pointer type"

    The fix involves adding appropriate casts (static_cast, reinterpret_cast).
    """

    error_codes: List[str] = [
        'cannot convert',
        'invalid conversion',
        'incompatible type',
        'incompatible pointer',
    ]

    # Patterns to extract type information
    TYPE_PATTERNS = [
        r"cannot convert\s*[`'\"]?([^`'\"]+)[`'\"]?\s*to\s*[`'\"]?([^`'\"]+)",
        r"invalid conversion from\s*[`'\"]?([^`'\"]+)[`'\"]?\s*to\s*[`'\"]?([^`'\"]+)",
        r"incompatible (?:pointer )?type.*from\s*[`'\"]?([^`'\"]+)[`'\"]?\s*to\s*[`'\"]?([^`'\"]+)",
    ]

    def __init__(self, name: str = "TypeConversionSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about type conversion."""
        raw_log = diagnostic.raw_log.lower()

        # Check for type conversion keywords
        indicators = [
            'cannot convert',
            'invalid conversion',
            'incompatible type',
            'incompatible pointer',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract type info
        info = self._extract_type_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected type conversion issue: {info}")
            return True

        return False

    def _extract_type_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract type conversion information from error log."""
        for pattern in self.TYPE_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                return {
                    'from_type': match.group(1).strip(),
                    'to_type': match.group(2).strip(),
                }
        return None

    def _suggest_cast(self, from_type: str, to_type: str) -> str:
        """Suggest the appropriate cast type."""
        from_lower = from_type.lower()
        to_lower = to_type.lower()

        # const removal needs const_cast
        if 'const' in from_lower and 'const' not in to_lower:
            return 'const_cast'

        # Pointer conversions typically use reinterpret_cast
        if '*' in from_type and '*' in to_type:
            return 'reinterpret_cast'

        # Numeric conversions use static_cast
        numeric_types = ['int', 'long', 'short', 'float', 'double', 'char', 'size_t']
        is_numeric = any(t in from_lower for t in numeric_types)
        if is_numeric:
            return 'static_cast'

        # Default to static_cast
        return 'static_cast'

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the type conversion error."""
        info = self._extract_type_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        from_type = info['from_type']
        to_type = info['to_type']
        cast_type = self._suggest_cast(from_type, to_type)

        return {
            'from_type': from_type,
            'to_type': to_type,
            'cast_type': cast_type,
            'source_file': str(source_file),
            'line': line,
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the type conversion."""
        plan = ExecutionPlan()

        from_type = analysis_result.get('from_type', '')
        to_type = analysis_result.get('to_type', '')
        cast_type = analysis_result.get('cast_type', 'static_cast')

        plan.steps.append({
            'action': 'ADD_CAST',
            'params': {
                'cast_type': cast_type,
                'target_type': to_type,
            }
        })

        self.logger.info(
            f"Plan: Use {cast_type}<{to_type}>(expr) to convert from {from_type}"
        )

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
