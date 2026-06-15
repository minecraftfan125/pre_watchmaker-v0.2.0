import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QLayout, QApplication, QWidget, QPushButton, QScrollArea, QDockWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QStackedWidget, QFrame,
    QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QPoint, QMimeData
from PyQt6.QtGui import QCursor, QPainter, QColor, QPixmap, QImage, QFont, QFontDatabase
from special_ux import *

class FlowLayout(QLayout):
    """
    流式佈局：物件自動換行，所有格子尺寸一致。

    對齊模式（alignment 參數）：
    - AlignLeft  + 單行：物件靠左，物件間距 = left_margin
    - AlignRight + 單行：物件靠右，物件間距 = right_margin
    - 其他對齊或多行：space-evenly（左右邊緣間距 = 物件間距）

    建構參數
    --------
    left_margin  : 左側水平邊距（像素），預設 0
    right_margin : 右側水平邊距（像素），預設 0
    v_spacing    : 行間縱向間距（像素），預設 0
    alignment    : Qt.AlignmentFlag，預設 AlignLeft
    上下邊距透過標準 setContentsMargins 管理。
    """

    def __init__(self, parent=None, *, left_margin=0, right_margin=0, v_spacing=0,
                 alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(parent)
        self._lm = left_margin
        self._rm = right_margin
        self._v_spacing = v_spacing
        self._alignment = alignment
        self._items = []

    # ── QLayout 必要介面 ─────────────────────────────────────────

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        # 最小寬度 = 左邊距 + 最寬格子 + 右邊距
        sw, _ = self._slot_size()
        min_w = self._lm + sw + self._rm
        min_h = self._do_layout(QRect(0, 0, min_w, 0), apply=False)
        return QSize(min_w, min_h)

    # ── 私有輔助 ─────────────────────────────────────────────────

    def _slot_size(self):
        """回傳 (最大寬, 最大高)，無 items 時回傳 (0, 0)。"""
        if not self._items:
            return 0, 0
        sw = max(item.sizeHint().width()  for item in self._items)
        sh = max(item.sizeHint().height() for item in self._items)
        return sw, sh

    def _do_layout(self, rect, *, apply):
        """
        核心排版邏輯。
        apply=True  → 對每個 item 呼叫 setGeometry 實際擺位。
        apply=False → 僅計算並回傳所需總高度。
        """
        sw, sh = self._slot_size()
        if not self._items or sw == 0 or sh == 0:
            return 0

        margins = self.contentsMargins()
        top    = margins.top()
        bottom = margins.bottom()

        available_w = rect.width() - self._lm - self._rm
        _AF = Qt.AlignmentFlag
        is_left  = bool(self._alignment & _AF.AlignLeft)
        is_right = bool(self._alignment & _AF.AlignRight)

        # 左/右對齊使用固定間距，影響每行最大欄數計算
        if is_left:
            _fixed_gap = self._lm
        elif is_right:
            _fixed_gap = self._rm
        else:
            _fixed_gap = 0

        if _fixed_gap > 0:
            # n 個物件需 n*sw + (n-1)*gap ≤ available_w → n ≤ (available_w + gap) / (sw + gap)
            n_cols = min(len(self._items), max(1, (available_w + _fixed_gap) // (sw + _fixed_gap)))
        else:
            n_cols = min(len(self._items), max(1, available_w // sw))

        n_rows = (len(self._items) + n_cols - 1) // n_cols
        is_single_row = n_rows == 1

        if apply:
            x0 = rect.x() + self._lm
            y0 = rect.y() + top

            for idx, item in enumerate(self._items):
                row = idx // n_cols
                col = idx % n_cols

                if n_cols == 1:
                    # 單欄：依對齊靠左 / 靠右 / 置中
                    if is_left:
                        sx = x0
                    elif is_right:
                        sx = x0 + available_w - sw
                    else:
                        sx = x0 + max(0, available_w - sw) // 2
                elif is_single_row and is_left:
                    # 左對齊單行：物件間距 = left_margin，靠左堆疊
                    sx = x0 + col * (sw + self._lm)
                elif is_single_row and is_right:
                    # 右對齊單行：物件間距 = right_margin，靠右堆疊
                    sx = x0 + available_w - sw - (n_cols - 1 - col) * (sw + self._rm)
                else:
                    # space-evenly：邊緣間距 = 物件間距（多行或非左右對齊）
                    gap = (available_w - n_cols * sw) / (n_cols + 1)
                    sx = x0 + round((col + 1) * gap + col * sw)

                sy = y0 + row * (sh + self._v_spacing)

                iw = item.sizeHint().width()
                ih = item.sizeHint().height()
                item.setGeometry(QRect(
                    sx + (sw - iw) // 2,
                    sy + (sh - ih) // 2,
                    iw, ih,
                ))

        return top + n_rows * sh + max(0, n_rows - 1) * self._v_spacing + bottom


class AttrFlowLayout(FlowLayout):
    """
    屬性面板 FlowLayout 子類：
    - _is_group=True 的 widget 群組單獨佔滿一整行，不參與一般行高計算
    - 其餘 item 欄寬取自身 sizeHint().width()，行高取該行最大高
    """

    @staticmethod
    def _is_group(item) -> bool:
        w = item.widget()
        return bool(w and getattr(w, "_is_group", False))

    @staticmethod
    def _field_type(item) -> str:
        w = item.widget()
        return getattr(w, "_field_type", "") if w else ""

    def _do_layout(self, rect, *, apply):
        if not self._items:
            return 0

        margins = self.contentsMargins()
        top = margins.top()
        bottom = margins.bottom()
        available_w = max(rect.width() - self._lm - self._rm, 1)

        # 換行規則：group 獨佔一行；不同 _field_type 或寬度不足則換行
        rows: list[list] = []
        row: list = []
        row_w = 0
        row_type = ""
        for item in self._items:
            if self._is_group(item):
                if row:
                    rows.append(row)
                    row, row_w, row_type = [], 0, ""
                rows.append([item])
            else:
                iw = max(item.sizeHint().width(), 1)
                item_type = self._field_type(item)
                if not row:
                    row.append(item)
                    row_w, row_type = iw, item_type
                elif item_type != row_type or row_w + self._lm + iw > available_w:
                    rows.append(row)
                    row, row_w, row_type = [item], iw, item_type
                else:
                    row.append(item)
                    row_w += self._lm + iw
        if row:
            rows.append(row)

        # 每行高度取該行 item 最大高
        def _row_h(r: list) -> int:
            return max((item.sizeHint().height() for item in r), default=1)

        if apply:
            y = rect.y() + top
            for r in rows:
                rh = _row_h(r)
                x = rect.x() + self._lm
                for item in r:
                    iw = available_w if self._is_group(item) else max(item.sizeHint().width(), 1)
                    item.setGeometry(QRect(x, y, iw, rh))
                    x += iw + self._lm
                y += rh + self._v_spacing

        total_h = top + bottom
        for i, r in enumerate(rows):
            total_h += _row_h(r)
            if i < len(rows) - 1:
                total_h += self._v_spacing
        return total_h


class _HScrollArea(QScrollArea):
    """水平捲動容器：滑鼠滾輪固定橫向捲動。"""
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        sb = self.horizontalScrollBar()
        sb.setValue(sb.value() - delta // 3)
        event.accept()


@drag_data("mime")
class Tab(QWidget):
    """
    對應唯一 QWidget 視窗的 Tab 元件。
    左側顯示視窗標題，右側為關閉鈕。
    點擊 Tab 本體發出 activated；點擊關閉鈕發出 close_requested。
    外部呼叫 set_active(bool) 切換 active/inactive 視覺狀態。
    """

    activated      = pyqtSignal(QWidget)
    close_requested = pyqtSignal(QWidget)

    def __init__(self, window: QWidget, parent=None):
        super().__init__(parent)
        self._window = window
        self._active = False
        self.mime = QMimeData()
        self.mime.setData("tab", b"")
        self.setObjectName("Tab")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左側 2px active 指示條
        self._indicator = QFrame()
        self._indicator.setFixedWidth(2)
        layout.addWidget(self._indicator)

        # 視窗名稱標籤
        self._name_label = QLabel(self._window.windowTitle())
        self._name_label.setContentsMargins(8, 0, 8, 0)
        layout.addWidget(self._name_label)
        self._window.windowTitleChanged.connect(self._name_label.setText)
        layout.addStretch()

        # 關閉鈕
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setFlat(True)
        self._close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._close_btn.clicked.connect(
            lambda: self.close_requested.emit(self._window)
        )
        layout.addWidget(self._close_btn)
        layout.addSpacing(4)

        # 右側 1px 分隔線
        self._right_sep = QFrame()
        self._right_sep.setFixedWidth(1)
        self._right_sep.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.12); }"
        )
        layout.addWidget(self._right_sep)

        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        if self._active:
            bg, hover_bg   = "#1E1E1E", "#303030"
            text_color     = "rgba(255,255,255,0.87)"
            indicator_color = "#90CAF9"
        else:
            bg, hover_bg   = "#121212", "#252525"
            text_color     = "rgba(255,255,255,0.60)"
            indicator_color = "transparent"

        self.setStyleSheet(f"""
            #Tab {{
                background-color: {bg};
            }}
            #Tab:hover {{
                background-color: {hover_bg};
            }}
        """)
        self._indicator.setStyleSheet(
            f"background-color: {indicator_color};"
        )
        self._name_label.setStyleSheet(
            f"color: {text_color}; background: transparent;"
        )
        self._close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255,255,255,0.60);
                background: transparent;
                border: none;
                font-size: 14px;
                border-radius: 9px;
            }
            QPushButton:hover {
                color: #000000;
                background-color: #CF6679;
            }
        """)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def mouseReleaseEvent(self, event):
        # @drag_data 裝飾器截取此 method 為 _orig_release，拖曳時不會觸發
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self._window)
        super().mouseReleaseEvent(event)


class TabWidget(QWidget):
    """
    頂部 tab bar（_HScrollArea 包裹，橫向捲動，tab 固定寬 160px）+ 下方 QStackedWidget。
    選取歷史用於關閉 tab 時回退；拖曳重排由 _tab_bar 的 drop 事件處理。
    """

    window_activated = pyqtSignal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: list[Tab] = []
        self._history: list[QWidget] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # tab bar 內容容器；acceptDrops 設在此層，drop 事件由 Tab 子件向上傳遞至此
        self._tab_bar = QWidget()
        self._tab_bar.setObjectName("TabBar")
        self._tab_bar.setFixedHeight(32)
        self._tab_bar.setStyleSheet("#TabBar { background-color: #121212; }")
        self._tab_bar.setAcceptDrops(True)
        self._tab_bar.dragEnterEvent = self._bar_drag_enter
        self._tab_bar.dragMoveEvent  = self._bar_drag_move
        self._tab_bar.dropEvent      = self._bar_drop

        self._bar_layout = QHBoxLayout(self._tab_bar)
        self._bar_layout.setContentsMargins(0, 0, 0, 0)
        self._bar_layout.setSpacing(0)
        self._bar_layout.addStretch()

        # setWidgetResizable(True)：scroll area 自動將 _tab_bar 撐至 max(viewport, minimumSizeHint)
        # 當 tab 超出 viewport 時自動開放橫向捲動範圍；wheelEvent 由 _HScrollArea 攔截
        self._tab_scroll = _HScrollArea()
        self._tab_scroll.setWidget(self._tab_bar)
        self._tab_scroll.setWidgetResizable(True)
        self._tab_scroll.setFixedHeight(32)
        self._tab_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tab_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tab_scroll.setStyleSheet(
            "QScrollArea { background-color: #121212; border: none; }"
        )
        self._tab_scroll.viewport().setStyleSheet("background-color: #121212;")

        self._stack = QStackedWidget()

        root.addWidget(self._tab_scroll)
        root.addWidget(self._stack)

    # ── 公開 API ──────────────────────────────────────────────────

    def add_tab(self, window: QWidget):
        tab = Tab(window, self._tab_bar)
        tab.setFixedWidth(160)
        tab.activated.connect(self._on_activated)
        tab.close_requested.connect(self._on_close)
        self._tabs.append(tab)
        self._bar_layout.insertWidget(len(self._tabs) - 1, tab)
        # 告知 scroll area 最小可捲動寬度
        self._tab_bar.setMinimumWidth(len(self._tabs) * 160)
        self._stack.addWidget(window)
        self._activate(window)

    # ── 內部邏輯 ──────────────────────────────────────────────────

    def _activate(self, window: QWidget):
        if window in self._history:
            self._history.remove(window)
        self._history.append(window)
        self._stack.setCurrentWidget(window)
        for tab in self._tabs:
            tab.set_active(tab._window is window)
        self.window_activated.emit(window)

    def _on_activated(self, window: QWidget):
        self._activate(window)

    def _on_close(self, window: QWidget):
        tab = next((t for t in self._tabs if t._window is window), None)
        if tab is None:
            return
        if hasattr(window, "can_close") and not window.can_close():
            return
        self._history = [w for w in self._history if w is not window]
        self._tabs.remove(tab)
        self._bar_layout.removeWidget(tab)
        tab.deleteLater()
        self._tab_bar.setMinimumWidth(len(self._tabs) * 160)
        self._stack.removeWidget(window)
        if self._history:
            self._activate(self._history[-1])

    # ── Tab bar drop 處理（拖曳重排）─────────────────────────────

    def _bar_drag_enter(self, event):
        if event.mimeData().hasFormat("tab"):
            event.acceptProposedAction()

    def _bar_drag_move(self, event):
        if event.mimeData().hasFormat("tab"):
            event.acceptProposedAction()

    def _bar_drop(self, event):
        if not event.mimeData().hasFormat("tab"):
            return
        dragged = DragManager.get_data()
        if not isinstance(dragged, Tab) or dragged not in self._tabs:
            return

        # event.position() 已是 _tab_bar 本地座標（Qt 在 deliver 時自動映射）
        drop_x = event.position().toPoint().x()
        insert_idx = len(self._tabs)
        for i, tab in enumerate(self._tabs):
            if drop_x < tab.x() + tab.width() // 2:
                insert_idx = i
                break

        old_idx = self._tabs.index(dragged)
        if insert_idx == old_idx or insert_idx == old_idx + 1:
            event.acceptProposedAction()
            return

        self._tabs.remove(dragged)
        self._bar_layout.removeWidget(dragged)

        adj = insert_idx if insert_idx <= old_idx else insert_idx - 1
        self._tabs.insert(adj, dragged)
        self._bar_layout.insertWidget(adj, dragged)

        event.acceptProposedAction()


# ── DropOverlay 圖標對應 ──────────────────────────────────────────────────────

_ICON_FILES: dict[str, str] = {
    'center':        'window-merge.png',
    'top':           'window-up.png',
    'bottom':        'window-buttom.png',
    'left':          'window-left.png',
    'right':         'window-right.png',
    'outer_top':     'top-window.png',
    'outer_bottom':  'buttom-window.png',
    'outer_left':    'left-window.png',
    'outer_right':   'right-window.png',
}
_ICON_DIR = Path(__file__).parent / "img" / "icon"


class DropOverlay(QWidget):
    """
    浮在某個 TabWidget 上方的半透明疊加層。
    顯示 9 個方向圖標（中心羅盤 5 個 + 外緣 4 個），
    懸停圖標時顯示白色半透明預覽矩形。
    由 TabWidgetManager 透過 reposition() / reset() 控制。
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._hovered_zone: str | None = None
        self._icon_labels: dict[str, QLabel] = {}
        self._icon_rects:  dict[str, QRect]  = {}
        self._preview_rect: QRect | None = None
        self._setup_icons()
        self.hide()

    def _setup_icons(self):
        for zone, filename in _ICON_FILES.items():
            lbl = QLabel(self)
            px = QPixmap(str(_ICON_DIR / filename))
            if not px.isNull():
                lbl.setPixmap(px.scaled(
                    32, 32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            lbl.setFixedSize(48, 48)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: rgba(40, 40, 40, 200);
                    border-radius: 8px;
                }
            """)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.hide()
            self._icon_labels[zone] = lbl

    def reposition(self, target_rect: QRect):
        self.setGeometry(target_rect)
        self._place_icons()
        for lbl in self._icon_labels.values():
            lbl.show()
        self.show()
        self.raise_()

    def _place_icons(self):
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        positions = {
            'center':       (cx,                     cy),
            'top':          (cx,                     max(24, cy - 64)),
            'bottom':       (cx,                     min(h - 24, cy + 64)),
            'left':         (max(24, cx - 64),       cy),
            'right':        (min(w - 24, cx + 64),   cy),
            'outer_top':    (cx,                     32),
            'outer_bottom': (cx,                     h - 32),
            'outer_left':   (32,                     cy),
            'outer_right':  (w - 32,                 cy),
        }
        for zone, (x, y) in positions.items():
            self._icon_labels[zone].move(x - 24, y - 24)
            self._icon_rects[zone] = QRect(x - 28, y - 28, 56, 56)

    def update_hover(self, local_pos: QPoint):
        new_zone: str | None = None
        for zone, rect in self._icon_rects.items():
            if rect.contains(local_pos):
                new_zone = zone
                break
        if new_zone != self._hovered_zone:
            self._hovered_zone = new_zone
            self._compute_preview_rect()
            self.update()

    def _compute_preview_rect(self):
        if self._hovered_zone is None:
            self._preview_rect = None
            return
        w, h = self.width(), self.height()
        z = self._hovered_zone
        if   z == 'center':       r = QRect(0,      0,      w,          h)
        elif z == 'top':          r = QRect(0,      0,      w,          h // 2)
        elif z == 'bottom':       r = QRect(0,      h // 2, w,          h - h // 2)
        elif z == 'left':         r = QRect(0,      0,      w // 2,     h)
        elif z == 'right':        r = QRect(w // 2, 0,      w - w // 2, h)
        elif z == 'outer_top':    r = QRect(0,      0,      w,          h // 2)
        elif z == 'outer_bottom': r = QRect(0,      h // 2, w,          h - h // 2)
        elif z == 'outer_left':   r = QRect(0,      0,      w // 2,     h)
        elif z == 'outer_right':  r = QRect(w // 2, 0,      w - w // 2, h)
        else:                     r = None
        self._preview_rect = r

    def get_hovered_zone(self) -> str | None:
        return self._hovered_zone

    def reset(self):
        self._hovered_zone = None
        self._preview_rect = None
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self._preview_rect:
            p.fillRect(self._preview_rect, QColor(255, 255, 255, 40))
            pen = p.pen()
            pen.setColor(QColor(0x90, 0xCA, 0xF9, 180))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawRect(self._preview_rect.adjusted(1, 1, -1, -1))
        p.end()


class WidgetManager(QWidget):
    """
    通用分割面板管理器基類。
    管理 QSplitter 樹的建立/分割/合併，以及 DropOverlay 的顯示與定位。
    子類須實作四個抽象鉤子：
      _create_managed_widget / _move_item / _widget_of / _widget_is_empty
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._widgets:        list[QWidget] = []
        self._active_widget:  QWidget | None = None
        self._restructuring = False

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._root_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._root_splitter.setHandleWidth(0)
        self._root_splitter.setChildrenCollapsible(False)
        root_layout.addWidget(self._root_splitter)

        self._root_splitter.addWidget(self._create_managed_widget())

        self._overlay = DropOverlay(self)

    # ── 抽象鉤子 ─────────────────────────────────────────────────

    def _create_managed_widget(self) -> QWidget:
        raise NotImplementedError

    def _move_item(self, item, source_widget: QWidget | None, target_widget: QWidget | None):
        """將 item 從 source_widget 移至 target_widget；任一為 None 時跳過該側。"""
        raise NotImplementedError

    def _widget_of(self, item) -> QWidget | None:
        raise NotImplementedError

    def _widget_is_empty(self, widget: QWidget) -> bool:
        raise NotImplementedError

    def _source_would_empty(self, source_widget: QWidget, item) -> bool:
        """移走 item 後 source_widget 是否會變空。子類可覆寫以允許多項目自分割。"""
        return True

    def _make_split_widget(self, source_item, source_widget: QWidget | None) -> QWidget:
        """分割時要放入新位置的 widget。預設建立新的空白受管 widget。"""
        return self._create_managed_widget()

    def _already_at_outer(self, source_widget: QWidget, direction: str) -> bool:
        """source_widget 是否已在 root_splitter 對應外側。子類可覆寫。"""
        return False

    # ── Drag-and-Drop 事件（由子類的 @accept_drop 觸發）────────────

    def dragMoveEvent(self, event):
        pos    = event.position().toPoint()
        widget = self._find_widget_at(pos)
        if widget is None:
            self._overlay.reset()
            event.acceptProposedAction()
            return
        self._active_widget = widget
        origin = widget.mapTo(self, QPoint(0, 0))
        self._overlay.reposition(QRect(origin, widget.size()))
        self._overlay.update_hover(pos - origin)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._overlay.reset()
        self._active_widget = None

    def dropEvent(self, event):
        zone        = self._overlay.get_hovered_zone()
        source_item = DragManager.get_data()
        target      = self._active_widget
        self._overlay.reset()
        self._active_widget = None
        if zone is None or source_item is None or target is None:
            event.acceptProposedAction()
            return
        self._execute_drop(zone, source_item, target)
        event.acceptProposedAction()

    # ── 分割 / 合併調度 ───────────────────────────────────────────

    def _find_widget_at(self, local_pos: QPoint) -> QWidget | None:
        for widget in self._widgets:
            origin = widget.mapTo(self, QPoint(0, 0))
            if QRect(origin, widget.size()).contains(local_pos):
                return widget
        return None

    def _execute_drop(self, zone: str, source_item, target_widget: QWidget):
        if zone == 'center':
            source_widget = self._widget_of(source_item)
            if source_widget is None or source_widget is target_widget:
                return
            self._move_item(source_item, source_widget, target_widget)
        elif zone in ('top', 'bottom', 'left', 'right'):
            self._split_widget(target_widget, zone, source_item)
        else:
            self._split_at_root(zone[len('outer_'):], source_item, target_widget)

    def _split_widget(self, target_widget: QWidget, direction: str, source_item):
        source_widget = self._widget_of(source_item)
        if source_widget is target_widget and self._source_would_empty(source_widget, source_item):
            return

        self._restructuring = True
        if source_widget is not None:
            self._move_item(source_item, source_widget, None)

        new_widget = self._make_split_widget(source_item, source_widget)

        orientation = (
            Qt.Orientation.Horizontal
            if direction in ('left', 'right')
            else Qt.Orientation.Vertical
        )
        parent_sp = target_widget.parentWidget()
        if not isinstance(parent_sp, QSplitter):
            self._restructuring = False
            return
        idx       = parent_sp.indexOf(target_widget)
        old_sizes = parent_sp.sizes()

        new_sp = QSplitter(orientation)
        new_sp.setHandleWidth(0)
        new_sp.setChildrenCollapsible(False)

        target_widget.hide()
        target_widget.setParent(None)
        parent_sp.insertWidget(idx, new_sp)

        if direction in ('left', 'top'):
            new_sp.addWidget(new_widget)
            new_sp.addWidget(target_widget)
        else:
            new_sp.addWidget(target_widget)
            new_sp.addWidget(new_widget)
        target_widget.show()

        slot = old_sizes[idx] if idx < len(old_sizes) else 400
        new_sp.setSizes([slot // 2, slot - slot // 2])
        parent_sp.setSizes(old_sizes)

        self._move_item(source_item, None, new_widget)
        self._restructuring = False
        if source_widget is not None:
            self._cleanup_empty(source_widget)

    def _split_at_root(self, direction: str, source_item, hovered_widget: QWidget | None = None):
        source_widget = self._widget_of(source_item)
        if (source_widget is not None
                and source_widget is hovered_widget
                and self._source_would_empty(source_widget, source_item)):
            return
        if source_widget is not None and self._already_at_outer(source_widget, direction):
            return

        self._restructuring = True
        if source_widget is not None:
            self._move_item(source_item, source_widget, None)

        new_widget = self._make_split_widget(source_item, source_widget)
        self._move_item(source_item, None, new_widget)

        desired = (
            Qt.Orientation.Horizontal
            if direction in ('left', 'right')
            else Qt.Orientation.Vertical
        )
        if self._root_splitter.orientation() == desired:
            if direction in ('left', 'top'):
                self._root_splitter.insertWidget(0, new_widget)
            else:
                self._root_splitter.addWidget(new_widget)
            n     = self._root_splitter.count()
            total = (
                self._root_splitter.width()
                if desired == Qt.Orientation.Horizontal
                else self._root_splitter.height()
            )
            self._root_splitter.setSizes([total // n] * n)
        else:
            self._wrap_root(desired, direction, new_widget)

        self._restructuring = False
        if source_widget is not None:
            self._cleanup_empty(source_widget)

    def _wrap_root(self, new_orientation: Qt.Orientation,
                   direction: str, new_widget: QWidget):
        layout   = self.layout()
        old_root = self._root_splitter
        layout.removeWidget(old_root)
        old_root.setParent(None)

        new_outer = QSplitter(new_orientation)
        new_outer.setHandleWidth(0)
        new_outer.setChildrenCollapsible(False)

        if direction in ('left', 'top'):
            new_outer.addWidget(new_widget)
            new_outer.addWidget(old_root)
        else:
            new_outer.addWidget(old_root)
            new_outer.addWidget(new_widget)

        layout.insertWidget(0, new_outer)
        self._root_splitter = new_outer

        total = (
            new_outer.width()
            if new_orientation == Qt.Orientation.Horizontal
            else new_outer.height()
        )
        new_outer.setSizes([total // 2, total - total // 2])

    def _cleanup_empty(self, widget: QWidget):
        if not self._widget_is_empty(widget):
            return
        if widget not in self._widgets:
            return
        if len(self._widgets) == 1:
            return

        parent_sp   = widget.parentWidget()
        grandparent = parent_sp.parent() if isinstance(parent_sp, QSplitter) else None
        gp_sizes    = grandparent.sizes() if isinstance(grandparent, QSplitter) else None

        widget.setParent(None)
        widget.deleteLater()
        self._widgets.remove(widget)

        if not isinstance(parent_sp, QSplitter):
            return

        if parent_sp.count() == 1:
            child = parent_sp.widget(0)
            if isinstance(grandparent, QSplitter):
                gp_idx = grandparent.indexOf(parent_sp)
                child.setParent(None)
                grandparent.insertWidget(gp_idx, child)
                parent_sp.deleteLater()
                if gp_sizes:
                    grandparent.setSizes(gp_sizes)
            else:
                layout = self.layout()
                layout.removeWidget(parent_sp)
                parent_sp.setParent(None)
                if isinstance(child, QSplitter):
                    layout.insertWidget(0, child)
                    self._root_splitter = child
                else:
                    # child 是受管 widget，包裝以維持 _root_splitter 不變性
                    wrapper = QSplitter(Qt.Orientation.Horizontal)
                    wrapper.setHandleWidth(0)
                    wrapper.setChildrenCollapsible(False)
                    child.setParent(None)
                    wrapper.addWidget(child)
                    layout.insertWidget(0, wrapper)
                    self._root_splitter = wrapper
                parent_sp.deleteLater()


@accept_drop("drop_mime")
class TabWidgetManager(WidgetManager):
    """
    分頁管理器：繼承 WidgetManager，以 TabWidget 作為受管 widget。
    公開 API：add_tab / merge_all_tabs / delete_all_tabs / restore_closed_tab。
    分割/合併由拖曳至 DropOverlay 觸發。
    """

    active_window_changed = pyqtSignal(QWidget)

    def __init__(self, parent=None):
        # _batch_deleting / _closed_history 須在 super().__init__ 前設定，
        # 因為父類 __init__ 會呼叫 _create_managed_widget → _hook_cleanup
        self._batch_deleting = False
        self._closed_history: list[tuple[str, QWidget]] = []
        self.drop_mime = QMimeData()
        self.drop_mime.setData("tab", b"")
        super().__init__(parent)

    # ── WidgetManager 抽象鉤子實作 ─────────────────────────────────

    def _create_managed_widget(self) -> TabWidget:
        tw = TabWidget()
        self._widgets.append(tw)
        self._hook_cleanup(tw)
        tw.window_activated.connect(self.active_window_changed)
        return tw

    def _move_item(self, item, source_widget: TabWidget | None, target_widget: TabWidget | None):
        window = item._window
        if source_widget is not None:
            source_widget._on_close(window)
        if target_widget is not None:
            target_widget.add_tab(window)

    def _widget_of(self, item) -> TabWidget | None:
        for tw in self._widgets:
            if isinstance(tw, TabWidget) and item in tw._tabs:
                return tw
        return None

    def _widget_is_empty(self, widget: QWidget) -> bool:
        return isinstance(widget, TabWidget) and not widget._tabs

    def _source_would_empty(self, source_widget, item) -> bool:
        return isinstance(source_widget, TabWidget) and len(source_widget._tabs) <= 1

    # ── 公開 API ──────────────────────────────────────────────────

    def add_tab(self, window: QWidget):
        if self._widgets:
            self._widgets[0].add_tab(window)
        else:
            tw = self._create_managed_widget()
            self._root_splitter.addWidget(tw)
            tw.add_tab(window)

    def focus_tab_by_title(self, title: str) -> bool:
        """若已有 windowTitle 相同的分頁，切換到該頁並回傳 True；否則回傳 False。"""
        for tw in self._widgets:
            for tab in tw._tabs:
                if tab._window.windowTitle() == title:
                    tw._activate(tab._window)
                    return True
        return False

    def merge_all_tabs(self):
        """將所有面板的分頁合併至最左上角 TabWidget。"""
        if len(self._widgets) <= 1:
            return
        target = self._widgets[0]
        others = list(self._widgets[1:])
        self._restructuring = True
        for src_tw in others:
            for window in [t._window for t in list(src_tw._tabs)]:
                src_tw._on_close(window)
                target.add_tab(window)
        self._restructuring = False
        for src_tw in others:
            self._cleanup_empty(src_tw)

    def delete_all_tabs(self):
        """刪除所有面板的所有分頁（不記錄至歷史）。"""
        self._batch_deleting = True
        self._restructuring = True
        for tw in list(self._widgets):
            for window in [t._window for t in list(tw._tabs)]:
                tw._on_close(window)
        self._restructuring = False
        self._batch_deleting = False
        for src_tw in list(self._widgets[1:]):
            self._cleanup_empty(src_tw)

    def restore_closed_tab(self, window: QWidget):
        """從最近關閉清單還原分頁至左側第一個 TabWidget。"""
        self._closed_history = [
            (t, w) for t, w in self._closed_history if w is not window
        ]
        if self._widgets:
            self._widgets[0].add_tab(window)

    def close_window(self, window: QWidget) -> None:
        """程式端關閉指定 window 所在的分頁，不記錄至最近關閉清單。"""
        for tw in list(self._widgets):
            if any(t._window is window for t in tw._tabs):
                tw._on_close(window)
                # 移除剛才因 hook 加入的歷史記錄
                self._closed_history = [
                    (t, w) for t, w in self._closed_history if w is not window
                ]
                return

    # ── TabWidget 建立與清除鉤子 ──────────────────────────────────

    def _hook_cleanup(self, tw: TabWidget):
        original_on_close = tw._on_close

        def patched_on_close(window: QWidget):
            if not self._restructuring and not self._batch_deleting:
                title = window.windowTitle() or "Untitled"
                self._closed_history = [
                    (t, w) for t, w in self._closed_history if w is not window
                ]
                self._closed_history.insert(0, (title, window))
                if len(self._closed_history) > 20:
                    self._closed_history.pop()
            original_on_close(window)
            if not self._restructuring:
                self._cleanup_empty(tw)

        tw._on_close = patched_on_close


class BMFontChar:
    """BMFont 單個字元資訊"""
    def __init__(self):
        self.id = 0
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.xoffset = 0
        self.yoffset = 0
        self.xadvance = 0
        self.page = 0
        self.chnl = 0


class BMFont:
    """BMFont 點陣圖字型解析器"""

    def __init__(self, fnt_path):
        self.fnt_path = fnt_path
        self.base_dir = os.path.dirname(fnt_path)
        self.face = ""
        self.size = 0
        self.bold = False
        self.italic = False
        self.line_height = 0
        self.base = 0
        self.scale_w = 0
        self.scale_h = 0
        self.pages = {}
        self.chars = {}
        self.kernings = {}
        self._parse_fnt()

    def _parse_fnt(self):
        try:
            with open(self.fnt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('info '):
                        self._parse_info(line)
                    elif line.startswith('common '):
                        self._parse_common(line)
                    elif line.startswith('page '):
                        self._parse_page(line)
                    elif line.startswith('char '):
                        self._parse_char(line)
                    elif line.startswith('kerning '):
                        self._parse_kerning(line)
        except Exception as e:
            print(f"Error parsing BMFont file {self.fnt_path}: {e}")

    def _parse_value(self, line, key):
        pattern = rf'{key}=(?:"([^"]*)"|(\S+))'
        match = re.search(pattern, line)
        if match:
            return match.group(1) if match.group(1) is not None else match.group(2)
        return None

    def _parse_int(self, line, key, default=0):
        value = self._parse_value(line, key)
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def _parse_info(self, line):
        self.face = self._parse_value(line, 'face') or ""
        self.size = self._parse_int(line, 'size')
        self.bold = self._parse_int(line, 'bold') == 1
        self.italic = self._parse_int(line, 'italic') == 1

    def _parse_common(self, line):
        self.line_height = self._parse_int(line, 'lineHeight')
        self.base = self._parse_int(line, 'base')
        self.scale_w = self._parse_int(line, 'scaleW')
        self.scale_h = self._parse_int(line, 'scaleH')

    def _parse_page(self, line):
        page_id = self._parse_int(line, 'id')
        filename = self._parse_value(line, 'file')
        if filename:
            filename = filename.strip('"')
            image_path = os.path.join(self.base_dir, filename)
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    self.pages[page_id] = pixmap
                else:
                    print(f"Warning: Failed to load BMFont image: {image_path}")
            else:
                print(f"Warning: BMFont image not found: {image_path}")

    def _parse_char(self, line):
        char = BMFontChar()
        char.id       = self._parse_int(line, 'id')
        char.x        = self._parse_int(line, 'x')
        char.y        = self._parse_int(line, 'y')
        char.width    = self._parse_int(line, 'width')
        char.height   = self._parse_int(line, 'height')
        char.xoffset  = self._parse_int(line, 'xoffset')
        char.yoffset  = self._parse_int(line, 'yoffset')
        char.xadvance = self._parse_int(line, 'xadvance')
        char.page     = self._parse_int(line, 'page')
        char.chnl     = self._parse_int(line, 'chnl')
        self.chars[char.id] = char

    def _parse_kerning(self, line):
        first  = self._parse_int(line, 'first')
        second = self._parse_int(line, 'second')
        amount = self._parse_int(line, 'amount')
        self.kernings[(first, second)] = amount

    def get_kerning(self, first_char, second_char):
        first_id  = ord(first_char)  if isinstance(first_char,  str) else first_char
        second_id = ord(second_char) if isinstance(second_char, str) else second_char
        return self.kernings.get((first_id, second_id), 0)

    def get_char(self, char):
        char_id = ord(char) if isinstance(char, str) else char
        return self.chars.get(char_id)

    def measure_text(self, text, scale=1.0):
        if not text:
            return (0, 0)
        width = 0
        height = self.line_height * scale
        prev_char = None
        for char in text:
            char_info = self.get_char(char)
            if char_info:
                if prev_char:
                    width += self.get_kerning(prev_char, char) * scale
                width += char_info.xadvance * scale
            prev_char = char
        return (int(width), int(height))

    def render_text(self, text, scale=1.0, color=None):
        if not text or not self.pages:
            return QPixmap()
        width, height = self.measure_text(text, scale)
        if width <= 0 or height <= 0:
            return QPixmap()
        result = QPixmap(width, height)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x = 0
        prev_char = None
        for char in text:
            char_info = self.get_char(char)
            if not char_info:
                prev_char = char
                continue
            if prev_char:
                x += self.get_kerning(prev_char, char) * scale
            page_pixmap = self.pages.get(char_info.page)
            if page_pixmap:
                src_rect = QRect(char_info.x, char_info.y, char_info.width, char_info.height)
                dst_rect = QRect(
                    int(x + char_info.xoffset * scale),
                    int(char_info.yoffset * scale),
                    int(char_info.width * scale),
                    int(char_info.height * scale),
                )
                painter.drawPixmap(dst_rect, page_pixmap, src_rect)
            x += char_info.xadvance * scale
            prev_char = char
        painter.end()
        if color and color.isValid():
            result = self._colorize_pixmap(result, color)
        return result

    def _colorize_pixmap(self, pixmap, color):
        if pixmap.isNull():
            return pixmap
        image = pixmap.toImage()
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                if pixel.alpha() > 0:
                    gray = (pixel.red() + pixel.green() + pixel.blue()) // 3
                    intensity = gray / 255.0
                    new_color = QColor(
                        int(color.red()   * intensity),
                        int(color.green() * intensity),
                        int(color.blue()  * intensity),
                        pixel.alpha(),
                    )
                    image.setPixelColor(x, y, new_color)
        return QPixmap.fromImage(image)


class FontManager:
    """字型管理器，負責載入和管理自訂字型（TTF/OTF 及 BMFont）。"""

    _instance = None
    _fonts_loaded = False
    _font_families = {}
    _bmfonts = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not FontManager._fonts_loaded:
            self._load_fonts()
            FontManager._fonts_loaded = True

    def _load_fonts(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(base_dir, "font")
        if not os.path.exists(font_dir):
            print(f"Warning: Font directory not found: {font_dir}")
            return
        for filename in os.listdir(font_dir):
            filepath = os.path.join(font_dir, filename)
            if filename.lower().endswith(('.ttf', '.otf')):
                self._load_ttf_font(filepath, filename)
            elif filename.lower().endswith('.fnt'):
                self._load_bmfont(filepath, filename)

    def _load_ttf_font(self, font_path, filename):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Warning: Failed to load font: {font_path}")
            return
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family_name = families[0]
            font_key = os.path.splitext(filename)[0]
            FontManager._font_families[font_key] = family_name
            FontManager._font_families[filename]  = family_name

    def _load_bmfont(self, fnt_path, filename):
        try:
            bmfont = BMFont(fnt_path)
            if bmfont.pages:
                font_key = os.path.splitext(filename)[0]
                FontManager._bmfonts[font_key] = bmfont
                FontManager._bmfonts[filename]  = bmfont
        except Exception as e:
            print(f"Warning: Failed to load BMFont: {fnt_path}, {e}")

    def get_font_family(self, font_name):
        if font_name in FontManager._font_families:
            return FontManager._font_families[font_name]
        font_name_lower = font_name.lower()
        for key, family in FontManager._font_families.items():
            if key.lower() == font_name_lower:
                return family
        return None

    def get_bmfont(self, font_name):
        if font_name in FontManager._bmfonts:
            return FontManager._bmfonts[font_name]
        font_name_lower = font_name.lower()
        for key, bmfont in FontManager._bmfonts.items():
            if key.lower() == font_name_lower:
                return bmfont
        return None

    def is_bmfont(self, font_name):
        return self.get_bmfont(font_name) is not None

    def get_available_fonts(self):
        fonts = set()
        for key in FontManager._font_families:
            if not key.lower().endswith(('.ttf', '.otf')):
                fonts.add(key)
        for key in FontManager._bmfonts:
            if not key.lower().endswith('.fnt'):
                fonts.add(key)
        return sorted(fonts)

    def get_ttf_fonts(self):
        return sorted(k for k in FontManager._font_families
                      if not k.lower().endswith(('.ttf', '.otf')))

    def get_bitmap_fonts(self):
        return sorted(k for k in FontManager._bmfonts
                      if not k.lower().endswith('.fnt'))

    def get_font(self, font_name, size=12):
        family = self.get_font_family(font_name)
        return QFont(family, size) if family else QFont("Arial", size)
