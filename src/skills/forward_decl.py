"""
Forward Declaration Skill - Fix circular dependency errors.

This skill detects incomplete type errors caused by circular
dependencies and suggests forward declarations.

Implements ID 09 from top30_skills.md.
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
class ForwardDeclSkill(BaseSkill):
    """
    Skill for fixing circular dependency errors with forward declarations.

    Handles errors like:
    - "incomplete type 'class Foo' used"
    - "forward declaration of 'struct Bar'"
    - "invalid use of incomplete type"

    The fix involves adding a forward declaration in the appropriate header.
    """

    error_codes: List[str] = [
        'incomplete type',
        'forward declaration',
        'invalid use of incomplete',
    ]

    # Patterns to extract type information
    FORWARD_DECL_PATTERNS = [
        r"incomplete type\s*[`'\"]?(class|struct)\s+(\w+)",
        r"invalid use of incomplete type\s*[`'\"]?(class|struct)\s+(\w+)",
        r"forward declaration of\s*[`'\"]?(class|struct)\s+(\w+)",
        r"[`'\"](\w+)[`'\"].*incomplete type",
    ]

    def __init__(self, name: str = "ForwardDeclSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about an incomplete type."""
        raw_log = diagnostic.raw_log.lower()

        # Check for incomplete type keywords
        indicators = [
            'incomplete type',
            'forward declaration',
            'invalid use of incomplete',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the type info
        info = self._extract_type_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected forward declaration issue: {info}")
            return True

        return False

    def _extract_type_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the incomplete type from error log."""
        for pattern in self.FORWARD_DECL_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return {
                        'type_kind': groups[0],  # class or struct
                        'type_name': groups[1],
                    }
                elif len(groups) == 1:
                    return {
                        'type_kind': 'class',  # Default to class
                        'type_name': groups[0],
                    }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the incomplete type error.

        Determines:
        - The type name
        - The type kind (class/struct)
        - Where to insert the forward declaration
        """
        info = self._extract_type_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract type info from error")
            return None

        type_name = info['type_name']
        type_kind = info['type_kind']
        source_file = Path(diagnostic.location.get('file', ''))

        # Generate the forward declaration
        forward_decl = f'{type_kind} {type_name};'

        return {
            'type_name': type_name,
            'type_kind': type_kind,
            'source_file': str(source_file),
            'forward_declaration': forward_decl,
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'type_name' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to add the forward declaration.
        """
        plan = ExecutionPlan()

        forward_decl = analysis_result.get('forward_declaration', '')
        source_file = analysis_result.get('source_file', '')

        plan.steps.append({
            'action': 'INSERT_FORWARD_DECL',
            'params': {
                'source_file': source_file,
                'declaration': forward_decl,
            }
        })

        self.logger.info(f"Plan: Insert forward declaration '{forward_decl}'")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
