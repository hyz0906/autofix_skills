"""
Tests for Wave 4 Skills: Build System Resilience.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.blueprint_syntax import BlueprintSyntaxSkill
from src.skills.gn_scope import GNScopeSkill
from src.skills.multiple_def import MultipleDefSkill
from src.skills.variant_mismatch import VariantMismatchSkill
from src.skills.ninja_cache import NinjaCacheSkill


class TestBlueprintSyntaxSkill:
    """Tests for BlueprintSyntaxSkill (ID 25)."""

    def test_detect_parse_error(self):
        """Test detection of Blueprint parse errors."""
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
        """Test detection of unexpected token errors."""
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

    def test_no_detect_non_blueprint(self):
        """Test that non-Blueprint errors are not detected."""
        skill = BlueprintSyntaxSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='parse error',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="parse error in test.cpp"
        )

        assert skill.detect(diag) is False


class TestGNScopeSkill:
    """Tests for GNScopeSkill (ID 26)."""

    def test_detect_undefined_identifier(self):
        """Test detection of undefined identifier in GN."""
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
        """Test detection of 'no effect' warnings."""
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


class TestMultipleDefSkill:
    """Tests for MultipleDefSkill (ID 16)."""

    def test_detect_multiple_definition(self):
        """Test detection of multiple definition errors."""
        skill = MultipleDefSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='multiple definition',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="ld.lld: error: multiple definition of 'MyFunction'"
        )

        assert skill.detect(diag) is True

    def test_detect_duplicate_symbol(self):
        """Test detection of duplicate symbol errors."""
        skill = MultipleDefSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='duplicate symbol',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="ld: duplicate symbol '_globalVar' in libfoo.a and libbar.a"
        )

        assert skill.detect(diag) is True

    def test_extract_symbol(self):
        """Test symbol extraction."""
        skill = MultipleDefSkill()

        raw_log = "multiple definition of 'calculateSum'"
        info = skill._extract_symbol_info(raw_log)

        assert info is not None
        assert info['symbol'] == 'calculateSum'


class TestVariantMismatchSkill:
    """Tests for VariantMismatchSkill (ID 18)."""

    def test_detect_vendor_variant(self):
        """Test detection of vendor variant errors."""
        skill = VariantMismatchSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='vendor variant',
            location={'file': 'Android.bp', 'line': 10},
            symbol='',
            raw_log="'my_vendor_app' depends on vendor variant of 'libutils'"
        )

        assert skill.detect(diag) is True

    def test_detect_vndk_violation(self):
        """Test detection of VNDK violation errors."""
        skill = VariantMismatchSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='vndk',
            location={'file': 'Android.bp', 'line': 10},
            symbol='',
            raw_log="VNDK violation: 'libprivate' is not in VNDK"
        )

        assert skill.detect(diag) is True

    def test_no_detect_non_soong(self):
        """Test that non-Soong build systems are not detected."""
        skill = VariantMismatchSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='vendor',
            location={'file': 'BUILD.gn', 'line': 10},
            symbol='',
            raw_log="vendor variant not available"
        )

        assert skill.detect(diag) is False


class TestNinjaCacheSkill:
    """Tests for NinjaCacheSkill (ID 29)."""

    def test_detect_dirty_target(self):
        """Test detection of dirty target errors."""
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
        """Test detection of missing file errors."""
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
        """Test target extraction."""
        skill = NinjaCacheSkill()

        raw_log = "stat(out/obj/my_module.o): No such file or directory"
        info = skill._extract_target_info(raw_log)

        assert info is not None
        assert 'target' in info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
