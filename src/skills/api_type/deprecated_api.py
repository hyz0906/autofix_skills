"""
Deprecated API Skill - Fix deprecated API usage.

This skill detects deprecated API warnings and suggests
replacement APIs based on a knowledge base.

Implements ID 24 from top30_skills.md.
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
class DeprecatedAPISkill(BaseSkill):
    """
    Skill for fixing deprecated API usage.

    Handles warnings like:
    - "'foo' is deprecated, use 'bar' instead"
    - "warning: 'strcpy' is deprecated"
    - "[[deprecated]]"

    The fix involves replacing deprecated APIs with recommended alternatives.
    """

    error_codes: List[str] = [
        'deprecated',
        'obsolete',
        'superseded',
    ]

    # Patterns to extract deprecated API information
    DEPRECATED_PATTERNS = [
        r"[`'\"]?(\w+)[`'\"]?\s+is deprecated",
        r"deprecated.*[`'\"]?(\w+)[`'\"]?",
        r"use\s*[`'\"]?(\w+)[`'\"]?\s+instead",
        r"\[\[deprecated\]\].*[`'\"]?(\w+)[`'\"]?",
    ]

    # Known deprecated → replacement mappings
    DEPRECATED_API_MAP = {
        # C string functions
        'strcpy': 'strncpy or strlcpy',
        'strcat': 'strncat or strlcat',
        'sprintf': 'snprintf',
        'gets': 'fgets',
        'scanf': 'fgets + sscanf',
        # C memory functions
        'bzero': 'memset',
        'bcopy': 'memcpy or memmove',
        # POSIX
        'usleep': 'nanosleep',
        'tmpnam': 'mkstemp',
        # Android
        'ALOG': 'ALOG* macros with logging level',
        # C++
        'auto_ptr': 'unique_ptr',
        'random_shuffle': 'shuffle',
        'bind1st': 'bind or lambda',
        'bind2nd': 'bind or lambda',
        'ptr_fun': 'lambda',
        'mem_fun': 'mem_fn',
        'mem_fun_ref': 'mem_fn',
    }

    def __init__(self, name: str = "DeprecatedAPISkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error/warning is about deprecated API."""
        raw_log = diagnostic.raw_log.lower()

        # Check for deprecated keywords
        indicators = ['deprecated', 'obsolete']

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the deprecated API
        info = self._extract_deprecated_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected deprecated API: {info}")
            return True

        return False

    def _extract_deprecated_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the deprecated API from error log."""
        deprecated_api = None
        replacement = None

        for pattern in self.DEPRECATED_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                deprecated_api = match.group(1)
                break

        if deprecated_api:
            # Look for replacement in the log
            replacement_match = re.search(
                r"use\s*[`'\"]?(\w+)[`'\"]?\s+instead",
                raw_log, re.IGNORECASE
            )
            if replacement_match:
                replacement = replacement_match.group(1)
            else:
                # Check our known mappings
                replacement = self.DEPRECATED_API_MAP.get(deprecated_api)

            return {
                'deprecated': deprecated_api,
                'replacement': replacement,
            }

        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the deprecated API warning."""
        info = self._extract_deprecated_info(diagnostic.raw_log)
        if not info:
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        return {
            'deprecated': info['deprecated'],
            'replacement': info['replacement'],
            'source_file': str(source_file),
            'line': line,
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to replace the deprecated API."""
        plan = ExecutionPlan()

        deprecated = analysis_result.get('deprecated', '')
        replacement = analysis_result.get('replacement')
        source_file = analysis_result.get('source_file', '')
        line = analysis_result.get('line', 1)

        if replacement:
            plan.steps.append({
                'action': 'REPLACE_API',
                'params': {
                    'source_file': source_file,
                    'line': line,
                    'old_api': deprecated,
                    'new_api': replacement,
                }
            })
            self.logger.info(f"Plan: Replace '{deprecated}' with '{replacement}'")
        else:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'deprecated': deprecated,
                    'suggestion': f"'{deprecated}' is deprecated, find replacement",
                }
            })

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
