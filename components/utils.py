import datetime
import re

from PyQt6.QtWidgets import QWidget

# ── Lua 表達式求值工具 ────────────────────────────────────────────────────────

_LUA = None   # LuaRuntime 單例（延遲初始化）
_TAG_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
TAG_RE = _TAG_RE  # 公開別名

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


def set_tag_value(tag_name: str, value: str) -> None:
    """設定無來源 tag 的測試值（不含大括號的 tag 名稱）。"""
    _TAG_VALUES[tag_name] = value


def _get_lua():
    global _LUA
    if _LUA is None:
        try:
            from lupa import LuaRuntime
            _LUA = LuaRuntime(unpack_returned_tuples=True)
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
    """將 {tag} 替換為合法 Lua 識別字 __tag__，避免被誤解析為 table constructor。"""
    return _TAG_RE.sub(r'__\1__', text)


def eval_lua_expr(text: str):
    """
    以 lupa LuaRuntime 求值單一 Lua 表達式。
    有來源 tag → 從系統時鐘注入；無來源 tag → 從 _TAG_VALUES 注入；其餘為 nil。
    """
    lua = _get_lua()
    if lua is None:
        return None
    try:
        g = lua.globals()
        # 1. 無來源 tag 手動設定值（有來源的 tag 不覆蓋）
        for name, val in _TAG_VALUES.items():
            if name not in _AUTO_TIME_TAG_NAMES:
                try:
                    g[f"__{name}__"] = float(val)
                except (ValueError, TypeError):
                    g[f"__{name}__"] = val
        # 2. 有來源的時間/日期 tag（覆蓋優先）
        for name, val in _compute_auto_time_tags().items():
            g[f"__{name}__"] = val
        return lua.eval(_preprocess_tags(text))
    except Exception:
        return None


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
