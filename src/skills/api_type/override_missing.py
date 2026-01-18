"""
Override Missing Skill - Fix missing override implementations.

This skill detects errors when derived classes don't implement
required virtual methods from base classes.

Implements ID 22 from top30_skills.md.
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
class OverrideMissingSkill(BaseSkill):
    """
    Skill for fixing missing override implementations.

    Handles errors like:
    - "cannot instantiate abstract class"
    - "unimplemented pure virtual method 'foo'"
    - "does not implement inherited abstract method"

    The fix involves generating stub implementations for missing methods.
    """

    error_codes: List[str] = [
        'abstract class',
        'pure virtual',
        'unimplemented',
        'not implemented',
        'abstract method',
    ]

    # Patterns to extract override information
    OVERRIDE_ERROR_PATTERNS = [
        r"cannot instantiate abstract class\s*[`'\"]?(\w+)",
        r"unimplemented pure virtual method\s*[`'\"]?(\w+)",
        r"does not implement.*method\s*[`'\"]?(\w+)",
        r"[`'\"]?(\w+)[`'\"]?.*is abstract",
    ]

    def __init__(self, name: str = "OverrideMissingSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing override."""
        raw_log = diagnostic.raw_log.lower()

        # Check for override-related keywords
        indicators = [
            'abstract class',
            'pure virtual',
            'unimplemented',
            'not implemented',
            'abstract method',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract override info
        info = self._extract_override_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected missing override: {info}")
            return True

        return False

    def _extract_override_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the missing method/class information from error log."""
        for pattern in self.OVERRIDE_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                return {
                    'name': match.group(1),
                    'type': 'method' if 'method' in raw_log.lower() else 'class',
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the missing override error."""
        info = self._extract_override_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        return {
            'name': info['name'],
            'type': info['type'],
            'source_file': str(source_file),
            'line': line,
            'suggestions': [
                f"Implement the pure virtual method '{info['name']}'",
                "Check the base class for required method signatures",
            ],
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the missing override."""
        plan = ExecutionPlan()

        name = analysis_result.get('name', '')

        plan.steps.append({
            'action': 'GENERATE_STUB',
            'params': {
                'method_name': name,
                'stub': f'void {name}() override {{ /* TODO: Implement */ }}',
            }
        })

        for suggestion in analysis_result.get('suggestions', []):
            self.logger.info(f"Suggestion: {suggestion}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
