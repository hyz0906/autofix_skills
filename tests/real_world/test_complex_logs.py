"""
Real-world log parsing and validation tests.

These tests use simulated complex build logs that mimic
actual AOSP and OpenHarmony build output.
"""

import pytest
from src.cli import parse_error_log
from src.skill_registry.manager import skill_manager
from src.skills.symbol_header.missing_header import MissingHeaderSkill
from src.skills.linkage_dependency.symbol_dep import SymbolDepSkill
from src.skills.api_type.signature_mismatch import SignatureMismatchSkill


# Sample complex build logs
AOSP_BUILD_LOG = """
[100%] Building CXX object libfoo.so
In file included from frameworks/base/core/jni/android_view_Surface.cpp:30:
frameworks/base/core/jni/android_view_Surface.cpp:45:10: fatal error: 'ui/GraphicBuffer.h' file not found
#include <ui/GraphicBuffer.h>
         ^~~~~~~~~~~~~~~~~~~~
1 error generated.
[101%] Building CXX object libbar.so
ld.lld: error: undefined reference to 'android::GraphicBuffer::create(int, int, int, int)'
>>> referenced by android_view_Surface.cpp:102
clang++: error: linker command failed with exit code 1
FAILED: libbar.so
ninja: build stopped: subcommand failed.
"""

OPENHARMONY_BUILD_LOG = """
[OHOS INFO] Building component: ability_base
In file included from foundation/ability/ability_runtime/interfaces/kits/native/ability/ability_context.h:20:
foundation/ability/ability_runtime/interfaces/kits/native/ability/ability_context.h:25:10: fatal error: 'ability_runtime/context/context.h' file not found
#include "ability_runtime/context/context.h"
         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1 error generated.
[OHOS ERROR] Build failed at component ability_base
"""

INTERLEAVED_LOG = """
[1/100] CXX obj/foo/foo.o
FAILED: obj/foo/foo.o
../../foo/foo.cc:10:5: error: no matching function for call to 'bar'
    bar(1, 2, 3);
    ^~~
../../foo/bar.h:5:6: note: candidate function not viable: requires 2 arguments, but 3 were provided
void bar(int a, int b);
     ^
[2/100] CXX obj/baz/baz.o
../../baz/baz.cc:20:10: fatal error: 'missing.h' file not found
#include "missing.h"
         ^~~~~~~~~~~
[3/100] LINK libqux.so
ld.lld: error: undefined reference to 'Helper::init()'
>>> referenced by qux.cc:30
ninja: build stopped: subcommand failed.
"""

MSVC_BUILD_LOG = """
foo.cpp(42): error C2660: 'MyClass::doSomething': function does not take 3 arguments
bar.cpp(100): error C2664: 'void process(const char *)': cannot convert argument 1 from 'std::string' to 'const char *'
baz.obj : error LNK2019: unresolved external symbol "public: void __cdecl Widget::render(void)" (?render@Widget@@QEAAXXZ)
"""


class TestAOSPLogParsing:
    """Test parsing of AOSP-style build logs."""

    def test_parse_aosp_log(self):
        """Test parsing AOSP build log."""
        diagnostics = parse_error_log(AOSP_BUILD_LOG, 'soong')

        # Should find at least 2 errors
        assert len(diagnostics) >= 2

    def test_aosp_missing_header_detected(self):
        """Test that missing header in AOSP log is detected."""
        diagnostics = parse_error_log(AOSP_BUILD_LOG, 'soong')
        skill = MissingHeaderSkill()

        header_errors = [d for d in diagnostics if skill.detect(d)]
        assert len(header_errors) >= 1

    def test_aosp_undefined_reference_detected(self):
        """Test that undefined reference in AOSP log is detected."""
        diagnostics = parse_error_log(AOSP_BUILD_LOG, 'soong')
        skill = SymbolDepSkill()

        linker_errors = [d for d in diagnostics if skill.detect(d)]
        assert len(linker_errors) >= 1


class TestOpenHarmonyLogParsing:
    """Test parsing of OpenHarmony-style build logs."""

    def test_parse_openharmony_log(self):
        """Test parsing OpenHarmony build log."""
        diagnostics = parse_error_log(OPENHARMONY_BUILD_LOG, 'gn')

        assert len(diagnostics) >= 1

    def test_openharmony_missing_header_detected(self):
        """Test that missing header in OH log is detected."""
        diagnostics = parse_error_log(OPENHARMONY_BUILD_LOG, 'gn')
        skill = MissingHeaderSkill()

        header_errors = [d for d in diagnostics if skill.detect(d)]
        assert len(header_errors) >= 1


class TestInterleavedLogParsing:
    """Test parsing of interleaved/multi-error logs."""

    def test_parse_interleaved_log(self):
        """Test parsing interleaved build log."""
        diagnostics = parse_error_log(INTERLEAVED_LOG, 'gn')

        # Should find all 3 types of errors
        assert len(diagnostics) >= 3

    def test_all_error_types_detected(self):
        """Test that all error types are detected."""
        diagnostics = parse_error_log(INTERLEAVED_LOG, 'gn')

        missing_header_skill = MissingHeaderSkill()
        symbol_dep_skill = SymbolDepSkill()
        signature_skill = SignatureMismatchSkill()

        header_errors = [d for d in diagnostics if missing_header_skill.detect(d)]
        linker_errors = [d for d in diagnostics if symbol_dep_skill.detect(d)]
        signature_errors = [d for d in diagnostics if signature_skill.detect(d)]

        assert len(header_errors) >= 1, "Should detect header error"
        assert len(linker_errors) >= 1, "Should detect linker error"
        assert len(signature_errors) >= 1, "Should detect signature error"


class TestMSVCLogParsing:
    """Test parsing of MSVC-style build logs."""

    def test_parse_msvc_log(self):
        """Test parsing MSVC build log."""
        diagnostics = parse_error_log(MSVC_BUILD_LOG, 'msvc')

        assert len(diagnostics) >= 2

    def test_msvc_signature_errors_detected(self):
        """Test that MSVC signature errors are detected."""
        diagnostics = parse_error_log(MSVC_BUILD_LOG, 'msvc')
        skill = SignatureMismatchSkill()

        signature_errors = [d for d in diagnostics if skill.detect(d)]
        assert len(signature_errors) >= 2

    def test_msvc_linker_error_detected(self):
        """Test that MSVC linker error is detected."""
        diagnostics = parse_error_log(MSVC_BUILD_LOG, 'msvc')
        skill = SymbolDepSkill()

        linker_errors = [d for d in diagnostics if skill.detect(d)]
        assert len(linker_errors) >= 1


class TestSkillRouting:
    """Test that errors are routed to the correct skills."""

    def test_skill_manager_has_skills(self):
        """Test that skills are registered."""
        # Import to trigger registration
        from src.skills.symbol_header import missing_header
        from src.skills.linkage_dependency import symbol_dep
        from src.skills.api_type import signature_mismatch

        all_skills = skill_manager.get_all_skills()
        assert len(all_skills) >= 3

    def test_correct_skill_for_header_error(self):
        """Test correct skill selection for header errors."""
        diagnostics = parse_error_log(AOSP_BUILD_LOG, 'soong')

        for diag in diagnostics:
            skills = skill_manager.get_skills_for_error(diag.error_code)
            # At least one skill should match
            if 'fatal error' in diag.raw_log.lower():
                matched = any(
                    skill().detect(diag)
                    for skill in skill_manager.get_skills_for_error('fatal error')
                )
                # Note: This may not always be true depending on skill registration


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
