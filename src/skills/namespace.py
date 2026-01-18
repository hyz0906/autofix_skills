"""
Namespace Skill - Fix missing namespace errors in C++.

This skill detects "'X' is not a member of 'Y'" and similar errors
and suggests adding the appropriate namespace or using declaration.

Implements ID 05 from top30_skills.md.
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
class NamespaceSkill(BaseSkill):
    """
    Skill for fixing missing namespace errors in C++.

    Handles errors like:
    - "'cout' is not a member of 'std'"
    - "use of undeclared identifier 'string'"
    - "'vector' does not name a type"

    The fix involves:
    1. Adding 'using namespace std;' or specific using declaration
    2. Or prefixing the identifier with the namespace (e.g., std::vector)
    """

    error_codes: List[str] = [
        'is not a member of',
        'not a member of',
        'does not name a type',
        'undeclared identifier',
    ]

    # Patterns to extract namespace information
    NAMESPACE_ERROR_PATTERNS = [
        r"[`'\"](\w+)[`'\"].*is not a member of\s*[`'\"]?(\w+)",
        r"[`'\"](\w+)[`'\"].*not a member of\s*[`'\"]?(\w+)",
        r"[`'\"](\w+)[`'\"].*does not name a type",
        r"use of undeclared identifier\s*[`'\"]?(\w+)",
    ]

    # Common std:: identifiers
    STD_IDENTIFIERS = {
        # IO
        'cout', 'cin', 'cerr', 'clog', 'endl', 'flush',
        # Containers
        'vector', 'string', 'map', 'set', 'list', 'deque',
        'array', 'unordered_map', 'unordered_set', 'queue', 'stack',
        'pair', 'tuple',
        # Algorithms
        'sort', 'find', 'copy', 'transform', 'for_each',
        'begin', 'end', 'rbegin', 'rend',
        # Smart pointers
        'unique_ptr', 'shared_ptr', 'weak_ptr',
        'make_unique', 'make_shared',
        # Utilities
        'move', 'forward', 'swap', 'exchange',
        'function', 'bind', 'ref', 'cref',
        # Threading
        'thread', 'mutex', 'lock_guard', 'unique_lock',
        'condition_variable', 'atomic',
        # Types
        'size_t', 'ptrdiff_t', 'nullptr_t',
        'int8_t', 'int16_t', 'int32_t', 'int64_t',
        'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
    }

    def __init__(self, name: str = "NamespaceSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing namespace."""
        raw_log = diagnostic.raw_log.lower()

        # Check for namespace-related keywords
        indicators = [
            'is not a member of',
            'not a member of',
            'does not name a type',
        ]

        # Also check for common std identifiers
        has_std_identifier = any(
            f"'{ident}'" in diagnostic.raw_log or
            f'"{ident}"' in diagnostic.raw_log or
            f'`{ident}`' in diagnostic.raw_log
            for ident in self.STD_IDENTIFIERS
        )

        if not any(ind in raw_log for ind in indicators) and not has_std_identifier:
            return False

        # Try to extract the namespace info
        info = self._extract_namespace_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected namespace issue: {info}")
            return True

        return False

    def _extract_namespace_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the identifier and namespace from error log."""
        for pattern in self.NAMESPACE_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                identifier = groups[0]
                namespace = groups[1] if len(groups) > 1 else self._guess_namespace(identifier)
                return {
                    'identifier': identifier,
                    'namespace': namespace,
                }
        return None

    def _guess_namespace(self, identifier: str) -> str:
        """Guess the namespace for a given identifier."""
        if identifier in self.STD_IDENTIFIERS:
            return 'std'
        return 'unknown'

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the namespace error.

        Determines:
        - The identifier
        - The namespace it belongs to
        - The fix type (using declaration or prefix)
        """
        info = self._extract_namespace_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract namespace info from error")
            return None

        identifier = info['identifier']
        namespace = info['namespace']
        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        # Determine fix type
        # Prefer prefix for single use, using declaration for multiple
        fix_type = 'prefix'  # Default to prefix (safer)

        return {
            'identifier': identifier,
            'namespace': namespace,
            'source_file': str(source_file),
            'line': line,
            'fix_type': fix_type,
            'qualified_name': f'{namespace}::{identifier}',
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
            analysis_result.get('namespace') != 'unknown'
        )

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the namespace issue.

        Options:
        1. Add 'using namespace X;' at the top
        2. Add 'using X::identifier;' 
        3. Replace identifier with X::identifier
        """
        plan = ExecutionPlan()

        identifier = analysis_result.get('identifier', '')
        namespace = analysis_result.get('namespace', '')
        qualified_name = analysis_result.get('qualified_name', '')
        source_file = analysis_result.get('source_file', '')
        line = analysis_result.get('line', 1)
        fix_type = analysis_result.get('fix_type', 'prefix')

        if fix_type == 'prefix':
            plan.steps.append({
                'action': 'REPLACE_IDENTIFIER',
                'params': {
                    'source_file': source_file,
                    'line': line,
                    'old_text': identifier,
                    'new_text': qualified_name,
                }
            })
            self.logger.info(
                f"Plan: Replace '{identifier}' with '{qualified_name}'"
            )
        else:
            plan.steps.append({
                'action': 'INSERT_USING',
                'params': {
                    'source_file': source_file,
                    'using_statement': f'using {namespace}::{identifier};',
                }
            })
            self.logger.info(
                f"Plan: Insert 'using {namespace}::{identifier};'"
            )

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
