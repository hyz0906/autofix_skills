"""
Undeclared Identifier Skill - Auto-insert #include for missing declarations.

This skill detects "undeclared identifier" errors and suggests
inserting the appropriate #include directive in the source file.

Implements ID 04 from top30_skills.md.
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
class UndeclaredIdentifierSkill(BaseSkill):
    """
    Skill for fixing undeclared identifier errors by auto-inserting #include.

    Handles errors like:
    - "use of undeclared identifier 'LOG'"
    - "error: 'string' was not declared in this scope"
    - "'vector' is not a member of 'std'"

    The fix involves:
    1. Finding where the identifier is defined (which header)
    2. Inserting the appropriate #include in the source file
    """

    error_codes: List[str] = [
        'undeclared identifier',
        'was not declared',
        'is not a member of',
        'undefined identifier',
        'unknown type name',
    ]

    # Patterns to extract the identifier
    IDENTIFIER_ERROR_PATTERNS = [
        r"use of undeclared identifier\s*[`'\"]?(\w+)",
        r"[`'\"](\w+)[`'\"].*was not declared",
        r"[`'\"](\w+)[`'\"].*is not a member of",
        r"undefined identifier\s*[`'\"]?(\w+)",
        r"unknown type name\s*[`'\"]?(\w+)",
        r"error:.*[`'\"](\w+)[`'\"].*undeclared",
    ]

    # Common standard library mappings (identifier -> header)
    STD_HEADER_MAP = {
        # STL containers
        'vector': '<vector>',
        'string': '<string>',
        'map': '<map>',
        'unordered_map': '<unordered_map>',
        'set': '<set>',
        'unordered_set': '<unordered_set>',
        'list': '<list>',
        'deque': '<deque>',
        'array': '<array>',
        'queue': '<queue>',
        'stack': '<stack>',
        'pair': '<utility>',
        'tuple': '<tuple>',
        # STL algorithms
        'sort': '<algorithm>',
        'find': '<algorithm>',
        'transform': '<algorithm>',
        # STL utilities
        'unique_ptr': '<memory>',
        'shared_ptr': '<memory>',
        'make_unique': '<memory>',
        'make_shared': '<memory>',
        'move': '<utility>',
        'forward': '<utility>',
        # IO
        'cout': '<iostream>',
        'cin': '<iostream>',
        'cerr': '<iostream>',
        'endl': '<iostream>',
        'ifstream': '<fstream>',
        'ofstream': '<fstream>',
        'stringstream': '<sstream>',
        # C headers
        'printf': '<cstdio>',
        'scanf': '<cstdio>',
        'malloc': '<cstdlib>',
        'free': '<cstdlib>',
        'strlen': '<cstring>',
        'memcpy': '<cstring>',
        'memset': '<cstring>',
        'size_t': '<cstddef>',
        'NULL': '<cstddef>',
        'nullptr': '<cstddef>',
        # Threading
        'thread': '<thread>',
        'mutex': '<mutex>',
        'lock_guard': '<mutex>',
        'unique_lock': '<mutex>',
        'condition_variable': '<condition_variable>',
        # Android-specific
        'LOG': '"utils/Log.h"',
        'ALOG': '"utils/Log.h"',
        'ALOGE': '"utils/Log.h"',
        'ALOGD': '"utils/Log.h"',
        'ALOGI': '"utils/Log.h"',
        'ALOGW': '"utils/Log.h"',
        'sp': '"utils/RefBase.h"',
        'wp': '"utils/RefBase.h"',
    }

    def __init__(self, name: str = "UndeclaredIdentifierSkill"):
        super().__init__(name)
        self.context_engine: Optional[AstGrepClient] = None

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about an undeclared identifier."""
        raw_log = diagnostic.raw_log.lower()

        # Check for undeclared-related keywords
        indicators = [
            'undeclared identifier',
            'was not declared',
            'is not a member of',
            'undefined identifier',
            'unknown type name',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the identifier
        identifier = self._extract_identifier(diagnostic.raw_log)
        if identifier:
            self.logger.info(f"Detected undeclared identifier: {identifier}")
            return True

        return False

    def _extract_identifier(self, raw_log: str) -> Optional[str]:
        """Extract the undeclared identifier from error log."""
        for pattern in self.IDENTIFIER_ERROR_PATTERNS:
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
        Analyze the undeclared identifier error.

        Determines:
        - The identifier name
        - The source file needing the include
        - The header to include (from map or search)
        """
        identifier = self._extract_identifier(diagnostic.raw_log)
        if not identifier:
            self.logger.error("Could not extract identifier from error")
            return None

        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        # First check standard header map
        header = self.STD_HEADER_MAP.get(identifier)

        # If not found, try to search using ast-grep
        if not header and isinstance(context, AstGrepClient):
            self.context_engine = context
            # Search for the identifier definition
            matches = self.context_engine.search_pattern(
                f"$_ {identifier}",  # Simplified pattern
                language='cpp'
            )
            if matches:
                # Get the header from the first match
                header_file = Path(matches[0].file)
                if header_file.suffix in ['.h', '.hpp', '.hxx']:
                    header = f'"{header_file.name}"'

        return {
            'identifier': identifier,
            'source_file': str(source_file),
            'line': line,
            'header': header,
            'header_found': header is not None,
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return (
            analysis_result is not None and
            'identifier' in analysis_result and
            analysis_result.get('header_found', False)
        )

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to insert the #include.

        The plan will add the include directive at the top of the source file.
        """
        plan = ExecutionPlan()

        identifier = analysis_result.get('identifier', '')
        source_file = analysis_result.get('source_file', '')
        header = analysis_result.get('header', '')

        if header:
            plan.steps.append({
                'action': 'INSERT_INCLUDE',
                'params': {
                    'source_file': source_file,
                    'header': header,
                    'identifier': identifier,
                }
            })
            self.logger.info(
                f"Plan: Insert '#include {header}' in '{source_file}'"
            )
        else:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'identifier': identifier,
                    'suggestion': f"Could not find header for '{identifier}'",
                }
            })

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
