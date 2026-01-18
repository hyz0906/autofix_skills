"""
Multiple Definition Skill - Fix duplicate symbol errors.

This skill detects multiple definition/duplicate symbol errors
and suggests removing duplicate dependencies.

Implements ID 16 from top30_skills.md.
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
class MultipleDefSkill(BaseSkill):
    """
    Skill for fixing multiple definition/duplicate symbol errors.

    Handles errors like:
    - "multiple definition of 'foo'"
    - "duplicate symbol '_bar'"
    - "symbol 'baz' is multiply defined"

    The fix involves removing duplicate inputs from the build.
    """

    error_codes: List[str] = [
        'multiple definition',
        'duplicate symbol',
        'multiply defined',
        'already defined',
    ]

    # Patterns to extract symbol information
    MULTIPLE_DEF_PATTERNS = [
        r"multiple definition of\s*[`'\"]?(\w+)",
        r"duplicate symbol\s*[`'\"]?([_\w]+)",
        r"[`'\"]?(\w+)[`'\"]?\s+is multiply defined",
        r"[`'\"]?(\w+)[`'\"]?\s+already defined",
    ]

    def __init__(self, name: str = "MultipleDefSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about multiple definitions."""
        raw_log = diagnostic.raw_log.lower()

        # Check for multiple definition keywords
        indicators = [
            'multiple definition',
            'duplicate symbol',
            'multiply defined',
            'already defined',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract symbol info
        info = self._extract_symbol_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected multiple definition: {info}")
            return True

        return False

    def _extract_symbol_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the multiply defined symbol from log."""
        for pattern in self.MULTIPLE_DEF_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                return {
                    'symbol': match.group(1),
                }
        return None

    def _extract_object_files(self, raw_log: str) -> List[str]:
        """Extract object files mentioned in the error."""
        # Look for .o files
        obj_pattern = r'([^\s]+\.o)'
        matches = re.findall(obj_pattern, raw_log)
        return list(set(matches))

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the multiple definition error."""
        info = self._extract_symbol_info(diagnostic.raw_log)
        if not info:
            return None

        symbol = info['symbol']
        obj_files = self._extract_object_files(diagnostic.raw_log)

        return {
            'symbol': symbol,
            'object_files': obj_files,
            'suggestions': [
                f"Check for duplicate libraries providing '{symbol}'",
                "Remove one of the duplicate dependencies",
                "Use 'ld --allow-multiple-definition' as a workaround",
            ],
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the multiple definition."""
        plan = ExecutionPlan()

        symbol = analysis_result.get('symbol', '')
        obj_files = analysis_result.get('object_files', [])

        if len(obj_files) >= 2:
            plan.steps.append({
                'action': 'REMOVE_DUPLICATE_DEP',
                'params': {
                    'symbol': symbol,
                    'objects': obj_files,
                    'keep': obj_files[0],
                    'remove': obj_files[1:],
                }
            })
            self.logger.info(f"Plan: Remove duplicate object providing '{symbol}'")
        else:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'symbol': symbol,
                    'suggestions': analysis_result.get('suggestions', []),
                }
            })

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
