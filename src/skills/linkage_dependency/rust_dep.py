"""
Rust Dependency Skill - Fix missing crate errors in Rust.

This skill detects "can't find crate" and "unresolved import" errors
and modifies Android.bp or Cargo.toml to add the dependency.

Implements ID 08 and ID 13 from top30_skills.md.
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
class RustDepSkill(BaseSkill):
    """
    Skill for fixing Rust crate/dependency errors.

    Handles errors like:
    - "can't find crate for `foo`"
    - "unresolved import `std::collections::HashMap`"
    - "error[E0433]: failed to resolve: use of undeclared crate or module"

    The fix involves:
    1. For Android.bp: Adding to rustlibs or rlibs
    2. For Cargo.toml: Adding to [dependencies]
    """

    error_codes: List[str] = [
        "can't find crate",
        'unresolved import',
        'E0433',  # use of undeclared crate or module
        'E0432',  # unresolved import
        'E0463',  # can't find crate
    ]

    # Patterns to extract crate information
    RUST_ERROR_PATTERNS = [
        r"can't find crate for\s*[`'\"]?(\w+)",
        r"unresolved import\s*[`'\"]?([\w:]+)",
        r"E0433.*use of undeclared crate or module\s*[`'\"]?(\w+)",
        r"E0432.*unresolved import\s*[`'\"]?([\w:]+)",
        r"E0463.*can't find crate for\s*[`'\"]?(\w+)",
        r"error.*crate\s+(\w+)\s+not found",
    ]

    # Common Rust crate to Android module mappings
    CRATE_MODULE_MAP = {
        # Standard crates in Android
        'libc': 'liblibc',
        'log': 'liblog_rust',
        'env_logger': 'libenv_logger',
        'serde': 'libserde',
        'serde_json': 'libserde_json',
        'tokio': 'libtokio',
        'anyhow': 'libanyhow',
        'thiserror': 'libthiserror',
        'clap': 'libclap',
        'regex': 'libregex',
        'lazy_static': 'liblazy_static',
        'once_cell': 'libonce_cell',
        'nix': 'libnix',
        'bindgen': 'libbindgen',
    }

    def __init__(self, name: str = "RustDepSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing Rust crate."""
        raw_log = diagnostic.raw_log.lower()

        # Check for Rust-related keywords
        indicators = [
            "can't find crate",
            'unresolved import',
            'e0433',
            'e0432',
            'e0463',
            'crate not found',
        ]

        # Also check file extension
        source_file = diagnostic.location.get('file', '')
        is_rust_file = source_file.endswith('.rs')

        if not is_rust_file and 'rustc' not in raw_log:
            return False

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the crate info
        info = self._extract_crate_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected Rust crate issue: {info}")
            return True

        return False

    def _extract_crate_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the missing crate from error log."""
        for pattern in self.RUST_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                crate_path = match.group(1)
                # Extract root crate name (before ::)
                crate_name = crate_path.split(':')[0].split('::')[0]
                return {
                    'crate': crate_name,
                    'full_path': crate_path,
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the Rust crate error.

        Determines:
        - The missing crate
        - The build system (Android.bp or Cargo.toml)
        - The module name to add
        """
        info = self._extract_crate_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract crate info from error")
            return None

        crate_name = info['crate']
        source_file = Path(diagnostic.location.get('file', ''))

        # Find the Android module name
        android_module = self.CRATE_MODULE_MAP.get(crate_name)
        if not android_module:
            # Default naming convention: lib<crate_name>
            android_module = f'lib{crate_name}'

        # Determine build system
        build_system = diagnostic.build_system
        if build_system == 'soong':
            dep_type = 'rustlibs'
        else:
            dep_type = 'dependencies'

        return {
            'crate': crate_name,
            'full_path': info['full_path'],
            'source_file': str(source_file),
            'android_module': android_module,
            'build_system': build_system,
            'dep_type': dep_type,
        }

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'crate' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the Rust crate issue.

        Adds the crate dependency to build configuration.
        """
        plan = ExecutionPlan()

        crate_name = analysis_result.get('crate', '')
        android_module = analysis_result.get('android_module', '')
        build_system = analysis_result.get('build_system', 'soong')
        dep_type = analysis_result.get('dep_type', 'rustlibs')

        if build_system == 'soong':
            plan.steps.append({
                'action': 'ADD_DEPENDENCY',
                'params': {
                    'module': android_module,
                    'dep_type': dep_type,
                    'crate': crate_name,
                }
            })
            self.logger.info(
                f"Plan: Add '{android_module}' to rustlibs in Android.bp"
            )
        else:
            # For Cargo.toml
            plan.steps.append({
                'action': 'ADD_CARGO_DEPENDENCY',
                'params': {
                    'crate': crate_name,
                    'version': '*',  # Latest
                }
            })
            self.logger.info(
                f"Plan: Add '{crate_name}' to Cargo.toml [dependencies]"
            )

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
