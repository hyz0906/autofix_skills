"""
Tests for Wave 1 Skills: Visibility, FlagCleaner, Permission, UndeclaredIdentifier.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.visibility import VisibilitySkill
from src.skills.flag_cleaner import FlagCleanerSkill
from src.skills.permission import PermissionSkill
from src.skills.undeclared_identifier import UndeclaredIdentifierSkill


class TestVisibilitySkill:
    """Tests for VisibilitySkill (ID 15)."""

    def test_detect_visibility_error(self):
        """Test detection of visibility errors."""
        skill = VisibilitySkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='visibility',
            location={'file': 'Android.bp', 'line': 1},
            symbol='',
            raw_log="'//vendor/my_module:target' depends on '//system/lib:hidden_lib' which is not visible to this module"
        )

        assert skill.detect(diag) is True

    def test_detect_visibility_violation(self):
        """Test detection of visibility violation."""
        skill = VisibilitySkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='visibility',
            location={'file': 'Android.bp', 'line': 1},
            symbol='',
            raw_log="visibility violation: module 'my_target' depends on 'hidden_module'"
        )

        assert skill.detect(diag) is True

    def test_no_detect_unrelated(self):
        """Test that unrelated errors are not detected."""
        skill = VisibilitySkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='E0001',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="fatal error: 'foo.h' file not found"
        )

        assert skill.detect(diag) is False

    def test_extract_module_info(self):
        """Test module info extraction."""
        skill = VisibilitySkill()

        raw_log = "'//vendor/app:main' depends on '//system/core:libutils' which is not visible"
        info = skill._extract_module_info(raw_log)

        assert info is not None
        assert info['requesting_module'] == '//vendor/app:main'
        assert info['target_module'] == '//system/core:libutils'


class TestFlagCleanerSkill:
    """Tests for FlagCleanerSkill (ID 27)."""

    def test_detect_unknown_argument(self):
        """Test detection of unknown argument errors."""
        skill = FlagCleanerSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='unknown argument',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="clang: error: unknown argument: '-fno-strict-overflow'"
        )

        assert skill.detect(diag) is True

    def test_detect_unsupported_option(self):
        """Test detection of unsupported option errors."""
        skill = FlagCleanerSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='unsupported option',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="clang: error: unsupported option '-fno-aggressive-loop-optimizations'"
        )

        assert skill.detect(diag) is True

    def test_detect_unknown_warning(self):
        """Test detection of unknown warning option errors."""
        skill = FlagCleanerSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='unknown warning option',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="warning: unknown warning option '-Wno-unused-but-set-variable'"
        )

        assert skill.detect(diag) is True

    def test_extract_flag(self):
        """Test flag extraction."""
        skill = FlagCleanerSkill()

        raw_log = "clang: error: unknown argument: '-fno-strict-overflow'"
        flag = skill._extract_flag(raw_log)

        assert flag == '-fno-strict-overflow'

    def test_classify_flag(self):
        """Test flag classification."""
        skill = FlagCleanerSkill()

        assert skill._classify_flag('-Wno-error') == 'warning'
        assert skill._classify_flag('-fPIC') == 'feature'
        assert skill._classify_flag('-O2') == 'optimization'
        assert skill._classify_flag('-march=armv8') == 'machine'


class TestPermissionSkill:
    """Tests for PermissionSkill (ID 30)."""

    def test_detect_permission_denied(self):
        """Test detection of permission denied errors."""
        skill = PermissionSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='permission denied',
            location={'file': 'build.sh', 'line': 1},
            symbol='',
            raw_log="bash: ./configure: Permission denied"
        )

        assert skill.detect(diag) is True

    def test_detect_eacces(self):
        """Test detection of EACCES errors."""
        skill = PermissionSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='EACCES',
            location={'file': 'script.sh', 'line': 1},
            symbol='',
            raw_log="EACCES: permission denied, ./build.sh"
        )

        assert skill.detect(diag) is True

    def test_extract_script_path(self):
        """Test script path extraction."""
        skill = PermissionSkill()

        raw_log = "bash: ./configure: Permission denied"
        path = skill._extract_script_path(raw_log)

        assert path == './configure'

    def test_looks_like_script(self):
        """Test script detection."""
        skill = PermissionSkill()

        assert skill._looks_like_script('./configure') is True
        assert skill._looks_like_script('build.sh') is True
        assert skill._looks_like_script('script.py') is True
        # Note: extension-less files are accepted as possible scripts
        # so 'file.txt' could be matched if it's read as extension-less
        assert skill._looks_like_script('bootstrap') is True


class TestUndeclaredIdentifierSkill:
    """Tests for UndeclaredIdentifierSkill (ID 04)."""

    def test_detect_undeclared_identifier(self):
        """Test detection of undeclared identifier errors."""
        skill = UndeclaredIdentifierSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undeclared identifier',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: use of undeclared identifier 'vector'"
        )

        assert skill.detect(diag) is True

    def test_detect_not_declared(self):
        """Test detection of 'was not declared' errors."""
        skill = UndeclaredIdentifierSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='not declared',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: 'string' was not declared in this scope"
        )

        assert skill.detect(diag) is True

    def test_extract_identifier(self):
        """Test identifier extraction."""
        skill = UndeclaredIdentifierSkill()

        raw_log = "error: use of undeclared identifier 'LOG'"
        identifier = skill._extract_identifier(raw_log)

        assert identifier == 'LOG'

    def test_std_header_lookup(self):
        """Test standard header lookup."""
        skill = UndeclaredIdentifierSkill()

        # Test known identifiers
        assert skill.STD_HEADER_MAP.get('vector') == '<vector>'
        assert skill.STD_HEADER_MAP.get('string') == '<string>'
        assert skill.STD_HEADER_MAP.get('cout') == '<iostream>'
        assert skill.STD_HEADER_MAP.get('LOG') == '"utils/Log.h"'

    def test_analyze_with_known_identifier(self):
        """Test analysis with known standard library identifier."""
        skill = UndeclaredIdentifierSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undeclared identifier',
            location={'file': '/path/to/test.cpp', 'line': 10},
            symbol='',
            raw_log="error: use of undeclared identifier 'vector'"
        )

        result = skill.analyze(diag, None)

        assert result is not None
        assert result['identifier'] == 'vector'
        assert result['header'] == '<vector>'
        assert result['header_found'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
