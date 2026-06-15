"""
lua_script.py — Lua 腳本分頁面板

四個子面板：
  上半左  LuaEditorPanel   （語法高亮編輯器）
  上半右  _LuaPreviewCanvas（錶盤即時預覽）
  下半左  SyntaxPanel      （語法問題）
  下半右  _LuaObjectExplorer（物件可見性控制）

TODO（尚未實作）：
  - wm_action() 字串參數補全：偵測游標在 wm_action('...') 引號內時，
    提供 tap_action 常數清單（color_switch_next / w_app: / m_app: 等）。
  - wm_anim_set() 第二引數補全：偵測 wm_anim_set('name', '...') 時，
    提供 'anim_in' / 'dur_in' / 'anim_out' / 'dur_out' 等欄位名稱。
  - shader 參數 tooltip：當圖層屬性含 shader 欄位時，
    在 SyntaxPanel 或 hover tooltip 顯示 u_1~u_4 的語義說明
    （Segment: u_1=角度, u_2=偏移, u_3=內側不透明度；
     GradientLinear: u_1=起始色, u_2=終止色, u_3=角度°, u_4=不透明度%）。
  - tweens.* 動態補全：解析目前腳本中所有 wm_schedule{tween='...'} 呼叫，
    在圖層表達式輸入 'tweens.' 後提供已定義的 tween 名稱清單。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from antlr4 import InputStream, CommonTokenStream, Token
    from antlr4.error.ErrorListener import ErrorListener as _AntlrErrorListener
    from luaparser.parser.LuaLexer import LuaLexer as _LuaLexer
    from luaparser.parser.LuaParser import LuaParser as _LuaParser
    _HAS_LUAPARSER = True
except ImportError:
    _HAS_LUAPARSER = False

from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QSize, pyqtSignal, QEvent, QRectF,
)
from PyQt6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QPainter, QPalette,
    QTextCursor, QPixmap, QIcon,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QPlainTextEdit, QSplitter, QListWidget, QListWidgetItem,
    QSizePolicy, QScrollArea,
)
from components.utils import set_tag_value, TAG_RE, _AUTO_TIME_TAG_NAMES, _TAG_VALUES

if TYPE_CHECKING:
    from edit_watch import PanelWidgetManager

_IMG_EDIT_DIR = Path(__file__).parent / "img" / "edit"


# ── WatchMaker 常數 ──────────────────────────────────────────────────────────

WM_TAGS: list[str] = [
    # Date
    "{dd}", "{ddz}", "{ddy}", "{ddw1}", "{ddw2}", "{ddw}", "{ddww}",
    "{ddw1_1}", "{ddw2_1}", "{ddw_1}", "{ddww_1}",
    *[f"{{ddw{s}_{n}}}" for n in range(2, 6) for s in ("1", "2", "", "w")], "{ddw0}", "{ddim}",
    "{dn}", "{dnn}", "{dnnn}", "{dnnnn}", "{dy}", "{dyy}", "{dwm}", "{dw}",
    # Time
    "{dh}", "{dh11}", "{dh24}", "{dh23}",
    "{dhutc12}", "{dhutc12z}", "{dhutc24}", "{dhutc24z}", "{dutcoff}",
    "{dht}", "{dh24t}", "{dhz}", "{dh11z}", "{dh24z}", "{dh23z}",
    "{dhtt}", "{dhto}", "{dh11tt}", "{dh11to}", "{dh24tt}", "{dh24to}",
    "{dh23tt}", "{dh23to}",
    "{dm}", "{dmz}", "{dmt}", "{dmo}", "{dmat}", "{dmtt}", "{dmot}",
    "{ds}", "{dsz}", "{dst}", "{dso}", "{dsat}", "{dstt}", "{dsot}",
    "{da}", "{dss}", "{dssz}", "{dsps}", "{depoch}", "{dz}", "{dtp}",
    "{drh}", "{drh24}", "{drh0}", "{drm}", "{drs}", "{drss}", "{drms}",
    # Color / Counter
    "{ucolor}", "{ucolor_b}", "{c_elapsed}",
    "{c_0_100_2_st}", "{c_0_100_2_rp}", "{c_0_100_2_rv}", "{c_0_100_2_rv_2}",
    # Timezone (tz1–tz3)
    *[f"{{tz{n}{s}}}" for n in range(1, 4)
      for s in ("l", "ll", "o", "om", "dst", "t", "rh", "rh24", "rm")],
    # Battery
    "{bl}", "{blp}", "{br}", "{btc}", "{btf}", "{btcd}", "{btfd}", "{bc}",
    # Phone
    "{pbl}", "{pblp}", "{pbr}", "{pbtc}", "{pbtf}", "{pbtcd}", "{pbtfd}",
    "{pbc}", "{pws}", "{pwc}",
    # Device
    "{aname}", "{aman}", "{awname}", "{around}", "{atyre}", "{abright}",
    "{adimlo}", "{abss}", "{abssl}", "{alat}", "{alon}", "{alatd}", "{alond}",
    "{alatdd}", "{alondd}", "{aalt}", "{aw3w}", "{aw3w1}", "{aw3w2}", "{aw3w3}",
    # Stopwatch
    "{swh}", "{swm}", "{sws}", "{swss}", "{swsss}", "{swsst}",
    "{swr}", "{swrm}", "{swrs}", "{swrss}",
    # Weather
    "{wl}", "{wt}", "{wth}", "{wtl}", "{wtd}", "{wthd}", "{wtld}", "{wm}",
    "{wct}", "{wci}", "{wh}", "{whp}", "{wp}", "{wws}",
    "{wwd}", "{wwdb}", "{wwdbb}", "{wcl}", "{wr}",
    "{wsr}", "{wss}", "{wsrp}", "{wssp}", "{wmp}", "{wml}", "{wlu}",
    *[f"{{wf{d}{s}}}" for d in range(6)
      for s in ("dt", "dth", "dtl", "dct", "dci")],
    # Calendar (c1–c10)
    "{cex}",
    *[f"{{c{n}{s}}}" for n in range(1, 11)
      for s in ("ex", "t", "bd", "b", "br", "bp", "ed", "e", "er", "ep",
                "l", "c", "ad", "cal", "i")],
    # Health / Sensor
    "{ssc}", "{sdst}", "{sdstu}", "{scal}", "{stsc}", "{stdst}", "{stcal}",
    "{shr}", "{shr_1}", "{shr_2}",
    *[f"{{shr_{n}}}" for n in range(3, 9)],
    "{srh}", "{sprs}",
    "{sax}", "{say}", "{saz}", "{sgx}", "{sgy}", "{sgz}",
    "{scr}", "{sct}", "{sctd}", "{scb}", "{scbb}", "{sctdb}", "{sctdbb}",
    # Complication (m1–m4)
    *[f"{{m{n}{s}}}" for n in range(1, 5)
      for s in ("text", "title", "value", "min", "max")],
]

_WM_TAGS_NAMES: frozenset[str] = frozenset(t[1:-1] for t in WM_TAGS)

WM_API_NAMES: list[str] = [
    "wm_tag", "wm_action", "wm_schedule", "wm_unschedule_all",
    "wm_vibrate", "wm_sfx", "wm_transition",
    "wm_anim_set", "wm_anim_start",
    "is_bright",
    "on_hour", "on_minute", "on_second", "on_millisecond",
    "on_display_bright", "on_display_not_bright",
]

LUA_KEYWORDS: list[str] = [
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "if", "in", "local", "nil", "not", "or", "repeat",
    "return", "then", "true", "until", "while",
]

WM_EASING: list[str] = [
    "linear",
    "inQuad",    "outQuad",    "inOutQuad",    "outInQuad",
    "inCubic",   "outCubic",   "inOutCubic",   "outInCubic",
    "inQuart",   "outQuart",   "inOutQuart",   "outInQuart",
    "inQuint",   "outQuint",   "inOutQuint",   "outInQuint",
    "inSine",    "outSine",    "inOutSine",    "outInSine",
    "inExpo",    "outExpo",    "inOutExpo",    "outInExpo",
    "inCirc",    "outCirc",    "inOutCirc",    "outInCirc",
    "inElastic", "outElastic", "inOutElastic", "outInElastic",
    "inBack",    "outBack",    "inOutBack",    "outInBack",
    "inBounce",  "outBounce",  "inOutBounce",  "outInBounce",
]


# ── 語法檢查 ─────────────────────────────────────────────────────────────────

def _check_lua_syntax(text: str, numeric: bool = False,
                      expression_mode: bool = True) -> list[dict]:
    """
    以 luaparser（ANTLR4）做完整 Lua 語法分析。
    numeric=True：額外檢查最外層 return 值是否為字串型別（用於數值屬性欄位）。
    expression_mode=True：圖層屬性欄位單行表達式模式，只以 'return <text>' 解析。
    回傳 list[{line, col, message, level}]，按行號排序。
    """
    if _HAS_LUAPARSER:
        return _check_lua_syntax_luaparser(text, numeric, expression_mode)
    return _check_lua_syntax_fallback(text)


def _check_numeric_return(text: str) -> list[dict]:
    """
    檢查 'return <text>' 的最外層回傳值節點型別。
    若為 String 或 Concat（字串串接），回傳 error；其餘型別視為可能是數值，不報錯。
    """
    try:
        from luaparser import ast as lua_ast
        from luaparser.astnodes import String, Concat
        tree = lua_ast.parse("return " + text)
        if not tree or not tree.body or not tree.body.body:
            return []
        ret = tree.body.body[0]
        if not hasattr(ret, "values") or not ret.values:
            return []
        val = ret.values[0]
        if isinstance(val, (String, Concat)):
            return [{"line": 1, "col": 0,
                     "message": "expression must return a number", "level": "error"}]
    except Exception:
        pass
    return []


def _check_lua_syntax_luaparser(text: str, numeric: bool = False,
                                expression_mode: bool = True) -> list[dict]:
    class _Collector(_AntlrErrorListener):
        def __init__(self):
            super().__init__()
            self.errors: list[dict] = []

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            self.errors.append({
                "line":    line,
                "col":     column,
                "message": msg,
                "level":   "error",
            })

    def _parse(src: str) -> list[dict]:
        lexer = _LuaLexer(InputStream(src))
        lexer.removeErrorListeners()
        lc = _Collector()
        lexer.addErrorListener(lc)
        tokens = CommonTokenStream(lexer, channel=Token.DEFAULT_CHANNEL)
        parser = _LuaParser(tokens)
        parser.removeErrorListeners()
        pc = _Collector()
        parser.addErrorListener(pc)
        parser.start_()
        return lc.errors + pc.errors

    if expression_mode:
        # 圖層屬性欄位：只以 'return <text>' 解析（WatchMaker 只接受單一表達式）
        issues = _parse("return " + text)
        if not issues:
            if numeric:
                return _check_numeric_return(text)
            return []
        return sorted(issues, key=lambda x: x["line"])

    # base script 模式：先嘗試完整 Lua script 解析
    issues = _parse(text)
    if not issues:
        if numeric:
            return _check_numeric_return(text)
        return []

    # 若失敗，嘗試以 'return <text>' 解析（防止誤報純表達式）
    if not _parse("return " + text):
        if numeric:
            return _check_numeric_return(text)
        return []

    return sorted(issues, key=lambda x: x["line"])


def _check_lua_syntax_fallback(text: str) -> list[dict]:
    """備用：純 Python 括號 / block 關鍵字平衡檢查（luaparser 未安裝時使用）。"""
    issues: list[dict] = []
    n = len(text)
    line = 1
    processed: list[tuple[str, int]] = []
    i = 0

    def _skip_long(start: int, level: int) -> int:
        nonlocal line
        closing = "]" + "=" * level + "]"
        j = start
        while j < n:
            if text[j] == "\n":
                line += 1
            if text[j: j + len(closing)] == closing:
                return j + len(closing)
            j += 1
        return n

    while i < n:
        c = text[i]
        if c == "\n":
            processed.append(("\n", line)); line += 1; i += 1; continue
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            i += 2
            if i < n and text[i] == "[":
                eq, j = 0, i + 1
                while j < n and text[j] == "=": eq += 1; j += 1
                if j < n and text[j] == "[":
                    i = _skip_long(j + 1, eq); continue
            while i < n and text[i] != "\n": i += 1
            continue
        if c in ('"', "'"):
            q, sl, i = c, line, i + 1; closed = False
            while i < n:
                if text[i] == "\\" and i + 1 < n: i += 2; continue
                if text[i] == "\n": break
                if text[i] == q: closed = True; i += 1; break
                i += 1
            if not closed:
                issues.append({"line": sl, "col": 0,
                               "message": "Unterminated string literal", "level": "error"})
            continue
        if c == "[":
            eq, j = 0, i + 1
            while j < n and text[j] == "=": eq += 1; j += 1
            if j < n and text[j] == "[":
                i = _skip_long(j + 1, eq); continue
        processed.append((c, line)); i += 1

    bracket_stack: list[tuple[str, int]] = []
    match_close = {")": "(", "]": "[", "}": "{"}
    match_open  = {"(": ")", "[": "]", "{": "}"}
    block_stack: list[tuple[str, int]] = []
    pi, plen = 0, len(processed)
    while pi < plen:
        c, ln = processed[pi]
        if c in "([{":
            bracket_stack.append((c, ln)); pi += 1; continue
        if c in ")]}":
            if bracket_stack and bracket_stack[-1][0] == match_close[c]:
                bracket_stack.pop()
            elif bracket_stack:
                issues.append({"line": ln, "col": 0,
                               "message": (f"Bracket mismatch: '{c}' but opened "
                                           f"'{bracket_stack[-1][0]}' at line {bracket_stack[-1][1]}"),
                               "level": "error"})
                bracket_stack.pop()
            else:
                issues.append({"line": ln, "col": 0,
                               "message": f"Unexpected '{c}' without opening bracket",
                               "level": "error"})
            pi += 1; continue
        if c.isalpha() or c == "_":
            chars, wln = [c], ln; pi += 1
            while pi < plen and (processed[pi][0].isalnum() or processed[pi][0] == "_"):
                chars.append(processed[pi][0]); pi += 1
            word = "".join(chars)
            if word in ("if", "function", "do"): block_stack.append((word, wln))
            elif word == "repeat": block_stack.append(("repeat", wln))
            elif word == "end":
                if block_stack:
                    if block_stack[-1][0] == "repeat":
                        issues.append({"line": wln, "col": 0,
                                       "message": f"'end' cannot close 'repeat'; use 'until'",
                                       "level": "error"})
                    block_stack.pop()
                else:
                    issues.append({"line": wln, "col": 0,
                                   "message": "Unexpected 'end' (no matching opener)",
                                   "level": "error"})
            elif word == "until":
                if block_stack and block_stack[-1][0] == "repeat": block_stack.pop()
                else:
                    issues.append({"line": wln, "col": 0,
                                   "message": "'until' without matching 'repeat'",
                                   "level": "error"})
            continue
        pi += 1
    for bc, bln in bracket_stack:
        issues.append({"line": bln, "col": 0,
                       "message": f"Unclosed '{bc}' (missing '{match_open[bc]}')",
                       "level": "error"})
    for kw, kln in reversed(block_stack):
        close_kw = "until" if kw == "repeat" else "end"
        issues.append({"line": kln, "col": 0,
                       "message": f"'{kw}' block not closed (missing '{close_kw}')",
                       "level": "error"})
    return sorted(issues, key=lambda x: x["line"])


# ── 共用樣式輔助 ──────────────────────────────────────────────────────────────

def _section_hdr(text: str) -> "QLabel":
    """子面板標題列（24px，全大寫，與 PanelHeader 統一樣式）。"""
    lbl = QLabel(text.upper())
    lbl.setFixedHeight(24)
    lbl.setStyleSheet(
        "QLabel {"
        "  background: #1E1E1E;"
        "  color: #61FFFFFF;"
        "  font-size: 10px;"
        "  font-weight: 600;"
        "  letter-spacing: 1px;"
        "  padding-left: 10px;"
        "  border-bottom: 1px solid #1FFFFFFF;"
        "}"
    )
    return lbl


# ── 語法高亮 ─────────────────────────────────────────────────────────────────

class LuaHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)

        def _fmt(hex_color: str, bold=False, italic=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(hex_color))
            if bold:   f.setFontWeight(QFont.Weight.Bold)
            if italic: f.setFontItalic(True)
            return f

        self._rules = [
            (re.compile(
                r"\b(?:and|break|do|else|elseif|end|false|for|function|"
                r"if|in|local|nil|not|or|repeat|return|then|true|until|while)\b"
             ), _fmt("#90CAF9", bold=True)),
            (re.compile(r"\b(?:" + "|".join(WM_API_NAMES) + r")\b"),
             _fmt("#03DAC6", bold=True)),
            (re.compile(r"\b(?:" + "|".join(WM_EASING) + r")\b"),
             _fmt("#CE93D8")),
            (re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}"),
             _fmt("#FFB74D")),
            (re.compile(r"\bvar_\w+"),      _fmt("#FFD54F")),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), _fmt("#81C784")),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), _fmt("#81C784")),
            (re.compile(r"--[^\n]*"),        _fmt("#61FFFFFF", italic=True)),
            (re.compile(r"\b\d+(?:\.\d+)?\b"), _fmt("#CE93D8")),
        ]

    def highlightBlock(self, text: str):
        for pat, fmt in self._rules:
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── 行號邊距 ─────────────────────────────────────────────────────────────────

class _LineArea(QWidget):
    def __init__(self, editor: "_CodeEdit"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor._line_w(), 0)

    def paintEvent(self, event):
        self._editor._paint_lines(event, self)


class _CodeEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lnum = _LineArea(self)
        self.blockCountChanged.connect(self._upd_margin)
        self.updateRequest.connect(self._scroll_lnum)
        self._upd_margin(0)

    def _line_w(self) -> int:
        return max(3, len(str(self.blockCount()))) \
               * self.fontMetrics().horizontalAdvance("9") + 12

    def _upd_margin(self, _):
        self.setViewportMargins(self._line_w(), 0, 0, 0)

    def _scroll_lnum(self, rect, dy):
        if dy:
            self._lnum.scroll(0, dy)
        else:
            self._lnum.update(0, rect.y(), self._lnum.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._upd_margin(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lnum.setGeometry(cr.left(), cr.top(), self._line_w(), cr.height())

    def _paint_lines(self, event, area: QWidget):
        p = QPainter(area)
        p.fillRect(event.rect(), QColor("#0A0A10"))
        blk = self.firstVisibleBlock()
        bn  = blk.blockNumber()
        top = self.blockBoundingGeometry(blk).translated(self.contentOffset()).top()
        bot = top + self.blockBoundingRect(blk).height()
        while blk.isValid() and top <= event.rect().bottom():
            if blk.isVisible() and bot >= event.rect().top():
                p.setPen(QColor("#61FFFFFF"))
                p.drawText(0, int(top), area.width() - 4,
                           int(self.blockBoundingRect(blk).height()),
                           Qt.AlignmentFlag.AlignRight, str(bn + 1))
            blk = blk.next()
            top = bot
            bot = top + self.blockBoundingRect(blk).height()
            bn += 1
        p.end()


# ── 自動補全彈出 ──────────────────────────────────────────────────────────────

class _CompletionPopup(QListWidget):
    completed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tool 型視窗不建立 keyboard grab（Popup 型會搶走所有鍵盤事件）
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMaximumHeight(180)
        self.setFixedWidth(260)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QListWidget {
                background: #222222;
                border: 1px solid #2AFFFFFF;
                border-radius: 6px;
                color: #DEFFFFFF;
                font-size: 12px;
                outline: none;
                padding: 3px;
            }
            QListWidget::item {
                padding: 4px 10px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #2090CAF9;
                color: #90CAF9;
            }
            QListWidget::item:hover:!selected {
                background: #14FFFFFF;
            }
        """)
        self.itemClicked.connect(lambda item: self.completed.emit(item.text()))

    def show_at(self, global_pos: QPoint, items: list[str]):
        self.clear()
        for it in items:
            self.addItem(it)
        if items:
            self.setCurrentRow(0)
            self.move(global_pos)
            self.show()
        else:
            self.hide()

    def move_sel(self, d: int):
        self.setCurrentRow(max(0, min(self.currentRow() + d, self.count() - 1)))

    def confirm(self) -> str | None:
        item = self.currentItem()
        if item:
            t = item.text()
            self.completed.emit(t)
            self.hide()
            return t
        return None


# ── 編輯器面板 ────────────────────────────────────────────────────────────────

# 顏色是在 QPalette 中設定的，因此它不包含在 QSS 中（以避免與 QSyntaxHighlighter 衝突）
_EDIT_QSS = """
QPlainTextEdit {
    background: #0E0E13;
    border: none;
    font-family: Consolas, "Courier New", monospace;
    font-size: 13px;
    selection-background-color: #2090CAF9;
    selection-color: #DEFFFFFF;
}
"""
_TB_BTN = """
QPushButton {
    background: transparent;
    color: #99FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QPushButton:hover   { background: #14FFFFFF; color: #DEFFFFFF; }
QPushButton:pressed { background: #1A90CAF9; color: #90CAF9; }
"""


class LuaEditorPanel(QWidget):
    text_changed    = pyqtSignal(str)
    apply_requested = pyqtSignal()

    def __init__(self, initial_text: str = "", parent=None):
        super().__init__(parent)
        self._popup      = _CompletionPopup()
        self._comp_start = -1
        self._comp_mode  = ""
        self._popup.completed.connect(self._insert_completion)
        self._build(initial_text)

    def _build(self, text: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 工具列：Undo / Redo + 右側語言標示
        tb = QWidget()
        tb.setFixedHeight(30)
        tb.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #1FFFFFFF;")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(4, 0, 8, 0)
        tl.setSpacing(2)

        def _btn(label: str, tip: str = "") -> QPushButton:
            b = QPushButton(label)
            b.setStyleSheet(_TB_BTN)
            b.setFixedHeight(24)
            if tip:
                b.setToolTip(tip)
            return b

        undo_b = _btn("↩", "Undo  Ctrl+Z")
        redo_b = _btn("↪", "Redo  Ctrl+Y")
        tl.addWidget(undo_b)
        tl.addWidget(redo_b)
        tl.addStretch()

        lang_lbl = QLabel("LUA")
        lang_lbl.setStyleSheet(
            "color: #4290CAF9; font-size: 10px; font-weight: 700;"
            " padding-right: 2px;"
        )
        tl.addWidget(lang_lbl)
        root.addWidget(tb)

        self._edit = _CodeEdit()
        self._edit.setStyleSheet(_EDIT_QSS)

        # 文字顏色以 QPalette 設定，避免 QSS color 覆蓋 QSyntaxHighlighter 的 setFormat
        pal = self._edit.palette()
        pal.setColor(QPalette.ColorRole.Base,            QColor(0x0E, 0x0E, 0x13))
        pal.setColor(QPalette.ColorRole.Text,            QColor(255, 255, 255, 222))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 97))
        pal.setColor(QPalette.ColorRole.Highlight,       QColor(0x90, 0xCA, 0xF9, 48))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255, 222))
        self._edit.setPalette(pal)

        self._edit.setPlainText(text)
        self._edit.setTabStopDistance(
            4 * self._edit.fontMetrics().horizontalAdvance(" "))
        self._highlighter = LuaHighlighter(self._edit.document())
        self._edit.textChanged.connect(
            lambda: self.text_changed.emit(self._edit.toPlainText()))
        self._edit.textChanged.connect(self._maybe_complete)
        # event filter 攔截補全快捷鍵，保留 Enter 為正常換行
        self._edit.installEventFilter(self)
        root.addWidget(self._edit)

        undo_b.clicked.connect(self._edit.undo)
        redo_b.clicked.connect(self._edit.redo)

    def get_text(self) -> str:
        return self._edit.toPlainText()

    def set_text(self, t: str):
        self._edit.setPlainText(t)

    def eventFilter(self, obj, event):
        if obj is not self._edit:
            return False
        # 失焦時關閉補全視窗
        if event.type() == QEvent.Type.FocusOut:
            self._popup.hide()
            return False
        if event.type() != QEvent.Type.KeyPress:
            return False
        k = event.key()
        if self._popup.isVisible():
            if k == Qt.Key.Key_Up:
                self._popup.move_sel(-1)
                return True
            if k == Qt.Key.Key_Down:
                self._popup.move_sel(1)
                return True
            if k == Qt.Key.Key_Tab:
                self._popup.confirm()
                return True
            if k == Qt.Key.Key_Escape:
                self._popup.hide()
                return True
            # 其他鍵（含 Enter）正常傳遞，不強制選取補全
        if (k in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.apply_requested.emit()
            return True
        return False

    # ── 自動補全 ──────────────────────────────────────────────────

    def _maybe_complete(self):
        cur = self._edit.textCursor()
        btxt = cur.block().text()
        pos = cur.positionInBlock()
        if pos == 0:
            self._popup.hide()
            return

        # Tag 補全：找最近的未閉合 {
        tag_start = -1
        for k in range(pos - 1, -1, -1):
            if btxt[k] == "{":   tag_start = k; break
            if btxt[k] == "}":   break
        if tag_start >= 0:
            prefix = btxt[tag_start + 1: pos]
            cands = [t for t in WM_TAGS
                     if t[1:-1].lower().startswith(prefix.lower())][:20]
            if cands:
                self._comp_mode = "tag"
                self._comp_start = tag_start
                self._popup.show_at(
                    self._edit.viewport().mapToGlobal(
                        self._edit.cursorRect().bottomLeft()), cands)
                return

        # 單字補全：WM API（優先）+ Lua 保留字
        ws = pos
        while ws > 0 and (btxt[ws - 1].isalnum() or btxt[ws - 1] == "_"):
            ws -= 1
        word = btxt[ws:pos]
        if len(word) >= 2:
            api_cands    = [a for a in WM_API_NAMES if a.startswith(word)]
            easing_cands = [e for e in WM_EASING if e.startswith(word)]
            kw_cands     = [k for k in LUA_KEYWORDS if k.startswith(word)]
            cands = (api_cands + easing_cands + kw_cands)[:15]
            if cands:
                self._comp_mode = "word"
                self._comp_start = ws
                self._popup.show_at(
                    self._edit.viewport().mapToGlobal(
                        self._edit.cursorRect().bottomLeft()), cands)
                return
        self._popup.hide()

    def _insert_completion(self, text: str):
        cur = self._edit.textCursor()
        pos = cur.positionInBlock()
        bp  = cur.block().position()
        if self._comp_mode == "tag":
            cur.setPosition(bp + self._comp_start)
            cur.setPosition(bp + pos, QTextCursor.MoveMode.KeepAnchor)
            cur.insertText(text)
        else:  # "word" mode（WM API 加括號，Lua 保留字直接插入）
            cur.setPosition(bp + self._comp_start)
            cur.setPosition(bp + pos, QTextCursor.MoveMode.KeepAnchor)
            if text in WM_API_NAMES:
                cur.insertText(text + "()")
                c2 = self._edit.textCursor()
                c2.movePosition(QTextCursor.MoveOperation.Left,
                                QTextCursor.MoveMode.MoveAnchor)
                self._edit.setTextCursor(c2)
            else:
                cur.insertText(text)
        self._popup.hide()
        self._edit.setFocus()


# ── 語法問題面板 ──────────────────────────────────────────────────────────────

class SyntaxPanel(QWidget):
    jump_to_line = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_section_hdr("Syntax Issues"))

        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: #0E0E13;
                border: none;
                color: #DEFFFFFF;
                font-size: 12px;
                font-family: Consolas, "Courier New", monospace;
                outline: none;
            }
            QListWidget::item {
                padding: 4px 12px;
                border-bottom: 1px solid #0AFFFFFF;
            }
            QListWidget::item:last { border-bottom: none; }
            QListWidget::item:selected {
                background: #1A90CAF9;
                color: #DEFFFFFF;
            }
            QListWidget::item:hover:!selected {
                background: #0AFFFFFF;
            }
        """)
        self._list.itemClicked.connect(
            lambda item: self.jump_to_line.emit(
                item.data(Qt.ItemDataRole.UserRole) or 1))
        root.addWidget(self._list)

    def update_issues(self, issues: list[dict]):
        self._list.clear()
        for iss in issues:
            lvl   = iss.get("level", "error")
            icon  = "✕" if lvl == "error" else "⚠"
            color = "#CF6679" if lvl == "error" else "#FFB74D"
            item  = QListWidgetItem(f"{icon}  L{iss['line']}  {iss['message']}")
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, iss["line"])
            self._list.addItem(item)


# ── Tags Settings Panel ───────────────────────────────────────────────────────

_TAG_CHIP_QSS = (
    "QLabel {"
    "  background: #1FFFB74D;"
    "  color: #FFB74D;"
    "  border: 1px solid #33FFB74D;"
    "  border-radius: 3px;"
    "  font-size: 10px;"
    "  font-weight: 600;"
    "  padding: 1px 5px;"
    "}"
)
_TAG_CHIP_UNKNOWN_QSS = (
    "QLabel {"
    "  background: #14FFFFFF;"
    "  color: #99FFFFFF;"
    "  border: 1px solid #1FFFFFFF;"
    "  border-radius: 3px;"
    "  font-size: 10px;"
    "  font-weight: 600;"
    "  padding: 1px 5px;"
    "}"
)
_TAG_INPUT_QSS = """
QLineEdit {
    background: #0E0E13;
    color: #DEFFFFFF;
    border: 1px solid #1FFFFFFF;
    border-radius: 3px;
    font-size: 11px;
    padding: 1px 4px;
}
QLineEdit:focus { border-color: #4490CAF9; }
"""


class _TagsPanel(QWidget):
    tags_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, QLineEdit] = {}

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(_section_hdr("Tag Values"))

        # scroll 始終存在；placeholder / row 都放在 scroll 內
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: #0E0E13; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 5px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1FFFFFFF; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #3AFFFFFF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        vl.addWidget(scroll, stretch=1)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: #0E0E13;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(8, 6, 8, 6)
        self._inner_layout.setSpacing(4)

        self._placeholder = QLabel("No tags in expression")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            "QLabel { color: #61FFFFFF; font-size: 11px; padding: 16px; "
            "background: transparent; }"
        )
        self._inner_layout.addWidget(self._placeholder)
        self._inner_layout.addStretch()
        scroll.setWidget(self._inner)

    def update_tags(self, text: str):
        """掃描 text 中的 tag，只顯示無來源 tag 的 row。"""
        found_order: list[str] = []
        seen: set[str] = set()
        for m in TAG_RE.finditer(text):
            name = m.group(1)
            if name not in _AUTO_TIME_TAG_NAMES and name not in seen:
                seen.add(name)
                found_order.append(name)

        # 移除消失的 tag
        for name in list(self._rows):
            if name not in seen:
                self._remove_row(name)

        # 依序新增新 tag（保留已在 _TAG_VALUES 中的值）
        for name in found_order:
            if name not in self._rows:
                self._add_row(name)

        self._placeholder.setVisible(not bool(self._rows))

    def _add_row(self, tag_name: str):
        row = QWidget()
        row.setFixedHeight(28)
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        chip = QLabel(f"{{{tag_name}}}")
        chip.setFixedHeight(20)
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(
            _TAG_CHIP_QSS if tag_name in _WM_TAGS_NAMES else _TAG_CHIP_UNKNOWN_QSS)
        rl.addWidget(chip)

        inp = QLineEdit()
        inp.setFixedHeight(22)
        inp.setStyleSheet(_TAG_INPUT_QSS)
        inp.setPlaceholderText("value")
        if tag_name in _TAG_VALUES:
            inp.setText(_TAG_VALUES[tag_name])
        inp.textChanged.connect(lambda val, n=tag_name: self._on_value_changed(n, val))
        rl.addWidget(inp)

        # 插入到 stretch 之前
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
        self._rows[tag_name] = inp

    def _remove_row(self, tag_name: str):
        inp = self._rows.pop(tag_name, None)
        if inp is None:
            return
        row = inp.parentWidget()
        if row is not None:
            self._inner_layout.removeWidget(row)
            row.deleteLater()

    def _on_value_changed(self, tag_name: str, value: str):
        set_tag_value(tag_name, value)
        self.tags_changed.emit()


# ── 錶盤預覽（離屏渲染）────────────────────────────────────────────────────────

class _LuaPreviewCanvas(QWidget):
    """以離屏渲染方式顯示主要編輯區相同場景的唯讀預覽。"""

    def __init__(self, panel_mgr: "PanelWidgetManager", parent=None):
        super().__init__(parent)
        self._panel_mgr  = panel_mgr
        self._hidden_ids: set[int] = set()

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        vl.addWidget(_section_hdr("Watch Preview"))

        self._canvas = QLabel()
        self._canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas.setStyleSheet("background: #0A0A10;")
        vl.addWidget(self._canvas, stretch=1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        panel_mgr.attr_changed.connect(self._schedule_refresh)
        panel_mgr.instance_selected.connect(self._schedule_refresh)
        panel_mgr.lua_committed.connect(self._schedule_refresh)

        QTimer.singleShot(300, self._refresh)

    def set_hidden_ids(self, hidden: set[int]):
        self._hidden_ids = hidden
        self._schedule_refresh()

    def _schedule_refresh(self, *_):
        self._timer.start(80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_refresh()

    def _refresh(self):
        scene = self._panel_mgr._edit_view._canvas.scene()
        if scene is None:
            return
        rect = scene.sceneRect()
        if rect.isEmpty() or rect.width() <= 0 or rect.height() <= 0:
            return

        size = self._canvas.size()
        if size.width() <= 0 or size.height() <= 0:
            return

        # 暫時隱藏 Lua explorer 標記的物件（渲染後立即還原，避免主畫布閃爍）
        items_to_restore: list = []
        for inst_id in self._hidden_ids:
            inst = self._panel_mgr._instances.get(inst_id)
            if inst:
                ci = inst.get("canvas_item")
                if ci is not None and ci.isVisible():
                    ci.setVisible(False)
                    items_to_restore.append(ci)

        # 暫時隱藏選取 overlay（自訂 _SelectionOverlay / _MultiSelectOverlay）
        overlay       = getattr(scene, "_overlay",       None)
        multi_overlay = getattr(scene, "_multi_overlay", None)
        ov_vis  = overlay       is not None and overlay.isVisible()
        mov_vis = multi_overlay is not None and multi_overlay.isVisible()
        if ov_vis:
            overlay.hide()
        if mov_vis:
            multi_overlay.hide()

        scale = min(size.width() / rect.width(), size.height() / rect.height())
        pw = max(1, int(rect.width() * scale))
        ph = max(1, int(rect.height() * scale))
        pixmap = QPixmap(pw, ph)
        pixmap.fill(QColor("#0A0A10"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scene.render(painter, QRectF(0, 0, pw, ph), rect)
        painter.end()

        if ov_vis:
            overlay.show()
        if mov_vis:
            multi_overlay.show()
        for ci in items_to_restore:
            ci.setVisible(True)

        self._canvas.setPixmap(pixmap)


# ── 物件可見性控制（Lua 用） ──────────────────────────────────────────────────

_EYE_PIXMAP:       "QPixmap | None" = None
_EYE_CROSS_PIXMAP: "QPixmap | None" = None


def _get_eye_px() -> tuple[QPixmap, QPixmap]:
    global _EYE_PIXMAP, _EYE_CROSS_PIXMAP
    if _EYE_PIXMAP is None:
        _EYE_PIXMAP       = QPixmap(str(_IMG_EDIT_DIR / "eye-light.png"))
        _EYE_CROSS_PIXMAP = QPixmap(str(_IMG_EDIT_DIR / "eye-crossed-light.png"))
    return _EYE_PIXMAP, _EYE_CROSS_PIXMAP


class _LuaObjectExplorer(QWidget):
    """同步主要物件總管的資料；眼睛圖示僅控制 preview 中的可見性。"""

    def __init__(self, panel_mgr: "PanelWidgetManager",
                 preview: "_LuaPreviewCanvas", parent=None):
        super().__init__(parent)
        self._panel_mgr  = panel_mgr
        self._preview    = preview
        self._hidden_ids: set[int] = set()

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        vl.addWidget(_section_hdr("Objects"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: #121212; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 5px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1FFFFFFF; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #3AFFFFFF; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: transparent; }
        """)
        vl.addWidget(scroll)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: #0E0E13;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.addStretch()
        scroll.setWidget(self._inner)

        panel_mgr.instance_selected.connect(self._refresh_list)

        # 定期同步（補捉 undo/redo 後的 instance 變化）
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._refresh_list)
        self._sync_timer.start(1000)

        QTimer.singleShot(100, self._refresh_list)

    def _refresh_list(self, *_):
        # 清空現有 rows（保留尾端 stretch）
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        eye_px, cross_px = _get_eye_px()
        icon_size = 16

        for inst_id, inst in self._panel_mgr._instances.items():
            name     = inst["values"].get("Name", f"Object {inst_id}")
            obj_type = inst.get("object_type", "")
            is_hidden = inst_id in self._hidden_ids

            row = QWidget()
            row.setFixedHeight(30)
            row.setObjectName("ObjRow")
            row.setStyleSheet(
                "QWidget#ObjRow { background: transparent; }"
                "QWidget#ObjRow:hover { background: #0FFFFFFF; }"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 0, 8, 0)
            rl.setSpacing(6)

            eye_btn = QPushButton()
            eye_btn.setFixedSize(20, 20)
            eye_btn.setFlat(True)
            eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            eye_btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
            px = cross_px if is_hidden else eye_px
            scaled = px.scaled(icon_size, icon_size,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            eye_btn.setIcon(QIcon(scaled))
            eye_btn.setIconSize(QSize(icon_size, icon_size))
            eye_btn.clicked.connect(
                lambda _c=False, _id=inst_id: self._toggle(_id))
            rl.addWidget(eye_btn)

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                f"color: {'#61FFFFFF' if is_hidden else '#DEFFFFFF'}; font-size: 12px;")
            rl.addWidget(name_lbl)
            rl.addStretch()

            type_lbl = QLabel(obj_type)
            type_lbl.setStyleSheet("color: #61FFFFFF; font-size: 10px;")
            rl.addWidget(type_lbl)

            self._inner_layout.insertWidget(
                self._inner_layout.count() - 1, row)

    def _toggle(self, inst_id: int):
        if inst_id in self._hidden_ids:
            self._hidden_ids.discard(inst_id)
        else:
            self._hidden_ids.add(inst_id)
        self._preview.set_hidden_ids(set(self._hidden_ids))
        self._refresh_list()


# ── 簡單 header ───────────────────────────────────────────────────────────────

class _LuaHeader(QWidget):
    def __init__(self, title: str, numeric: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setObjectName("LuaHeader")
        self.setStyleSheet(
            "#LuaHeader { background: #1E1E1E; border-bottom: 1px solid #1FFFFFFF; }")

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 8, 0)
        h.setSpacing(8)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            "color: #DEFFFFFF; font-size: 12px; font-weight: 500;")
        h.addWidget(self._title)

        if numeric:
            badge = QLabel("NUMERIC")
            badge.setStyleSheet(
                "QLabel {"
                "  background: #1481C784;"
                "  color: #81C784;"
                "  border: 1px solid #3081C784;"
                "  border-radius: 3px;"
                "  font-size: 9px;"
                "  font-weight: 700;"
                "  padding: 1px 5px;"
                "}"
            )
            h.addWidget(badge)

        h.addStretch()

        self._ok_label = QLabel("✓  Applied")
        self._ok_label.setStyleSheet(
            "color: #81C784; font-size: 11px; font-weight: 500;"
        )
        self._ok_label.hide()
        h.addWidget(self._ok_label)

    def show_applied(self):
        self._ok_label.show()
        QTimer.singleShot(2000, self._ok_label.hide)


# ── LuaScriptPanel ────────────────────────────────────────────────────────────

_SP_QSS = (
    "QSplitter::handle { background: #14FFFFFF; }"
    "QSplitter::handle:hover { background: #2AFFFFFF; }"
    "QSplitter::handle:horizontal { width: 1px; }"
    "QSplitter::handle:vertical { height: 1px; }"
)


class LuaScriptPanel(QWidget):
    """
    Lua 腳本大面板（TabWidgetManager 分頁內容）。
    上半：LuaEditorPanel | Watch Preview
    下半：Syntax Issues   | Object Explorer
    """

    script_committed = pyqtSignal(str)

    def __init__(self, object_name: str, field_name: str,
                 initial_value: str, panel_mgr: "PanelWidgetManager",
                 numeric: bool = False, expression_mode: bool = True,
                 parent=None):
        super().__init__(parent)
        title = f"{object_name}  —  {field_name}"
        self.setWindowTitle(title)
        self.setStyleSheet("background: #0E0E13;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = _LuaHeader(title, numeric=numeric)
        root.addWidget(self._header)

        self._v_split = QSplitter(Qt.Orientation.Vertical)
        self._v_split.setHandleWidth(1)
        self._v_split.setChildrenCollapsible(False)
        self._v_split.setStyleSheet(_SP_QSS)
        root.addWidget(self._v_split)

        # 上半：editor (左) + preview (右)
        self._top = QSplitter(Qt.Orientation.Horizontal)
        self._top.setHandleWidth(1)
        self._top.setChildrenCollapsible(False)
        self._top.setStyleSheet(_SP_QSS)
        self._editor  = LuaEditorPanel(initial_value)
        self._preview = _LuaPreviewCanvas(panel_mgr)
        self._top.addWidget(self._editor)
        self._top.addWidget(self._preview)
        self._top.setSizes([600, 220])

        # 下半：tags (左) + syntax (中) + explorer (右)
        self._bot = QSplitter(Qt.Orientation.Horizontal)
        self._bot.setHandleWidth(1)
        self._bot.setChildrenCollapsible(False)
        self._bot.setStyleSheet(_SP_QSS)
        self._tags_panel = _TagsPanel()
        self._syntax   = SyntaxPanel()
        self._explorer = _LuaObjectExplorer(panel_mgr, self._preview)
        self._bot.addWidget(self._tags_panel)
        self._bot.addWidget(self._syntax)
        self._bot.addWidget(self._explorer)
        self._bot.setSizes([180, 420, 220])

        self._v_split.addWidget(self._top)
        self._v_split.addWidget(self._bot)
        self._v_split.setSizes([420, 200])

        self._numeric          = numeric
        self._expression_mode  = expression_mode
        self._last_applied     = initial_value
        self._panel_mgr        = panel_mgr

        self._editor.text_changed.connect(self._on_text_changed)
        self._editor.text_changed.connect(self._tags_panel.update_tags)
        self._editor.apply_requested.connect(self._on_apply)   # Ctrl+↵ 即時套用
        self._syntax.jump_to_line.connect(self._jump_line)
        self._tags_panel.tags_changed.connect(self._on_tags_changed)

        # debounce auto-apply：輸入停止 400ms 後自動套用
        self._auto_apply_timer = QTimer(self)
        self._auto_apply_timer.setSingleShot(True)
        self._auto_apply_timer.timeout.connect(self._on_apply)
        self._editor.text_changed.connect(
            lambda _: self._auto_apply_timer.start(400))

        # 週期 refresh：每 1s 以最新時間 tag 值重算畫面
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._on_time_refresh)
        self._refresh_timer.start()

        QTimer.singleShot(80, lambda: (
            self._on_text_changed(initial_value),
            self._tags_panel.update_tags(initial_value),
        ))

    def _on_text_changed(self, text: str):
        self._syntax.update_issues(_check_lua_syntax(
            text, numeric=self._numeric, expression_mode=self._expression_mode))

    def _on_apply(self):
        text = self._editor.get_text()
        self._last_applied = text
        self.script_committed.emit(text)
        self._header.show_applied()

    def can_close(self) -> bool:
        """TabWidget._on_close 關閉前呼叫；停止 timer 並套用尚未 debounce 的變更。"""
        self._auto_apply_timer.stop()
        self._refresh_timer.stop()
        if self._editor.get_text() != self._last_applied:
            self._on_apply()
        return True

    def _jump_line(self, line: int):
        doc = self._editor._edit.document()
        blk = doc.findBlockByLineNumber(line - 1)
        if blk.isValid():
            c = QTextCursor(blk)
            self._editor._edit.setTextCursor(c)
            self._editor._edit.setFocus()

    def _on_tags_changed(self):
        self._preview._schedule_refresh()
        self._panel_mgr.refresh_all_instances()
        self._on_text_changed(self._editor.get_text())

    def _on_time_refresh(self):
        """週期 refresh：以最新系統時間重算所有 canvas item 的有來源 tag 值。"""
        self._panel_mgr.refresh_all_instances()
        self._preview._schedule_refresh()
