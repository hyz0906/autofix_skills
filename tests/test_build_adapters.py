"""
Tests for Build Adapters.
"""

import pytest
import tempfile
from pathlib import Path
from src.build_adapters.kbuild import KbuildAdapter
from src.build_adapters.cmake import CMakeAdapter
from src.build_adapters.makefile import MakefileAdapter


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
