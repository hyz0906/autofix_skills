"""
Build File Parser Utilities.

This module provides robust parsing utilities for Blueprint (Android.bp)
and GN (BUILD.gn) files. It handles nested structures, comments, and
string literals properly.

This replaces the fragile regex-based parsing with structural parsing.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


class TokenType(Enum):
    """Token types for the lexer."""
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    COMMA = auto()
    EQUALS = auto()
    PLUS = auto()
    PLUS_EQUALS = auto()
    COMMENT = auto()
    NEWLINE = auto()
    WHITESPACE = auto()
    EOF = auto()


@dataclass
class Token:
    """Represents a lexical token."""
    type: TokenType
    value: str
    line: int
    column: int


@dataclass
class ParsedModule:
    """Represents a parsed module/target from a build file."""
    module_type: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    start_offset: int = 0
    end_offset: int = 0
    raw_text: str = ""


class BuildFileLexer:
    """
    Lexer for Blueprint and GN syntax.

    Handles:
    - String literals (including multi-line)
    - Comments (// and /* */)
    - Nested braces/brackets
    - Identifiers and keywords
    """

    def __init__(self, content: str):
        self.content = content
        self.pos = 0
        self.line = 1
        self.column = 1

    def peek(self, offset: int = 0) -> str:
        """Peek at the character at current position + offset."""
        pos = self.pos + offset
        if pos < len(self.content):
            return self.content[pos]
        return ''

    def advance(self) -> str:
        """Advance position and return current character."""
        if self.pos >= len(self.content):
            return ''
        char = self.content[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def skip_whitespace(self) -> None:
        """Skip whitespace characters (but not newlines for some parsers)."""
        while self.peek() in ' \t\r':
            self.advance()

    def read_string(self) -> str:
        """Read a quoted string, handling escapes."""
        quote = self.advance()  # consume opening quote
        result = []
        while self.peek() and self.peek() != quote:
            if self.peek() == '\\':
                self.advance()  # consume backslash
                escaped = self.advance()
                result.append(escaped)
            else:
                result.append(self.advance())
        if self.peek() == quote:
            self.advance()  # consume closing quote
        return ''.join(result)

    def read_identifier(self) -> str:
        """Read an identifier (alphanumeric + underscore)."""
        result = []
        while self.peek() and (self.peek().isalnum() or self.peek() in '_'):
            result.append(self.advance())
        return ''.join(result)

    def read_number(self) -> str:
        """Read a numeric literal."""
        result = []
        while self.peek() and (self.peek().isdigit() or self.peek() in '.-'):
            result.append(self.advance())
        return ''.join(result)

    def skip_line_comment(self) -> str:
        """Skip a // comment and return its content."""
        result = []
        self.advance()  # consume first /
        self.advance()  # consume second /
        while self.peek() and self.peek() != '\n':
            result.append(self.advance())
        return ''.join(result)

    def skip_block_comment(self) -> str:
        """Skip a /* */ comment and return its content."""
        result = []
        self.advance()  # consume /
        self.advance()  # consume *
        while self.pos < len(self.content) - 1:
            if self.peek() == '*' and self.peek(1) == '/':
                self.advance()  # consume *
                self.advance()  # consume /
                break
            result.append(self.advance())
        return ''.join(result)

    def tokenize(self) -> Iterator[Token]:
        """Generate tokens from the content."""
        while self.pos < len(self.content):
            line, col = self.line, self.column
            char = self.peek()

            if char in ' \t\r':
                self.skip_whitespace()
                continue

            if char == '\n':
                self.advance()
                yield Token(TokenType.NEWLINE, '\n', line, col)
                continue

            if char == '/' and self.peek(1) == '/':
                comment = self.skip_line_comment()
                yield Token(TokenType.COMMENT, comment, line, col)
                continue

            if char == '/' and self.peek(1) == '*':
                comment = self.skip_block_comment()
                yield Token(TokenType.COMMENT, comment, line, col)
                continue

            if char in '"\'':
                value = self.read_string()
                yield Token(TokenType.STRING, value, line, col)
                continue

            if char.isalpha() or char == '_':
                value = self.read_identifier()
                yield Token(TokenType.IDENTIFIER, value, line, col)
                continue

            if char.isdigit() or (char == '-' and self.peek(1).isdigit()):
                value = self.read_number()
                yield Token(TokenType.NUMBER, value, line, col)
                continue

            if char == '{':
                self.advance()
                yield Token(TokenType.LBRACE, '{', line, col)
            elif char == '}':
                self.advance()
                yield Token(TokenType.RBRACE, '}', line, col)
            elif char == '[':
                self.advance()
                yield Token(TokenType.LBRACKET, '[', line, col)
            elif char == ']':
                self.advance()
                yield Token(TokenType.RBRACKET, ']', line, col)
            elif char == '(':
                self.advance()
                yield Token(TokenType.LPAREN, '(', line, col)
            elif char == ')':
                self.advance()
                yield Token(TokenType.RPAREN, ')', line, col)
            elif char == ':':
                self.advance()
                yield Token(TokenType.COLON, ':', line, col)
            elif char == ',':
                self.advance()
                yield Token(TokenType.COMMA, ',', line, col)
            elif char == '=' and self.peek(1) != '=':
                self.advance()
                yield Token(TokenType.EQUALS, '=', line, col)
            elif char == '+' and self.peek(1) == '=':
                self.advance()
                self.advance()
                yield Token(TokenType.PLUS_EQUALS, '+=', line, col)
            elif char == '+':
                self.advance()
                yield Token(TokenType.PLUS, '+', line, col)
            else:
                # Skip unknown characters
                self.advance()

        yield Token(TokenType.EOF, '', self.line, self.column)


class BlueprintParser:
    """
    Parser for Android.bp (Blueprint) files.

    Blueprint syntax:
    - module_type { property: value, ... }
    - Properties can be: strings, lists, maps, booleans
    """

    def __init__(self, content: str):
        self.content = content
        self.lexer = BuildFileLexer(content)
        self.tokens: List[Token] = []
        self.pos = 0

    def parse(self) -> List[ParsedModule]:
        """Parse the content and return a list of modules."""
        # First, tokenize everything
        self.tokens = [t for t in self.lexer.tokenize()
                       if t.type not in (TokenType.COMMENT, TokenType.NEWLINE, TokenType.WHITESPACE)]
        self.pos = 0

        modules = []
        while not self._at_end():
            module = self._parse_module()
            if module:
                modules.append(module)
        return modules

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens) or self.tokens[self.pos].type == TokenType.EOF

    def _current(self) -> Token:
        if self._at_end():
            return Token(TokenType.EOF, '', 0, 0)
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self._current()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        if self._current().type != token_type:
            raise ValueError(f"Expected {token_type}, got {self._current().type}")
        return self._advance()

    def _parse_module(self) -> Optional[ParsedModule]:
        """Parse a module definition: module_type { ... }"""
        if self._current().type != TokenType.IDENTIFIER:
            self._advance()  # Skip unexpected token
            return None

        start_offset = self._find_offset_for_token(self._current())
        module_type = self._advance().value

        if self._current().type != TokenType.LBRACE:
            return None

        self._advance()  # consume {

        properties = self._parse_properties()

        end_offset = self._find_offset_for_token(self._current())
        self._expect(TokenType.RBRACE)

        # Get the module name from properties
        name = properties.get('name', '')

        return ParsedModule(
            module_type=module_type,
            name=name,
            properties=properties,
            start_offset=start_offset,
            end_offset=end_offset + 1,
            raw_text=self.content[start_offset:end_offset + 1]
        )

    def _parse_properties(self) -> Dict[str, Any]:
        """Parse property list inside { }."""
        properties = {}
        while not self._at_end() and self._current().type != TokenType.RBRACE:
            if self._current().type == TokenType.IDENTIFIER:
                name = self._advance().value
                if self._current().type == TokenType.COLON:
                    self._advance()  # consume :
                    value = self._parse_value()
                    properties[name] = value
                    # Handle optional comma
                    if self._current().type == TokenType.COMMA:
                        self._advance()
            else:
                self._advance()  # skip unexpected token
        return properties

    def _parse_value(self) -> Any:
        """Parse a property value (string, list, map, bool, number)."""
        token = self._current()

        if token.type == TokenType.STRING:
            self._advance()
            return token.value

        if token.type == TokenType.NUMBER:
            self._advance()
            return int(token.value) if '.' not in token.value else float(token.value)

        if token.type == TokenType.IDENTIFIER:
            self._advance()
            if token.value in ('true', 'false'):
                return token.value == 'true'
            return token.value

        if token.type == TokenType.LBRACKET:
            return self._parse_list()

        if token.type == TokenType.LBRACE:
            return self._parse_map()

        # Unknown value type
        self._advance()
        return None

    def _parse_list(self) -> List[Any]:
        """Parse a list: [ value, value, ... ]."""
        self._expect(TokenType.LBRACKET)
        items = []
        while not self._at_end() and self._current().type != TokenType.RBRACKET:
            value = self._parse_value()
            if value is not None:
                items.append(value)
            if self._current().type == TokenType.COMMA:
                self._advance()
            elif self._current().type == TokenType.PLUS:
                # Handle list concatenation: [ ] + [ ]
                self._advance()
        if self._current().type == TokenType.RBRACKET:
            self._advance()
        return items

    def _parse_map(self) -> Dict[str, Any]:
        """Parse a map/struct: { key: value, ... }."""
        self._expect(TokenType.LBRACE)
        return self._parse_properties()

    def _find_offset_for_token(self, token: Token) -> int:
        """Find the byte offset in content for a given token's line/column."""
        offset = 0
        line = 1
        for i, char in enumerate(self.content):
            if line == token.line:
                col = i - offset + 1
                if col >= token.column:
                    # Search for the actual token value starting here
                    remaining = self.content[i:]
                    if remaining.startswith(token.value) or token.type in (TokenType.LBRACE, TokenType.RBRACE):
                        return i
            if char == '\n':
                line += 1
                offset = i + 1
        return 0


class GNParser:
    """
    Parser for BUILD.gn files.

    GN syntax:
    - target_type("name") { property = value ... }
    - Properties use = instead of :
    """

    def __init__(self, content: str):
        self.content = content
        self.lexer = BuildFileLexer(content)
        self.tokens: List[Token] = []
        self.pos = 0

    def parse(self) -> List[ParsedModule]:
        """Parse the content and return a list of targets."""
        self.tokens = [t for t in self.lexer.tokenize()
                       if t.type not in (TokenType.COMMENT, TokenType.NEWLINE, TokenType.WHITESPACE)]
        self.pos = 0

        targets = []
        while not self._at_end():
            target = self._parse_target()
            if target:
                targets.append(target)
        return targets

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens) or self.tokens[self.pos].type == TokenType.EOF

    def _current(self) -> Token:
        if self._at_end():
            return Token(TokenType.EOF, '', 0, 0)
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self._current()
        self.pos += 1
        return token

    def _parse_target(self) -> Optional[ParsedModule]:
        """Parse a target: target_type("name") { ... }"""
        if self._current().type != TokenType.IDENTIFIER:
            self._advance()
            return None

        target_type = self._advance().value

        if self._current().type != TokenType.LPAREN:
            return None

        self._advance()  # consume (

        if self._current().type != TokenType.STRING:
            return None

        name = self._advance().value

        if self._current().type == TokenType.RPAREN:
            self._advance()  # consume )

        if self._current().type != TokenType.LBRACE:
            return None

        self._advance()  # consume {

        properties = self._parse_properties()

        if self._current().type == TokenType.RBRACE:
            self._advance()

        return ParsedModule(
            module_type=target_type,
            name=name,
            properties=properties
        )

    def _parse_properties(self) -> Dict[str, Any]:
        """Parse GN property assignments."""
        properties = {}
        while not self._at_end() and self._current().type != TokenType.RBRACE:
            if self._current().type == TokenType.IDENTIFIER:
                name = self._advance().value
                if self._current().type in (TokenType.EQUALS, TokenType.PLUS_EQUALS):
                    self._advance()
                    value = self._parse_value()
                    if name in properties and isinstance(properties[name], list):
                        properties[name].extend(value if isinstance(value, list) else [value])
                    else:
                        properties[name] = value
            else:
                self._advance()
        return properties

    def _parse_value(self) -> Any:
        """Parse a GN value."""
        token = self._current()

        if token.type == TokenType.STRING:
            self._advance()
            return token.value

        if token.type == TokenType.NUMBER:
            self._advance()
            return int(token.value)

        if token.type == TokenType.IDENTIFIER:
            self._advance()
            if token.value in ('true', 'false'):
                return token.value == 'true'
            return token.value

        if token.type == TokenType.LBRACKET:
            return self._parse_list()

        if token.type == TokenType.LBRACE:
            return self._parse_scope()

        self._advance()
        return None

    def _parse_list(self) -> List[Any]:
        """Parse a GN list: [ ... ]."""
        self._advance()  # consume [
        items = []
        while not self._at_end() and self._current().type != TokenType.RBRACKET:
            value = self._parse_value()
            if value is not None:
                items.append(value)
            if self._current().type == TokenType.COMMA:
                self._advance()
        if self._current().type == TokenType.RBRACKET:
            self._advance()
        return items

    def _parse_scope(self) -> Dict[str, Any]:
        """Parse a GN scope: { ... }."""
        self._advance()  # consume {
        props = self._parse_properties()
        if self._current().type == TokenType.RBRACE:
            self._advance()
        return props


def parse_android_bp(content: str) -> List[ParsedModule]:
    """Parse Android.bp content and return list of modules."""
    parser = BlueprintParser(content)
    return parser.parse()


def parse_build_gn(content: str) -> List[ParsedModule]:
    """Parse BUILD.gn content and return list of targets."""
    parser = GNParser(content)
    return parser.parse()
