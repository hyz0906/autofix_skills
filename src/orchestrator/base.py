"""
Orchestrator - the central control system for AutoFix-Skill.

This module implements the main task orchestration, including environment
detection, skill loading, and the repair pipeline (Detect -> Analyze -> Execute -> Verify).
"""

import hashlib
import os
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skill_registry.manager import (
    BaseSkill,
    DiagnosticObject,
    ExecutionPlan,
    SkillResult,
    skill_manager,
)
from src.utils.logger import get_logger

# Build Adapters
from src.build_adapters.soong import SoongAdapter
from src.build_adapters.gn import GNAdapter
from src.build_adapters.kbuild import KbuildAdapter
from src.build_adapters.cmake import CMakeAdapter
from src.build_adapters.makefile import MakefileAdapter
from src.build_adapters.interface import IBuildAdapter

# Context Engine
from src.context_engine.ast_grep_client import AstGrepClient

logger = get_logger(__name__)


class Platform(Enum):
    """Detected platform/build environment."""
    AOSP = auto()
    OPENHARMONY = auto()
    UNKNOWN = auto()


class BuildSystem(Enum):
    """Detected primary build system."""
    SOONG = auto()  # Android.bp based
    GN = auto()      # BUILD.gn based
    KBUILD = auto()  # Kernel Makefile based
    CMAKE = auto()
    UNKNOWN = auto()


@dataclass
class Environment:
    """Represents the detected build environment."""
    platform: Platform
    build_system: BuildSystem
    root_dir: Path
    out_dir: Optional[Path] = None


class Orchestrator:
    """
    The central controller for the AutoFix-Skill system.

    Responsibilities:
    - Environment detection (AOSP vs OpenHarmony)
    - Skill loading and pipeline management
    - Driving the Detect -> Analyze -> Execute -> Verify lifecycle
    - File modification transaction management (FMT)
    """

    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize the Orchestrator.

        Args:
            root_dir: The root directory of the source tree.
                      If not provided, attempts to detect via git.
        """
        self.logger = get_logger(__name__)
        self.root_dir = root_dir or self._detect_root_dir()
        self.environment = self._detect_environment()
        self._file_checksums: Dict[Path, str] = {}

        # Initialize context engine for semantic code search
        self.context_engine = AstGrepClient(self.root_dir)

        # Initialize build adapter based on detected environment
        self.adapter = self._get_adapter(self.environment.build_system)

    def _get_adapter(self, build_system: 'BuildSystem') -> Optional[IBuildAdapter]:
        """
        Factory method to get the appropriate build adapter.

        Args:
            build_system: The detected build system type.

        Returns:
            An instance of the appropriate adapter, or None if unsupported.
        """
        adapter_map = {
            BuildSystem.SOONG: SoongAdapter,
            BuildSystem.GN: GNAdapter,
            BuildSystem.KBUILD: KbuildAdapter,
            BuildSystem.CMAKE: CMakeAdapter,
        }

        adapter_class = adapter_map.get(build_system)
        if adapter_class:
            self.logger.info(f"Using adapter: {adapter_class.__name__}")
            return adapter_class(self.root_dir)

        # Fallback to generic Makefile adapter
        if (self.root_dir / 'Makefile').exists():
            self.logger.info("Using MakefileAdapter as fallback")
            return MakefileAdapter(self.root_dir)

        self.logger.warning(f"No adapter available for build system: {build_system}")
        return None

    def _detect_root_dir(self) -> Path:
        """Detect the root directory of the source tree using git."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            self.logger.warning("Could not detect git root. Using current directory.")
            return Path.cwd()

    def _detect_environment(self) -> Environment:
        """
        Detect the build platform and system based on marker files.

        As per design.md Section 1.2 and requirement.md Section 2.1.
        """
        platform = Platform.UNKNOWN
        build_system = BuildSystem.UNKNOWN
        out_dir = None

        # Check for AOSP markers
        aosp_marker = self.root_dir / 'build' / 'envsetup.sh'
        if aosp_marker.exists():
            platform = Platform.AOSP
            build_system = BuildSystem.SOONG
            out_dir = self.root_dir / 'out'
            self.logger.info("Detected AOSP environment (Soong build system)")

        # Check for OpenHarmony markers
        ohos_config = self.root_dir / 'out' / 'ohos_config.json'
        if ohos_config.exists():
            platform = Platform.OPENHARMONY
            build_system = BuildSystem.GN
            out_dir = self.root_dir / 'out'
            self.logger.info("Detected OpenHarmony environment (GN build system)")

        # Check for standalone GN marker (BUILD.gn in root)
        if platform == Platform.UNKNOWN and (self.root_dir / 'BUILD.gn').exists():
            build_system = BuildSystem.GN
            self.logger.info("Detected GN build system (unknown platform)")

        return Environment(
            platform=platform,
            build_system=build_system,
            root_dir=self.root_dir,
            out_dir=out_dir
        )

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute SHA256 checksum of a file for FMT tracking."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def track_file(self, file_path: Path) -> None:
        """
        Start tracking a file for modification conflicts (FMT).

        As per design.md Section 4.2.
        """
        if file_path.exists():
            self._file_checksums[file_path] = self._compute_checksum(file_path)
            self.logger.debug(f"Tracking file: {file_path}")

    def check_file_conflict(self, file_path: Path) -> bool:
        """
        Check if a tracked file has been modified externally.

        Returns:
            True if the file was modified, False otherwise.
        """
        if file_path not in self._file_checksums:
            return False

        current_checksum = self._compute_checksum(file_path)
        if current_checksum != self._file_checksums[file_path]:
            self.logger.warning(f"File conflict detected: {file_path}")
            return True
        return False

    def run_pipeline(self, diagnostics: List[DiagnosticObject]) -> Dict[str, Any]:
        """
        Run the repair pipeline for a list of diagnostics.

        Args:
            diagnostics: A list of DiagnosticObject instances.

        Returns:
            A summary dict with results for each diagnostic.
        """
        results = {
            'total': len(diagnostics),
            'fixed': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        for diag in diagnostics:
            self.logger.info(f"Processing error: {diag.error_code} in {diag.location.get('file')}")

            # Find applicable skills
            applicable_skills = skill_manager.get_skills_for_error(diag.error_code)

            if not applicable_skills:
                self.logger.warning(f"No skill found for error code: {diag.error_code}")
                results['skipped'] += 1
                results['details'].append({
                    'uid': diag.uid,
                    'status': 'skipped',
                    'reason': 'No applicable skill'
                })
                continue

            # Try each applicable skill
            fixed = False
            for skill_class in applicable_skills:
                skill = skill_class(name=skill_class.__name__)

                # Step 1: Detect
                if not skill.detect(diag):
                    continue

                self.logger.info(f"Skill {skill.name} matched for {diag.uid}")

                # Step 2: Analyze
                analysis_result = skill.analyze(diag, context=self.context_engine)
                if analysis_result is None:
                    self.logger.warning(f"Skill {skill.name} analysis failed")
                    continue

                # Step 3: Pre-check
                if not skill.pre_check(diag, analysis_result):
                    self.logger.warning(f"Skill {skill.name} pre-check failed")
                    continue

                # Step 4: Execute
                plan = skill.execute(diag, analysis_result)
                self.logger.info(f"Generated execution plan with {len(plan.steps)} steps")

                # Step 4b: Apply the plan via BuildAdapter
                plan_applied = self._apply_plan(plan, diag)
                if not plan_applied:
                    self.logger.warning(f"Failed to apply plan for {diag.uid}")
                    continue

                # Step 5: Verify
                verify_result = skill.verify(diag)
                if verify_result == SkillResult.SUCCESS:
                    fixed = True
                    results['fixed'] += 1
                    results['details'].append({
                        'uid': diag.uid,
                        'status': 'fixed',
                        'skill': skill.name
                    })
                    break

            if not fixed:
                results['failed'] += 1
                results['details'].append({
                    'uid': diag.uid,
                    'status': 'failed'
                })

        return results

    def _apply_plan(self, plan: ExecutionPlan, diag: DiagnosticObject) -> bool:
        """
        Apply an execution plan by invoking the appropriate adapter methods.

        Args:
            plan: The execution plan generated by a skill.
            diag: The diagnostic object for context.

        Returns:
            True if all steps were applied successfully, False otherwise.
        """
        if not self.adapter:
            self.logger.warning("No adapter available to apply plan")
            return False

        success = True
        for step in plan.steps:
            action = step.get('action', '')
            params = step.get('params', {})

            self.logger.info(f"Applying action: {action}")

            try:
                if action == 'ADD_DEPENDENCY':
                    target = params.get('target') or params.get('module', '')
                    dep = params.get('dependency') or params.get('dep_name', '')
                    dep_type = params.get('dep_type', 'shared_library')
                    if target and dep:
                        result = self.adapter.inject_dependency(target, dep, dep_type)
                        if not result:
                            self.logger.warning(f"Failed to add dependency: {dep} to {target}")
                            success = False

                elif action == 'ADD_INCLUDE_PATH':
                    target = params.get('target', '')
                    path = params.get('path', '')
                    if target and path:
                        result = self.adapter.modify_include_path(target, path, 'add')
                        if not result:
                            success = False

                elif action == 'REMOVE_FLAG':
                    target = params.get('target', '')
                    flags = params.get('flags', [])
                    if target and flags:
                        result = self.adapter.update_cflags(target, flags, 'remove')
                        if not result:
                            success = False

                elif action == 'INSERT_IMPORT':
                    # Source file modification - handled directly
                    source_file = Path(params.get('source_file', ''))
                    import_stmt = params.get('import_statement', '')
                    if source_file.exists() and import_stmt:
                        self._insert_import(source_file, import_stmt)

                elif action == 'INSERT_INCLUDE':
                    source_file = Path(params.get('source_file', ''))
                    include_stmt = params.get('include_statement', '')
                    if source_file.exists() and include_stmt:
                        self._insert_include(source_file, include_stmt)

                elif action == 'GENERATE_STUB':
                    # This is informational - stubs are suggested, not auto-applied
                    stub = params.get('stub', '')
                    self.logger.info(f"Suggested stub: {stub}")

                elif action == 'RUN_COMMAND':
                    cmd = params.get('command', '')
                    if cmd:
                        subprocess.run(cmd, shell=True, cwd=self.root_dir, check=True)

                elif action == 'ANALYZE':
                    # Informational action, just log
                    suggestion = params.get('suggestion', '')
                    self.logger.info(f"Analysis suggestion: {suggestion}")

                else:
                    self.logger.warning(f"Unknown action: {action}")

            except Exception as e:
                self.logger.error(f"Error applying action {action}: {e}")
                success = False

        return success

    def _insert_import(self, source_file: Path, import_stmt: str) -> None:
        """Insert an import statement into a Java/Kotlin source file."""
        content = source_file.read_text()

        # Find the package declaration and insert after it
        lines = content.split('\n')
        insert_idx = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('package '):
                insert_idx = i + 1
                break

        # Check if import already exists
        if import_stmt in content:
            self.logger.info(f"Import already exists: {import_stmt}")
            return

        lines.insert(insert_idx, import_stmt)
        source_file.write_text('\n'.join(lines))
        self.logger.info(f"Inserted import: {import_stmt}")

    def _insert_include(self, source_file: Path, include_stmt: str) -> None:
        """Insert an #include statement into a C/C++ source file."""
        content = source_file.read_text()

        # Check if include already exists
        if include_stmt in content:
            self.logger.info(f"Include already exists: {include_stmt}")
            return

        # Find existing includes and insert after them
        lines = content.split('\n')
        last_include_idx = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('#include'):
                last_include_idx = i + 1

        if last_include_idx == 0:
            # No existing includes, insert at beginning
            last_include_idx = 0

        lines.insert(last_include_idx, include_stmt)
        source_file.write_text('\n'.join(lines))
        self.logger.info(f"Inserted include: {include_stmt}")

    def stash_changes(self) -> bool:
        """
        Stash current changes before applying fixes. (Git-based rollback)

        As per design.md Section 6.1.
        """
        try:
            subprocess.run(['git', 'add', '.'], cwd=self.root_dir, check=True)
            subprocess.run(['git', 'stash'], cwd=self.root_dir, check=True)
            self.logger.info("Changes stashed successfully")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to stash changes: {e}")
            return False

    def restore_file(self, file_path: Path) -> bool:
        """
        Restore a file to its original state. (Rollback)

        As per design.md Section 6.1.
        """
        try:
            subprocess.run(
                ['git', 'checkout', '--', str(file_path)],
                cwd=self.root_dir,
                check=True
            )
            self.logger.info(f"Restored file: {file_path}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to restore file {file_path}: {e}")
            return False
