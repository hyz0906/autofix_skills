"""
Context Engine - ast-grep client for semantic code search.

This module wraps the `ast-grep` (sg) command-line tool to provide
high-efficiency structural code pattern matching and symbol search
across the source tree.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchMatch:
    """Represents a single match from an ast-grep search."""
    file: str
    line: int
    column: int
    text: str
    rule_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class AstGrepClient:
    """
    Client for interacting with ast-grep (sg) for semantic code search.

    As per design.md Section 2.2, this engine:
    - Supports incremental on-demand scanning
    - Dynamically generates search rules based on error symbols
    - Provides local index caching for common directories
    """

    def __init__(self, root_dir: Optional[Path] = None, sg_binary: str = 'sg'):
        """
        Initialize the AstGrepClient.

        Args:
            root_dir: The root directory of the source tree.
            sg_binary: Path to the sg binary (default: 'sg' from PATH).
        """
        self.root_dir = root_dir or Path.cwd()
        self.sg_binary = sg_binary
        self.logger = get_logger(__name__)
        self._verify_sg_available()

    def _verify_sg_available(self) -> bool:
        """Check if the sg binary is available."""
        try:
            result = subprocess.run(
                [self.sg_binary, '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.debug(f"ast-grep available: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            self.logger.warning(
                f"ast-grep (sg) not found at '{self.sg_binary}'. "
                "Symbol search functionality will be limited."
            )
        return False

    def search_pattern(
        self,
        pattern: str,
        language: str = 'cpp',
        directory: Optional[Path] = None,
        json_output: bool = True
    ) -> List[SearchMatch]:
        """
        Search for a code pattern using ast-grep.

        Args:
            pattern: The pattern to search for (ast-grep pattern syntax).
            language: The source language (e.g., 'cpp', 'c', 'python').
            directory: The directory to search in (defaults to root_dir).
            json_output: Whether to request JSON output.

        Returns:
            A list of SearchMatch objects.

        Example:
            client.search_pattern('void $FUNC(...)', 'cpp')
        """
        search_dir = directory or self.root_dir

        cmd = [
            self.sg_binary,
            'scan',
            '--pattern', pattern,
            '--lang', language,
        ]

        if json_output:
            cmd.append('--json')

        cmd.append(str(search_dir))

        self.logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.root_dir
            )

            if result.returncode != 0 and result.stderr:
                self.logger.warning(f"ast-grep error: {result.stderr}")
                return []

            if not result.stdout.strip():
                return []

            if json_output:
                return self._parse_json_output(result.stdout)
            else:
                return self._parse_text_output(result.stdout)

        except FileNotFoundError:
            self.logger.error("ast-grep (sg) binary not found")
            return []
        except Exception as e:
            self.logger.error(f"Error running ast-grep: {e}")
            return []

    def _parse_json_output(self, output: str) -> List[SearchMatch]:
        """Parse JSON output from ast-grep."""
        matches = []
        try:
            data = json.loads(output)
            for item in data:
                match = SearchMatch(
                    file=item.get('file', ''),
                    line=item.get('range', {}).get('start', {}).get('line', 0),
                    column=item.get('range', {}).get('start', {}).get('column', 0),
                    text=item.get('text', ''),
                    rule_id=item.get('ruleId'),
                    meta=item.get('meta')
                )
                matches.append(match)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse ast-grep JSON output: {e}")
        return matches

    def _parse_text_output(self, output: str) -> List[SearchMatch]:
        """Parse text output from ast-grep (fallback)."""
        matches = []
        for line in output.strip().split('\n'):
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    matches.append(SearchMatch(
                        file=parts[0],
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        column=0,
                        text=parts[2] if len(parts) > 2 else ''
                    ))
        return matches

    def search_function_definition(
        self,
        function_name: str,
        language: str = 'cpp',
        directory: Optional[Path] = None
    ) -> List[SearchMatch]:
        """
        Search for a function definition by name.

        As per design.md Section 2.2:
        'When identifying error: X was not declared, Engine dynamically generates
        an ast-grep search rule matching all function_definition with name X.'

        Args:
            function_name: The name of the function to search for.
            language: The source language.
            directory: The directory to search.

        Returns:
            A list of matches where the function is defined.
        """
        # Pattern for function definitions
        # This is a simplified pattern; real patterns may be more complex
        pattern = f"$RET {function_name}($$$PARAMS) {{ $$$BODY }}"
        return self.search_pattern(pattern, language, directory)

    def search_header_file(
        self,
        header_name: str,
        directory: Optional[Path] = None
    ) -> List[Path]:
        """
        Search for header files by name.

        Args:
            header_name: The header file name (e.g., 'my_header.h').
            directory: The directory to search.

        Returns:
            A list of Paths to matching header files.
        """
        search_dir = directory or self.root_dir
        results = []

        try:
            # Use find command for simple file search
            cmd = ['find', str(search_dir), '-name', header_name, '-type', 'f']
            result = subprocess.run(cmd, capture_output=True, text=True)

            for line in result.stdout.strip().split('\n'):
                if line:
                    results.append(Path(line))

        except Exception as e:
            self.logger.error(f"Error searching for header: {e}")

        return results

    def search_include_statement(
        self,
        include_pattern: str,
        directory: Optional[Path] = None
    ) -> List[SearchMatch]:
        """
        Search for #include statements matching a pattern.

        Args:
            include_pattern: The include pattern to search for.
            directory: The directory to search.

        Returns:
            A list of SearchMatch objects.
        """
        # ast-grep pattern for include statements
        pattern = f'#include "{include_pattern}"'
        return self.search_pattern(pattern, 'cpp', directory)
