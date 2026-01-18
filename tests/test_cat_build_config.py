"""
Tests for Build Config Skills.
Includes: FlagCleaner, Permission, BlueprintSyntax, GNScope, NinjaCache.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.build_config.flag_cleaner import FlagCleanerSkill
from src.skills.build_config.permission import PermissionSkill
from src.skills.build_config.blueprint_syntax import BlueprintSyntaxSkill
from src.skills.build_config.gn_scope import GNScopeSkill
from src.skills.build_config.ninja_cache import NinjaCacheSkill


class TestFlagCleanerSkill:
    """Tests for FlagCleanerSkill (ID 27)."""

    def test_detect_unknown_argument(self):
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
        skill = FlagCleanerSkill()
        raw_log = "clang: error: unknown argument: '-fno-strict-overflow'"
        assert skill._extract_flag(raw_log) == '-fno-strict-overflow'

    def test_classify_flag(self):
        skill = FlagCleanerSkill()
        assert skill._classify_flag('-Wno-error') == 'warning'
        assert skill._classify_flag('-fPIC') == 'feature'
        assert skill._classify_flag('-O2') == 'optimization'
        assert skill._classify_flag('-march=armv8') == 'machine'


class TestPermissionSkill:
    """Tests for PermissionSkill (ID 30)."""

    def test_detect_permission_denied(self):
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
        skill = PermissionSkill()
        raw_log = "bash: ./configure: Permission denied"
        path = skill._extract_script_path(raw_log)
        assert path == './configure'

    def test_looks_like_script(self):
        skill = PermissionSkill()
        assert skill._looks_like_script('./configure') is True
        assert skill._looks_like_script('build.sh') is True
        assert skill._looks_like_script('script.py') is True


class TestBlueprintSyntaxSkill:
    """Tests for BlueprintSyntaxSkill (ID 25)."""

    def test_detect_parse_error(self):
        skill = BlueprintSyntaxSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='parse error',
            location={'file': 'Android.bp', 'line': 10},
            symbol='',
            raw_log="Android.bp:10:5: parse error: expected ',' before ']'"
        )
        assert skill.detect(diag) is True

    def test_detect_unexpected_token(self):
        skill = BlueprintSyntaxSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='unexpected',
            location={'file': 'Android.bp', 'line': 15},
            symbol='',
            raw_log="Android.bp:15:1: unexpected '}'"
        )
        assert skill.detect(diag) is True


class TestGNScopeSkill:
    """Tests for GNScopeSkill (ID 26)."""

    def test_detect_undefined_identifier(self):
        skill = GNScopeSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undefined',
            location={'file': 'BUILD.gn', 'line': 10},
            symbol='',
            raw_log="Undefined identifier 'my_flag'"
        )
        assert skill.detect(diag) is True

    def test_detect_no_effect(self):
        skill = GNScopeSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='no effect',
            location={'file': 'BUILD.gn', 'line': 20},
            symbol='',
            raw_log="Assignment had no effect for 'unused_var'"
        )
        assert skill.detect(diag) is True


class TestNinjaCacheSkill:
    """Tests for NinjaCacheSkill (ID 29)."""

    def test_detect_dirty_target(self):
        skill = NinjaCacheSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='ninja error',
            location={'file': 'build.ninja', 'line': 1},
            symbol='',
            raw_log="ninja: error: 'obj/foo/bar.o' is dirty, build.ninja needs to be regenerated"
        )
        assert skill.detect(diag) is True

    def test_detect_missing_file(self):
        skill = NinjaCacheSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='stat',
            location={'file': 'build.ninja', 'line': 1},
            symbol='',
            raw_log="ninja: error: stat(obj/component/file.o): No such file or directory"
        )
        assert skill.detect(diag) is True

    def test_extract_target(self):
        skill = NinjaCacheSkill()
        raw_log = "stat(out/obj/my_module.o): No such file or directory"
        info = skill._extract_target_info(raw_log)
        assert info is not None
        assert 'target' in info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
