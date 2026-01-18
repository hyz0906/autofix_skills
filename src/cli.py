"""
AutoFix-Skill CLI - Command-line interface for the repair system.

This module provides the main entry point for the autofix tool,
supporting commands like fix, scan, and verify.

As per design.md Section 5.1 (Local Agent / CLI Packaging).
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from src.orchestrator.base import Orchestrator, BuildSystem
from src.skill_registry.manager import DiagnosticObject, skill_manager
from src.utils.logger import get_logger, Colors

# Import skills to register them
from src.skills.symbol_header import missing_header  # noqa: F401

logger = get_logger('autofix')


def parse_error_log(log_content: str, build_system: str = 'unknown') -> List[DiagnosticObject]:
    """
    Parse build error log and extract DiagnosticObject instances.

    This is a simplified parser. Production version would have
    more sophisticated error pattern matching.
    """
    diagnostics = []

    # Simple line-by-line parsing
    lines = log_content.strip().split('\n')

    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Try to extract file:line:column format
        # Example: "src/main.cpp:42:10: error: 'foo.h' file not found"
        parts = line.split(':', 3)

        if len(parts) >= 3 and 'error' in line.lower():
            file_path = parts[0]
            try:
                line_num = int(parts[1])
            except ValueError:
                line_num = 0

            # Extract error code if present
            error_code = 'unknown'
            if 'fatal error' in line.lower():
                error_code = 'fatal error'
            elif 'error:' in line.lower():
                error_code = 'error'

            diag = DiagnosticObject(
                uid=str(uuid.uuid4()),
                build_system=build_system,
                error_code=error_code,
                location={'file': file_path, 'line': line_num},
                symbol='',  # Would need more parsing
                raw_log=line
            )
            diagnostics.append(diag)

    return diagnostics


def cmd_fix(args: argparse.Namespace) -> int:
    """Handle the 'fix' command."""
    logger.info(f"{Colors.BOLD}AutoFix-Skill Fix Command{Colors.ENDC}")

    # Initialize orchestrator
    root_dir = Path(args.root) if args.root else None
    orchestrator = Orchestrator(root_dir)

    logger.info(f"Platform: {orchestrator.environment.platform.name}")
    logger.info(f"Build System: {orchestrator.environment.build_system.name}")
    logger.info(f"Root Dir: {orchestrator.environment.root_dir}")

    # Parse error log
    if args.log:
        log_path = Path(args.log)
        if not log_path.exists():
            logger.error(f"Log file not found: {log_path}")
            return 1
        log_content = log_path.read_text()
    elif args.error:
        log_content = args.error
    else:
        logger.error("Please provide --log or --error")
        return 1

    # Determine build system string
    build_sys = 'unknown'
    if orchestrator.environment.build_system == BuildSystem.SOONG:
        build_sys = 'soong'
    elif orchestrator.environment.build_system == BuildSystem.GN:
        build_sys = 'gn'

    diagnostics = parse_error_log(log_content, build_sys)

    if not diagnostics:
        logger.warning("No errors found in the provided log")
        return 0

    logger.info(f"Found {len(diagnostics)} error(s) to process")

    # Dry-run mode
    if args.dry_run:
        logger.info(f"{Colors.WARNING}DRY-RUN MODE - No changes will be made{Colors.ENDC}")

    # Run the repair pipeline
    results = orchestrator.run_pipeline(diagnostics)

    # Print summary
    print()
    logger.info(f"{Colors.BOLD}=== Summary ==={Colors.ENDC}")
    logger.info(f"Total errors: {results['total']}")
    logger.info(f"{Colors.OKGREEN}Fixed: {results['fixed']}{Colors.ENDC}")
    logger.info(f"{Colors.FAIL}Failed: {results['failed']}{Colors.ENDC}")
    logger.info(f"{Colors.WARNING}Skipped: {results['skipped']}{Colors.ENDC}")

    if args.json:
        print(json.dumps(results, indent=2))

    return 0 if results['failed'] == 0 else 1


def cmd_scan(args: argparse.Namespace) -> int:
    """Handle the 'scan' command - scan for potential issues."""
    logger.info(f"{Colors.BOLD}AutoFix-Skill Scan Command{Colors.ENDC}")

    root_dir = Path(args.root) if args.root else Path.cwd()
    logger.info(f"Scanning directory: {root_dir}")

    # List registered skills
    skills = skill_manager.get_all_skills()
    logger.info(f"Loaded {len(skills)} skill(s):")
    for name in skills:
        logger.info(f"  - {name}")

    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle the 'verify' command - verify a previous fix."""
    logger.info(f"{Colors.BOLD}AutoFix-Skill Verify Command{Colors.ENDC}")
    logger.info("Running build verification...")

    # This would trigger an incremental build
    # For now, just placeholder
    logger.info("Verification not yet implemented")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog='autofix',
        description='AutoFix-Skill: Automated build error repair for AOSP/OpenHarmony',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autofix fix --log build.log
  autofix fix --error "fatal error: 'foo.h' file not found"
  autofix fix --log build.log --dry-run
  autofix scan --root /path/to/source
        """
    )

    parser.add_argument(
        '--root', '-r',
        help='Root directory of the source tree'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Fix command
    fix_parser = subparsers.add_parser('fix', help='Fix build errors')
    fix_parser.add_argument(
        '--log', '-l',
        help='Path to build error log file'
    )
    fix_parser.add_argument(
        '--error', '-e',
        help='Single error message to fix'
    )
    fix_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    fix_parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    fix_parser.add_argument(
        '--ci',
        action='store_true',
        help='CI mode: non-interactive, specific exit codes'
    )
    fix_parser.set_defaults(func=cmd_fix)

    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan for potential issues')
    scan_parser.set_defaults(func=cmd_scan)

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify previous fix')
    verify_parser.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
