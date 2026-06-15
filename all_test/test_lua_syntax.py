"""
測試 lua_script._check_lua_syntax：
1. 有效 Lua 程式 → 不回傳錯誤
2. WatchMaker inline expression（非 statement）→ 透過 return wrap 路徑通過
3. 無效 Lua → 回傳含行號與訊息 substring 的錯誤
"""
import pytest
from lua_script import _check_lua_syntax


# ---------------------------------------------------------------------------
# 有效 Lua 程式
# ---------------------------------------------------------------------------

_VALID_CASES = [
    ("empty string", ""),
    ("comment only", "-- just a comment\n-- another line"),
    (
        "on_second function",
        "function on_second(h, m, s)\n"
        "  local angle = s * 6\n"
        "  wm_action(\"rotate\", angle)\n"
        "end",
    ),
    (
        "on_millisecond function",
        "function on_millisecond(dt)\n"
        "  tweens.rotate_sec = tweens.rotate_sec + dt * 0.001\n"
        "end",
    ),
    (
        "wm_tag call",
        "local t = wm_tag(\"{dd}\")",
    ),
    (
        "wm_vibrate call",
        "wm_vibrate(100)",
    ),
    (
        "wm_sfx call",
        "wm_sfx(\"chime.ogg\")",
    ),
    (
        "wm_transition call",
        "wm_transition(\"Fade\")",
    ),
    (
        "wm_schedule table-call (no parens)",
        "wm_schedule { action=\"tween\", tween=\"r\", from=0, to=90, duration=1 }",
    ),
    (
        "wm_schedule chained animations",
        "wm_schedule {\n"
        "  { action=\"tween\", tween=\"r\", from=0, to=90, duration=0.5 },\n"
        "  { action=\"tween\", tween=\"r\", from=90, to=0, duration=0.5 },\n"
        "}",
    ),
    (
        "var_ prefix variables",
        "var_mynum = 42\n"
        "var_mystr = \"hello\"\n"
        "var_ms_posx = 0.0",
    ),
    (
        "is_bright conditional",
        "if is_bright then\n"
        "  wm_action(\"set_color\", \"#FFFFFF\")\n"
        "else\n"
        "  wm_action(\"set_color\", \"#000000\")\n"
        "end",
    ),
    (
        "tweens field access",
        "local r = tweens.rotate_sec",
    ),
    (
        "string stdlib",
        "local s = string.upper(\"hello\")\n"
        "local sub = string.sub(s, 1, 3)\n"
        "local rep = string.gsub(s, \"H\", \"h\")",
    ),
    (
        "nested if elseif else",
        "if x == 1 then\n"
        "  return \"one\"\n"
        "elseif x == 2 then\n"
        "  return \"two\"\n"
        "else\n"
        "  return \"other\"\n"
        "end",
    ),
    (
        "for loop with wm_action",
        "for i = 1, 10 do\n"
        "  wm_action(\"step\", i)\n"
        "end",
    ),
    (
        "repeat until loop",
        "local i = 0\n"
        "repeat\n"
        "  i = i + 1\n"
        "until i >= 5",
    ),
    (
        "while loop",
        "local i = 0\n"
        "while i < 10 do\n"
        "  i = i + 1\n"
        "end",
    ),
]


@pytest.mark.parametrize("name,src", _VALID_CASES, ids=[c[0] for c in _VALID_CASES])
def test_valid_lua(name, src):
    # _VALID_CASES 全部是完整 Lua script，使用 script mode（expression_mode=False）
    assert _check_lua_syntax(src, expression_mode=False) == [], \
        f"予期無錯誤但有：{_check_lua_syntax(src, expression_mode=False)}"


# ---------------------------------------------------------------------------
# WatchMaker inline expression（return wrap 路徑）
# ---------------------------------------------------------------------------

_EXPR_CASES = [
    (
        "tag in arithmetic expression",
        '({dm} % 2 == 0) and "even" or "odd"',
    ),
    (
        "string concat with tags",
        '"{c1b}" .. "{c1l}"',
    ),
    (
        "math with tag",
        "math.sin(math.rad({drh})) * 100",
    ),
    (
        "multi-level conditional with tags",
        '({dh} < 11) and "Morning" or ({dh} < 15) and "Noon" or "Evening"',
    ),
]


@pytest.mark.parametrize("name,src", _EXPR_CASES, ids=[c[0] for c in _EXPR_CASES])
def test_expression_context_via_return_wrap(name, src):
    """這些 case 直接解析會失敗，必須透過 return wrap 路徑才能通過。"""
    # 先確認直接解析確實有錯誤（驗證 return wrap 路徑被使用到）
    from antlr4 import InputStream, CommonTokenStream, Token
    from antlr4.error.ErrorListener import ErrorListener as _Base
    from luaparser.parser.LuaLexer import LuaLexer
    from luaparser.parser.LuaParser import LuaParser

    class _Collector(_Base):
        def __init__(self): super().__init__(); self.errors = []
        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            self.errors.append(msg)

    def _direct_parse(text):
        lexer = LuaLexer(InputStream(text))
        lexer.removeErrorListeners()
        lc = _Collector(); lexer.addErrorListener(lc)
        tokens = CommonTokenStream(lexer, channel=Token.DEFAULT_CHANNEL)
        parser = LuaParser(tokens)
        parser.removeErrorListeners()
        pc = _Collector(); parser.addErrorListener(pc)
        parser.start_()
        return lc.errors + pc.errors

    assert _direct_parse(src), f"此 case 直接解析應失敗，但意外成功（return wrap 未被測試到）"
    # 透過 _check_lua_syntax 應無錯誤
    assert _check_lua_syntax(src) == [], f"return wrap 後應無錯誤但有：{_check_lua_syntax(src)}"


# ---------------------------------------------------------------------------
# 無效 Lua 程式
# ---------------------------------------------------------------------------

def _has_error_at(issues, line, *substrings):
    """確認 issues 中有一個 line==line 且 message 包含所有 substring 的項目。"""
    for e in issues:
        if e["line"] == line and all(s in e["message"] for s in substrings):
            return True
    return False


def _has_any_error(issues):
    return len(issues) > 0


def test_invalid_missing_end():
    src = "if x then\n  print(x)"
    issues = _check_lua_syntax(src, expression_mode=False)
    assert issues, "應偵測到 missing end 錯誤"
    # 錯誤應在第 2 行（EOF 處）且訊息含 'end' 或 'EOF'
    assert any(
        e["line"] == 2 and ("end" in e["message"] or "EOF" in e["message"])
        for e in issues
    ), f"預期 line=2 含 'end'/'EOF'，實際：{issues}"


def test_invalid_function_missing_end():
    src = "function foo()\n  return 1"
    issues = _check_lua_syntax(src)
    assert issues, "應偵測到 function missing end 錯誤"
    assert any(
        e["line"] == 2 and ("end" in e["message"] or "EOF" in e["message"])
        for e in issues
    ), f"預期 line=2 含 'end'/'EOF'，實際：{issues}"


def test_invalid_unclosed_paren():
    src = "print(x"
    issues = _check_lua_syntax(src)
    assert _has_any_error(issues), "應偵測到未閉合括號錯誤"
    assert issues[0]["line"] == 1, f"錯誤應在第 1 行，實際：{issues}"


def test_invalid_unexpected_end():
    src = "end"
    issues = _check_lua_syntax(src)
    assert issues, "應偵測到多餘 'end' 錯誤"
    assert any(
        e["line"] == 1 and "end" in e["message"]
        for e in issues
    ), f"預期 line=1 含 'end'，實際：{issues}"


def test_invalid_until_without_repeat():
    src = "until true"
    issues = _check_lua_syntax(src)
    assert issues, "應偵測到沒有對應 repeat 的 until 錯誤"
    assert any(
        e["line"] == 1 and "until" in e["message"]
        for e in issues
    ), f"預期 line=1 含 'until'，實際：{issues}"


def test_invalid_multiple_errors():
    src = "if x >\nend\nfunction"
    issues = _check_lua_syntax(src, expression_mode=False)
    assert len(issues) >= 2, f"應回傳至少 2 個錯誤，實際：{issues}"
    # 第一個錯誤應在前兩行
    assert issues[0]["line"] <= 2, f"第一個錯誤應在前兩行，實際：{issues[0]}"
    # 結果應按行號排序
    lines = [e["line"] for e in issues]
    assert lines == sorted(lines), f"錯誤應按行號排序，實際：{lines}"


# ---------------------------------------------------------------------------
# numeric=True：數值欄位運算式輸出型別驗證
# ---------------------------------------------------------------------------

_NUMERIC_OK_CASES = [
    ("integer literal",           "42"),
    ("float literal",             "3.14"),
    ("arithmetic expression",     "1 + 2 * 3"),
    ("tag arithmetic",            "{drh} * 6"),
    ("math function",             "math.sin(math.rad({drh})) * 100"),
    ("numeric ternary",           "is_bright and 1 or 0"),
    ("variable reference",        "var_mynum"),
    ("nested arithmetic",         "({dh} * 3600 + {dm} * 60 + {ds}) / 86400"),
    ("function call",             "wm_tag(\"{dh24z}\")"),  # 回傳值型別不明，應通過
]


@pytest.mark.parametrize(
    "name,src", _NUMERIC_OK_CASES, ids=[c[0] for c in _NUMERIC_OK_CASES]
)
def test_numeric_ok(name, src):
    """numeric=True 時，不應被誤判為非數值的運算式不報錯。"""
    assert _check_lua_syntax(src, numeric=True) == [], \
        f"應無錯誤但有：{_check_lua_syntax(src, numeric=True)}"


_NUMERIC_ERR_CASES = [
    ("string literal",        '"hello"'),
    ("single-quoted string",  "'world'"),
    ("string concat",         '"{c1b}" .. "{c1l}"'),
]


@pytest.mark.parametrize(
    "name,src", _NUMERIC_ERR_CASES, ids=[c[0] for c in _NUMERIC_ERR_CASES]
)
def test_numeric_error(name, src):
    """numeric=True 時，最外層 return 值為字串型別應回傳錯誤。"""
    issues = _check_lua_syntax(src, numeric=True)
    assert issues, f"應偵測到非數值錯誤，但無錯誤回傳"
    assert any("number" in e["message"] for e in issues), \
        f"錯誤訊息應含 'number'，實際：{issues}"


def test_numeric_does_not_affect_syntax_errors():
    """numeric=True 不影響語法錯誤的回報（語法錯誤優先）。"""
    src = "if x then"  # missing end
    issues = _check_lua_syntax(src, numeric=True)
    assert issues, "應回傳語法錯誤"
    # 語法錯誤訊息應含 end/EOF，而非 number
    assert any("end" in e["message"] or "EOF" in e["message"] for e in issues), \
        f"應為語法錯誤而非 numeric 錯誤，實際：{issues}"


def test_numeric_false_does_not_check_string_return():
    """numeric=False（預設）時，回傳字串不報錯。"""
    assert _check_lua_syntax('"hello"', numeric=False) == []
    assert _check_lua_syntax('"{c1b}" .. "{c1l}"', numeric=False) == []
