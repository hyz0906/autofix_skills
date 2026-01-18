"""
Tests for Wave 2 Skills and Adapters.
"""

import pytest
import tempfile
from pathlib import Path

from src.skill_registry.manager import DiagnosticObject
from src.skills.java_import import JavaImportSkill
from src.skills.rust_dep import RustDepSkill
from src.skills.kbuild_object import KbuildObjectSkill
from src.build_adapters.kbuild import KbuildAdapter
from src.build_adapters.cmake import CMakeAdapter
from src.build_adapters.makefile import MakefileAdapter


class TestJavaImportSkill:
    """Tests for JavaImportSkill (ID 06, 07)."""

    def test_detect_cannot_find_symbol(self):
        """Test detection of 'cannot find symbol' errors."""
        skill = JavaImportSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='cannot find symbol',
            location={'file': 'MainActivity.java', 'line': 10},
            symbol='',
            raw_log="error: cannot find symbol\n  symbol:   class RecyclerView"
        )

        assert skill.detect(diag) is True

    def test_detect_package_not_exist(self):
        """Test detection of 'package does not exist' errors."""
        skill = JavaImportSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='package does not exist',
            location={'file': '/path/to/Test.java', 'line': 5},
            symbol='',
            raw_log="error: package androidx.recyclerview.widget does not exist"
        )

        assert skill.detect(diag) is True

    def test_no_detect_non_java(self):
        """Test that non-Java files are not detected."""
        skill = JavaImportSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='cannot find symbol',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="cannot find symbol foo"
        )

        assert skill.detect(diag) is False

    def test_extract_package(self):
        """Test package extraction."""
        skill = JavaImportSkill()

        raw_log = "error: package com.google.gson does not exist"
        info = skill._extract_symbol_info(raw_log)

        assert info is not None
        assert 'com.google.gson' in info['symbol']


class TestRustDepSkill:
    """Tests for RustDepSkill (ID 08, 13)."""

    def test_detect_cant_find_crate(self):
        """Test detection of 'can't find crate' errors."""
        skill = RustDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='E0463',
            location={'file': 'main.rs', 'line': 1},
            symbol='',
            raw_log="error[E0463]: can't find crate for `serde`"
        )

        assert skill.detect(diag) is True

    def test_detect_unresolved_import(self):
        """Test detection of 'unresolved import' errors."""
        skill = RustDepSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='E0432',
            location={'file': 'lib.rs', 'line': 3},
            symbol='',
            raw_log="error[E0432]: unresolved import `tokio::runtime`"
        )

        assert skill.detect(diag) is True

    def test_extract_crate_name(self):
        """Test crate name extraction."""
        skill = RustDepSkill()

        raw_log = "error[E0463]: can't find crate for `anyhow`"
        info = skill._extract_crate_info(raw_log)

        assert info is not None
        assert info['crate'] == 'anyhow'

    def test_crate_module_mapping(self):
        """Test crate to Android module mapping."""
        skill = RustDepSkill()

        assert skill.CRATE_MODULE_MAP.get('serde') == 'libserde'
        assert skill.CRATE_MODULE_MAP.get('tokio') == 'libtokio'


class TestKbuildObjectSkill:
    """Tests for KbuildObjectSkill (ID 17)."""

    def test_detect_no_rule_for_object(self):
        """Test detection of 'No rule to make target' errors."""
        skill = KbuildObjectSkill()

        diag = DiagnosticObject(
            uid='test-uid',
            build_system='kbuild',
            error_code='no rule',
            location={'file': 'Makefile', 'line': 1},
            symbol='',
            raw_log="make: *** No rule to make target 'drivers/foo/bar.o'"
        )

        assert skill.detect(diag) is True

    def test_extract_object_file(self):
        """Test object file extraction."""
        skill = KbuildObjectSkill()

        raw_log = "No rule to make target 'drivers/my_driver.o'"
        info = skill._extract_object_info(raw_log)

        assert info is not None
        assert info['object'] == 'drivers/my_driver.o'
        assert info['source'] == 'drivers/my_driver.c'


class TestKbuildAdapter:
    """Tests for KbuildAdapter."""

    def test_find_build_file(self):
        """Test finding Kbuild/Makefile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subdir = root / 'drivers' / 'my_driver'
            subdir.mkdir(parents=True)

            # Create Makefile
            makefile = subdir / 'Makefile'
            makefile.write_text('obj-y += driver.o\n')

            # Create source file
            source = subdir / 'driver.c'
            source.touch()

            adapter = KbuildAdapter(root)
            result = adapter.find_build_file(source)

            assert result is not None
            assert result.name == 'Makefile'

    def test_extract_obj_list(self):
        """Test object list extraction."""
        adapter = KbuildAdapter(Path('.'))

        content = """
obj-y += foo.o
obj-y += bar.o baz.o
obj-$(CONFIG_TEST) += test.o
"""
        objs = adapter._extract_obj_list(content, 'obj-y')

        assert 'foo.o' in objs
        assert 'bar.o' in objs
        assert 'baz.o' in objs


class TestCMakeAdapter:
    """Tests for CMakeAdapter."""

    def test_find_build_file(self):
        """Test finding CMakeLists.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subdir = root / 'src'
            subdir.mkdir()

            # Create CMakeLists.txt
            cmake = subdir / 'CMakeLists.txt'
            cmake.write_text('add_executable(myapp main.cpp)\n')

            # Create source file
            source = subdir / 'main.cpp'
            source.touch()

            adapter = CMakeAdapter(root)
            result = adapter.find_build_file(source)

            assert result is not None
            assert result.name == 'CMakeLists.txt'

    def test_extract_targets(self):
        """Test target extraction."""
        adapter = CMakeAdapter(Path('.'))

        content = """
add_executable(myapp main.cpp utils.cpp)
add_library(mylib SHARED lib.cpp)
"""
        targets = adapter._extract_targets(content)

        assert len(targets) == 2
        assert targets[0][0] == 'myapp'
        assert targets[0][1] == 'executable'
        assert targets[1][0] == 'mylib'
        assert targets[1][1] == 'library'


class TestMakefileAdapter:
    """Tests for MakefileAdapter."""

    def test_find_build_file(self):
        """Test finding Makefile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create Makefile
            makefile = root / 'Makefile'
            makefile.write_text('TARGET = myapp\nSRCS = main.c\n')

            # Create source file
            source = root / 'main.c'
            source.touch()

            adapter = MakefileAdapter(root)
            result = adapter.find_build_file(source)

            assert result is not None
            assert result.name == 'Makefile'

    def test_extract_variable_list(self):
        """Test variable list extraction."""
        adapter = MakefileAdapter(Path('.'))

        content = """
SRCS = main.c utils.c
CFLAGS = -Wall -O2
"""
        srcs = adapter._extract_variable_list(content, 'SRCS')
        cflags = adapter._extract_variable_list(content, 'CFLAGS')

        assert 'main.c' in srcs
        assert 'utils.c' in srcs
        assert '-Wall' in cflags
        assert '-O2' in cflags


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
