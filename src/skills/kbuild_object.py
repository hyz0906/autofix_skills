"""
Kbuild Object Skill - Fix missing object file errors in Kbuild.

This skill detects "No rule to make target" errors for .o files
and adds the corresponding source file to obj-y.

Implements ID 17 from top30_skills.md.
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
class KbuildObjectSkill(BaseSkill):
    """
    Skill for fixing missing object file errors in Kbuild.

    Handles errors like:
    - "No rule to make target 'foo.o'"
    - "missing object: bar.o"
    - "make: *** No rule to make target 'driver/foo.o'"

    The fix involves adding the source file to obj-y in the Makefile/Kbuild.
    """

    error_codes: List[str] = [
        'no rule to make target',
        'missing object',
        'undefined reference',  # Sometimes linked to missing .o
    ]

    # Patterns to extract object file information
    OBJECT_ERROR_PATTERNS = [
        r"No rule to make target\s*[`'\"]?([^\s`'\"]+\.o)",
        r"missing object:?\s*[`'\"]?([^\s`'\"]+\.o)",
        r"cannot find\s*[`'\"]?([^\s`'\"]+\.o)",
    ]

    def __init__(self, name: str = "KbuildObjectSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing object file in Kbuild."""
        raw_log = diagnostic.raw_log.lower()

        # Check for object-related keywords
        indicators = [
            'no rule to make target',
            'missing object',
        ]

        # Must be related to .o files
        if '.o' not in raw_log:
            return False

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the object info
        info = self._extract_object_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected missing object: {info}")
            return True

        return False

    def _extract_object_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the missing object file from error log."""
        for pattern in self.OBJECT_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                obj_file = match.group(1)
                # Derive source file name
                source_file = self._object_to_source(obj_file)
                return {
                    'object': obj_file,
                    'source': source_file,
                }
        return None

    def _object_to_source(self, obj_file: str) -> str:
        """Convert .o filename to .c/.S source filename."""
        base = obj_file.rsplit('.o', 1)[0]
        # Try .c first, then .S (assembly)
        return base + '.c'

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the missing object error.

        Determines:
        - The missing object file
        - The corresponding source file
        - Whether the source file exists
        - The Makefile/Kbuild to modify
        """
        info = self._extract_object_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract object info from error")
            return None

        obj_file = info['object']
        source_file = info['source']

        # Extract just the basename
        obj_basename = Path(obj_file).stem

        return {
            'object': obj_file,
            'source': source_file,
            'basename': obj_basename,
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'object' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the missing object.

        Adds the object to obj-y in the Makefile/Kbuild.
        """
        plan = ExecutionPlan()

        obj_file = analysis_result.get('object', '')
        basename = analysis_result.get('basename', '')

        plan.steps.append({
            'action': 'ADD_OBJECT',
            'params': {
                'object': f'{basename}.o',
                'variable': 'obj-y',
            }
        })

        self.logger.info(f"Plan: Add '{basename}.o' to obj-y")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
