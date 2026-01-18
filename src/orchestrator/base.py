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
                analysis_result = skill.analyze(diag, context=None)  # TODO: inject context engine
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

                # TODO: Apply the plan via BuildAdapter

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
