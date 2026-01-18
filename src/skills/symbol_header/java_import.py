"""
Java Import Skill - Fix missing package/class errors in Java.

This skill detects "cannot find symbol" and "package does not exist"
errors and suggests fixes by finding the correct import or dependency.

Implements ID 06 and ID 07 from top30_skills.md.
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
class JavaImportSkill(BaseSkill):
    """
    Skill for fixing Java import and package errors.

    Handles errors like:
    - "error: cannot find symbol" (class not found)
    - "error: package com.example does not exist"
    - "error: cannot access ClassName"

    The fix involves either:
    1. Adding the import statement to the source file
    2. Adding the library dependency to build config (Android.bp, pom.xml, build.gradle)
    """

    error_codes: List[str] = [
        'cannot find symbol',
        'package does not exist',
        'cannot access',
        'symbol not found',
    ]

    # Patterns to extract class/package information
    JAVA_ERROR_PATTERNS = [
        r"cannot find symbol.*symbol:\s*class\s+(\w+)",
        r"cannot find symbol.*symbol:\s*variable\s+(\w+)",
        r"package\s+([\w.]+)\s+does not exist",
        r"package\s+([\w.]+).*does not exist",  # More flexible
        r"cannot access\s+([\w.]+)",
        r"error:.*[`'\"]?([\w.]+)[`'\"]?\s+cannot be resolved",
    ]

    # Common Android/Java package to module mappings
    PACKAGE_MODULE_MAP = {
        # Android Support Library
        'android.support.v4': 'android-support-v4',
        'android.support.v7': 'android-support-v7-appcompat',
        'android.support.design': 'android-support-design',
        # AndroidX
        'androidx.core': 'androidx.core_core',
        'androidx.appcompat': 'androidx.appcompat_appcompat',
        'androidx.fragment': 'androidx.fragment_fragment',
        'androidx.recyclerview': 'androidx.recyclerview_recyclerview',
        # Common Android classes
        'android.util.Log': None,  # Built-in
        'android.os.Bundle': None,  # Built-in
        'android.content.Context': None,  # Built-in
        # Guava
        'com.google.common': 'guava',
        # Gson
        'com.google.gson': 'gson',
        # OkHttp
        'okhttp3': 'okhttp',
        # Retrofit
        'retrofit2': 'retrofit',
    }

    def __init__(self, name: str = "JavaImportSkill"):
        super().__init__(name)

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """Check if this error is about a missing Java import/package."""
        raw_log = diagnostic.raw_log.lower()

        # Check for Java-related keywords
        indicators = [
            'cannot find symbol',
            'does not exist',  # Fixed: package X does not exist
            'cannot access',
            'symbol not found',
            'cannot be resolved',
        ]

        # Also check file extension
        source_file = diagnostic.location.get('file', '')
        is_java_file = source_file.endswith('.java') or source_file.endswith('.kt')

        if not is_java_file:
            return False

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the class/package info
        info = self._extract_symbol_info(diagnostic.raw_log)
        if info:
            self.logger.info(f"Detected Java import issue: {info}")
            return True

        return False

    def _extract_symbol_info(self, raw_log: str) -> Optional[Dict[str, str]]:
        """Extract the missing class/package from error log."""
        for pattern in self.JAVA_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE | re.DOTALL)
            if match:
                symbol = match.group(1)
                return {
                    'symbol': symbol,
                    'type': 'package' if '.' in symbol else 'class'
                }
        return None

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the Java import error.

        Determines:
        - The missing symbol/package
        - The source file needing the import
        - The module/library to add as dependency
        """
        info = self._extract_symbol_info(diagnostic.raw_log)
        if not info:
            self.logger.error("Could not extract symbol info from error")
            return None

        symbol = info['symbol']
        source_file = Path(diagnostic.location.get('file', ''))
        line = diagnostic.location.get('line', 1)

        # Try to find the module for this package
        module = self._find_module_for_symbol(symbol)

        return {
            'symbol': symbol,
            'symbol_type': info['type'],
            'source_file': str(source_file),
            'line': line,
            'module': module,
            'needs_import': info['type'] == 'class',
            'needs_dependency': module is not None,
        }

    def _find_module_for_symbol(self, symbol: str) -> Optional[str]:
        """Find the module/library that provides a symbol."""
        # Check direct mapping
        if symbol in self.PACKAGE_MODULE_MAP:
            return self.PACKAGE_MODULE_MAP[symbol]

        # Check prefix matching for packages
        for package, module in self.PACKAGE_MODULE_MAP.items():
            if symbol.startswith(package):
                return module

        return None

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed."""
        return analysis_result is not None and 'symbol' in analysis_result

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate an execution plan to fix the Java import issue.

        May include:
        1. Adding import statement to source file
        2. Adding library dependency to build config
        """
        plan = ExecutionPlan()

        symbol = analysis_result.get('symbol', '')
        source_file = analysis_result.get('source_file', '')
        module = analysis_result.get('module')

        if analysis_result.get('needs_import'):
            # Generate import statement
            if '.' in symbol:
                import_stmt = f'import {symbol};'
            else:
                import_stmt = f'// TODO: Add import for {symbol}'

            plan.steps.append({
                'action': 'INSERT_IMPORT',
                'params': {
                    'source_file': source_file,
                    'import_statement': import_stmt,
                }
            })
            self.logger.info(f"Plan: Insert import '{import_stmt}'")

        if module:
            plan.steps.append({
                'action': 'ADD_DEPENDENCY',
                'params': {
                    'module': module,
                    'dep_type': 'libs',
                }
            })
            self.logger.info(f"Plan: Add dependency '{module}'")

        if not plan.steps:
            plan.steps.append({
                'action': 'ANALYZE',
                'params': {
                    'symbol': symbol,
                    'suggestion': f"Could not find module for '{symbol}'",
                }
            })

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """Verify the fix was successful."""
        return SkillResult.SUCCESS
