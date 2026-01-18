"""
Ninja Cache Skill - Fix Ninja build cache corruption issues.

This skill detects Ninja cache-related errors and suggests
cleaning the build cache to resolve issues.

Implements ID 29 from top30_skills.md.
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
class NinjaCacheSkill(BaseSkill):
    """
    Skill for fixing Ninja build cache corruption issues.

    Handles errors like:
    - "ninja: error: ... is dirty"
    - "stat(...): No such file or directory"
    - "depfile is missing"
    - "build.ninja:123: error"

    The fix involves cleaning the affected targets.
    """

    error_codes: List[str] = [
        'dirty',
        'depfile',
        'stat(',
        'ninja: error',
        'build.ninja',
    ]

    # Patterns to extract target information
    NINJA_ERROR_PATTERNS = [
        r"ninja: error:.*[`'\"]?([^\s`'\"]+)[`'\"]?\s+is dirty",
        r"stat\(([^\)]+)\).*No such file",
        r"depfile.*[`'\"]?([^\s`'\"]+)[`'\"]?\s+is missing",
        r"missing input.*[`'\"]?([^\s`'\"]+)",
    ]

    def __init__(self, name: str = "NinjaCacheSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about Ninja cache issues."""
        raw_log = diagnostic.raw_log.lower()

        # Check for Ninja-related keywords
        indicators = [
            'ninja: error',
            'is dirty',
            'depfile',
            'stat(',
            'build.ninja',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Must be related to missing/corrupt cache
        cache_indicators = [
            'dirty',
            'missing',
            'no such file',
            'not found',
        ]

        if not any(ind in raw_log for ind in cache_indicators):
            return False

        self.logger.info("Detected Ninja cache issue")
        return True

    def _extract_target_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the affected target from the error log."""
        for pattern in self.NINJA_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                return {
                    'target': match.group(1),
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """Analyze the Ninja cache error."""
        info = self._extract_target_info(diagnostic.raw_log)

        target = info.get('target', '') if info else ''

        # If target is a file path, extract the module/component
        if target:
            target_path = Path(target)
            component = target_path.parent.name if target_path.parent.name else target
        else:
            component = ''

        return {
            'target': target,
            'component': component,
            'commands': [
                f'ninja -t clean {component}' if component else 'ninja -t clean',
                'rm -rf out/.ninja_log',
            ],
        }

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """Generate an execution plan to fix the Ninja cache issue."""
        plan = ExecutionPlan()

        target = analysis_result.get('target', '')
        component = analysis_result.get('component', '')
        commands = analysis_result.get('commands', [])

        for cmd in commands:
            plan.steps.append({
                'action': 'RUN_COMMAND',
                'params': {
                    'command': cmd,
                }
            })

        self.logger.info(f"Plan: Clean Ninja cache for '{target or 'all'}'")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        return SkillResult.SUCCESS
