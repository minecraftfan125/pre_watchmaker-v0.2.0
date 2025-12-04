"""Lua Syntax Checker using luaparser

Provides AST-based syntax validation for Lua scripts with
WatchMaker-specific API validation.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import re


class ErrorSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LuaSyntaxError:
    """Represents a syntax or semantic error"""
    line: int              # 0-indexed line number
    column: int            # 0-indexed column
    message: str
    severity: ErrorSeverity
    error_code: str        # e.g., "E001", "W001"
    start_pos: Optional[int] = None  # character position for highlighting
    length: Optional[int] = None     # length of error span


# Error message templates
ERROR_MESSAGES = {
    # Syntax errors
    "E000": "Internal parser error: {details}",
    "E001": "Syntax error: {details}",
    "E002": "Unexpected token: {token}",
    "E003": "Unclosed block: '{keyword}' started at line {start_line}",
    "E004": "Unmatched bracket: '{bracket}'",

    # WatchMaker-specific warnings
    "W001": "Unknown WatchMaker function: '{func_name}'",
    "W002": "Unknown callback function: '{func_name}'. Valid callbacks: {valid_list}",
    "W003": "Invalid action name: '{action}'",
    "W004": "Invalid easing function: '{easing}'",
    "W010": "wm_schedule requires a table argument",
}


class LuaSyntaxChecker:
    """Main syntax checker class using luaparser"""

    # Valid WatchMaker callback functions
    VALID_CALLBACKS = [
        'on_hour', 'on_minute', 'on_second', 'on_millisecond',
        'on_display_bright', 'on_display_not_bright'
    ]

    # WatchMaker tag pattern: {tag_name}
    TAG_PATTERN = re.compile(r'\{([a-zA-Z0-9_]+)\}')

    def __init__(self, watchmaker_api: Dict[str, Any] = None,
                 watchmaker_actions: List[str] = None,
                 easing_functions: List[str] = None):
        self.watchmaker_api = watchmaker_api or {}
        self.watchmaker_actions = watchmaker_actions or []
        self.easing_functions = easing_functions or []
        self._parser_available = self._check_parser_available()
        self._last_ast = None
        self._fallback_warned = False

        # Cache for performance
        self._cache_code = None
        self._cache_errors = None

    def _check_parser_available(self) -> bool:
        """Check if luaparser is installed"""
        try:
            from luaparser import ast
            return True
        except ImportError:
            return False

    @property
    def parser_available(self) -> bool:
        """Public property to check parser availability"""
        return self._parser_available

    def _preprocess_tags(self, code: str) -> str:
        """
        Preprocess WatchMaker tags by replacing {tag} with string literals.
        This allows the Lua parser to handle the code without syntax errors.
        Example: {dd} becomes "__wm_tag_dd__"
        """
        def replace_tag(match):
            tag_name = match.group(1)
            # Replace with a valid Lua string literal that won't cause syntax errors
            return f'"__wm_tag_{tag_name}__"'

        return self.TAG_PATTERN.sub(replace_tag, code)

    def _restore_tags_in_message(self, message: str) -> str:
        """
        Restore WatchMaker tag placeholders in error messages back to original format.
        Example: "__wm_tag_dd__" becomes {dd}
        """
        # Pattern to match "__wm_tag_xxx__" (with or without quotes)
        placeholder_pattern = re.compile(r'["\']?__wm_tag_([a-zA-Z0-9_]+)__["\']?')

        def restore_tag(match):
            tag_name = match.group(1)
            return '{' + tag_name + '}'

        return placeholder_pattern.sub(restore_tag, message)

    def check(self, code: str) -> List[LuaSyntaxError]:
        """
        Perform full syntax check on Lua code.

        Returns list of LuaSyntaxError objects, empty if no errors.
        Falls back to basic checking if parser unavailable.
        """
        if not code or not code.strip():
            return []

        # Return cached result if code unchanged
        if code == self._cache_code and self._cache_errors is not None:
            return self._cache_errors.copy()

        # Preprocess WatchMaker tags to avoid syntax errors
        preprocessed_code = self._preprocess_tags(code)

        if not self._parser_available:
            errors = self._basic_fallback_check(preprocessed_code)
        else:
            errors = self._do_full_check(preprocessed_code)

        # Restore tag placeholders in error messages
        for error in errors:
            error.message = self._restore_tags_in_message(error.message)

        # Update cache
        self._cache_code = code
        self._cache_errors = errors

        return errors

    def _do_full_check(self, code: str) -> List[LuaSyntaxError]:
        """Perform full parser-based check"""
        errors = []

        try:
            # Phase 1: Parse syntax
            syntax_errors = self._parse_syntax(code)
            errors.extend(syntax_errors)

            # Phase 2: Semantic analysis (only if parsing succeeded)
            if not syntax_errors and self._last_ast:
                semantic_errors = self._analyze_semantics(code)
                errors.extend(semantic_errors)

        except Exception as e:
            # Unexpected error - fall back
            import traceback
            traceback.print_exc()
            errors.append(LuaSyntaxError(
                line=0, column=0,
                message=f"Parser failed: {str(e)}",
                severity=ErrorSeverity.WARNING,
                error_code="E000"
            ))
            errors.extend(self._basic_fallback_check(code))

        return errors

    def _parse_syntax(self, code: str) -> List[LuaSyntaxError]:
        """Parse Lua code and extract syntax errors"""
        import sys
        import io
        from luaparser import ast
        from luaparser.ast import SyntaxException

        errors = []

        # Capture luaparser's stdout/stderr output (contains detailed error info)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        try:
            tree = ast.parse(code)
            self._last_ast = tree  # Cache for semantic analysis

        except SyntaxException as e:
            # Get captured stderr which contains ANTLR error messages
            stderr_output = captured_stderr.getvalue()
            stdout_output = captured_stdout.getvalue()

            # Parse ANTLR error messages from stderr
            parsed_errors = self._parse_antlr_errors(stderr_output + stdout_output, code)

            if parsed_errors:
                errors.extend(parsed_errors)
            else:
                # Fallback to exception message parsing
                error = self._parse_syntax_exception(e, code)
                errors.append(error)

            self._last_ast = None

        except Exception as e:
            # Try to extract line info from exception message
            error = self._parse_generic_exception(e, code)
            errors.append(error)
            self._last_ast = None

        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        return errors

    def _parse_antlr_errors(self, output: str, code: str) -> List[LuaSyntaxError]:
        """Parse ANTLR error messages from luaparser output"""
        errors = []
        seen_errors = set()  # Avoid duplicate errors
        code_lines = code.split('\n')

        # ANTLR error format: "line X:Y message"
        # Example: "line 4:0 missing 'end' at '<EOF>'"
        pattern = re.compile(r'line\s+(\d+):(\d+)\s+(.+?)(?=line\s+\d+:|\Z)', re.DOTALL)

        for match in pattern.finditer(output):
            reported_line = int(match.group(1)) - 1  # Convert to 0-indexed
            column = int(match.group(2))
            raw_message = match.group(3).strip().replace('\n', ' ').strip()

            # Extract the problematic token from error message
            # Format: "no viable alternative at input 'token'" or with escaped newline
            error_token = None

            # Try to match token with possible escaped newline
            token_match = re.search(r"at input\s+'([^']*)'", raw_message)
            if token_match:
                token_content = token_match.group(1)
                # Handle escaped newline in token - take first part
                if '\\n' in token_content:
                    error_token = token_content.split('\\n')[0].strip()
                else:
                    error_token = token_content.strip()
            else:
                token_match = re.search(r"mismatched input\s+'([^']*)'", raw_message)
                if token_match:
                    error_token = token_match.group(1).strip()

            # Find actual line by searching for the error token in code
            actual_line = reported_line

            if error_token:
                # Search backwards from reported line to find the token
                for search_line in range(min(reported_line, len(code_lines) - 1), -1, -1):
                    if search_line < len(code_lines):
                        token_pos = code_lines[search_line].find(error_token)
                        if token_pos >= 0:
                            actual_line = search_line
                            column = token_pos
                            break

            # Clean up message for display
            clean_message = raw_message
            # Remove escaped newlines and content after them in quoted strings
            clean_message = re.sub(r"'([^']*?)\\n[^']*'", r"'\1'", clean_message)
            clean_message = clean_message.replace('\\n', ' ').strip()

            # Create unique key to avoid duplicates
            error_key = (actual_line, clean_message)
            if error_key in seen_errors:
                continue
            seen_errors.add(error_key)

            # Calculate character position for highlighting
            start_pos = sum(len(l) + 1 for l in code_lines[:max(0, actual_line)]) + column

            # Determine highlight length
            highlight_len = len(error_token) if error_token else 1

            errors.append(LuaSyntaxError(
                line=max(0, actual_line),
                column=max(0, column),
                message=clean_message,
                severity=ErrorSeverity.ERROR,
                error_code="E001",
                start_pos=start_pos,
                length=max(1, highlight_len)
            ))

        return errors

    def _parse_syntax_exception(self, exc: Exception, code: str) -> LuaSyntaxError:
        """Parse luaparser SyntaxException to extract line/column info (fallback)"""
        msg = str(exc)

        # Try to extract line:column from message
        line = 0
        column = 0

        match = re.search(r'line\s*(\d+)(?::(\d+))?', msg, re.IGNORECASE)
        if match:
            line = int(match.group(1)) - 1  # Convert to 0-indexed
            column = int(match.group(2)) if match.group(2) else 0

        # Calculate character position for highlighting
        lines = code.split('\n')
        start_pos = sum(len(l) + 1 for l in lines[:max(0, line)]) + column

        # Clean up error message
        clean_msg = msg
        if clean_msg == "syntax errors":
            clean_msg = "Syntax error in code"

        return LuaSyntaxError(
            line=max(0, line),
            column=max(0, column),
            message=clean_msg,
            severity=ErrorSeverity.ERROR,
            error_code="E001",
            start_pos=start_pos,
            length=10
        )

    def _parse_generic_exception(self, exc: Exception, code: str) -> LuaSyntaxError:
        """Parse generic exception"""
        msg = str(exc)

        # Try to find line number in message
        line = 0
        match = re.search(r'line\s*(\d+)', msg, re.IGNORECASE)
        if match:
            line = int(match.group(1)) - 1

        return LuaSyntaxError(
            line=max(0, line),
            column=0,
            message=msg,
            severity=ErrorSeverity.ERROR,
            error_code="E001"
        )

    def _analyze_semantics(self, code: str) -> List[LuaSyntaxError]:
        """Analyze AST for WatchMaker-specific issues"""
        from luaparser import ast as luaast
        from luaparser import astnodes

        errors = []

        if not self._last_ast:
            return errors

        for node in luaast.walk(self._last_ast):
            # Check function calls
            if isinstance(node, astnodes.Call):
                call_errors = self._check_function_call(node)
                errors.extend(call_errors)

            # Check function definitions (for callbacks)
            if isinstance(node, (astnodes.Function, astnodes.LocalFunction)):
                func_errors = self._check_function_definition(node)
                errors.extend(func_errors)

        return errors

    def _check_function_call(self, node) -> List[LuaSyntaxError]:
        """Check if function call is valid WatchMaker API"""
        from luaparser import astnodes

        errors = []
        func_name = self._get_call_name(node)

        if not func_name:
            return errors

        line = (node.line - 1) if hasattr(node, 'line') and node.line else 0

        # Check WatchMaker functions
        if func_name.startswith('wm_'):
            if func_name not in self.watchmaker_api:
                errors.append(LuaSyntaxError(
                    line=line, column=0,
                    message=ERROR_MESSAGES["W001"].format(func_name=func_name),
                    severity=ErrorSeverity.WARNING,
                    error_code="W001"
                ))

            # Special validation for wm_schedule
            if func_name == 'wm_schedule':
                errors.extend(self._validate_wm_schedule(node))

            # Special validation for wm_action
            if func_name == 'wm_action':
                errors.extend(self._validate_wm_action(node))

        return errors

    def _check_function_definition(self, node) -> List[LuaSyntaxError]:
        """Check callback function definitions"""
        from luaparser import astnodes

        errors = []

        # Get function name
        func_name = None
        if hasattr(node, 'name') and node.name:
            if hasattr(node.name, 'id'):
                func_name = node.name.id
            elif isinstance(node.name, str):
                func_name = node.name

        if not func_name:
            return errors

        line = (node.line - 1) if hasattr(node, 'line') and node.line else 0

        # Check callback functions
        if func_name.startswith('on_'):
            if func_name not in self.VALID_CALLBACKS:
                errors.append(LuaSyntaxError(
                    line=line, column=0,
                    message=ERROR_MESSAGES["W002"].format(
                        func_name=func_name,
                        valid_list=', '.join(self.VALID_CALLBACKS)
                    ),
                    severity=ErrorSeverity.WARNING,
                    error_code="W002"
                ))

        return errors

    def _validate_wm_schedule(self, node) -> List[LuaSyntaxError]:
        """Validate wm_schedule table argument"""
        from luaparser import astnodes

        errors = []
        line = (node.line - 1) if hasattr(node, 'line') and node.line else 0

        # Check argument exists and is table
        if not hasattr(node, 'args') or not node.args:
            return errors

        args = node.args
        if isinstance(args, list) and len(args) > 0:
            arg = args[0]
        else:
            return errors

        if not isinstance(arg, astnodes.Table):
            errors.append(LuaSyntaxError(
                line=line, column=0,
                message=ERROR_MESSAGES["W010"],
                severity=ErrorSeverity.WARNING,
                error_code="W010"
            ))
            return errors

        # Extract table fields and check easing
        if hasattr(arg, 'fields') and arg.fields:
            for field in arg.fields:
                if hasattr(field, 'key') and hasattr(field.key, 'id'):
                    key = field.key.id
                    if key == 'easing' and hasattr(field, 'value'):
                        value = field.value
                        if hasattr(value, 's'):  # String value
                            easing = value.s
                            if self.easing_functions and easing not in self.easing_functions:
                                errors.append(LuaSyntaxError(
                                    line=line, column=0,
                                    message=ERROR_MESSAGES["W004"].format(easing=easing),
                                    severity=ErrorSeverity.WARNING,
                                    error_code="W004"
                                ))

        return errors

    def _validate_wm_action(self, node) -> List[LuaSyntaxError]:
        """Validate wm_action argument"""
        from luaparser import astnodes

        errors = []
        line = (node.line - 1) if hasattr(node, 'line') and node.line else 0

        if not hasattr(node, 'args') or not node.args:
            return errors

        args = node.args
        if isinstance(args, list) and len(args) > 0:
            arg = args[0]
        else:
            return errors

        if isinstance(arg, astnodes.String) and self.watchmaker_actions:
            action = arg.s
            # Check exact match or prefix match for actions ending with ':'
            if action not in self.watchmaker_actions:
                # Check prefix match (e.g., 'm_task:something')
                prefix_match = any(
                    action.startswith(a.rstrip(':'))
                    for a in self.watchmaker_actions if a.endswith(':')
                )
                if not prefix_match:
                    errors.append(LuaSyntaxError(
                        line=line, column=0,
                        message=ERROR_MESSAGES["W003"].format(action=action),
                        severity=ErrorSeverity.WARNING,
                        error_code="W003"
                    ))

        return errors

    def _get_call_name(self, node) -> Optional[str]:
        """Extract function name from Call node"""
        from luaparser import astnodes

        if hasattr(node, 'func'):
            func = node.func
            if isinstance(func, astnodes.Name):
                return func.id
            elif isinstance(func, astnodes.Index):
                # Handle table.method style
                if hasattr(func, 'idx') and hasattr(func.idx, 'id'):
                    return func.idx.id
        return None

    def _basic_fallback_check(self, code: str) -> List[LuaSyntaxError]:
        """Fallback to basic regex-based checking when parser unavailable"""
        if not self._fallback_warned:
            self._fallback_warned = True
            print("Warning: luaparser not installed, using basic syntax check")

        errors = []
        lines = code.split('\n')

        # Track block pairing
        block_stack = []
        block_keywords = {
            'function': 'end', 'if': 'end', 'for': 'end',
            'while': 'end', 'do': 'end', 'repeat': 'until',
        }

        # Track brackets across all lines
        paren_balance = 0
        bracket_balance = 0
        brace_balance = 0
        paren_open_line = -1
        bracket_open_line = -1
        brace_open_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('--') or not stripped:
                continue

            clean_line = self._remove_strings_fallback(stripped)

            # Check block start
            for keyword in block_keywords:
                if (clean_line.startswith(keyword + ' ') or
                    clean_line.startswith(keyword + '(') or
                    clean_line == keyword):
                    block_stack.append((keyword, i))
                    break

            # Check block end
            if (clean_line == 'end' or clean_line.startswith('end ') or
                clean_line.startswith('end)') or clean_line.startswith('end,')):
                if block_stack:
                    block_stack.pop()
                else:
                    errors.append(LuaSyntaxError(
                        line=i, column=0,
                        message="Unexpected 'end'",
                        severity=ErrorSeverity.ERROR,
                        error_code="E003"
                    ))

            # Check until
            if clean_line.startswith('until ') or clean_line == 'until':
                if block_stack and block_stack[-1][0] == 'repeat':
                    block_stack.pop()

            # Track brackets
            for char in clean_line:
                if char == '(':
                    if paren_balance == 0:
                        paren_open_line = i
                    paren_balance += 1
                elif char == ')':
                    paren_balance -= 1
                    if paren_balance < 0:
                        errors.append(LuaSyntaxError(
                            line=i, column=0,
                            message="Unmatched ')'",
                            severity=ErrorSeverity.ERROR,
                            error_code="E004"
                        ))
                        paren_balance = 0
                elif char == '[':
                    if bracket_balance == 0:
                        bracket_open_line = i
                    bracket_balance += 1
                elif char == ']':
                    bracket_balance -= 1
                    if bracket_balance < 0:
                        errors.append(LuaSyntaxError(
                            line=i, column=0,
                            message="Unmatched ']'",
                            severity=ErrorSeverity.ERROR,
                            error_code="E004"
                        ))
                        bracket_balance = 0
                elif char == '{':
                    if brace_balance == 0:
                        brace_open_line = i
                    brace_balance += 1
                elif char == '}':
                    brace_balance -= 1
                    if brace_balance < 0:
                        errors.append(LuaSyntaxError(
                            line=i, column=0,
                            message="Unmatched '}'",
                            severity=ErrorSeverity.ERROR,
                            error_code="E004"
                        ))
                        brace_balance = 0

        # Report unclosed blocks
        for keyword, line_num in block_stack:
            errors.append(LuaSyntaxError(
                line=line_num, column=0,
                message=ERROR_MESSAGES["E003"].format(keyword=keyword, start_line=line_num + 1),
                severity=ErrorSeverity.ERROR,
                error_code="E003"
            ))

        # Report unclosed brackets
        if paren_balance > 0:
            errors.append(LuaSyntaxError(
                line=paren_open_line, column=0,
                message="Unclosed '('",
                severity=ErrorSeverity.ERROR,
                error_code="E004"
            ))
        if bracket_balance > 0:
            errors.append(LuaSyntaxError(
                line=bracket_open_line, column=0,
                message="Unclosed '['",
                severity=ErrorSeverity.ERROR,
                error_code="E004"
            ))
        if brace_balance > 0:
            errors.append(LuaSyntaxError(
                line=brace_open_line, column=0,
                message="Unclosed '{'",
                severity=ErrorSeverity.ERROR,
                error_code="E004"
            ))

        return errors

    def _remove_strings_fallback(self, line: str) -> str:
        """Remove string literals from line to avoid false positives"""
        result = []
        in_string = False
        string_char = None
        i = 0
        while i < len(line):
            char = line[i]
            if not in_string:
                if char in '"\'':
                    in_string = True
                    string_char = char
                else:
                    result.append(char)
            else:
                if char == string_char and (i == 0 or line[i-1] != '\\'):
                    in_string = False
            i += 1
        return ''.join(result)

    def clear_cache(self):
        """Clear the result cache"""
        self._cache_code = None
        self._cache_errors = None
