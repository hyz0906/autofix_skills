"""
Tests for SignatureMismatchSkill.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.signature_mismatch import SignatureMismatchSkill


class TestSignatureMismatchSkill:
    """Test the SignatureMismatchSkill module."""

    def test_detect_no_matching_function(self):
        """Test detection of 'no matching function' errors."""
        skill = SignatureMismatchSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='no matching function',
            location={'file': 'test.cpp', 'line': 42},
            symbol='',
            raw_log="error: no matching function for call to 'MyClass::doSomething(int, int)'"
        )

        assert skill.detect(diag) is True

    def test_detect_too_many_arguments(self):
        """Test detection of 'too many arguments' errors."""
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
        """Test detection of 'too few arguments' errors."""
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
        """Test detection of type conversion errors."""
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
        """Test detection of MSVC linker errors."""
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
        """Test that unrelated errors are not detected."""
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
        """Test function name extraction from simple error."""
        skill = SignatureMismatchSkill()

        raw_log = "error: no matching function for call to 'MyClass::doSomething'"
        info = skill._extract_function_info(raw_log)

        assert info is not None
        assert info['function_name'] == 'MyClass::doSomething'

    def test_extract_function_name_too_many_args(self):
        """Test function name extraction from 'too many arguments' error."""
        skill = SignatureMismatchSkill()

        raw_log = "error: too many arguments to function 'void foo(int)'"
        info = skill._extract_function_info(raw_log)

        assert info is not None
        assert info['function_name'] == 'void foo(int)'

    def test_classify_error_too_many(self):
        """Test error classification."""
        skill = SignatureMismatchSkill()

        assert skill._classify_error("too many arguments to function") == 'too_many_args'
        assert skill._classify_error("too few arguments to function") == 'too_few_args'
        assert skill._classify_error("no matching function for call") == 'no_match'
        assert skill._classify_error("cannot convert 'int' to 'string'") == 'type_mismatch'

    def test_generate_suggestions(self):
        """Test suggestion generation."""
        skill = SignatureMismatchSkill()

        suggestions = skill._generate_suggestions(
            'too_many_args',
            'myFunction',
            [],
            "too many arguments"
        )

        assert len(suggestions) >= 1
        assert 'Remove extra arguments' in suggestions[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
