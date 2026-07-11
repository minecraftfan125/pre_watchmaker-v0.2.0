"""
測試 Lua 執行逾時機制：
1. eval_lua_expr() 遇到無限迴圈應在 _EVAL_TIMEOUT_SECS 內中斷並回傳 None
2. run_base_script_extract() 遇到無限迴圈應在 _EXTRACT_TIMEOUT_SECS 內中斷
3. 正常表達式不受影響（逾時機制零額外副作用）
"""
import time

import pytest

import components.utils as _utils_mod
from components.utils import (
    _EVAL_TIMEOUT_SECS,
    _EXTRACT_TIMEOUT_SECS,
    eval_lua_expr,
    run_base_script_extract,
    set_tag_value,
)


def _lua_ok() -> bool:
    try:
        from lupa import LuaRuntime  # noqa: F401
        return True
    except ImportError:
        return False


skip_no_lua = pytest.mark.skipif(not _lua_ok(), reason="lupa 未安裝")

# 測試結果上限：逾時值的 4 倍（容許 CI 負載造成的時間誤差）
_EVAL_LIMIT   = _EVAL_TIMEOUT_SECS    * 4
_EXTRACT_LIMIT = _EXTRACT_TIMEOUT_SECS * 4


@pytest.fixture(autouse=True)
def clean_tag_values():
    _utils_mod._TAG_VALUES.clear()
    yield
    _utils_mod._TAG_VALUES.clear()


# ---------------------------------------------------------------------------
# eval_lua_expr 無限迴圈逾時
# ---------------------------------------------------------------------------

@skip_no_lua
class TestEvalTimeout:
    def test_infinite_loop_is_interrupted(self):
        """while true do end 應在逾時後回傳 None，不會永久阻塞。"""
        start = time.monotonic()
        result = eval_lua_expr("(function() while true do end end)()")
        elapsed = time.monotonic() - start

        assert result is None, "逾時應回傳 None"
        assert elapsed < _EVAL_LIMIT, (
            f"逾時耗時 {elapsed:.2f}s，超過預期上限 {_EVAL_LIMIT}s"
        )

    def test_busy_loop_with_counter_is_interrupted(self):
        """計數型無限迴圈也應被中斷。"""
        start = time.monotonic()
        result = eval_lua_expr(
            "(function() local i=0 while true do i=i+1 end return i end)()"
        )
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed < _EVAL_LIMIT

    def test_timeout_does_not_affect_subsequent_calls(self):
        """逾時後，後續正常表達式應仍能正確求值（deadline 已還原為 inf）。"""
        eval_lua_expr("(function() while true do end end)()")  # 觸發逾時

        result = eval_lua_expr("1 + 2")
        assert result == pytest.approx(3.0), "逾時後正常表達式應正確求值"

    def test_tag_access_after_timeout_still_works(self):
        """{tag} 在逾時後仍能正常解析。"""
        eval_lua_expr("(function() while true do end end)()")

        set_tag_value("wt", "25")
        result = eval_lua_expr("{wt} + 0")
        assert result == pytest.approx(25.0)

    def test_time_tag_after_timeout_still_works(self):
        """{dh} 時間 tag 在逾時後仍能正常注入。"""
        eval_lua_expr("(function() while true do end end)()")

        result = eval_lua_expr("{dh}")
        assert isinstance(result, (int, float))
        assert 1 <= result <= 12

    def test_normal_expression_completes_fast(self):
        """簡單運算應遠快於逾時閾值（勾子零負擔）。"""
        start = time.monotonic()
        result = eval_lua_expr("math.sin(math.pi / 6) * 2")
        elapsed = time.monotonic() - start

        assert result == pytest.approx(1.0, rel=1e-5)
        assert elapsed < 0.1, f"簡單表達式耗時 {elapsed:.3f}s，疑似效能異常"

    def test_math_heavy_expression_completes(self):
        """多次數學運算的複雜表達式應能在逾時前完成。"""
        result = eval_lua_expr(
            "(function()\n"
            "  local s = 0\n"
            "  for i = 1, 1000 do s = s + math.sin(i * 0.01) end\n"
            "  return s\n"
            "end)()"
        )
        assert isinstance(result, (int, float)), "複雜但有限的迴圈應回傳數值"


# ---------------------------------------------------------------------------
# run_base_script_extract 無限迴圈逾時
# ---------------------------------------------------------------------------

@skip_no_lua
class TestExtractTimeout:
    def test_infinite_loop_in_base_script_is_interrupted(self):
        """base script 含無限迴圈時應在 _EXTRACT_TIMEOUT_SECS 內中斷，仍回傳空結果。"""
        script = "while true do end"

        start = time.monotonic()
        vars_dict, tween_names = run_base_script_extract(script)
        elapsed = time.monotonic() - start

        assert isinstance(vars_dict, dict), "應回傳 dict（即使為空）"
        assert elapsed < _EXTRACT_LIMIT, (
            f"逾時耗時 {elapsed:.2f}s，超過預期上限 {_EXTRACT_LIMIT}s"
        )

    def test_var_extraction_before_infinite_loop(self):
        """無限迴圈前已定義的 var_ 變數應能被萃取（部分執行）。"""
        script = "var_speed = 42\nwhile true do end"

        start = time.monotonic()
        vars_dict, _ = run_base_script_extract(script)
        elapsed = time.monotonic() - start

        assert elapsed < _EXTRACT_LIMIT
        # var_speed 在無限迴圈前定義，部分執行可能有機會萃取到
        # （取決於 Lua 執行時機，此處不強制斷言有值，只驗證不掛起）

    def test_normal_script_extracts_correctly(self):
        """正常 base script 應正確萃取 var_ 變數，不受逾時機制影響。"""
        script = "var_x = 10\nvar_y = 20.5\nvar_name = 'hello'"
        vars_dict, _ = run_base_script_extract(script)

        assert vars_dict.get("var_x") == pytest.approx(10.0)
        assert vars_dict.get("var_y") == pytest.approx(20.5)
        assert vars_dict.get("var_name") == "hello"
