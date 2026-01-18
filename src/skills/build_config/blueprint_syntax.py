"""
Blueprint Syntax Skill - Fix Android.bp syntax errors.

This skill detects syntax errors in Android.bp (Blueprint) files
and suggests fixes like missing commas, brackets, etc.

Implements ID 25 from top30_skills.md.
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
class BlueprintSyntaxSkill(BaseSkill):
    """
    Skill for fixing Android.bp syntax errors.

    Handles errors like:
    - "expected ',' before ']'"
    - "unexpected '}'"
    - "unrecognized property"
    - "parse error"

    The fix involves correcting syntax issues in the Blueprint file.
    """

    error_codes: List[str] = [
        'parse error',
        'expected',
        'unexpected',
        'unrecognized property',
        'syntax error',
    ]

    # Patterns to extract syntax error information
    SYNTAX_PATTERNS = [
        r"Android\.bp:(\d+):(\d+):\s*(.*)",
        r"expected\s*[`'\"]?([^`'\"]+)[`'\"]?\s*before\s*[`'\"]?([^`'\"]+)",
        r"unexpected\s*[`'\"]?([^`'\"]+)",
        r"unrecognized property\s*[`'\"]?(\w+)",
        r"parse error.*line\s*(\d+)",
    ]

    # Common Blueprint syntax fixes
    COMMON_FIXES = {
        'missing_comma': {
            'pattern': r'expected\s*[`\'"],',
            'fix': 'Add missing comma',
        },
        'missing_bracket': {
            'pattern': r'expected\s*[`\'"][\[\]\{\}]',
            'fix': 'Add missing bracket',
        },
        'extra_comma': {
            'pattern': r'unexpected\s*[`\'"],',
            'fix': 'Remove trailing comma',
        },
    }

    def __init__(self, name: str = "BlueprintSyntaxSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about Blueprint syntax."""
        raw_log = diagnostic.raw_log.lower()

        # Check for Blueprint file mention
        is_blueprint = 'android.bp' in diagnostic.raw_log.lower()
        
        # Or check for Soong build system
        is_soong = diagnostic.build_system == 'soong'

        if not is_blueprint and not is_soong:
            return False

        # Check for syntax error keywords
        indicators = [
            'parse error',
            'expected',
            'unexpected',
            'syntax error',
            'unrecognized property',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        self.logger.info("Detected Blueprint syntax error")
        return True

    def _extract_error_info(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """Extract syntax error details from log."""
        info = {}

        # Try to extract line number
        line_match = re.search(r'Android\.bp:(\d+)', raw_log, re.IGNORECASE)
        if line_match:
            info['line'] = int(line_match.group(1))

        # Try to extract column
        col_match = re.search(r'Android\.bp:\d+:(\d+)', raw_log, re.IGNORECASE)
        if col_match:
            info['column'] = int(col_match.group(1))

        # Determine error type
        if 'expected' in raw_log.lower() and ',' in raw_log:
            info['error_type'] = 'missing_comma'
        elif 'unexpected' in raw_log.lower() and ',' in raw_log:
            info['error_type'] = 'extra_comma'
        elif re.search(r'expected.*[\[\]\{\}]', raw_log, re.IGNORECASE):
            info['error_type'] = 'missing_bracket'
        else:
            info['error_type'] = 'unknown'

        return info if info else None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the Blueprint syntax error."""
        info = self._extract_error_info(diagnostic.raw_log)
        if not info:
            info = {}

        source_file = Path(diagnostic.location.get('file', 'Android.bp'))
        line = info.get('line', diagnostic.location.get('line', 1))

        error_type = info.get('error_type', 'unknown')
        fix_suggestion = self.COMMON_FIXES.get(error_type, {}).get('fix', 'Check syntax')

        return {
            'source_file': str(source_file),
            'line': line,
            'column': info.get('column'),
            'error_type': error_type,
            'fix_suggestion': fix_suggestion,
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the syntax error."""
        plan = ExecutionPlan()

        error_type = analysis_result.get('error_type', 'unknown')
        line = analysis_result.get('line', 1)
        fix = analysis_result.get('fix_suggestion', 'Check syntax')

        plan.steps.append({
            'action': 'FIX_SYNTAX',
            'params': {
                'error_type': error_type,
                'line': line,
                'fix': fix,
            }
        })

        self.logger.info(f"Plan: {fix} at line {line}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
