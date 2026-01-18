"""
Tests for SymbolDepSkill.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.symbol_dep import SymbolDepSkill


class TestSymbolDepSkill:
    """Test the SymbolDepSkill module."""

    def test_detect_undefined_reference(self):
        """Test detection of undefined reference errors."""
        skill = SymbolDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undefined reference',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="ld.lld: error: undefined reference to `MyFunction'"
        )

        assert skill.detect(diag) is True

    def test_detect_undefined_symbol(self):
        """Test detection of undefined symbol errors."""
        skill = SymbolDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undefined symbol',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="ld.lld: error: undefined symbol: SomeClass::method(int)"
        )

        assert skill.detect(diag) is True

    def test_detect_msvc_linker_error(self):
        """Test detection of MSVC linker errors."""
        skill = SymbolDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='msvc',
            error_code='LNK2019',
            location={'file': 'test.obj', 'line': 0},
            symbol='',
            raw_log='error LNK2019: unresolved external symbol "void __cdecl foo(void)" referenced in function main'
        )

        assert skill.detect(diag) is True

    def test_no_detect_unrelated_error(self):
        """Test that unrelated errors are not detected."""
        skill = SymbolDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='E0001',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: expected ';' before '}'"
        )

        assert skill.detect(diag) is False

    def test_extract_symbol_name_simple(self):
        """Test symbol name extraction from simple error."""
        skill = SymbolDepSkill()

        raw_log = "undefined reference to `MyFunction'"
        symbol = skill._extract_symbol_name(raw_log)
        assert symbol == 'MyFunction'

    def test_extract_symbol_name_with_namespace(self):
        """Test symbol name extraction with namespace."""
        skill = SymbolDepSkill()

        raw_log = "undefined symbol: MyNamespace::MyClass::myMethod"
        symbol = skill._extract_symbol_name(raw_log)
        assert symbol == 'MyNamespace::MyClass::myMethod'

    def test_demangle_simple_mangled_name(self):
        """Test demangling of simple C++ mangled names."""
        skill = SymbolDepSkill()

        # Simple mangled name: _Z3fooXXX means 'foo' with 3 characters
        demangled = skill._demangle_symbol('_Z3foov')
        assert demangled == 'foo'

    def test_demangle_unmangled_name(self):
        """Test that unmangled names pass through."""
        skill = SymbolDepSkill()

        demangled = skill._demangle_symbol('regular_function')
        assert demangled == 'regular_function'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
