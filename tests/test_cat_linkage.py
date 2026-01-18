"""
Tests for Linkage & Dependency Skills.
Includes: Visibility, RustDep, Vtable, MultipleDef, VariantMismatch, SymbolDep.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.linkage_dependency.visibility import VisibilitySkill
from src.skills.linkage_dependency.rust_dep import RustDepSkill
from src.skills.linkage_dependency.vtable import VtableSkill
from src.skills.linkage_dependency.multiple_def import MultipleDefSkill
from src.skills.linkage_dependency.variant_mismatch import VariantMismatchSkill
from src.skills.linkage_dependency.symbol_dep import SymbolDepSkill


class TestVisibilitySkill:
    """Tests for VisibilitySkill (ID 15)."""

    def test_detect_visibility_error(self):
        skill = VisibilitySkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='visibility',
            location={'file': 'Android.bp', 'line': 1},
            symbol='',
            raw_log="'//vendor/mod:target' depends on '//system/lib:hidden' which is not visible"
        )
        assert skill.detect(diag) is True

    def test_detect_visibility_violation(self):
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
        skill = VisibilitySkill()
        raw_log = "'//vendor/app:main' depends on '//system/core:libutils' which is not visible"
        info = skill._extract_module_info(raw_log)
        assert info['requesting_module'] == '//vendor/app:main'
        assert info['target_module'] == '//system/core:libutils'


class TestRustDepSkill:
    """Tests for RustDepSkill (ID 08, 13)."""

    def test_detect_cant_find_crate(self):
        skill = RustDepSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            error_code='E0463',
            build_system='soong',
            location={'file': 'main.rs', 'line': 1},
            symbol='',
            raw_log="error[E0463]: can't find crate for `serde`"
        )
        assert skill.detect(diag) is True

    def test_detect_unresolved_import(self):
        skill = RustDepSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            error_code='E0432',
            build_system='soong',
            location={'file': 'lib.rs', 'line': 1},
            symbol='',
            raw_log="error[E0432]: unresolved import `tokio::runtime`"
        )
        assert skill.detect(diag) is True

    def test_extract_crate_name(self):
        skill = RustDepSkill()
        raw_log = "error[E0463]: can't find crate for `anyhow`"
        info = skill._extract_crate_info(raw_log)
        assert info['crate'] == 'anyhow'

    def test_crate_module_mapping(self):
        skill = RustDepSkill()
        assert skill.CRATE_MODULE_MAP.get('serde') == 'libserde'


class TestVtableSkill:
    """Tests for VtableSkill (ID 14)."""

    def test_detect_vtable_error(self):
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


class TestMultipleDefSkill:
    """Tests for MultipleDefSkill (ID 16)."""

    def test_detect_multiple_definition(self):
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
        skill = MultipleDefSkill()
        raw_log = "multiple definition of 'calculateSum'"
        info = skill._extract_symbol_info(raw_log)
        assert info['symbol'] == 'calculateSum'


class TestVariantMismatchSkill:
    """Tests for VariantMismatchSkill (ID 18)."""

    def test_detect_vendor_variant(self):
        skill = VariantMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='vendor variant',
            location={'file': 'Android.bp', 'line': 1},
            symbol='',
            raw_log="'app' depends on vendor variant of 'lib' which is not available"
        )
        assert skill.detect(diag) is True

    def test_detect_vndk_violation(self):
        skill = VariantMismatchSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='vndk',
            location={'file': 'Android.bp', 'line': 1},
            symbol='',
            raw_log="VNDK violation: 'libprivate' is not in VNDK"
        )
        assert skill.detect(diag) is True

    def test_no_detect_non_soong(self):
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


class TestSymbolDepSkill:
    """Tests for SymbolDepSkill (ID 11, 12)."""

    def test_detect_undefined_reference(self):
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
        skill = SymbolDepSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='msvc',
            error_code='LNK2019',
            location={'file': 'test.obj', 'line': 0},
            symbol='',
            raw_log='error LNK2019: unresolved external symbol "void __cdecl foo(void)"'
        )
        assert skill.detect(diag) is True

    def test_no_detect_unrelated_error(self):
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

    def test_extract_symbol_name(self):
        skill = SymbolDepSkill()
        raw_log = "undefined reference to `MyFunction'"
        assert skill._extract_symbol_name(raw_log) == 'MyFunction'

    def test_demangle_simple_mangled_name(self):
        skill = SymbolDepSkill()
        demangled = skill._demangle_symbol('_Z3foov')
        assert demangled == 'foo'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
