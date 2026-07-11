import datetime
import pathlib
import re
import time

from PyQt6.QtWidgets import QWidget

# ── Lua 表達式求值工具 ────────────────────────────────────────────────────────

_LUA = None   # LuaRuntime 單例（延遲初始化）
_WM_API_LUA_PATH     = pathlib.Path(__file__).parent.parent / "lua" / "wm_api.lua"
_WM_SANDBOX_LUA_PATH = pathlib.Path(__file__).parent.parent / "lua" / "wm_sandbox.lua"

_EVAL_TIMEOUT_SECS    = 0.5      # 單次 eval 最大執行時間（秒）
_EXTRACT_TIMEOUT_SECS = 3.0      # base script 萃取最大執行時間（秒）
_HOOK_INSTR_COUNT     = 10_000   # 每 N 條 Lua 指令觸發一次逾時勾子

_lua_deadline = float('inf')  # 當前 eval 的截止時間戳（monotonic）；inf = 不逾時
_TAG_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
TAG_RE = _TAG_RE  # 公開別名
# 整個字串常值只包一個 tag（如 '{wci}'、"{bc}"）：WatchMaker 文件慣例會這樣寫以便與字串比較，
# 若照 _TAG_RE 原樣代換會被引號吃成純文字（永遠比較不相等）。需連同引號一起代換掉。
_QUOTED_TAG_RE = re.compile(r'([\'"])\{([a-zA-Z_][a-zA-Z0-9_]*)\}\1')

# 有來源的時間/日期 tag：由系統時鐘自動解析，不出現在 Tags Settings Panel
_AUTO_TIME_TAG_NAMES: frozenset[str] = frozenset({
    "dh", "dh11", "dh24", "dh23",
    "dhutc12", "dhutc12z", "dhutc24", "dhutc24z",
    "dht", "dh24t", "dhz", "dh11z", "dh24z", "dh23z",
    "dhtt", "dhto", "dh11tt", "dh11to", "dh24tt", "dh24to", "dh23tt", "dh23to",
    "dm", "dmz",
    "ds", "dsz", "dss", "dssz", "dsps",
    "da", "dtp", "depoch",
    "drh", "drh24", "drh0", "drm", "drs", "drss", "drms",
    "dd", "ddz", "ddy", "ddim", "ddw0",
    "ddw", "ddww", "ddw1", "ddw2",
    "dy", "dyy", "dwm", "dw",
    "dn", "dnn", "dnnn", "dnnnn",
})

# 無來源 tag 的使用者設定值（全域，session 內保留）
_TAG_VALUES: dict[str, str] = {}

# base script 萃取的 var_ 變數（全域，每次腳本套用時更新）
_VAR_VALUES: dict[str, object] = {}

# base script 中定義的 tween 名稱（用於補全與 tweens table 初始化）
_TWEEN_NAMES: list[str] = []


def set_tag_value(tag_name: str, value: str) -> None:
    """設定無來源 tag 的測試值（不含大括號的 tag 名稱）。"""
    _TAG_VALUES[tag_name] = value


def run_base_script_extract(
    script: str,
    wm_api_names: tuple[str, ...] = (),
) -> tuple[dict, list]:
    """
    以全新 LuaRuntime 執行 base script 並萃取 var_ 變數與 tween 名稱，
    執行成功後將此 runtime 升格為新的 _LUA 單例（取代舊單例）。
    如此 script 中定義的 function（例如 function var_a(b,c) return b+c end）
    才能被 eval_lua_expr() 求值的欄位表達式直接呼叫；且每次套用都是全新建立，
    舊版本已刪除的 function／變數不會殘留。
    lupa 未安裝時降級為只用 regex 萃取 tween 名稱。
    """
    global _LUA, _lua_deadline
    tween_names = list(set(re.findall(r"tween\s*=\s*['\"]([^'\"]+)['\"]", script)))
    vars_dict: dict = {}
    try:
        from lupa import LuaRuntime
        lua_tmp = LuaRuntime(unpack_returned_tuples=True)
        _loaded = False
        try:
            lua_tmp.execute(_WM_API_LUA_PATH.read_text(encoding="utf-8"))
            _loaded = True
        except (FileNotFoundError, OSError, Exception):
            pass
        if not _loaded:
            for fn in wm_api_names:
                lua_tmp.execute(f"function {fn}(...) end")
        # 安裝逾時勾子：與 _get_lua 共用同一個 _lua_deadline，
        # 因為此 runtime 執行完後會長駐成為 _LUA 單例，勾子必須能反映之後每次 eval 的截止時間。
        try:
            def _check_deadline(*_args):
                return time.monotonic() > _lua_deadline
            lua_tmp.globals()["_wm_check_deadline"] = _check_deadline
            lua_tmp.execute(
                "local _fn = _wm_check_deadline\n"
                "debug.sethook(function()\n"
                "    if _fn() then error('Lua 執行逾時') end\n"
                "end, '', " + str(_HOOK_INSTR_COUNT) + ")\n"
                "_wm_check_deadline = nil\n"
            )
        except Exception:
            pass
        try:
            lua_tmp.execute(_WM_SANDBOX_LUA_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, Exception):
            pass
        _lua_deadline = time.monotonic() + _EXTRACT_TIMEOUT_SECS
        try:
            lua_tmp.execute(script)
        except Exception:
            pass  # 部分執行仍可萃取已定義的 var_
        finally:
            _lua_deadline = float('inf')  # 還原為不逾時，避免影響升格後的下一次 eval
        raw = lua_tmp.eval(
            "(function() local t={} for k,v in pairs(_G) do"
            " if type(k)=='string' and k:sub(1,4)=='var_'"
            " and type(v)~='function' then t[k]=v end end return t end)()"
        )
        if raw is not None:
            for k, v in raw.items():
                if isinstance(v, (int, float, str, bool)):
                    vars_dict[k] = v
        _LUA = lua_tmp  # 升格為新單例：script 中定義的 function／變數即可被欄位表達式呼叫
    except Exception:
        vars_dict = {}
    return vars_dict, tween_names


def set_base_script_data(vars_dict: dict, tween_names: list) -> None:
    """更新 var_ 變數快取與 tweens table；每次 base script 套用後呼叫。"""
    global _VAR_VALUES, _TWEEN_NAMES
    _VAR_VALUES.clear()
    _VAR_VALUES.update(vars_dict)
    _TWEEN_NAMES.clear()
    _TWEEN_NAMES.extend(tween_names)
    lua = _get_lua()
    if lua is None:
        return
    lua.execute("tweens = {}")
    for name in tween_names:
        lua.execute(f"tweens['{name}'] = 0")


def get_tween_names() -> list[str]:
    """回傳目前 base script 中定義的 tween 名稱清單（用於補全）。"""
    return list(_TWEEN_NAMES)


def _get_lua():
    global _LUA
    if _LUA is None:
        try:
            from lupa import LuaRuntime
            _LUA = LuaRuntime(unpack_returned_tuples=True)
            try:
                _LUA.execute(_WM_API_LUA_PATH.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, Exception):
                pass
            # 安裝持久性逾時勾子（在 sandbox 移除 debug 之前）：
            # debug.sethook 要求真正的 Lua function，不接受 lupa POBJECT。
            # 解法：將 Python 截止時間檢查函式暫時暴露為 Lua 全域，
            # 以原生 Lua 閉包包裝後傳入 debug.sethook，再把全域名稱 nil 掉。
            try:
                def _check_deadline(*_args):
                    return time.monotonic() > _lua_deadline
                _LUA.globals()["_wm_check_deadline"] = _check_deadline
                _LUA.execute(
                    "local _fn = _wm_check_deadline\n"
                    "debug.sethook(function()\n"
                    "    if _fn() then error('Lua 執行逾時') end\n"
                    "end, '', " + str(_HOOK_INSTR_COUNT) + ")\n"
                    "_wm_check_deadline = nil\n"
                )
            except Exception:
                pass
            # sandbox 移除 debug 等危險全域；hook 已安裝，使用者無法從 Lua 存取 debug 移除它
            try:
                _LUA.execute(_WM_SANDBOX_LUA_PATH.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, Exception):
                pass
        except ImportError:
            pass
    return _LUA


def _compute_auto_time_tags() -> dict[str, object]:
    """從系統時鐘計算所有有來源時間/日期 tag 的當前值。"""
    now = datetime.datetime.now()
    h, m, s = now.hour, now.minute, now.second
    ms = now.microsecond // 1000
    h12 = h % 12 or 12
    h11 = h % 12
    drh  = ((h % 12 * 60 + m) / 720) * 360
    drm  = ((m * 60 + s) / 3600) * 360
    drs  = (s / 60) * 360
    drss = ((s * 1000 + ms) / 60000) * 360
    drms = (ms / 1000) * 360
    _DN_FULL  = ["Sunday", "Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday"]
    _DN_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    wd = now.isoweekday() % 7  # 0=Sun … 6=Sat
    # 當月天數（利用下月1日往前退一天）
    next_month = now.month % 12 + 1
    next_year  = now.year + (1 if now.month == 12 else 0)
    days_in_month = (datetime.date(next_year, next_month, 1)
                     - datetime.timedelta(days=1)).day
    am_pm_upper = "AM" if h < 12 else "PM"
    am_pm_lower = "am" if h < 12 else "pm"
    return {
        "dh": h12, "dh11": h11, "dh24": h, "dh23": h,
        "dhutc12": h12, "dhutc12z": f"{h12:02d}",
        "dhutc24": h,   "dhutc24z": f"{h:02d}",
        "dht":    f"{h12}:{m:02d}", "dh24t": f"{h:02d}:{m:02d}",
        "dhz":   f"{h12:02d}", "dh11z": f"{h11:02d}",
        "dh24z": f"{h:02d}",   "dh23z": f"{h:02d}",
        "dhtt":   am_pm_upper, "dhto":   am_pm_lower,
        "dh11tt": am_pm_upper, "dh11to": am_pm_lower,
        "dh24tt": am_pm_upper, "dh24to": am_pm_lower,
        "dh23tt": am_pm_upper, "dh23to": am_pm_lower,
        "dm": m, "dmz": f"{m:02d}",
        "ds": s, "dsz": f"{s:02d}",
        "dss": s + ms / 1000, "dssz": f"{s:02d}", "dsps": ms,
        "da": 1 if h >= 12 else 0, "dtp": "true" if h >= 12 else "false",
        "drh": drh, "drh24": (h / 24) * 360, "drh0": drh,
        "drm": drm, "drs": drs, "drss": drss, "drms": drms,
        "depoch": int(now.timestamp()),
        "dd": now.day, "ddz": f"{now.day:02d}",
        "ddy": now.timetuple().tm_yday,
        "ddim": days_in_month,
        "ddw": wd, "ddww": wd, "ddw0": wd,
        "ddw1": _DN_FULL[wd], "ddw2": _DN_SHORT[wd],
        "dy": now.year, "dyy": now.year % 100,
        "dwm": (now.day - 1) // 7 + 1, "dw": wd,
        "dn": now.strftime("%b"), "dnn": now.strftime("%B"),
        "dnnn": str(now.month), "dnnnn": f"{now.month:02d}",
    }


def _preprocess_tags(text: str) -> str:
    """將 {tag} 替換為 _WM_TAGS["tag"]，只有大括號語法才觸發標籤替換。
    先處理整個字串常值只包一個 tag 的情形（連同引號一起替換掉），
    避免代換結果被引號吃成純文字。
    """
    text = _QUOTED_TAG_RE.sub(r'_WM_TAGS["\2"]', text)
    return _TAG_RE.sub(r'_WM_TAGS["\1"]', text)


def eval_lua_expr(text: str):
    """
    以 lupa LuaRuntime 求值單一 Lua 表達式。
    有來源 tag → 從系統時鐘注入；無來源 tag → 從 _TAG_VALUES 注入；其餘為 nil。
    執行超過 _EVAL_TIMEOUT_SECS 秒時由 debug hook 中斷並回傳 None。
    """
    global _lua_deadline
    lua = _get_lua()
    if lua is None:
        return None
    _lua_deadline = time.monotonic() + _EVAL_TIMEOUT_SECS
    try:
        g = lua.globals()
        # 0. base script 的 var_ 變數（圖層表達式可直接引用）
        for name, val in _VAR_VALUES.items():
            g[name] = val
        # 1. 建構完整標籤字典（auto 覆蓋同名手動值）
        all_tags: dict[str, object] = {}
        for name, val in _TAG_VALUES.items():
            if name not in _AUTO_TIME_TAG_NAMES:
                try:
                    all_tags[name] = float(val)
                except (ValueError, TypeError):
                    all_tags[name] = val
        all_tags.update(_compute_auto_time_tags())
        # var_ 變數亦可用 {var_xxx} tag 語法存取（手動 tag 與時間 tag 優先）
        for name, val in _VAR_VALUES.items():
            if name not in all_tags and isinstance(val, (int, float, str, bool)):
                all_tags[name] = val
        # 2. 以 lupa.table_from 建立 Lua table（每次 eval 都是全新快照）
        g["_WM_TAGS"] = lua.table_from(all_tags)
        return lua.eval(_preprocess_tags(text))
    except Exception:
        return None
    finally:
        _lua_deadline = float('inf')  # 還原為不逾時，避免影響下一次呼叫


def to_float(value, fallback: float = 0.0) -> float:
    """
    將值轉為 float。
    優先 float() 直轉；若為 Lua 表達式則用 eval_lua_expr 求值；失敗回傳 fallback。
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    result = eval_lua_expr(str(value))
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        return float(result)
    return fallback


def to_str(value) -> str:
    """
    將值轉為字串。若 Lua 求值結果為 str/int/float 則使用；
    table（含 {tag} 語法）/ nil / 其他型別一律回傳原始字串。
    """
    text = str(value)
    result = eval_lua_expr(text)
    if isinstance(result, (str, int, float)) and not isinstance(result, bool):
        return str(result)
    return text


def summon_components(attribute: dict, parent=None):
    """
    動態建立一個具有指定屬性的 QWidget 元件。

    Args:
        attribute: 屬性字典，鍵為屬性名稱，值為預設值
        parent: 父元件

    Returns:
        Component: 具有指定屬性的 QWidget 實例
    """
    slots = tuple(attribute.keys())

    class Component(QWidget):
        __slots__ = slots

        def __init__(self, parent=None):
            super().__init__(parent)
            for k, v in attribute.items():
                setattr(self, k, v)

    return Component(parent)


__all__ = ['summon_components']
