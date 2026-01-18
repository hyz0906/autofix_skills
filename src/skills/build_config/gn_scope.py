"""
GN Scope Skill - Fix BUILD.gn scope and variable errors.

This skill detects scope errors and undefined variables in BUILD.gn files
and suggests fixes.

Implements ID 26 from top30_skills.md.
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
class GNScopeSkill(BaseSkill):
    """
    Skill for fixing BUILD.gn scope and variable errors.

    Handles errors like:
    - "Undefined identifier 'foo'"
    - "Assignment had no effect"
    - "Variable had no effect"
    - "Scope error"

    The fix involves defining variables or adjusting scope.
    """

    error_codes: List[str] = [
        'undefined identifier',
        'assignment had no effect',
        'variable had no effect',
        'scope error',
        'not defined',
    ]

    # Patterns to extract error information
    GN_ERROR_PATTERNS = [
        r"Undefined identifier\s*[`'\"]?(\w+)",
        r"[`'\"]?(\w+)[`'\"]?\s+is not defined",
        r"Assignment had no effect.*[`'\"]?(\w+)",
        r"declare_args.*[`'\"]?(\w+)",
    ]

    # Common GN variables and their purposes
    COMMON_GN_VARS = {
        'is_debug': 'Build type flag',
        'is_component_build': 'Component build mode',
        'target_os': 'Target operating system',
        'target_cpu': 'Target CPU architecture',
        'current_toolchain': 'Current toolchain label',
    }

    def __init__(self, name: str = "GNScopeSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about GN scope/variable issues."""
        raw_log = diagnostic.raw_log.lower()

        # Check for GN file mention
        is_gn = '.gn' in diagnostic.location.get('file', '').lower()
        is_gn_system = diagnostic.build_system == 'gn'

        if not is_gn and not is_gn_system:
            return False

        # Check for scope/variable error keywords
        indicators = [
            'undefined identifier',
            'not defined',
            'had no effect',
            'scope error',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        self.logger.info("Detected GN scope/variable error")
        return True

    def _extract_error_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract variable/scope error details from log."""
        for pattern in self.GN_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                var_name = match.group(1)
                return {
                    'variable': var_name,
                    'description': self.COMMON_GN_VARS.get(var_name, 'Unknown variable'),
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the GN scope error."""
        info = self._extract_error_info(diagnostic.raw_log)

        source_file = Path(diagnostic.location.get('file', 'BUILD.gn'))
        line = diagnostic.location.get('line', 1)

        variable = info.get('variable', 'unknown') if info else 'unknown'

        # Suggest fix based on error type
        if 'undefined' in diagnostic.raw_log.lower():
            fix_type = 'define_variable'
            suggestion = f"Define '{variable}' in declare_args() or import it"
        elif 'no effect' in diagnostic.raw_log.lower():
            fix_type = 'remove_unused'
            suggestion = f"Remove unused variable '{variable}' or use it"
        else:
            fix_type = 'check_scope'
            suggestion = f"Check scope of '{variable}'"

        return {
            'source_file': str(source_file),
            'line': line,
            'variable': variable,
            'fix_type': fix_type,
            'suggestion': suggestion,
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the GN error."""
        plan = ExecutionPlan()

        variable = analysis_result.get('variable', '')
        fix_type = analysis_result.get('fix_type', '')
        suggestion = analysis_result.get('suggestion', '')

        if fix_type == 'define_variable':
            plan.steps.append({
                'action': 'ADD_DECLARE_ARGS',
                'params': {
                    'variable': variable,
                    'default_value': 'false',
                }
            })
        elif fix_type == 'remove_unused':
            plan.steps.append({
                'action': 'REMOVE_VARIABLE',
                'params': {
                    'variable': variable,
                }
            })
        else:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'variable': variable,
                    'suggestion': suggestion,
                }
            })

        self.logger.info(f"Plan: {suggestion}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
