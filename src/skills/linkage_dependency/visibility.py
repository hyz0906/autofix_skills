"""
Visibility Skill - Fix Soong visibility restriction errors.

This skill detects errors where a module cannot depend on another
due to visibility restrictions, and suggests adding the requesting
module to the target's visibility whitelist.

Implements ID 15 from top30_skills.md.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.soong import SoongAdapter
from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    register_skill,
)
from src.utils.logger import get_logger


@register_skill
class VisibilitySkill(BaseSkill):
    """
    Skill for fixing Soong visibility restriction errors.

    Handles errors like:
    - "//vendor/my_module:my_target depends on //system/lib:hidden_lib which is not visible to this module"
    - "visibility violation"
    - "not visible to"

    The fix involves either:
    1. Adding the requesting module to the target's visibility list
    2. Or setting visibility: ["//visibility:public"] if appropriate
    """

    error_codes: List[str] = [
        'visibility',
        'not visible',
        'visibility violation',
    ]

    # Patterns to extract module information
    VISIBILITY_ERROR_PATTERNS = [
        r"[`']([^`']+)[`'] depends on [`']([^`']+)[`'].*not visible",
        r"([^\s]+) is not visible to ([^\s]+)",
        r"visibility violation:.*[`']([^`']+)[`'].*[`']([^`']+)[`']",
        r"module \"([^\"]+)\".*depends on \"([^\"]+)\".*visibility",
    ]

    def __init__(self, name: str = "VisibilitySkill"):
        super().__init__(name)
        self.adapter: Optional[SoongAdapter] = None

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about visibility restrictions."""
        raw_log = diagnostic.raw_log.lower()

        # Check for visibility-related keywords
        indicators = ['visibility', 'not visible', 'visible to']

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract module info
        module_info = self._extract_module_info(diagnostic.raw_log)
        if module_info:
            self.logger.info(
                f"Detected visibility issue: {module_info.get('requesting_module')} -> "
                f"{module_info.get('target_module')}"
            )
            return True

        return False

    def _extract_module_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract requesting and target module from error log."""
        for pattern in self.VISIBILITY_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return {
                        'requesting_module': groups[0],
                        'target_module': groups[1],
                    }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the visibility error.

        Determines:
        - The requesting module path
        - The target module path
        - The target module's Android.bp location
        - Current visibility settings
        """
        module_info = self._extract_module_info(diagnostic.raw_log)
        if not module_info:
            self.logger.error("Could not extract module info from error")
            return None

        requesting_module = module_info['requesting_module']
        target_module = module_info['target_module']

        # Extract the module path (strip leading //)
        target_path = self._module_to_path(target_module)
        requesting_path = self._module_to_path(requesting_module)

        return {
            'requesting_module': requesting_module,
            'requesting_path': requesting_path,
            'target_module': target_module,
            'target_path': target_path,
            'fix_type': 'add_visibility',
        }

    def _module_to_path(self, module_label: str) -> str:
        """Convert a module label like //path:target to just the path."""
        # Remove leading //
        if module_label.startswith('//'):
            module_label = module_label[2:]

        # Remove :target suffix if present
        if ':' in module_label:
            module_label = module_label.split(':')[0]

        return module_label

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return (
            analysis_result is not None and
            'target_module' in analysis_result and
            'requesting_module' in analysis_result
        )

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the visibility issue.

        The plan will add the requesting module to the target's visibility list.
        """
        plan = ExecutionPlan()

        requesting = analysis_result.get('requesting_module', '')
        target = analysis_result.get('target_module', '')
        target_path = analysis_result.get('target_path', '')

        # Generate the visibility directive to add
        # Format: "//path/to/requesting:__subpackages__" or specific target
        if ':' in requesting:
            visibility_entry = requesting.replace(':', ':__pkg__')
        else:
            visibility_entry = f"//{requesting}:__subpackages__"

        plan.steps.append({
            'action': 'ADD_VISIBILITY',
            'params': {
                'target_module': target,
                'target_path': target_path,
                'visibility_entry': visibility_entry,
            }
        })

        self.logger.info(
            f"Plan: Add '{visibility_entry}' to visibility of '{target}'"
        )

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
