"""
測試 Lua 沙盒（wm_sandbox.lua）是否正確封鎖危險全域，
同時確保安全 API 仍可正常使用。
"""
import pytest

import components.utils as _utils_mod
from components.utils import eval_lua_expr, set_tag_value


def _lua_ok() -> bool:
    try:
        from lupa import LuaRuntime  # noqa: F401
        return True
    except ImportError:
        return False


skip_no_lua = pytest.mark.skipif(not _lua_ok(), reason="lupa 未安裝")


@pytest.fixture(autouse=True)
def clean_tag_values():
    _utils_mod._TAG_VALUES.clear()
    yield
    _utils_mod._TAG_VALUES.clear()


# ---------------------------------------------------------------------------
# 危險全域應回傳 nil
# ---------------------------------------------------------------------------

@skip_no_lua
class TestDangerousGlobalsBlocked:
    """每個危險全域存取後應回傳 None（Lua nil），不得拋出可利用的物件。"""

    @pytest.mark.parametrize("expr", [
        "python",           # lupa Python 橋
        "io",               # 檔案讀寫
        "os",               # 行程執行
        "debug",            # Lua debug 庫
        "package",          # 模組載入器
        "require",          # require 函式
        "dofile",           # 從檔案執行
        "loadfile",         # 從檔案載入 chunk
        "load",             # 從字串載入 chunk
        "loadstring",       # Lua 5.1 別名
    ])
    def test_blocked_global_is_nil(self, expr):
        result = eval_lua_expr(expr)
        assert result is None, f"危險全域 `{expr}` 應為 nil，實際得到：{result!r}"

    def test_python_eval_not_accessible(self):
        """python.eval() 不能用於執行任意 Python。"""
        result = eval_lua_expr("python and python.eval or nil")
        assert result is None

    def test_os_execute_not_accessible(self):
        """os.execute 不能存在。"""
        result = eval_lua_expr("os and os.execute or nil")
        assert result is None

    def test_io_open_not_accessible(self):
        """io.open 不能存在。"""
        result = eval_lua_expr("io and io.open or nil")
        assert result is None

    def test_debug_getupvalue_not_accessible(self):
        """debug.getupvalue 不能存在。"""
        result = eval_lua_expr("debug and debug.getupvalue or nil")
        assert result is None

    def test_package_loaded_not_accessible(self):
        """package.loaded 不能存在。"""
        result = eval_lua_expr("package and package.loaded or nil")
        assert result is None


# ---------------------------------------------------------------------------
# 安全 API 仍可正常使用
# ---------------------------------------------------------------------------

@skip_no_lua
class TestSafeGlobalsStillWork:
    """移除危險全域後，安全的標準庫和 WM API 應仍可運作。"""

    def test_math_lib(self):
        assert eval_lua_expr("math.sin(math.pi / 2)") == pytest.approx(1.0)

    def test_math_floor(self):
        assert eval_lua_expr("math.floor(3.9)") == 3

    def test_string_lib(self):
        result = eval_lua_expr('string.upper("hello")')
        assert result == "HELLO"

    def test_string_format(self):
        result = eval_lua_expr('string.format("%02d", 5)')
        assert result == "05"

    def test_table_lib(self):
        result = eval_lua_expr(
            "(function() local t={3,1,2} table.sort(t) return t[1] end)()"
        )
        assert result == 1

    def test_tostring_tonumber(self):
        assert eval_lua_expr("tonumber('42')") == pytest.approx(42.0)
        assert eval_lua_expr("tostring(3.14)") == "3.14"

    def test_type_function(self):
        assert eval_lua_expr("type(42)") == "number"
        assert eval_lua_expr('type("hi")') == "string"

    def test_pcall(self):
        """pcall 仍可用於捕捉錯誤。"""
        result = eval_lua_expr("(function() local ok, e = pcall(error, 'x') return ok end)()")
        assert result is False

    def test_ipairs_pairs(self):
        result = eval_lua_expr(
            "(function() local s=0 for _,v in ipairs({1,2,3}) do s=s+v end return s end)()"
        )
        assert result == pytest.approx(6.0)

    def test_tag_substitution_still_works(self):
        """{tag} 語法在沙盒後仍正常替換。"""
        set_tag_value("wt", "25")
        assert eval_lua_expr("{wt} + 0") == pytest.approx(25.0)

    def test_auto_time_tag_still_works(self):
        """{dh} 等時間 tag 在沙盒後仍正常注入。"""
        result = eval_lua_expr("{dh}")
        assert isinstance(result, (int, float))
        assert 1 <= result <= 12

    def test_wm_tag_function_still_works(self):
        """wm_tag() 在沙盒後仍能查詢標籤表。"""
        set_tag_value("wt", "30")
        result = eval_lua_expr('wm_tag("wt")')
        assert result == pytest.approx(30.0)

    def test_wm_api_stubs_do_not_crash(self):
        """WM API no-op 存根在沙盒後仍可呼叫而不崩潰。"""
        for expr in [
            'wm_action("sw_start_stop")',
            'wm_vibrate(100, 1)',
            'wm_sfx("chime")',
            'wm_transition("fade")',
            'wm_anim_set("label", "opacity", 100)',
            'wm_anim_start("label")',
            'wm_unschedule_all()',
        ]:
            result = eval_lua_expr(expr)
            # no-op 回傳 nil，不得拋出例外
            assert result is None, f"{expr!r} 應回傳 nil，得到 {result!r}"
