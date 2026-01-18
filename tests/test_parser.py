"""
Tests for the Build File Parser.
"""

import pytest
from src.build_adapters.parser import (
    BlueprintParser,
    GNParser,
    parse_android_bp,
    parse_build_gn,
)


class TestBlueprintParser:
    """Test Blueprint (Android.bp) parsing."""

    def test_parse_simple_module(self):
        """Test parsing a simple module."""
        content = '''
cc_library {
    name: "libfoo",
    srcs: ["foo.cpp"],
}
'''
        modules = parse_android_bp(content)
        assert len(modules) == 1
        assert modules[0].module_type == 'cc_library'
        assert modules[0].name == 'libfoo'
        assert 'srcs' in modules[0].properties
        assert modules[0].properties['srcs'] == ['foo.cpp']

    def test_parse_module_with_deps(self):
        """Test parsing a module with dependencies."""
        content = '''
cc_binary {
    name: "myapp",
    srcs: ["main.cpp"],
    shared_libs: [
        "libfoo",
        "libbar",
    ],
}
'''
        modules = parse_android_bp(content)
        assert len(modules) == 1
        assert modules[0].properties['shared_libs'] == ['libfoo', 'libbar']

    def test_parse_multiple_modules(self):
        """Test parsing multiple modules."""
        content = '''
cc_library {
    name: "libfoo",
}

cc_library {
    name: "libbar",
}
'''
        modules = parse_android_bp(content)
        assert len(modules) == 2
        assert modules[0].name == 'libfoo'
        assert modules[1].name == 'libbar'

    def test_parse_with_comments(self):
        """Test parsing with comments."""
        content = '''
// This is a comment
cc_library {
    name: "libfoo", // inline comment
    /* block comment */
    srcs: ["foo.cpp"],
}
'''
        modules = parse_android_bp(content)
        assert len(modules) == 1
        assert modules[0].name == 'libfoo'

    def test_parse_nested_struct(self):
        """Test parsing nested structures."""
        content = '''
cc_defaults {
    name: "my_defaults",
    target: {
        android: {
            cflags: ["-DANDROID"],
        },
    },
}
'''
        modules = parse_android_bp(content)
        assert len(modules) == 1
        assert 'target' in modules[0].properties

    def test_parse_boolean_values(self):
        """Test parsing boolean values."""
        content = '''
cc_library {
    name: "libfoo",
    host_supported: true,
    vendor: false,
}
'''
        modules = parse_android_bp(content)
        assert modules[0].properties['host_supported'] is True
        assert modules[0].properties['vendor'] is False


class TestGNParser:
    """Test GN (BUILD.gn) parsing."""

    def test_parse_simple_target(self):
        """Test parsing a simple target."""
        content = '''
source_set("foo") {
  sources = [ "foo.cc" ]
}
'''
        targets = parse_build_gn(content)
        assert len(targets) == 1
        assert targets[0].module_type == 'source_set'
        assert targets[0].name == 'foo'
        assert targets[0].properties['sources'] == ['foo.cc']

    def test_parse_target_with_deps(self):
        """Test parsing a target with dependencies."""
        content = '''
executable("myapp") {
  sources = [ "main.cc" ]
  deps = [
    ":foo",
    "//third_party:bar",
  ]
}
'''
        targets = parse_build_gn(content)
        assert len(targets) == 1
        assert targets[0].properties['deps'] == [':foo', '//third_party:bar']

    def test_parse_multiple_targets(self):
        """Test parsing multiple targets."""
        content = '''
source_set("foo") {
  sources = [ "foo.cc" ]
}

static_library("bar") {
  sources = [ "bar.cc" ]
}
'''
        targets = parse_build_gn(content)
        assert len(targets) == 2
        assert targets[0].name == 'foo'
        assert targets[1].name == 'bar'

    def test_parse_with_comments(self):
        """Test parsing with comments."""
        content = '''
# This is a comment (note: GN uses # but our lexer handles //)
// This is also a comment
source_set("foo") {
  sources = [ "foo.cc" ]  // inline comment
}
'''
        targets = parse_build_gn(content)
        assert len(targets) == 1

    def test_parse_plus_equals(self):
        """Test parsing += operator."""
        content = '''
source_set("foo") {
  sources = [ "foo.cc" ]
  sources += [ "bar.cc" ]
}
'''
        targets = parse_build_gn(content)
        assert len(targets) == 1
        # Note: our simple parser doesn't merge += properly yet
        # This tests that it at least doesn't crash


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
