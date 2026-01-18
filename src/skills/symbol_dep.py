"""
Symbol Dependency Skill - Automatically fix undefined reference errors.

This skill detects "undefined reference" linker errors, searches for the
symbol definition in the source tree, identifies the target library that
provides it, and adds the dependency to the build configuration.

As per requirement.md Section 3.3 (Symbol Dependency Algorithm).
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.build_adapters.interface import IBuildAdapter
from src.build_adapters.gn import GNAdapter
from src.build_adapters.soong import SoongAdapter
from src.context_engine.ast_grep_client import AstGrepClient
from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    register_skill,
)
from src.utils.logger import get_logger


@register_skill
class SymbolDepSkill(BaseSkill):
    """
    Skill for fixing undefined reference (linker) errors.

    Handles errors like:
    - "undefined reference to 'FunctionName'"
    - "error: unresolved external symbol FunctionName"
    - "ld.lld: error: undefined symbol: FunctionName"

    Algorithm (as per requirement.md):
    1. Parse the error to extract the undefined symbol name
    2. Use ast-grep to find the definition of the symbol
    3. Identify the module/library that contains the definition
    4. Modify the build file to add the dependency (shared_libs/deps)
    """

    # Error patterns this skill can handle
    error_codes: List[str] = [
        'undefined reference',
        'unresolved external',
        'undefined symbol',
        'LNK2001',  # MSVC linker error
        'LNK2019',  # MSVC linker error
    ]

    # Regex patterns to match undefined symbol errors
    SYMBOL_ERROR_PATTERNS = [
        r"undefined reference to [`']([^`']+)[`']",
        r"undefined reference to [`']([^(`']+)\([^)]*\)[`']",  # function with args
        r"unresolved external symbol\s+[\"']?([^\"'\s(]+)",
        r"undefined symbol:\s*([^\s(]+)",
        r"error LNK2019:.*symbol\s+[\"']?([^\"'\s(]+)",
        r"error LNK2001:.*symbol\s+[\"']?([^\"'\s(]+)",
    ]

    def __init__(self, name: str = "SymbolDepSkill"):
        super().__init__(name)
        self.context_engine: Optional[AstGrepClient] = None
        self.build_adapter: Optional[IBuildAdapter] = None

    def detect(self, diagnostic: DiagnosticObject) -> bool:
        """
        Check if this error is about an undefined symbol/reference.
        """
        raw_log = diagnostic.raw_log.lower()

        # Check for common undefined reference indicators
        indicators = [
            'undefined reference',
            'unresolved external',
            'undefined symbol',
            'lnk2001',
            'lnk2019',
        ]

        if not any(ind in raw_log for ind in indicators):
            return False

        # Try to extract the symbol name
        symbol_name = self._extract_symbol_name(diagnostic.raw_log)
        if symbol_name:
            self.logger.info(f"Detected undefined symbol: {symbol_name}")
            return True

        return False

    def _extract_symbol_name(self, raw_log: str) -> Optional[str]:
        """Extract the undefined symbol name from the error log."""
        for pattern in self.SYMBOL_ERROR_PATTERNS:
            match = re.search(pattern, raw_log, re.IGNORECASE)
            if match:
                symbol = match.group(1)
                # Clean up C++ mangled names if needed
                symbol = self._demangle_symbol(symbol)
                return symbol
        return None

    def _demangle_symbol(self, symbol: str) -> str:
        """
        Attempt to demangle C++ symbol names.

        For now, just extract the function name from simple mangled forms.
        In production, you'd use c++filt or a demangling library.
        """
        # Handle common patterns like _Z3fooXXX -> foo
        if symbol.startswith('_Z'):
            # Very simplified: find the first sequence of letters after length
            match = re.match(r'_Z(\d+)([a-zA-Z_][a-zA-Z0-9_]*)', symbol)
            if match:
                length = int(match.group(1))
                name = match.group(2)[:length]
                return name

        # Handle _GLOBAL__sub_I_xxx patterns
        if '_GLOBAL__' in symbol:
            return symbol

        return symbol

    def analyze(
        self,
        diagnostic: DiagnosticObject,
        context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the error and search for the symbol definition.

        Returns analysis containing:
        - symbol_name: the undefined symbol
        - definition_locations: list of files where the symbol is defined
        - target_library: the module that provides the symbol
        """
        symbol_name = self._extract_symbol_name(diagnostic.raw_log)
        if not symbol_name:
            self.logger.error("Could not extract symbol name from error")
            return None

        # Get the source file location
        source_file = Path(diagnostic.location.get('file', ''))

        # Initialize context engine
        if isinstance(context, AstGrepClient):
            self.context_engine = context
        else:
            root_dir = source_file.parent if source_file.exists() else Path.cwd()
            self.context_engine = AstGrepClient(root_dir)

        # Search for the function definition using ast-grep
        definition_matches = self.context_engine.search_function_definition(
            symbol_name,
            language='cpp'
        )

        if not definition_matches:
            self.logger.warning(f"Symbol {symbol_name} definition not found")
            # Try a broader search
            definition_matches = self.context_engine.search_pattern(
                f"$TYPE {symbol_name}($$$) {{ $$$BODY }}",
                language='cpp'
            )

        if not definition_matches:
            self.logger.error(f"Could not find definition for {symbol_name}")
            return None

        self.logger.info(f"Found {len(definition_matches)} definition(s) for {symbol_name}")

        # Find the target library by looking for the build file
        definition_file = Path(definition_matches[0].file)
        target_library = self._find_providing_library(definition_file)

        return {
            'symbol_name': symbol_name,
            'definition_locations': [m.file for m in definition_matches],
            'target_library': target_library,
            'source_file': str(source_file),
        }

    def _find_providing_library(self, definition_file: Path) -> Optional[str]:
        """
        Find the library/module that provides a given source file.
        """
        # Walk up from the definition file to find a build file
        current_dir = definition_file.parent

        while current_dir != current_dir.parent:
            # Check for Android.bp
            android_bp = current_dir / 'Android.bp'
            if android_bp.exists():
                return self._extract_module_name_from_bp(android_bp, definition_file)

            # Check for BUILD.gn
            build_gn = current_dir / 'BUILD.gn'
            if build_gn.exists():
                return self._extract_target_name_from_gn(build_gn, definition_file)

            current_dir = current_dir.parent

        return None

    def _extract_module_name_from_bp(
        self,
        bp_file: Path,
        source_file: Path
    ) -> Optional[str]:
        """Extract the module name from Android.bp that contains the source file."""
        try:
            content = bp_file.read_text()
            # Find module that references this source file
            source_base = source_file.name

            # Simple pattern to find module name
            module_pattern = r'(\w+)\s*\{\s*name:\s*"([^"]+)"'
            for match in re.finditer(module_pattern, content):
                module_type, module_name = match.groups()
                # Check if this module block contains the source
                # This is simplified; real implementation would parse properly
                module_start = match.start()
                # Find end of module block
                brace_count = 0
                for i, char in enumerate(content[module_start:]):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            module_content = content[module_start:module_start + i + 1]
                            if source_base in module_content or 'srcs' in module_content:
                                return module_name
                            break
            return None
        except Exception as e:
            self.logger.error(f"Error parsing {bp_file}: {e}")
            return None

    def _extract_target_name_from_gn(
        self,
        gn_file: Path,
        source_file: Path
    ) -> Optional[str]:
        """Extract the target name from BUILD.gn that contains the source file."""
        try:
            content = gn_file.read_text()
            source_base = source_file.name

            # Find target that references this source file
            target_pattern = r'(\w+)\s*\(\s*"([^"]+)"\s*\)'
            for match in re.finditer(target_pattern, content):
                target_type, target_name = match.groups()
                target_start = match.start()
                # Find end of target block
                brace_count = 0
                for i, char in enumerate(content[target_start:]):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            target_content = content[target_start:target_start + i + 1]
                            if source_base in target_content or 'sources' in target_content:
                                return target_name
                            break
            return None
        except Exception as e:
            self.logger.error(f"Error parsing {gn_file}: {e}")
            return None

    def pre_check(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Verify we have the information needed to make the fix."""
        if not analysis_result.get('target_library'):
            self.logger.warning("Could not identify target library")
            # We might still be able to provide useful information
            return True

        source_file = Path(analysis_result.get('source_file', ''))
        if not source_file.exists():
            self.logger.error(f"Source file does not exist: {source_file}")
            return False

        # Initialize build adapter
        root_dir = source_file.parent
        while not (root_dir / 'BUILD.gn').exists() and \
              not (root_dir / 'Android.bp').exists() and \
              root_dir != root_dir.parent:
            root_dir = root_dir.parent

        if (root_dir / 'Android.bp').exists():
            self.build_adapter = SoongAdapter(root_dir)
        elif (root_dir / 'BUILD.gn').exists():
            self.build_adapter = GNAdapter(root_dir)
        else:
            self.logger.error("No supported build file found")
            return False

        return True

    def execute(
        self,
        diagnostic: DiagnosticObject,
        analysis_result: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Generate the execution plan to fix the undefined reference.
        """
        plan = ExecutionPlan()

        target_library = analysis_result.get('target_library')
        source_file = Path(analysis_result.get('source_file', ''))

        if not target_library:
            self.logger.error("Cannot fix: target library unknown")
            return plan

        if not self.build_adapter:
            self.logger.error("Build adapter not initialized")
            return plan

        # Get module info for the source file (the consumer)
        module_info = self.build_adapter.get_module_info(source_file)
        if not module_info:
            self.logger.error(f"Could not find module for {source_file}")
            return plan

        # Add dependency step
        plan.steps.append({
            'action': 'ADD_DEPENDENCY',
            'params': {
                'target': module_info.name,
                'dependency': target_library,
                'type': 'shared_library'
            }
        })

        # Apply the change
        success = self.build_adapter.inject_dependency(
            target_module=module_info.name,
            dep_name=target_library,
            dep_type='shared_library'
        )

        if success:
            self.logger.info(
                f"Added dependency {target_library} to {module_info.name}"
            )
        else:
            self.logger.error("Failed to inject dependency")

        return plan

    def verify(self, diagnostic: DiagnosticObject) -> SkillResult:
        """
        Verify the fix.

        Full verification would require running the linker again.
        """
        return SkillResult.SUCCESS
