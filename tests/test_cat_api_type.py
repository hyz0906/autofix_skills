"""
Tests for API & Type Skills.
Includes: SignatureMismatch, TypeConversion, ConstMismatch, OverrideMissing, DeprecatedAPI, VersionGuard.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.api_type.signature_mismatch import SignatureMismatchSkill
from src.skills.api_type.type_conversion import TypeConversionSkill
from src.skills.api_type.const_mismatch import ConstMismatchSkill
from src.skills.api_type.override_missing import OverrideMissingSkill
from src.skills.api_type.deprecated_api import DeprecatedAPISkill
from src.skills.api_type.version_guard import VersionGuardSkill


class TestSignatureMismatchSkill:
    """Tests for SignatureMismatchSkill (ID 19)."""

    def test_detect_no_matching_function(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='no matching function',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: no matching function for call to 'MyClass::doSum(int)'"
        )
        assert skill.detect(diag) is True

    def test_detect_too_many_arguments(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='too many arguments',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: too many arguments to function 'void foo(int)'"
        )
        assert skill.detect(diag) is True

    def test_detect_too_few_arguments(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='too few arguments',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: too few arguments to function 'void bar(int, int, int)'"
        )
        assert skill.detect(diag) is True

    def test_detect_cannot_convert(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='cannot convert',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: cannot convert 'std::string' to 'const char*'"
        )
        assert skill.detect(diag) is True

    def test_detect_msvc_error(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='msvc',
            error_code='C2660',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error C2660: 'MyFunction': function does not take 3 arguments"
        )
        assert skill.detect(diag) is True

    def test_no_detect_unrelated_error(self):
        skill = SignatureMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='E0001',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: 'foo.h' file not found"
        )
        assert skill.detect(diag) is False

    def test_extract_function_name_simple(self):
        skill = SignatureMismatchSkill()
        raw_log = "error: no matching function for call to 'MyClass::doSomething'"
        info = skill._extract_function_info(raw_log)
        assert info['function_name'] == 'MyClass::doSomething'

    def test_extract_function_name_too_many_args(self):
        skill = SignatureMismatchSkill()
        raw_log = "error: too many arguments to function 'void foo(int)'"
        info = skill._extract_function_info(raw_log)
        assert info['function_name'] == 'void foo(int)'

    def test_classify_error(self):
        skill = SignatureMismatchSkill()
        assert skill._classify_error("too many arguments to function") == 'too_many_args'
        assert skill._classify_error("too few arguments to function") == 'too_few_args'
        assert skill._classify_error("no matching function for call") == 'no_match'
        assert skill._classify_error("cannot convert 'int' to 'string'") == 'type_mismatch'

    def test_generate_suggestions(self):
        skill = SignatureMismatchSkill()
        suggestions = skill._generate_suggestions('too_many_args', 'myFunction', [], "too many arguments")
        assert len(suggestions) >= 1
        assert 'Remove extra arguments' in suggestions[0]


class TestTypeConversionSkill:
    """Tests for TypeConversionSkill (ID 20)."""

    def test_detect_cannot_convert(self):
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
        skill = TypeConversionSkill()
        raw_log = "cannot convert 'const char*' to 'char*'"
        info = skill._extract_type_info(raw_log)
        assert 'const char*' in info['from_type']
        assert 'char*' in info['to_type']

    def test_suggest_cast(self):
        skill = TypeConversionSkill()
        assert skill._suggest_cast('const char*', 'char*') == 'const_cast'
        assert skill._suggest_cast('int*', 'void*') == 'reinterpret_cast'
        assert skill._suggest_cast('int', 'long') == 'static_cast'


class TestConstMismatchSkill:
    """Tests for ConstMismatchSkill (ID 21)."""

    def test_detect_cv_qualifier_error(self):
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
        skill = DeprecatedAPISkill()
        assert skill.DEPRECATED_API_MAP.get('strcpy') is not None
        assert skill.DEPRECATED_API_MAP.get('auto_ptr') == 'unique_ptr'


class TestVersionGuardSkill:
    """Tests for VersionGuardSkill (ID 23)."""

    def test_detect_implicit_declaration(self):
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
        skill = VersionGuardSkill()
        assert skill.KERNEL_API_VERSIONS.get('timer_setup') == (4, 15, 0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
