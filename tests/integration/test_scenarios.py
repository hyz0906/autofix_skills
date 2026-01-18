"""
Integration tests for AutoFix-Skill.

These tests create realistic build scenarios with mock filesystem
structures and verify the end-to-end fix flow.
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from src.orchestrator.base import Orchestrator, Platform, BuildSystem
from src.skill_registry.manager import DiagnosticObject
from src.build_adapters.gn import GNAdapter
from src.build_adapters.soong import SoongAdapter
from src.skills.symbol_header.missing_header import MissingHeaderSkill


class TestGNIntegration:
    """Integration tests for GN (BUILD.gn) based projects."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_project_structure(self):
        """Create a mock OpenHarmony-like project structure."""
        # Create directory structure
        (self.temp_dir / 'foundation' / 'ability').mkdir(parents=True)
        (self.temp_dir / 'foundation' / 'multimedia').mkdir(parents=True)
        (self.temp_dir / 'out').mkdir()

        # Create ohos_config.json marker
        (self.temp_dir / 'out' / 'ohos_config.json').write_text('{}')

        # Create a BUILD.gn in foundation/ability
        build_gn = self.temp_dir / 'foundation' / 'ability' / 'BUILD.gn'
        build_gn.write_text('''
source_set("ability_base") {
  sources = [
    "ability_manager.cpp",
  ]
  deps = []
}
''')

        # Create source file
        source_file = self.temp_dir / 'foundation' / 'ability' / 'ability_manager.cpp'
        source_file.write_text('#include "ability.h"\nint main() {}')

        # Create a header in multimedia
        header_dir = self.temp_dir / 'foundation' / 'multimedia' / 'include'
        header_dir.mkdir(parents=True)
        (header_dir / 'audio_client.h').write_text('// audio client header')

        return source_file, build_gn

    def test_environment_detection_openharmony(self):
        """Test that OpenHarmony environment is properly detected."""
        self._create_project_structure()

        orchestrator = Orchestrator(self.temp_dir)

        assert orchestrator.environment.platform == Platform.OPENHARMONY
        assert orchestrator.environment.build_system == BuildSystem.GN

    def test_gn_adapter_find_build_file(self):
        """Test that GN adapter finds the correct BUILD.gn."""
        source_file, build_gn = self._create_project_structure()

        adapter = GNAdapter(self.temp_dir)
        found = adapter.find_build_file(source_file)

        assert found is not None
        assert found == build_gn

    def test_gn_adapter_get_module_info(self):
        """Test that GN adapter extracts module info."""
        source_file, _ = self._create_project_structure()

        adapter = GNAdapter(self.temp_dir)
        info = adapter.get_module_info(source_file)

        assert info is not None
        assert info.name == 'ability_base'
        assert info.module_type == 'source_set'

    def test_gn_adapter_inject_dependency(self):
        """Test dependency injection into BUILD.gn."""
        source_file, build_gn = self._create_project_structure()

        adapter = GNAdapter(self.temp_dir)
        success = adapter.inject_dependency(
            target_module='ability_base',
            dep_name='//foundation/multimedia:audio_client',
            dep_type='shared_library'
        )

        assert success is True

        # Verify the dependency was added
        content = build_gn.read_text()
        assert '//foundation/multimedia:audio_client' in content

    def test_gn_adapter_modify_include_path(self):
        """Test include path modification in BUILD.gn."""
        source_file, build_gn = self._create_project_structure()

        adapter = GNAdapter(self.temp_dir)
        success = adapter.modify_include_path(
            target_module='ability_base',
            path='foundation/multimedia/include',
            action='add'
        )

        assert success is True

        content = build_gn.read_text()
        assert 'foundation/multimedia/include' in content


class TestSoongIntegration:
    """Integration tests for Soong (Android.bp) based projects."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_project_structure(self):
        """Create a mock AOSP-like project structure."""
        # Create directory structure
        (self.temp_dir / 'build').mkdir()
        (self.temp_dir / 'out').mkdir()
        (self.temp_dir / 'frameworks' / 'base').mkdir(parents=True)
        (self.temp_dir / 'external' / 'libcxx' / 'include').mkdir(parents=True)

        # Create envsetup.sh marker
        (self.temp_dir / 'build' / 'envsetup.sh').write_text('#!/bin/bash')

        # Create Android.bp
        android_bp = self.temp_dir / 'frameworks' / 'base' / 'Android.bp'
        android_bp.write_text('''
cc_library {
    name: "libframeworks",
    srcs: [
        "core.cpp",
    ],
    shared_libs: [],
}
''')

        # Create source file
        source_file = self.temp_dir / 'frameworks' / 'base' / 'core.cpp'
        source_file.write_text('#include <vector>\nint main() {}')

        return source_file, android_bp

    def test_environment_detection_aosp(self):
        """Test that AOSP environment is properly detected."""
        self._create_project_structure()

        orchestrator = Orchestrator(self.temp_dir)

        assert orchestrator.environment.platform == Platform.AOSP
        assert orchestrator.environment.build_system == BuildSystem.SOONG

    def test_soong_adapter_find_build_file(self):
        """Test that Soong adapter finds the correct Android.bp."""
        source_file, android_bp = self._create_project_structure()

        adapter = SoongAdapter(self.temp_dir)
        found = adapter.find_build_file(source_file)

        assert found is not None
        assert found == android_bp

    def test_soong_adapter_get_module_info(self):
        """Test that Soong adapter extracts module info."""
        source_file, _ = self._create_project_structure()

        adapter = SoongAdapter(self.temp_dir)
        info = adapter.get_module_info(source_file)

        assert info is not None
        assert info.name == 'libframeworks'
        assert info.module_type == 'cc_library'

    def test_soong_adapter_inject_dependency(self):
        """Test dependency injection into Android.bp."""
        source_file, android_bp = self._create_project_structure()

        adapter = SoongAdapter(self.temp_dir)
        success = adapter.inject_dependency(
            target_module='libframeworks',
            dep_name='libcxx',
            dep_type='shared_library'
        )

        assert success is True

        content = android_bp.read_text()
        assert 'libcxx' in content


class TestEndToEndScenarios:
    """End-to-end test scenarios."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_header_skill_detection(self):
        """Test that MissingHeaderSkill detects header errors."""
        skill = MissingHeaderSkill()

        diag = DiagnosticObject(
            uid='test',
            build_system='gn',
            error_code='fatal error',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="fatal error: 'missing.h' file not found"
        )

        assert skill.detect(diag) is True

    def test_full_pipeline_mock(self):
        """Test the full orchestrator pipeline with mock data."""
        # Create minimal project structure
        (self.temp_dir / 'out').mkdir()
        (self.temp_dir / 'out' / 'ohos_config.json').write_text('{}')

        orchestrator = Orchestrator(self.temp_dir)

        # Create a diagnostic that won't have a matching skill
        diag = DiagnosticObject(
            uid='test',
            build_system='gn',
            error_code='UNKNOWN_ERROR',
            location={'file': 'test.cpp', 'line': 1},
            symbol='',
            raw_log="some unknown error"
        )

        results = orchestrator.run_pipeline([diag])

        assert results['total'] == 1
        assert results['skipped'] == 1  # No skill matches


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
