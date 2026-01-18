"""
Variant Mismatch Skill - Fix Soong vendor/system partition errors.

This skill detects errors when vendor modules cannot depend on
system modules and suggests enabling vendor_available.

Implements ID 18 from top30_skills.md.
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
class VariantMismatchSkill(BaseSkill):
    """
    Skill for fixing Soong vendor/system variant mismatch errors.

    Handles errors like:
    - "depends on vendor variant of 'libfoo'"
    - "is not visible to vendor modules"
    - "vendor variant not available"
    - "VNDK violation"

    The fix involves setting vendor_available: true on the target module.
    """

    error_codes: List[str] = [
        'vendor variant',
        'vendor_available',
        'vndk',
        'not visible to vendor',
        'vendor module',
    ]

    # Patterns to extract module information
    VARIANT_PATTERNS = [
        r"[`'\"]?(\w+)[`'\"]?\s+depends on vendor variant of\s*[`'\"]?(\w+)",
        r"[`'\"]?(\w+)[`'\"]?\s+is not visible to vendor",
        r"vendor variant.*[`'\"]?(\w+)[`'\"]?.*not available",
        r"VNDK.*[`'\"]?(\w+)[`'\"]?",
    ]

    def __init__(self, name: str = "VariantMismatchSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about vendor/system variant mismatch."""
        raw_log = diagnostic.raw_log.lower()

        # Must be Soong build system
        if diagnostic.build_system != 'soong':
            return False

        # Check for variant-related keywords
        indicators = [
            'vendor variant',
            'vendor_available',
            'vndk',
            'not visible to vendor',
            'vendor module',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        self.logger.info("Detected vendor/system variant mismatch")
        return True

    def _extract_module_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract module names from the error log."""
        for pattern in self.VARIANT_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return {
                        'requesting_module': groups[0],
                        'target_module': groups[1],
                    }
                else:
                    return {
                        'target_module': groups[0],
                    }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the variant mismatch error."""
        info = self._extract_module_info(diagnostic.raw_log)

        target_module = info.get('target_module', 'unknown') if info else 'unknown'
        requesting_module = info.get('requesting_module') if info else None

        return {
            'target_module': target_module,
            'requesting_module': requesting_module,
            'fix_property': 'vendor_available: true',
            'alternative': 'Or add to VNDK list if appropriate',
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the variant mismatch."""
        plan = ExecutionPlan()

        target_module = analysis_result.get('target_module', '')

        plan.steps.append({
            'action': 'ADD_PROPERTY',
            'params': {
                'module': target_module,
                'property': 'vendor_available',
                'value': 'true',
            }
        })

        self.logger.info(
            f"Plan: Add 'vendor_available: true' to module '{target_module}'"
        )

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
