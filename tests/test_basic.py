"""
Basic tests for AutoFix-Skill components.
"""

import pytest
from pathlib import Path

from src.utils.logger import get_logger
from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    SkillManager,
)


class TestLogger:
    """Test the logger module."""

    def test_get_logger(self):
        """Test that we can create a logger."""
        logger = get_logger('test')
        assert logger is not None
        assert logger.name == 'test'

    def test_logger_reuse(self):
        """Test that the same logger is returned for the same name."""
        logger1 = get_logger('test_reuse')
        logger2 = get_logger('test_reuse')
        assert logger1 is logger2


class TestSkillRegistry:
    """Test the skill registry module."""

    def test_diagnostic_object_creation(self):
        """Test DiagnosticObject creation."""
        diag = DiagnosticObject(
            uid='test-uid',
            build_system='gn',
            error_code='E0020',
            location={'file': 'test.cpp', 'line': 42},
            symbol='MyFunction',
            raw_log="error: 'MyFunction' was not declared"
        )
        assert diag.uid == 'test-uid'
        assert diag.build_system == 'gn'
        assert diag.error_code == 'E0020'
        assert diag.location['file'] == 'test.cpp'

    def test_execution_plan_creation(self):
        """Test ExecutionPlan creation."""
        plan = ExecutionPlan()
        assert plan.version == "1.0"
        assert plan.steps == []

        plan.steps.append({
            'action': 'ADD_DEPENDENCY',
            'params': {'target': 'lib_test', 'dependency': '//path:dep'}
        })
        assert len(plan.steps) == 1

    def test_skill_manager_registration(self):
        """Test skill registration."""
        manager = SkillManager()

        class DummySkill(BaseSkill):
            error_codes = ['E9999']

            def detect(self, diagnostic):
                return True

            def analyze(self, diagnostic, context):
                return {}

            def execute(self, diagnostic, analysis_result):
                return ExecutionPlan()

        manager.register(DummySkill)

        assert 'DummySkill' in manager.get_all_skills()
        assert DummySkill in manager.get_skills_for_error('E9999')

    def test_skill_manager_no_match(self):
        """Test that unknown error codes return empty list."""
        manager = SkillManager()
        skills = manager.get_skills_for_error('UNKNOWN_CODE')
        assert skills == []


class TestCLI:
    """Test the CLI module."""

    def test_parse_error_log_simple(self):
        """Test basic error log parsing."""
        from src.cli import parse_error_log

        log = "src/main.cpp:42:10: error: 'foo.h' file not found"
        diagnostics = parse_error_log(log, 'gn')

        assert len(diagnostics) == 1
        assert diagnostics[0].location['file'] == 'src/main.cpp'
        assert diagnostics[0].location['line'] == 42

    def test_parse_error_log_empty(self):
        """Test parsing empty log."""
        from src.cli import parse_error_log

        diagnostics = parse_error_log('', 'gn')
        assert diagnostics == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
