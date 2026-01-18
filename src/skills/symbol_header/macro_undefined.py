"""
Macro Undefined Skill - Fix undefined macro errors.

This skill detects undefined macro errors and suggests
adding the macro definition.

Implements ID 10 from top30_skills.md.
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
class MacroUndefinedSkill(BaseSkill):
    """
    Skill for fixing undefined macro errors.

    Handles errors like:
    - "'FOO' was not declared in this scope"
    - "use of undeclared identifier 'DEBUG_MODE'"
    - "'CONFIG_FEATURE' is not defined"

    The fix involves:
    1. Adding -DMACRO to build flags
    2. Or adding #define in source file
    """

    error_codes: List[str] = [
        'undeclared',
        'not defined',
        'undefined',
    ]

    # Patterns to extract macro information
    MACRO_PATTERNS = [
        r"[`'\"]?([A-Z_][A-Z0-9_]*)[`'\"]?\s+was not declared",
        r"[`'\"]?([A-Z_][A-Z0-9_]*)[`'\"]?\s+is not defined",
        r"use of undeclared identifier\s+[`'\"]?([A-Z_][A-Z0-9_]*)",
        r"#if.*[`'\"]?([A-Z_][A-Z0-9_]*)[`'\"]?.*not defined",
    ]

    # Common macros and their typical values
    COMMON_MACROS = {
        'DEBUG': '1',
        'NDEBUG': '1',
        'LOG_TAG': '"MyModule"',
        'CONFIG_DEBUG': '1',
        'ANDROID': '1',
        '__ANDROID__': '1',
        'LINUX': '1',
        '__linux__': '1',
    }

    def __init__(self, name: str = "MacroUndefinedSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about an undefined macro."""
        raw_log = diagnostic.raw_log

        # Look for macro-like patterns (ALL_CAPS_WITH_UNDERSCORES)
        macro_pattern = r'[`\'"](([A-Z_][A-Z0-9_]{2,}))[`\'"]'
        has_macro_like = re.search(macro_pattern, raw_log)

        if not has_macro_like:
            return False

        raw_log_lower = raw_log.lower()

        # Check for undefined keywords
        indicators = [
            'not declared',
            'not defined',
            'undeclared identifier',
        ]

        if not any(ind in raw_log_lower for ind in indicators):
            return False

        # Try to extract macro info
        info = self._extract_macro_info(raw_log)
        if info:
            self.logger.info(f"Detected undefined macro: {info}")
            return True

        return False

    def _extract_macro_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the undefined macro from error log."""
        for pattern in self.MACRO_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                macro = match.group(1)
                return {
                    'macro': macro,
                    'default_value': self.COMMON_MACROS.get(macro, '1'),
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the undefined macro error."""
        info = self._extract_macro_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        macro = info['macro']
        default_value = info['default_value']

        return {
            'macro': macro,
            'default_value': default_value,
            'source_file': str(source_file),
            'line': line,
            'cflag': f'-D{macro}={default_value}',
            'define': f'#define {macro} {default_value}',
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to define the macro."""
        plan = ExecutionPlan()

        macro = analysis_result.get('macro', '')
        cflag = analysis_result.get('cflag', '')
        define = analysis_result.get('define', '')

        # Prefer adding to build flags
        plan.steps.append({
            'action': 'ADD_CFLAG',
            'params': {
                'flag': cflag,
            }
        })
        self.logger.info(f"Plan: Add '{cflag}' to cflags")

        # Alternative: add #define
        plan.steps.append({
            'action': 'ADD_DEFINE',
            'params': {
                'define': define,
            }
        })
        self.logger.info(f"Alternative: Add '{define}' to source")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
