"""
Tests for Symbol & Header Skills.
Includes: UndeclaredIdentifier, JavaImport, Namespace, ForwardDecl, MacroUndefined, KbuildObject.
"""

import pytest
from src.skill_registry.manager import DiagnosticObject
from src.skills.symbol_header.undeclared_identifier import UndeclaredIdentifierSkill
from src.skills.symbol_header.java_import import JavaImportSkill
from src.skills.symbol_header.namespace import NamespaceSkill
from src.skills.symbol_header.forward_decl import ForwardDeclSkill
from src.skills.symbol_header.macro_undefined import MacroUndefinedSkill
from src.skills.symbol_header.kbuild_object import KbuildObjectSkill


class TestUndeclaredIdentifierSkill:
    """Tests for UndeclaredIdentifierSkill (ID 04)."""

    def test_detect_undeclared_identifier(self):
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
        skill = UndeclaredIdentifierSkill()
        raw_log = "error: use of undeclared identifier 'LOG'"
        identifier = skill._extract_identifier(raw_log)
        assert identifier == 'LOG'

    def test_std_header_lookup(self):
        skill = UndeclaredIdentifierSkill()
        assert skill.STD_HEADER_MAP.get('vector') == '<vector>'
        assert skill.STD_HEADER_MAP.get('string') == '<string>'

    def test_analyze_with_known_identifier(self):
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


class TestJavaImportSkill:
    """Tests for JavaImportSkill (ID 06, 07)."""

    def test_detect_cannot_find_symbol(self):
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
        skill = JavaImportSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='soong',
            error_code='package does not exist',
            location={'file': 'Test.java', 'line': 5},
            symbol='',
            raw_log="error: package androidx.recyclerview.widget does not exist"
        )
        assert skill.detect(diag) is True

    def test_no_detect_non_java(self):
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
        skill = JavaImportSkill()
        raw_log = "error: package com.google.gson does not exist"
        info = skill._extract_symbol_info(raw_log)
        assert info is not None
        assert 'com.google.gson' in info['symbol']


class TestNamespaceSkill:
    """Tests for NamespaceSkill (ID 05)."""

    def test_detect_not_member_of(self):
        skill = NamespaceSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='not a member',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: 'cout' is not a member of 'std'"
        )
        assert skill.detect(diag) is True

    def test_guess_namespace(self):
        skill = NamespaceSkill()
        assert skill._guess_namespace('vector') == 'std'


class TestForwardDeclSkill:
    """Tests for ForwardDeclSkill (ID 09)."""

    def test_detect_incomplete_type(self):
        skill = ForwardDeclSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='incomplete type',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: incomplete type 'class MyClass' used"
        )
        assert skill.detect(diag) is True

    def test_extract_type_info(self):
        skill = ForwardDeclSkill()
        raw_log = "incomplete type 'struct Buffer' used"
        info = skill._extract_type_info(raw_log)
        assert info['type_name'] == 'Buffer'
        assert info['type_kind'] == 'struct'


class TestMacroUndefinedSkill:
    """Tests for MacroUndefinedSkill (ID 10)."""

    def test_detect_undefined_macro(self):
        skill = MacroUndefinedSkill()
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='undeclared',
            location={'file': 'test.cpp', 'line': 10},
            symbol='',
            raw_log="error: 'DEBUG_MODE' was not declared in this scope"
        )
        assert skill.detect(diag) is True

    def test_extract_macro_info(self):
        skill = MacroUndefinedSkill()
        raw_log = "'CONFIG_FEATURE' was not declared in this scope"
        info = skill._extract_macro_info(raw_log)
        assert info['macro'] == 'CONFIG_FEATURE'


class TestKbuildObjectSkill:
    """Tests for KbuildObjectSkill (ID 17)."""

    def test_detect_no_rule_for_object(self):
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
        skill = KbuildObjectSkill()
        raw_log = "No rule to make target 'drivers/my_driver.o'"
        info = skill._extract_object_info(raw_log)
        assert info['object'] == 'drivers/my_driver.o'
        assert info['source'] == 'drivers/my_driver.c'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
