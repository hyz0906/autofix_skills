"""
Tests for Wave 3 Skills: Intelligent Code Repair.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.namespace import NamespaceSkill
from src.skills.forward_decl import ForwardDeclSkill
from src.skills.vtable import VtableSkill
from src.skills.const_mismatch import ConstMismatchSkill
from src.skills.override_missing import OverrideMissingSkill
from src.skills.deprecated_api import DeprecatedAPISkill
from src.skills.macro_undefined import MacroUndefinedSkill
from src.skills.version_guard import VersionGuardSkill
from src.skills.type_conversion import TypeConversionSkill


class TestNamespaceSkill:
    """Tests for NamespaceSkill (ID 05)."""

    def test_detect_not_member_of(self):
        """Test detection of 'not a member of' errors."""
        skill = NamespaceSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='not a member',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: 'cout' is not a member of 'std'"
        )

        assert skill.detect(diag) is True

    def test_guess_namespace(self):
        """Test namespace guessing."""
        skill = NamespaceSkill()

        assert skill._guess_namespace('vector') == 'std'
        assert skill._guess_namespace('cout') == 'std'
        assert skill._guess_namespace('string') == 'std'
        assert skill._guess_namespace('unknown_func') == 'unknown'


class TestForwardDeclSkill:
    """Tests for ForwardDeclSkill (ID 09)."""

    def test_detect_incomplete_type(self):
        """Test detection of incomplete type errors."""
        skill = ForwardDeclSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='incomplete type',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: incomplete type 'class MyClass' used in nested name specifier"
        )

        assert skill.detect(diag) is True

    def test_extract_type_info(self):
        """Test type extraction."""
        skill = ForwardDeclSkill()

        raw_log = "incomplete type 'struct Buffer' used"
        info = skill._extract_type_info(raw_log)

        assert info is not None
        assert info['type_name'] == 'Buffer'
        assert info['type_kind'] == 'struct'


class TestVtableSkill:
    """Tests for VtableSkill (ID 14)."""

    def test_detect_vtable_error(self):
        """Test detection of vtable errors."""
        skill = VtableSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='vtable',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="undefined reference to 'vtable for MyClass'"
        )

        assert skill.detect(diag) is True

    def test_detect_typeinfo_error(self):
        """Test detection of typeinfo errors."""
        skill = VtableSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='typeinfo',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="undefined reference to 'typeinfo for BaseClass'"
        )

        assert skill.detect(diag) is True


class TestConstMismatchSkill:
    """Tests for ConstMismatchSkill (ID 21)."""

    def test_detect_cv_qualifier_error(self):
        """Test detection of cv-qualifier mismatch."""
        skill = ConstMismatchSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='const',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: differs only in cv-qualifiers from 'void foo() const'"
        )

        assert skill.detect(diag) is True


class TestOverrideMissingSkill:
    """Tests for OverrideMissingSkill (ID 22)."""

    def test_detect_abstract_class(self):
        """Test detection of abstract class errors."""
        skill = OverrideMissingSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='abstract',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: cannot instantiate abstract class 'Derived'"
        )

        assert skill.detect(diag) is True

    def test_detect_unimplemented_virtual(self):
        """Test detection of unimplemented virtual methods."""
        skill = OverrideMissingSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='pure virtual',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="unimplemented pure virtual method 'doWork' in 'Worker'"
        )

        assert skill.detect(diag) is True


class TestDeprecatedAPISkill:
    """Tests for DeprecatedAPISkill (ID 24)."""

    def test_detect_deprecated_warning(self):
        """Test detection of deprecated API warnings."""
        skill = DeprecatedAPISkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='deprecated',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="warning: 'strcpy' is deprecated, use 'strncpy' instead"
        )

        assert skill.detect(diag) is True

    def test_deprecated_api_map(self):
        """Test deprecated API mappings."""
        skill = DeprecatedAPISkill()

        assert skill.DEPRECATED_API_MAP.get('strcpy') is not None
        assert skill.DEPRECATED_API_MAP.get('auto_ptr') == 'unique_ptr'
        assert skill.DEPRECATED_API_MAP.get('bzero') == 'memset'


class TestMacroUndefinedSkill:
    """Tests for MacroUndefinedSkill (ID 10)."""

    def test_detect_undefined_macro(self):
        """Test detection of undefined macro errors."""
        skill = MacroUndefinedSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undeclared',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: 'DEBUG_MODE' was not declared in this scope"
        )

        assert skill.detect(diag) is True

    def test_extract_macro_info(self):
        """Test macro extraction."""
        skill = MacroUndefinedSkill()

        raw_log = "'CONFIG_FEATURE' was not declared in this scope"
        info = skill._extract_macro_info(raw_log)

        assert info is not None
        assert info['macro'] == 'CONFIG_FEATURE'


class TestVersionGuardSkill:
    """Tests for VersionGuardSkill (ID 23)."""

    def test_detect_implicit_declaration(self):
        """Test detection of implicit declaration in kernel code."""
        skill = VersionGuardSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='kbuild',
            error_code='implicit',
            location={'file': 'drivers/my_driver.c', 'line': 10},
            symbol='',
            raw_log="warning: implicit declaration of function 'timer_setup'"
        )

        assert skill.detect(diag) is True

    def test_kernel_api_versions(self):
        """Test kernel API version mappings."""
        skill = VersionGuardSkill()

        assert skill.KERNEL_API_VERSIONS.get('timer_setup') == (4, 15, 0)
        assert skill.KERNEL_API_VERSIONS.get('devm_platform_ioremap_resource') == (5, 0, 0)


class TestTypeConversionSkill:
    """Tests for TypeConversionSkill (ID 20)."""

    def test_detect_cannot_convert(self):
        """Test detection of type conversion errors."""
        skill = TypeConversionSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='cannot convert',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: cannot convert 'int*' to 'void*'"
        )

        assert skill.detect(diag) is True

    def test_extract_type_info(self):
        """Test type extraction."""
        skill = TypeConversionSkill()

        raw_log = "cannot convert 'const char*' to 'char*'"
        info = skill._extract_type_info(raw_log)

        assert info is not None
        assert 'const char*' in info['from_type']
        assert 'char*' in info['to_type']

    def test_suggest_cast(self):
        """Test cast suggestion."""
        skill = TypeConversionSkill()

        assert skill._suggest_cast('const char*', 'char*') == 'const_cast'
        assert skill._suggest_cast('int*', 'void*') == 'reinterpret_cast'
        assert skill._suggest_cast('int', 'long') == 'static_cast'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
