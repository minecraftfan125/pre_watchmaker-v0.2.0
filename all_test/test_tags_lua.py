"""
測試 tag 注入機制與 Lua 表達式求值正確性：
1. 手動 tag（set_tag_value）→ eval_lua_expr 正確解析
2. 自動時間 tag → 從系統時鐘注入，且無法被 set_tag_value 覆蓋
3. 多物件場景 → 不同物件各自的 tag 共用同一個 _TAG_VALUES，互不干擾
4. TAG_RE → 正確擷取 {tag} 模式
5. _AUTO_TIME_TAG_NAMES → 涵蓋核心時鐘 tag
6. to_float / to_str → 含 tag 運算式的型別轉換
"""
import datetime
import pytest

import components.utils as _utils_mod
from components.utils import (
    TAG_RE,
    _AUTO_TIME_TAG_NAMES,
    _compute_auto_time_tags,
    eval_lua_expr,
    set_tag_value,
    to_float,
    to_str,
)


# ---------------------------------------------------------------------------
# Fixture：每個測試前後清空 _TAG_VALUES，防止跨測試污染
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tag_values():
    _utils_mod._TAG_VALUES.clear()
    yield
    _utils_mod._TAG_VALUES.clear()


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _lua_ok() -> bool:
    try:
        from lupa import LuaRuntime  # noqa: F401
        return True
    except ImportError:
        return False


skip_no_lua = pytest.mark.skipif(not _lua_ok(), reason="lupa 未安裝")


# ---------------------------------------------------------------------------
# TAG_RE 模式擷取
# ---------------------------------------------------------------------------

class TestTagRE:
    def test_single_tag(self):
        assert TAG_RE.findall("{dh}") == ["dh"]

    def test_multiple_tags(self):
        assert TAG_RE.findall("{dh}:{dm}:{ds}") == ["dh", "dm", "ds"]

    def test_tag_in_arithmetic(self):
        assert TAG_RE.findall("{wt} + {offset}") == ["wt", "offset"]

    def test_no_tag(self):
        assert TAG_RE.findall("math.sin(0.5)") == []

    def test_nested_braces_not_matched(self):
        # {1invalid} 不符合識別字規則（首字為數字），不應被擷取
        assert TAG_RE.findall("{1bad}") == []

    def test_underscore_tag(self):
        assert TAG_RE.findall("{my_var}") == ["my_var"]

    def test_mixed_content(self):
        tags = TAG_RE.findall('"{c1b}" .. " " .. {drh}')
        assert set(tags) == {"c1b", "drh"}

    def test_duplicate_tags(self):
        tags = TAG_RE.findall("{wt} + {wt}")
        assert tags == ["wt", "wt"]


# ---------------------------------------------------------------------------
# _AUTO_TIME_TAG_NAMES 成員資格
# ---------------------------------------------------------------------------

class TestAutoTimeTagNames:
    @pytest.mark.parametrize("tag", [
        "dh", "dh24", "dm", "ds", "drh", "drm", "drs",
        "dd", "dy", "dn", "dnn", "ddw",
    ])
    def test_core_time_tags_in_set(self, tag):
        assert tag in _AUTO_TIME_TAG_NAMES, f"{tag} 應在 _AUTO_TIME_TAG_NAMES 中"

    def test_manual_tag_not_in_set(self):
        for tag in ("wt", "hum", "aqi", "myvar", "city"):
            assert tag not in _AUTO_TIME_TAG_NAMES, f"{tag} 不應在 _AUTO_TIME_TAG_NAMES 中"

    def test_is_frozenset(self):
        assert isinstance(_AUTO_TIME_TAG_NAMES, frozenset)


# ---------------------------------------------------------------------------
# _compute_auto_time_tags 回傳值合理性
# ---------------------------------------------------------------------------

class TestComputeAutoTimeTags:
    def test_returns_all_expected_keys(self):
        tags = _compute_auto_time_tags()
        for key in ("dh", "dm", "ds", "drh", "drm", "drs", "dd", "dy", "dn"):
            assert key in tags, f"缺少 key: {key}"

    def test_hour_range(self):
        tags = _compute_auto_time_tags()
        assert 1 <= tags["dh"] <= 12         # 12h 制
        assert 0 <= tags["dh24"] <= 23       # 24h 制
        assert 0 <= tags["dm"] <= 59
        assert 0 <= tags["ds"] <= 59

    def test_drh_range(self):
        tags = _compute_auto_time_tags()
        assert 0 <= tags["drh"] < 360

    def test_drm_range(self):
        tags = _compute_auto_time_tags()
        assert 0 <= tags["drm"] < 360

    def test_drs_range(self):
        tags = _compute_auto_time_tags()
        assert 0 <= tags["drs"] < 360

    def test_day_range(self):
        tags = _compute_auto_time_tags()
        assert 1 <= tags["dd"] <= 31

    def test_year_reasonable(self):
        tags = _compute_auto_time_tags()
        assert 2020 <= tags["dy"] <= 2100

    def test_dn_is_abbreviated_month(self):
        tags = _compute_auto_time_tags()
        valid = {"Jan","Feb","Mar","Apr","May","Jun",
                 "Jul","Aug","Sep","Oct","Nov","Dec"}
        assert tags["dn"] in valid

    def test_ddw1_is_full_day_name(self):
        tags = _compute_auto_time_tags()
        valid = {"Sunday","Monday","Tuesday","Wednesday",
                 "Thursday","Friday","Saturday"}
        assert tags["ddw1"] in valid

    def test_dhz_is_zero_padded(self):
        tags = _compute_auto_time_tags()
        assert len(tags["dhz"]) == 2
        assert tags["dhz"].isdigit()

    def test_matches_system_clock(self):
        before = datetime.datetime.now()
        tags = _compute_auto_time_tags()
        after = datetime.datetime.now()
        # dm 應等於 before 或 after 的分鐘（跨分鐘邊界容差 ±1）
        assert before.minute - 1 <= tags["dm"] <= after.minute + 1


# ---------------------------------------------------------------------------
# eval_lua_expr：手動 tag 求值
# ---------------------------------------------------------------------------

@skip_no_lua
class TestEvalLuaExprManualTags:
    def test_no_tag_simple_arithmetic(self):
        assert eval_lua_expr("1 + 2") == pytest.approx(3.0)

    def test_single_manual_tag_numeric(self):
        set_tag_value("wt", "25")
        result = eval_lua_expr("{wt}")
        assert result == pytest.approx(25.0)

    def test_tag_in_addition(self):
        set_tag_value("wt", "30")
        result = eval_lua_expr("{wt} + 5")
        assert result == pytest.approx(35.0)

    def test_tag_in_multiplication(self):
        set_tag_value("ratio", "0.5")
        result = eval_lua_expr("{ratio} * 100")
        assert result == pytest.approx(50.0)

    def test_two_manual_tags_in_expression(self):
        set_tag_value("a", "10")
        set_tag_value("b", "3")
        result = eval_lua_expr("{a} - {b}")
        assert result == pytest.approx(7.0)

    def test_tag_float_value(self):
        set_tag_value("pi_approx", "3.14")
        result = eval_lua_expr("{pi_approx} * 2")
        assert result == pytest.approx(6.28, rel=1e-4)

    def test_tag_zero_value(self):
        set_tag_value("myvar", "0")
        result = eval_lua_expr("{myvar} * 99")
        assert result == pytest.approx(0.0)

    def test_string_tag_in_concat(self):
        # {unit} → _WM_TAGS["unit"]，可取到設定值
        set_tag_value("unit", "42")
        result = eval_lua_expr('"Temp:" .. {unit}')
        assert isinstance(result, str)
        assert "42" in result

    def test_tag_not_set_returns_none_or_zero(self):
        # 未設定的 tag → _WM_TAGS["xyz_unset"] 為 nil → eval 失敗 → None
        result = eval_lua_expr("{xyz_unset}")
        # 不 crash，回傳 None（nil）
        assert result is None

    def test_double_underscore_is_not_a_tag(self):
        """__dh__ 語法不再自動解析為時間 tag，應回傳 None。"""
        result = eval_lua_expr("__dh__")
        assert result is None

    def test_string_tag_accessed_as_variable(self):
        # {label} 直接作為表達式 → __label__（Lua 變數）→ 取到字串值
        set_tag_value("label", "hot")
        result = eval_lua_expr("{label}")
        assert isinstance(result, str)
        assert result == "hot"

    def test_expression_with_math_lib_and_tag(self):
        set_tag_value("angle_deg", "90")
        result = eval_lua_expr("math.sin(math.rad({angle_deg}))")
        assert result == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# eval_lua_expr：自動時間 tag
# ---------------------------------------------------------------------------

@skip_no_lua
class TestEvalLuaExprAutoTimeTags:
    def test_dh_resolves_to_number(self):
        result = eval_lua_expr("{dh}")
        assert isinstance(result, (int, float))
        assert 1 <= result <= 12

    def test_dm_resolves_to_number(self):
        result = eval_lua_expr("{dm}")
        assert isinstance(result, (int, float))
        assert 0 <= result <= 59

    def test_ds_resolves_to_number(self):
        result = eval_lua_expr("{ds}")
        assert isinstance(result, (int, float))
        assert 0 <= result <= 59

    def test_drh_in_arithmetic(self):
        result = eval_lua_expr("{drh} * 1")
        assert isinstance(result, (int, float))
        assert 0 <= result < 360

    def test_auto_tag_not_overridden_by_set_tag_value(self):
        # 設定一個與 auto tag 同名的手動值，不應生效（auto 優先）
        set_tag_value("dh", "999")
        result = eval_lua_expr("{dh}")
        # dh 是 12h 制，合法範圍 1–12
        assert isinstance(result, (int, float))
        assert 1 <= result <= 12, f"auto tag 'dh' 應從系統時鐘取值，實際={result}"

    def test_auto_and_manual_tags_coexist(self):
        set_tag_value("wt", "28")
        result_wt  = eval_lua_expr("{wt}")
        result_drh = eval_lua_expr("{drh}")
        assert result_wt == pytest.approx(28.0)
        assert isinstance(result_drh, (int, float)) and 0 <= result_drh < 360

    def test_mixed_auto_and_manual_in_one_expr(self):
        set_tag_value("offset", "5")
        result = eval_lua_expr("{ds} + {offset}")
        assert isinstance(result, (int, float))
        # ds 範圍 0-59，offset=5，結果 5-64
        assert 5 <= result <= 64


# ---------------------------------------------------------------------------
# 多物件場景：多個物件的 tag 共用 _TAG_VALUES 互不污染
# ---------------------------------------------------------------------------

@skip_no_lua
class TestMultiObjectTagScenario:
    """
    模擬 refresh_all_instances 依序對不同 canvas item 呼叫 apply_attr（eval_lua_expr）的情境。
    各物件的表達式使用不同 tag，共用同一個全域 _TAG_VALUES。
    """

    def test_two_objects_different_manual_tags(self):
        """物件 A 用 {wt}，物件 B 用 {hum}，互不干擾。"""
        set_tag_value("wt",  "25")
        set_tag_value("hum", "80")

        result_a = eval_lua_expr("{wt}")
        result_b = eval_lua_expr("{hum}")

        assert result_a == pytest.approx(25.0)
        assert result_b == pytest.approx(80.0)

    def test_three_objects_mixed_tag_types(self):
        """
        物件 A: 手動 tag {wt}
        物件 B: 自動時間 tag {drh}
        物件 C: 混合 {wt} + {drh}
        """
        set_tag_value("wt", "30")

        r_a = eval_lua_expr("{wt}")
        r_b = eval_lua_expr("{drh}")
        r_c = eval_lua_expr("{wt} + {drh}")

        assert r_a == pytest.approx(30.0)
        assert isinstance(r_b, (int, float)) and 0 <= r_b < 360
        assert r_c == pytest.approx(30.0 + r_b)

    def test_same_tag_used_by_multiple_objects(self):
        """多個物件共用同一個 tag 值，皆取到相同結果。"""
        set_tag_value("scale", "2")

        r1 = eval_lua_expr("{scale} * 10")
        r2 = eval_lua_expr("{scale} * 20")
        r3 = eval_lua_expr("{scale} + 1")

        assert r1 == pytest.approx(20.0)
        assert r2 == pytest.approx(40.0)
        assert r3 == pytest.approx(3.0)

    def test_updating_tag_value_affects_all_subsequent_evals(self):
        """更新 tag 值後，後續所有物件的求值都反映新值。"""
        set_tag_value("brightness", "50")
        before = eval_lua_expr("{brightness}")

        set_tag_value("brightness", "100")
        after = eval_lua_expr("{brightness}")

        assert before == pytest.approx(50.0)
        assert after  == pytest.approx(100.0)

    def test_object_with_no_tags_unaffected_by_tag_values(self):
        """純數值運算的物件不受 _TAG_VALUES 影響。"""
        set_tag_value("anything", "999")
        result = eval_lua_expr("3.14 * 2")
        assert result == pytest.approx(6.28, rel=1e-4)

    def test_many_tags_simultaneously(self):
        """同時設定多個 tag 並各自正確解析。"""
        tag_data = {
            "t1": "1", "t2": "2", "t3": "3",
            "t4": "4", "t5": "5",
        }
        for name, val in tag_data.items():
            set_tag_value(name, val)

        for name, val in tag_data.items():
            result = eval_lua_expr(f"{{{name}}}")
            assert result == pytest.approx(float(val)), \
                f"tag {name} 應為 {val}，實際 {result}"


# ---------------------------------------------------------------------------
# to_float：含 tag 的運算式轉型
# ---------------------------------------------------------------------------

@skip_no_lua
class TestToFloatWithTags:
    def test_plain_number_string(self):
        assert to_float("42") == pytest.approx(42.0)

    def test_tag_expression(self):
        set_tag_value("wt", "25")
        result = to_float("{wt}")
        assert result == pytest.approx(25.0)

    def test_tag_arithmetic(self):
        set_tag_value("base", "10")
        result = to_float("{base} * 3.5")
        assert result == pytest.approx(35.0)

    def test_auto_time_tag(self):
        result = to_float("{drm}")
        assert isinstance(result, float)
        assert 0.0 <= result < 360.0

    def test_invalid_expr_returns_fallback(self):
        assert to_float("not_a_number_xyz", fallback=0.0) == pytest.approx(0.0)

    def test_custom_fallback(self):
        assert to_float("???", fallback=-1.0) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# to_str：含 tag 的運算式轉字串
# ---------------------------------------------------------------------------

@skip_no_lua
class TestToStrWithTags:
    def test_plain_number(self):
        result = to_str("3.14")
        assert result == "3.14"

    def test_simple_arithmetic(self):
        result = to_str("10 + 5")
        assert result == "15" or result == "15.0"

    def test_manual_tag_in_expr(self):
        set_tag_value("wt", "25")
        result = to_str("{wt}")
        # to_str 對 float 呼叫 str()，結果為 "25" 或 "25.0"
        assert "25" in result

    def test_auto_time_tag(self):
        result = to_str("{ds}")
        # ds 為秒 0-59，to_str 應回傳數字字串
        try:
            val = float(result)
            assert 0 <= val <= 59
        except ValueError:
            # 若 eval 失敗（例如 lupa 不可用），to_str 回傳原始文字
            assert result == "{ds}"

    def test_invalid_lua_returns_original(self):
        # 無效的 Lua 表達式 → eval_lua_expr 回傳 None → to_str 回傳原字串
        original = "invalid && syntax ##"
        result = to_str(original)
        assert result == original
