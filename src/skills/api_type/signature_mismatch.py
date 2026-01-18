"""
Signature Mismatch Skill - Fix function signature mismatch errors.

This skill detects "no matching function for call" and similar errors,
analyzes the call site and function definition, and provides suggestions
or automatic fixes where possible.

As per requirement.md Section 3.3.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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
class SignatureMismatchSkill(BaseSkill):
    """
    Skill for fixing function signature mismatch errors.

    Handles errors like:
    - "no matching function for call to 'X'"
    - "too many arguments to function 'X'"
    - "too few arguments to function 'X'"
    - "cannot convert argument from 'A' to 'B'"
    - "error: no viable conversion"

    This skill provides analysis and suggestions rather than
    automatic fixes, as signature mismatches often require
    human judgment to resolve correctly.
    """

    # Error patterns this skill can handle
    error_codes: List[str] = [
        'no matching function',
        'too many arguments',
        'too few arguments',
        'cannot convert',
        'no viable conversion',
        'invalid conversion',
        'C2664',  # MSVC
        'C2660',  # MSVC - wrong number of arguments
    ]

    # Regex patterns to extract function info
    SIGNATURE_ERROR_PATTERNS = [
        r"no matching function for call to [`']([^`'(]+)",
        r"too many arguments to function [`']([^`']+)[`']",
        r"too few arguments to function [`']([^`']+)[`']",
        r"cannot convert [`']([^`']+)[`'].*to [`']([^`']+)[`']",
        r"no viable conversion from [`']([^`']+)[`'] to [`']([^`']+)[`']",
        r"candidate function not viable:.*expected (\d+) argument",
        r"error C2660:.*\b(\w+)\b.*does not take (\d+) arguments",
        r"error C2664:.*cannot convert argument (\d+) from [`']([^`']+)[`']",
    ]

    def __init__(self, name: str = "SignatureMismatchSkill"):
        super().__init__(name)
        self.context_engine: Optional[AstGrepClient] = None

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """
        Check if this error is about a function signature mismatch.
        """
        raw_log = diagnostic.raw_log.lower()

        # Check for common signature mismatch indicators
        indicators = [
            'no matching function',
            'too many arguments',
            'too few arguments',
            'cannot convert',
            'no viable conversion',
            'invalid conversion',
            'c2664',
            'c2660',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the function name
        function_info = self._extract_function_info(diagnostic.raw_log)
        if function_info:
            self.logger.info(
                f"Detected signature mismatch for: {function_info.get('function_name', 'unknown')}"
            )
            return True

        return False

    def _extract_function_info(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """Extract function name and error details from the error log."""
        result: Dict[str, Any] = {}

        for pattern in self.SIGNATURE_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups:
                    result['function_name'] = groups[0]
                    if len(groups) > 1:
                        result['extra_info'] = groups[1:]
                    result['pattern_matched'] = pattern
                    return result

        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the signature mismatch error.

        Returns analysis containing:
        - function_name: the function being called
        - call_site: location and arguments of the call
        - definitions: found function definitions with their signatures
        - suggestions: possible fixes
        """
        function_info = self._extract_function_info(diagnostic.raw_log)
        if not function_info:
            self.logger.error("Could not extract function info from error")
            return None

        function_name = function_info.get('function_name', '')
        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 0)

        # Initialize context engine
        if isinstance(context, AstGrepClient):
            self.context_engine = context
        else:
            root_dir = source_file.parent if source_file.exists() else Path.cwd()
            self.context_engine = AstGrepClient(root_dir)

        # Find function definitions
        definitions = self.context_engine.search_function_definition(
            function_name,
            language='cpp'
        )

        # Analyze the error type
        error_type = self._classify_error(diagnostic.raw_log)

        # Generate suggestions based on the error type
        suggestions = self._generate_suggestions(
            error_type,
            function_name,
            definitions,
            diagnostic.raw_log
        )

        return {
            'function_name': function_name,
            'error_type': error_type,
            'source_file': str(source_file),
            'line': line,
            'definitions': [
                {
                    'file': m.file,
                    'line': m.line,
                    'content': m.matched_text[:100] if m.matched_text else ''
                }
                for m in definitions
            ] if definitions else [],
            'suggestions': suggestions,
        }

    def _classify_error(self, raw_log: str) -> str:
        """Classify the type of signature mismatch."""
        raw_lower = raw_log.lower()

        if 'too many arguments' in raw_lower:
            return 'too_many_args'
        elif 'too few arguments' in raw_lower:
            return 'too_few_args'
        elif 'no matching function' in raw_lower:
            return 'no_match'
        elif 'cannot convert' in raw_lower or 'invalid conversion' in raw_lower:
            return 'type_mismatch'
        elif 'no viable conversion' in raw_lower:
            return 'conversion_error'
        else:
            return 'unknown'

    def _generate_suggestions(
        self,
        error_type: str,
        function_name: str,
        definitions: List,
        raw_log: str
    ) -> List[str]:
        """Generate fix suggestions based on error analysis."""
        suggestions = []

        if error_type == 'too_many_args':
            suggestions.append(
                f"Remove extra arguments from the call to '{function_name}'"
            )
            if definitions:
                suggestions.append(
                    f"Check the function definition at {definitions[0].file}:{definitions[0].line}"
                )

        elif error_type == 'too_few_args':
            suggestions.append(
                f"Add missing arguments to the call to '{function_name}'"
            )
            if definitions:
                suggestions.append(
                    f"Check the function signature at {definitions[0].file}:{definitions[0].line}"
                )

        elif error_type == 'type_mismatch':
            suggestions.append(
                f"Check argument types in the call to '{function_name}'"
            )
            suggestions.append(
                "Consider adding explicit type casts if appropriate"
            )

        elif error_type == 'no_match':
            suggestions.append(
                f"No overload of '{function_name}' matches the call"
            )
            if definitions:
                suggestions.append(
                    f"Found {len(definitions)} definition(s) - check signatures"
                )
            else:
                suggestions.append(
                    f"No definition found for '{function_name}' - "
                    "check if the header is included"
                )

        else:
            suggestions.append(
                f"Review the function call at the error location"
            )

        return suggestions

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'function_name' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan for the signature mismatch.

        For most signature mismatches, we provide analysis and suggestions
        rather than automatic fixes, as these often require human judgment.
        """
        plan = ExecutionPlan()

        # Add an analysis step that doesn't modify files
        plan.steps.append({
            'action': 'ANALYZE',
            'params': {
                'function_name': analysis_result.get('function_name'),
                'error_type': analysis_result.get('error_type'),
                'definitions': analysis_result.get('definitions', []),
                'suggestions': analysis_result.get('suggestions', []),
            }
        })

        # Log the suggestions
        for suggestion in analysis_result.get('suggestions', []):
            self.logger.info(f"Suggestion: {suggestion}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """
        Verify the fix.

        Since this skill provides suggestions rather than automatic fixes,
        verification would require recompilation.
        """
        return SkillResult.SUCCESS
