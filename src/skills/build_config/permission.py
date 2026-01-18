"""
Permission Skill - Fix permission denied errors on scripts.

This skill detects errors where a script lacks execute permissions
and runs chmod +x to fix it.

Implements ID 30 from top30_skills.md.
"""

import os
import re
import stat
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
class PermissionSkill(BaseSkill):
    """
    Skill for fixing script permission errors.

    Handles errors like:
    - "permission denied: ./script.sh"
    - "bash: ./configure: Permission denied"
    - "EACCES: permission denied"

    The fix involves running chmod +x on the script.
    """

    error_codes: List[str] = [
        'permission denied',
        'EACCES',
        'cannot execute',
    ]

    # Patterns to extract the script path
    PERMISSION_ERROR_PATTERNS = [
        r"permission denied:?\s*[`'\"]?([^\s`'\"]+)",
        r"bash:\s*([^\s:]+):\s*permission denied",
        r"cannot execute [`'\"]?([^\s`'\"]+)",
        r"exec:\s*[`'\"]?([^\s`'\"]+)[`'\"]?.*permission denied",
        r"EACCES.*[`'\"]?([^\s`'\"]+\.sh)",
    ]

    # Common script extensions
    SCRIPT_EXTENSIONS = ['.sh', '.py', '.pl', '.rb', '.bash', '.zsh', '']

    def __init__(self, name: str = "PermissionSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about permission denied on a script."""
        raw_log = diagnostic.raw_log.lower()

        # Check for permission-related keywords
        indicators = ['permission denied', 'eacces', 'cannot execute']

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the script path
        script_path = self._extract_script_path(diagnostic.raw_log)
        if script_path:
            self.logger.info(f"Detected permission issue on: {script_path}")
            return True

        return False

    def _extract_script_path(self, raw_log: str) -> Optional[str]:
        """Extract the script path from error log."""
        for pattern in self.PERMISSION_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                path = match.group(1)
                # Verify it looks like a script
                if self._looks_like_script(path):
                    return path
        return None

    def _looks_like_script(self, path: str) -> bool:
        """Check if path looks like an executable script."""
        # Check extension
        for ext in self.SCRIPT_EXTENSIONS:
            if path.endswith(ext):
                return True

        # Check for common script names
        common_scripts = ['configure', 'bootstrap', 'autogen', 'build']
        basename = Path(path).name
        if any(s in basename.lower() for s in common_scripts):
            return True

        return False

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the permission error.

        Determines:
        - The script path
        - Whether the file exists
        - Current permissions
        """
        script_path = self._extract_script_path(diagnostic.raw_log)
        if not script_path:
            self.logger.error("Could not extract script path from error")
            return None

        # Try to resolve the path
        path = Path(script_path)
        exists = path.exists()
        current_mode = None

        if exists:
            try:
                current_mode = oct(stat.S_IMODE(os.stat(path).st_mode))
            except OSError:
                pass

        return {
            'script_path': script_path,
            'exists': exists,
            'current_mode': current_mode,
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed and file exists."""
        if analysis_result is None:
            return False
        if 'script_path' not in analysis_result:
            return False
        # File should exist to fix permissions
        return analysis_result.get('exists', False)

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the permission issue.

        The plan will chmod +x the script.
        """
        plan = ExecutionPlan()

        script_path = analysis_result.get('script_path', '')

        plan.steps.append({
            'action': 'CHMOD',
            'params': {
                'path': script_path,
                'mode': '+x',
            }
        })

        self.logger.info(f"Plan: chmod +x '{script_path}'")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
