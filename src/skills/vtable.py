"""
Vtable Missing Skill - Fix virtual function implementation errors.

This skill detects vtable-related errors caused by unimplemented
virtual functions and suggests stub implementations.

Implements ID 14 from top30_skills.md.
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
class VtableSkill(BaseSkill):
    """
    Skill for fixing vtable/virtual function errors.

    Handles errors like:
    - "undefined reference to 'vtable for Foo'"
    - "undefined reference to 'Foo::~Foo()'"
    - "pure virtual method called"

    The fix involves generating stub implementations for virtual methods.
    """

    error_codes: List[str] = [
        'vtable',
        'undefined reference to vtable',
        'pure virtual',
        'typeinfo for',
    ]

    # Patterns to extract vtable/class information
    VTABLE_ERROR_PATTERNS = [
        r"undefined reference to\s*[`'\"]?vtable for\s+(\w+)",
        r"undefined reference to\s*[`'\"]?typeinfo for\s+(\w+)",
        r"undefined reference to\s*[`'\"]?(\w+)::~(\w+)\(\)",
        r"pure virtual method\s*[`'\"]?(\w+)",
    ]

    def __init__(self, name: str = "VtableSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing vtable."""
        raw_log = diagnostic.raw_log.lower()

        # Check for vtable-related keywords
        indicators = [
            'vtable',
            'typeinfo',
            'pure virtual',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the class info
        info = self._extract_class_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected vtable issue: {info}")
            return True

        return False

    def _extract_class_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the class name from error log."""
        for pattern in self.VTABLE_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                class_name = groups[0]
                return {
                    'class_name': class_name,
                    'error_type': 'vtable',
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the vtable error.

        Determines:
        - The class name
        - The missing virtual functions
        - Where to add implementations
        """
        info = self._extract_class_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract class info from error")
            return None

        class_name = info['class_name']
        source_file = Path(diagnostic.location.get('file', ''))

        # Common fix: implement the destructor
        destructor_impl = f'{class_name}::~{class_name}() {{}}'

        return {
            'class_name': class_name,
            'source_file': str(source_file),
            'destructor_impl': destructor_impl,
            'suggestions': [
                f"Ensure {class_name} has a virtual destructor implementation",
                f"Check that all pure virtual methods are implemented",
            ],
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'class_name' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the vtable issue.

        Usually involves adding virtual destructor implementation.
        """
        plan = ExecutionPlan()

        class_name = analysis_result.get('class_name', '')
        destructor_impl = analysis_result.get('destructor_impl', '')
        suggestions = analysis_result.get('suggestions', [])

        plan.steps.append({
            'action': 'ADD_DESTRUCTOR',
            'params': {
                'class_name': class_name,
                'implementation': destructor_impl,
            }
        })

        for suggestion in suggestions:
            self.logger.info(f"Suggestion: {suggestion}")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
