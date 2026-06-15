"""
all_test/main.py — Minimalist Dark 視覺展示
以 test_design.txt 定義的 Minimalist Dark 設計系統重新詮釋應用主畫面。
執行方式（從專案根目錄）：python all_test/main.py
"""

import sys
import ctypes
import ctypes.wintypes
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QMenuBar, QMenu, QScrollArea, QLineEdit, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QSize, QTimer, QObject, QEvent,
    QAbstractNativeEventFilter, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPixmap, QBrush, QCursor, QFont,
    QRadialGradient, QIcon,
)

_PARENT   = Path(__file__).resolve().parent.parent
_SAVES    = _PARENT / "saves"
_ICON_DIR = _PARENT / "img" / "my_watches"

sys.path.insert(0, str(_PARENT))
from special_ui import FlowLayout

# ── 縮放邊距常數 ──────────────────────────────────────────────────────────────
RESIZE_MARGIN    = 8
_HT_LEFT         = 10
_HT_RIGHT        = 11
_HT_TOP          = 12
_HT_TOP_LEFT     = 13
_HT_TOP_RIGHT    = 14
_HT_BOTTOM       = 15
_HT_BOTTOM_LEFT  = 16
_HT_BOTTOM_RIGHT = 17

# ── Minimalist Dark 設計 Token ────────────────────────────────────────────────
_BG      = "#0A0A0F"
_BG_ALT  = "#12121A"
_MUTED   = "#1A1A24"
_ACCENT  = "#F59E0B"
_FG      = "rgba(250,250,250,0.87)"

# 排序按鈕樣式：active 用琥珀底，inactive 用深色底
_BTN_ACTIVE = f"""
    QPushButton {{
        background-color: {_ACCENT};
        color: {_BG};
        border: none;
        border-radius: 4px;
        font-size: 12px;
    }}
"""
_BTN_INACTIVE = """
    QPushButton {
        background-color: #1E1E2A;
        color: rgba(250,250,250,0.50);
        border: none;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: rgba(245,158,11,0.15);
        color: rgba(250,250,250,0.87);
    }
"""

_STYLESHEET = f"""
QWidget#title_bar {{
    background-color: {_BG_ALT};
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
QLabel#title_label {{
    color: {_FG};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding-left: 4px;
}}
QPushButton#btn_min, QPushButton#btn_max {{
    background: transparent;
    border: none;
    color: rgba(250,250,250,0.35);
    font-size: 13px;
}}
QPushButton#btn_min:hover, QPushButton#btn_max:hover {{
    background: rgba(245,158,11,0.15);
    color: rgba(250,250,250,0.87);
}}
QPushButton#btn_close {{
    background: transparent;
    border: none;
    color: rgba(250,250,250,0.35);
    font-size: 13px;
}}
QPushButton#btn_close:hover {{
    background: #EF4444;
    color: #FFFFFF;
}}
QMenuBar {{
    background-color: {_BG_ALT};
    color: {_FG};
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding: 2px 0;
    font-size: 13px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: rgba(255,255,255,0.05);
}}
QMenuBar::item:pressed {{
    background: rgba(245,158,11,0.10);
}}
QMenu {{
    background-color: #16161F;
    color: {_FG};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 7px 32px 7px 16px;
    border-radius: 4px;
    margin: 1px 4px;
}}
QMenu::item:selected {{
    background: rgba(245,158,11,0.12);
    color: {_ACCENT};
}}
QMenu::item:disabled {{
    color: rgba(250,250,250,0.22);
}}
QMenu::separator {{
    height: 1px;
    background: rgba(255,255,255,0.06);
    margin: 4px 0;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.10);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(245,158,11,0.45);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


# ── 工具函式 ──────────────────────────────────────────────────────────────────
def _tint(path: Path, color: QColor, size: int) -> QIcon:
    """圖示著色：將非透明像素填為指定顏色"""
    px = QPixmap(str(path)).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    dst = QPixmap(px.size())
    dst.fill(Qt.GlobalColor.transparent)
    p = QPainter(dst)
    p.drawPixmap(0, 0, px)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(dst.rect(), color)
    p.end()
    return QIcon(dst)


def _make_logo(size: int = 16) -> QPixmap:
    """琥珀色圓形 logo 佔位圖示"""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(_ACCENT)))
    p.setPen(Qt.PenStyle.NoPen)
    r = 2
    p.drawEllipse(r, r, size - r * 2, size - r * 2)
    p.end()
    return px


_CLR_ON_ACTIVE = QColor(0x0A, 0x0A, 0x0F)   # 琥珀底上的深色圖示
_CLR_INACTIVE  = QColor(0x90, 0x90, 0xA0)   # 未選中圖示色


# ── 手錶卡片（Minimalist Dark 風格）─────────────────────────────────────────
class _WatchCard(QWidget):
    clicked = pyqtSignal(str)

    _STYLE_NORMAL = """
        #WatchCard {
            background-color: #1A1A24;
            border: 1px solid rgba(255,255,255,18);
            border-radius: 12px;
        }
    """
    _STYLE_HOVER = """
        #WatchCard {
            background-color: #1E1E2C;
            border: 1px solid rgba(245,158,11,90);
            border-radius: 12px;
        }
    """

    def __init__(self, name: str, image_path: Path,
                 is_add: bool = False, parent=None):
        super().__init__(parent)
        self._name = name
        self.setFixedSize(256, 300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("WatchCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._STYLE_NORMAL)
        self._setup_ui(image_path, is_add)

    def _setup_ui(self, image_path: Path, is_add: bool):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        img_container = QWidget()
        img_container.setFixedSize(256, 256)
        img_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        img_container.setStyleSheet(
            "background-color: #12121A;"
            " border-radius: 11px 11px 0 0;"
        )

        img_label = QLabel(img_container)
        img_label.setFixedSize(256, 256)
        img_label.setStyleSheet("background: transparent;")
        px = QPixmap(str(image_path))
        if not px.isNull():
            img_label.setPixmap(
                px.scaled(256, 256,
                          Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )

        if not is_add:
            opt_btn = QPushButton("⋯", img_container)
            opt_btn.setFixedSize(24, 24)
            opt_btn.move(228, 4)
            opt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            opt_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,0,0,0.50);
                    border: none;
                    border-radius: 12px;
                    color: rgba(250,250,250,0.65);
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: rgba(245,158,11,0.55);
                    color: #0A0A0F;
                }
            """)

        root.addWidget(img_container)

        name_label = QLabel(self._name)
        name_label.setFixedHeight(44)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(
            "color: rgba(250,250,250,0.87); font-size: 13px;"
            " background: transparent;"
        )
        root.addWidget(name_label)

    def enterEvent(self, event):
        self.setStyleSheet(self._STYLE_HOVER)
        effect = QGraphicsDropShadowEffect(self)
        effect.setColor(QColor(245, 158, 11, 65))
        effect.setBlurRadius(28)
        effect.setOffset(0, 0)
        self.setGraphicsEffect(effect)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._STYLE_NORMAL)
        self.setGraphicsEffect(None)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
        super().mouseReleaseEvent(event)


# ── My Watches 頁面（Minimalist Dark 風格）───────────────────────────────────
class _WatchCabinet(QWidget):
    watch_selected      = pyqtSignal(str)
    add_watch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sort_by   = "time"
        self._ascending = True
        self._filter    = ""
        self._setup_ui()
        self._reload()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 透明讓主視窗的環境光暈透出
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        self._container = QWidget()
        self._container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._container.setStyleSheet("background: transparent;")
        self._flow = FlowLayout(
            self._container,
            left_margin=20,
            right_margin=20,
            v_spacing=20,
        )
        self._flow.setContentsMargins(0, 20, 0, 20)
        scroll.setWidget(self._container)
        root.addWidget(scroll)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("CabinetHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setStyleSheet("""
            QWidget#CabinetHeader {
                background-color: #12121A;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
        """)

        outer = QHBoxLayout(header)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(0)

        title = QLabel("My Watches")
        title.setStyleSheet(
            "color: rgba(250,250,250,0.87); font-size: 18px; font-weight: 600;"
            " letter-spacing: -0.3px; background: transparent;"
        )
        outer.addWidget(title)
        outer.addStretch()

        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(6)

        # 排序列
        sort_row = QHBoxLayout()
        sort_row.setSpacing(4)

        self._btn_time = QPushButton()
        self._btn_name = QPushButton()
        self._btn_asc  = QPushButton()
        self._btn_desc = QPushButton()

        for btn, w in ((self._btn_time, 32), (self._btn_name, 32),
                       (self._btn_asc, 28),  (self._btn_desc, 28)):
            btn.setFixedSize(w, 28)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(20, 20))

        self._ic_time = (
            _tint(_ICON_DIR / "time-sort-dark.png", _CLR_ON_ACTIVE, 20),
            _tint(_ICON_DIR / "time-sort-dark.png", _CLR_INACTIVE,  20),
        )
        self._ic_name = (
            _tint(_ICON_DIR / "name-sort-dark.png", _CLR_ON_ACTIVE, 20),
            _tint(_ICON_DIR / "name-sort-dark.png", _CLR_INACTIVE,  20),
        )
        self._ic_sort = (
            _tint(_ICON_DIR / "sort-alt-dark.png", _CLR_ON_ACTIVE, 20),
            _tint(_ICON_DIR / "sort-alt-dark.png", _CLR_INACTIVE,  20),
        )

        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background: rgba(255,255,255,0.15);")

        sort_row.addWidget(self._btn_time)
        sort_row.addWidget(self._btn_name)
        sort_row.addWidget(sep)
        sort_row.addWidget(self._btn_asc)
        sort_row.addWidget(self._btn_desc)
        right_v.addLayout(sort_row)

        # 搜尋列
        search_row = QHBoxLayout()
        search_row.setSpacing(6)

        self._search = QLineEdit()
        self._search.setFixedHeight(30)
        self._search.setMinimumWidth(180)
        self._search.setPlaceholderText("Search watches...")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(26,26,36,200);
                color: rgba(250,250,250,0.87);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                padding: 0 10px 0 30px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: rgba(245,158,11,0.45);
            }}
        """)

        _search_ic = QLabel(self._search)
        _search_px = QPixmap(str(_ICON_DIR / "search-dark.png")).scaled(
            14, 14,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        _search_ic.setPixmap(_search_px)
        _search_ic.setFixedSize(14, 14)
        _search_ic.move(8, 8)
        _search_ic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._btn_opt = QPushButton()
        self._btn_opt.setFixedSize(30, 30)
        self._btn_opt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_opt.setIcon(_tint(_ICON_DIR / "option-dark.png", _CLR_INACTIVE, 18))
        self._btn_opt.setIconSize(QSize(18, 18))
        self._btn_opt.setStyleSheet(_BTN_INACTIVE)

        search_row.addWidget(self._search, 1)
        search_row.addWidget(self._btn_opt)
        right_v.addLayout(search_row)

        outer.addWidget(right)

        self._btn_time.clicked.connect(lambda: self._set_sort("time"))
        self._btn_name.clicked.connect(lambda: self._set_sort("name"))
        self._btn_asc.clicked.connect(lambda: self._set_order(True))
        self._btn_desc.clicked.connect(lambda: self._set_order(False))
        self._search.textChanged.connect(self._on_search)

        self._sync_btns()
        return header

    def _sync_btns(self):
        t_on = self._sort_by == "time"
        a_on = self._ascending

        self._btn_time.setChecked(t_on)
        self._btn_name.setChecked(not t_on)
        self._btn_asc.setChecked(a_on)
        self._btn_desc.setChecked(not a_on)

        self._btn_time.setIcon(self._ic_time[0 if t_on     else 1])
        self._btn_name.setIcon(self._ic_name[0 if not t_on else 1])
        self._btn_asc.setIcon( self._ic_sort[0 if a_on     else 1])
        self._btn_desc.setIcon(self._ic_sort[0 if not a_on else 1])

        self._btn_time.setStyleSheet(_BTN_ACTIVE   if t_on     else _BTN_INACTIVE)
        self._btn_name.setStyleSheet(_BTN_ACTIVE   if not t_on else _BTN_INACTIVE)
        self._btn_asc.setStyleSheet( _BTN_ACTIVE   if a_on     else _BTN_INACTIVE)
        self._btn_desc.setStyleSheet(_BTN_INACTIVE if a_on     else _BTN_ACTIVE)

    def _set_sort(self, key: str):
        self._sort_by = key
        self._sync_btns()
        self._reload()

    def _set_order(self, asc: bool):
        self._ascending = asc
        self._sync_btns()
        self._reload()

    def _on_search(self, text: str):
        self._filter = text.lower()
        self._reload()

    def _reload(self):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        watches: list[dict] = []
        for d in _SAVES.iterdir():
            if not d.is_dir():
                continue
            json_path = d / "sort.json"
            if not json_path.exists():
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            img = next(d.glob("*.png"), None)
            if img is None:
                continue
            watches.append({
                "name": data.get("name", d.name),
                "time": data.get("time", ""),
                "img":  img,
            })

        if self._filter:
            watches = [w for w in watches if self._filter in w["name"].lower()]

        sk = (
            (lambda w: w["name"].lower())
            if self._sort_by == "name"
            else (lambda w: w["time"])
        )
        watches.sort(key=sk, reverse=not self._ascending)

        add_card = _WatchCard(
            "Add Watch",
            _ICON_DIR / "time-add-dark.png",
            is_add=True,
        )
        add_card.clicked.connect(lambda _: self.add_watch_requested.emit())
        self._flow.addWidget(add_card)

        for w in watches:
            card = _WatchCard(w["name"], w["img"])
            card.clicked.connect(self.watch_selected.emit)
            self._flow.addWidget(card)


# ── 標題列 ────────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setObjectName("title_bar")
        self._drag_pos: QPoint | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        icon = QLabel()
        icon.setPixmap(_make_logo(16))
        icon.setFixedSize(20, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Watchmaker")
        self.title_label.setObjectName("title_label")

        def _btn(name: str, text: str) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName(name)
            b.setFixedSize(46, 36)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return b

        self.btn_min   = _btn("btn_min",   "—")
        self.btn_max   = _btn("btn_max",   "□")
        self.btn_close = _btn("btn_close", "✕")

        self.btn_min.clicked.connect(self.window().showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(self.window().close)

        layout.addWidget(icon)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def _toggle_max(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self.btn_max.setText("□")
        else:
            win.showMaximized()
            self.btn_max.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            win = self.window()
            if win.isMaximized():
                win.showNormal()
                self.btn_max.setText("□")
                self._drag_pos = QPoint(win.width() // 2, self.height() // 2)
            win.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
        super().mouseDoubleClickEvent(event)


# ── Windows 原生縮放（同 main.py，HWND 在 showEvent 後快取）────────────────
class _WinResizeFilter(QAbstractNativeEventFilter):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._win  = window
        self._hwnd: int | None = None

    def refresh_hwnd(self, hwnd: int):
        self._hwnd = hwnd

    def nativeEventFilter(self, event_type: bytes, message) -> tuple[bool, int]:
        if event_type != b"windows_generic_MSG":
            return False, 0
        if self._hwnd is None or self._win.isMaximized():
            return False, 0
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.hWnd != self._hwnd:
            return False, 0
        if msg.message != 0x0084:
            return False, 0

        x = ctypes.c_int16(msg.lParam & 0xFFFF).value
        y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value

        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(
            ctypes.wintypes.HWND(self._hwnd), ctypes.byref(rect)
        )
        dpr = self._win.devicePixelRatio()
        m   = int(RESIZE_MARGIN * dpr)
        l, t, r, b = rect.left, rect.top, rect.right, rect.bottom

        on_l = x <= l + m
        on_r = x >= r - m
        on_t = y <= t + m
        on_b = y >= b - m

        if on_t and on_l: return True, _HT_TOP_LEFT
        if on_t and on_r: return True, _HT_TOP_RIGHT
        if on_b and on_l: return True, _HT_BOTTOM_LEFT
        if on_b and on_r: return True, _HT_BOTTOM_RIGHT
        if on_l:          return True, _HT_LEFT
        if on_r:          return True, _HT_RIGHT
        if on_t:          return True, _HT_TOP
        if on_b:          return True, _HT_BOTTOM
        return False, 0


# ── Linux / macOS 縮放（同 main.py）─────────────────────────────────────────
class _ResizeFilter(QObject):
    _CURSOR_MAP: dict[str, Qt.CursorShape] = {
        "left":         Qt.CursorShape.SizeHorCursor,
        "right":        Qt.CursorShape.SizeHorCursor,
        "top":          Qt.CursorShape.SizeVerCursor,
        "bottom":       Qt.CursorShape.SizeVerCursor,
        "top-left":     Qt.CursorShape.SizeFDiagCursor,
        "bottom-right": Qt.CursorShape.SizeFDiagCursor,
        "top-right":    Qt.CursorShape.SizeBDiagCursor,
        "bottom-left":  Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._win           = window
        self.direction: str | None    = None
        self._start_global: QPoint | None = None
        self._start_geo:    QRect  | None = None

    def eventFilter(self, obj, event) -> bool:
        if not isinstance(obj, QWidget) or self._win.isMaximized():
            return False
        if not self._is_descendant(obj):
            return False

        t = event.type()

        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            direction = self._direction_at(event.globalPosition().toPoint())
            if direction:
                self.direction     = direction
                self._start_global = event.globalPosition().toPoint()
                self._start_geo    = QRect(self._win.geometry())
                self._win.grabMouse()
                return True

        elif t == QEvent.Type.MouseMove:
            if self.direction:
                self._do_resize(event.globalPosition().toPoint())
                return True

        elif t == QEvent.Type.MouseButtonRelease:
            if self.direction:
                self.direction     = None
                self._start_global = None
                self._start_geo    = None
                self._win.releaseMouse()
                return True

        return False

    def _is_descendant(self, widget: QWidget) -> bool:
        w = widget
        while w is not None:
            if w is self._win:
                return True
            w = w.parent()
        return False

    def _direction_at(self, global_pos: QPoint) -> str | None:
        geo = self._win.geometry()
        m   = RESIZE_MARGIN
        x, y = global_pos.x(), global_pos.y()
        l, t, r, b = geo.left(), geo.top(), geo.right(), geo.bottom()

        on_l = x <= l + m
        on_r = x >= r - m
        on_t = y <= t + m
        on_b = y >= b - m

        if on_t and on_l: return "top-left"
        if on_t and on_r: return "top-right"
        if on_b and on_l: return "bottom-left"
        if on_b and on_r: return "bottom-right"
        if on_l:          return "left"
        if on_r:          return "right"
        if on_t:          return "top"
        if on_b:          return "bottom"
        return None

    def _do_resize(self, current: QPoint):
        if not self._start_geo or not self.direction:
            return
        dx   = current.x() - self._start_global.x()
        dy   = current.y() - self._start_global.y()
        geo  = QRect(self._start_geo)
        minw = self._win.minimumWidth()
        minh = self._win.minimumHeight()

        if "left"   in self.direction and geo.width()  - dx >= minw: geo.setLeft(geo.left() + dx)
        if "right"  in self.direction: geo.setRight(max(geo.left() + minw, geo.right() + dx))
        if "top"    in self.direction and geo.height() - dy >= minh: geo.setTop(geo.top() + dy)
        if "bottom" in self.direction: geo.setBottom(max(geo.top() + minh, geo.bottom() + dy))

        self._win.setGeometry(geo)


# ── 主視窗 ────────────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    """
    Minimalist Dark 視覺展示主視窗。
    paintEvent 繪製兩顆柔和琥珀光球作為環境光暈背景。
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 500)
        self.resize(1280, 800)
        self.setStyleSheet(_STYLESHEET)
        self._build_ui()
        self._setup_resize()

    def paintEvent(self, event):
        """環境光暈：深板岩底色 + 兩顆琥珀輻射漸層"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(_BG))

        w, h = self.width(), self.height()

        # 上方中央光暈
        g1 = QRadialGradient(w / 2, 0, 520)
        g1.setColorAt(0, QColor(245, 158, 11, 20))
        g1.setColorAt(1, QColor(245, 158, 11, 0))
        p.fillRect(self.rect(), QBrush(g1))

        # 右下角光暈
        g2 = QRadialGradient(w * 1.12, h * 1.08, 430)
        g2.setColorAt(0, QColor(245, 158, 11, 13))
        g2.setColorAt(1, QColor(245, 158, 11, 0))
        p.fillRect(self.rect(), QBrush(g2))

        p.end()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        menu_bar       = self._build_menu_bar()
        cabinet        = _WatchCabinet()

        layout.addWidget(self.title_bar)
        layout.addWidget(menu_bar)
        layout.addWidget(cabinet, 1)

    def _build_menu_bar(self) -> QMenuBar:
        bar = QMenuBar()

        file_menu = bar.addMenu("File")
        file_menu.addAction("New")
        file_menu.addAction("Open")
        file_menu.addAction("Save")
        file_menu.addAction("Save As")
        file_menu.addSeparator()
        file_menu.addAction("Export")
        file_menu.addSeparator()
        file_menu.addAction("Exit").triggered.connect(self.close)

        view_menu = bar.addMenu("View")
        view_menu.addAction("Zoom In")
        view_menu.addAction("Zoom Out")
        view_menu.addSeparator()
        view_menu.addAction("Reset Layout")

        settings_menu = bar.addMenu("Settings")
        settings_menu.addAction("Preferences")

        about_menu = bar.addMenu("About")
        about_menu.addAction("About Watchmaker")

        return bar

    def _setup_resize(self):
        app = QApplication.instance()
        if sys.platform == "win32":
            self._win_filter = _WinResizeFilter(self)
            app.installNativeEventFilter(self._win_filter)
            return

        self._resize_filter  = _ResizeFilter(self)
        self._cursor_override = False
        self._last_dir: str | None = None
        app.installEventFilter(self._resize_filter)

        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(30)
        self._cursor_timer.timeout.connect(self._update_cursor)
        self._cursor_timer.start()

    def _update_cursor(self):
        if self.isMaximized() or self._resize_filter.direction:
            return
        pos       = QCursor.pos()
        direction = self._resize_filter._direction_at(pos)
        if direction == self._last_dir:
            return
        self._last_dir = direction
        if self._cursor_override:
            QApplication.restoreOverrideCursor()
            self._cursor_override = False
        if direction:
            QApplication.setOverrideCursor(
                _ResizeFilter._CURSOR_MAP.get(direction, Qt.CursorShape.ArrowCursor)
            )
            self._cursor_override = True

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == "win32" and hasattr(self, "_win_filter"):
            self._win_filter.refresh_hwnd(int(self.winId()))

    def closeEvent(self, event):
        app = QApplication.instance()
        if sys.platform == "win32" and hasattr(self, "_win_filter"):
            app.removeNativeEventFilter(self._win_filter)
        elif hasattr(self, "_resize_filter"):
            app.removeEventFilter(self._resize_filter)
        if hasattr(self, "_cursor_override") and self._cursor_override:
            QApplication.restoreOverrideCursor()
        super().closeEvent(event)


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 系統字型設定（替代 Space Grotesk / Inter）
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
