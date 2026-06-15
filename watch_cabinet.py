"""
watch_cabinet.py — My Watches 頁面
固定頂部工具列（水平單列）+ 垂直捲動卡片格（FlowLayout）。
"""

from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QSize, QRect, QRectF,
    pyqtSignal, pyqtProperty,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)

from special_ui import FlowLayout

_SAVES_DIR = Path(__file__).parent / "saves"
_ICON_DIR  = Path(__file__).parent / "img" / "my_watches"

# ── MD2 色彩常數 ──────────────────────────────────────────────────────────────
_C_BG       = QColor(0x12, 0x12, 0x12)
_C_SURF_1   = QColor(0x1E, 0x1E, 0x1E)   # 1dp
_C_SURF_1A  = QColor(0x1A, 0x1A, 0x1A)   # Add Watch 背景
_C_IMG_BG   = QColor(0x22, 0x22, 0x22)   # 圖片佔位背景
_C_PRIMARY  = QColor(0x90, 0xCA, 0xF9)   # Blue 200
_C_BORDER   = QColor(255, 255, 255, 31)   # 12% 白
_C_TEXT_HI  = QColor(255, 255, 255, 222)  # 87% 白
_C_TEXT_MED = QColor(255, 255, 255, 153)  # 60% 白
_C_ADD_DASH = QColor(144, 202, 249, 102)  # primary 40%

_CARD_W = 256
_CARD_H = 300
_IMG_H  = 256
_CARD_R = 12  # border-radius

_TAB_W  = 160  # Tab 固定寬度（special_ui.py Tab.setFixedWidth(160) 同步）

# 排序狀態循環：(sort_by, ascending)
_SORT_CYCLE = [
    ("time", True),
    ("time", False),
    ("name", True),
    ("name", False),
]

# ── QSS 常數 ──────────────────────────────────────────────────────────────────
_QSS_BTN_ACTIVE = """
    QPushButton {
        background-color: #90CAF9;
        border: none;
        border-radius: 8px;
    }
"""
_QSS_BTN_INACTIVE = """
    QPushButton {
        background-color: transparent;
        border: none;
        border-radius: 8px;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 20);
    }
"""
_QSS_OPT_BTN = """
    QPushButton {
        background-color: transparent;
        border: none;
        border-radius: 8px;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 20);
    }
"""
_QSS_SEARCH = """
    QLineEdit {
        background-color: #1E1E1E;
        color: rgba(255, 255, 255, 222);
        border: 1px solid rgba(255, 255, 255, 31);
        border-radius: 8px;
        padding: 0 8px 0 28px;
        font-size: 13px;
    }
    QLineEdit:hover {
        border-color: rgba(255, 255, 255, 51);
    }
    QLineEdit:focus {
        border-color: #90CAF9;
    }
"""
_QSS_SCROLL = """
    QScrollArea {
        border: none;
        background-color: #121212;
    }
    QScrollBar:vertical {
        background: rgba(255, 255, 255, 13);
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 51);
        border-radius: 4px;
        min-height: 32px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 97);
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: none;
    }
"""

# ── 圖示著色輔助 ───────────────────────────────────────────────────────────────
def _tint(path: Path, color: QColor, size: int) -> QIcon:
    """將圖示非透明像素著色為 color。"""
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


_CLR_ON_ACTIVE = QColor(0, 0, 0)
_CLR_INACTIVE  = QColor(0xDE, 0xDE, 0xDE)


def _compound_icon(left: QIcon, right: QIcon, each: int = 16) -> QIcon:
    """橫向合成兩個圖示成一張 QIcon（left + 2px gap + right）。"""
    p1 = left.pixmap(each, each)
    p2 = right.pixmap(each, each)
    out = QPixmap(each * 2 + 2, each)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, p1)
    p.drawPixmap(each + 2, 0, p2)
    p.end()
    return QIcon(out)


# ── 普通錶盤卡片 ───────────────────────────────────────────────────────────────
class WatchCard(QWidget):
    """256×300 手錶卡片：paintEvent 繪製圓角裁切圖片 + hover 動畫。"""
    clicked = pyqtSignal(str)

    def __init__(self, name: str, image_path: Path, parent=None):
        super().__init__(parent)
        self._name = name
        px = QPixmap(str(image_path))
        self._pixmap = (
            px.scaled(_CARD_W, _IMG_H,
                      Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
            if not px.isNull() else None
        )
        self._hover_alpha = 0

        self._anim = QPropertyAnimation(self, b"hoverAlpha")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFixedSize(_CARD_W, _CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        # 選項鈕 32×32，右上角 margin 8px
        self._opt_btn = QPushButton(self)
        self._opt_btn.setFixedSize(32, 32)
        self._opt_btn.move(_CARD_W - 32 - 8, 8)
        self._opt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opt_btn.setIcon(_tint(_ICON_DIR / "option-dark.png", _CLR_INACTIVE, 16))
        self._opt_btn.setIconSize(QSize(16, 16))
        self._opt_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 115);
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 179);
            }
        """)

    def _get_hover_alpha(self) -> int:
        return self._hover_alpha

    def _set_hover_alpha(self, val: int):
        self._hover_alpha = val
        self.update()

    hoverAlpha = pyqtProperty(int, _get_hover_alpha, _set_hover_alpha)

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_alpha)
        self._anim.setEndValue(20)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_alpha)
        self._anim.setEndValue(0)
        self._anim.start()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 建立圓角裁切路徑
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), _CARD_R, _CARD_R)
        painter.setClipPath(path)

        # 圖片區
        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            painter.fillRect(QRect(0, 0, _CARD_W, _IMG_H), _C_IMG_BG)

        # 名稱區背景
        painter.fillRect(QRect(0, _IMG_H, _CARD_W, _CARD_H - _IMG_H), _C_SURF_1)

        # Hover 白色疊加層（elevation 提升效果）
        if self._hover_alpha > 0:
            painter.fillRect(self.rect(), QColor(255, 255, 255, self._hover_alpha))

        # 名稱文字
        painter.setPen(_C_TEXT_HI)
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(
            QRect(0, _IMG_H, _CARD_W, _CARD_H - _IMG_H),
            Qt.AlignmentFlag.AlignCenter,
            self._name,
        )

        # 邊框繪製在裁切路徑外，避免被裁掉
        painter.setClipping(False)
        pen = QPen(_C_BORDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            _CARD_R, _CARD_R,
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
        super().mouseReleaseEvent(event)


# ── 新增錶盤卡片 ───────────────────────────────────────────────────────────────
class AddWatchCard(QWidget):
    """虛線邊框 + ＋圖示的新增卡片，hover 時邊框轉為實線主色。"""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_CARD_W, _CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._hover_alpha = 0

        self._anim = QPropertyAnimation(self, b"hoverAlpha")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_hover_alpha(self) -> int:
        return self._hover_alpha

    def _set_hover_alpha(self, val: int):
        self._hover_alpha = val
        self.update()

    hoverAlpha = pyqtProperty(int, _get_hover_alpha, _set_hover_alpha)

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_alpha)
        self._anim.setEndValue(20)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_alpha)
        self._anim.setEndValue(0)
        self._anim.start()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), _CARD_R, _CARD_R)
        painter.setClipPath(path)

        # 背景
        painter.fillRect(self.rect(), _C_SURF_1A)

        # Hover 疊加層
        if self._hover_alpha > 0:
            painter.fillRect(self.rect(), QColor(255, 255, 255, self._hover_alpha))

        painter.setClipping(False)

        # 邊框：hover 前虛線，hover 後實線主色
        hovering = self._hover_alpha >= 10
        pen = QPen(_C_PRIMARY if hovering else _C_ADD_DASH)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.SolidLine if hovering else Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(1, 1, -1, -1),
            _CARD_R, _CARD_R,
        )

        # ＋ 符號（垂直置中偏上，為文字留空間）
        painter.setPen(_C_PRIMARY)
        painter.setFont(QFont("Segoe UI", 40, QFont.Weight.Light))
        painter.drawText(
            QRect(0, _CARD_H // 2 - 72, _CARD_W, 56),
            Qt.AlignmentFlag.AlignCenter,
            "+",
        )

        # Add Watch 文字
        painter.setPen(_C_TEXT_MED)
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(
            QRect(0, _CARD_H // 2 - 8, _CARD_W, 28),
            Qt.AlignmentFlag.AlignCenter,
            "Add Watch",
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ── WatchCabinet 主頁面 ────────────────────────────────────────────────────────
class WatchCabinet(QWidget):
    """My Watches 頁面：水平單列工具列 + 垂直捲動卡片格。"""
    watch_selected      = pyqtSignal(str)
    add_watch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sort_by    = "time"
        self._ascending  = True
        self._filter_str = ""
        self._setup_ui()
        self._reload_cards()

    # ── UI 建立 ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(_QSS_SCROLL)
        scroll.viewport().setStyleSheet("background-color: #121212;")

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background-color: #121212;")
        self._flow = FlowLayout(
            self._cards_container,
            left_margin=16,
            right_margin=16,
            v_spacing=16,
        )
        self._flow.setContentsMargins(0, 16, 0, 16)
        scroll.setWidget(self._cards_container)

        scroll_container = QWidget()
        scroll_container.setStyleSheet("background-color: #121212;")
        sc_layout = QVBoxLayout(scroll_container)
        sc_layout.setContentsMargins(0, 0, 12, 0)
        sc_layout.setSpacing(0)
        sc_layout.addWidget(scroll)
        root.addWidget(scroll_container)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("WatchCabinetHeader")
        header.setFixedHeight(56)
        header.setStyleSheet("""
            QWidget#WatchCabinetHeader {
                background-color: #1E1E1E;
                border-bottom: 1px solid rgba(255, 255, 255, 31);
            }
        """)

        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 16, 0)
        row.setSpacing(4)

        # 標題區：固定 _TAB_W px，與 tab 等寬；左側 padding 16px 放在內部
        title_area = QWidget()
        title_area.setFixedWidth(_TAB_W)
        title_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        ta_layout = QHBoxLayout(title_area)
        ta_layout.setContentsMargins(16, 0, 0, 0)
        ta_layout.setSpacing(0)
        title = QLabel("My Watches")
        title.setStyleSheet(
            "color: rgba(255, 255, 255, 222); font-size: 18px; font-weight: 600;"
        )
        ta_layout.addWidget(title)
        ta_layout.addStretch()
        row.addWidget(title_area)

        row.addStretch()

        # 排序循環鈕（單顆，點擊依序切換 4 種狀態）
        self._btn_sort = QPushButton()
        self._btn_sort.setFixedSize(40, 32)
        self._btn_sort.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sort.setIconSize(QSize(34, 16))
        self._btn_sort.setStyleSheet(_QSS_BTN_INACTIVE)
        row.addWidget(self._btn_sort)

        row.addSpacing(8)

        # 搜尋框
        self._search = QLineEdit()
        self._search.setFixedHeight(32)
        self._search.setMinimumWidth(160)
        self._search.setPlaceholderText("Search...")
        self._search.setStyleSheet(_QSS_SEARCH)

        # 搜尋圖示嵌入左側
        _ic = QLabel(self._search)
        _px = QPixmap(str(_ICON_DIR / "search-dark.png")).scaled(
            16, 16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        _ic.setPixmap(_px)
        _ic.setFixedSize(16, 16)
        _ic.move(6, 8)
        _ic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self._search, 1)

        row.addSpacing(4)

        # 選項按鈕
        self._btn_opt = QPushButton()
        self._btn_opt.setFixedSize(32, 32)
        self._btn_opt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_opt.setIcon(_tint(_ICON_DIR / "option-dark.png", _CLR_INACTIVE, 20))
        self._btn_opt.setIconSize(QSize(20, 20))
        self._btn_opt.setStyleSheet(_QSS_OPT_BTN)
        row.addWidget(self._btn_opt)

        # 複合圖示預載：key(time/name) × dir(up/down) 共 4 種
        _ic_time = _tint(_ICON_DIR / "time-sort-dark.png", _CLR_INACTIVE, 16)
        _ic_name = _tint(_ICON_DIR / "name-sort-dark.png", _CLR_INACTIVE, 16)
        _ic_up   = _tint(_ICON_DIR / "sort-size-up.png",   _CLR_INACTIVE, 16)
        _ic_down = _tint(_ICON_DIR / "sort-size-down.png", _CLR_INACTIVE, 16)
        self._sort_icons = [
            _compound_icon(_ic_time, _ic_up),    # time ↑
            _compound_icon(_ic_time, _ic_down),  # time ↓
            _compound_icon(_ic_name, _ic_up),    # name ↑
            _compound_icon(_ic_name, _ic_down),  # name ↓
        ]

        self._btn_sort.clicked.connect(self._cycle_sort)
        self._search.textChanged.connect(self._on_search)

        self._sync_sort_btn()
        return header

    # ── 排序 / 搜尋 ───────────────────────────────────────────────────────────

    def _sort_state_index(self) -> int:
        return _SORT_CYCLE.index((self._sort_by, self._ascending))

    def _sync_sort_btn(self):
        self._btn_sort.setIcon(self._sort_icons[self._sort_state_index()])

    def _cycle_sort(self):
        next_idx = (self._sort_state_index() + 1) % len(_SORT_CYCLE)
        self._sort_by, self._ascending = _SORT_CYCLE[next_idx]
        self._sync_sort_btn()
        self._reload_cards()

    def _on_search(self, text: str):
        self._filter_str = text.lower()
        self._reload_cards()

    # ── 卡片載入 ──────────────────────────────────────────────────────────────

    def _reload_cards(self):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        watches: list[dict] = []
        if _SAVES_DIR.exists():
            for d in _SAVES_DIR.iterdir():
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

        if self._filter_str:
            watches = [w for w in watches
                       if self._filter_str in w["name"].lower()]

        sort_key = (
            (lambda w: w["name"].lower())
            if self._sort_by == "name"
            else (lambda w: w["time"])
        )
        watches.sort(key=sort_key, reverse=not self._ascending)

        add_card = AddWatchCard()
        add_card.clicked.connect(self.add_watch_requested.emit)
        self._flow.addWidget(add_card)

        for w in watches:
            card = WatchCard(w["name"], w["img"])
            card.clicked.connect(self.watch_selected.emit)
            self._flow.addWidget(card)
