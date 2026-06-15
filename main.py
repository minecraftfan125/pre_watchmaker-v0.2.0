import sys
import ctypes
import ctypes.wintypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy,
    QMenuBar, QMenu,
)
from special_ui import TabWidgetManager
from watch_cabinet import WatchCabinet
from edit_watch import PanelWidgetManager
from lua_script import LuaScriptPanel
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QTimer, QObject, QEvent,
    QAbstractNativeEventFilter,
)
from PyQt6.QtGui import QColor, QPainter, QPixmap, QBrush, QCursor, QUndoGroup, QKeySequence

# ── 常數 ────────────────────────────────────────────────────────────────────
RESIZE_MARGIN = 8  # 邊緣縮放觸發寬度（邏輯像素）

# Windows WM_NCHITTEST 回傳值
_HT_LEFT         = 10
_HT_RIGHT        = 11
_HT_TOP          = 12
_HT_TOP_LEFT     = 13
_HT_TOP_RIGHT    = 14
_HT_BOTTOM       = 15
_HT_BOTTOM_LEFT  = 16
_HT_BOTTOM_RIGHT = 17

# ── 樣式表 ──────────────────────────────────────────────────────────────────
_STYLESHEET = """
QMainWindow, QWidget#central_widget {
    background: #121212;
}
QWidget#title_bar {
    background: #121212;
    border-bottom: 1px solid rgba(255, 255, 255, 13);
}
QLabel#title_label {
    color: rgba(255, 255, 255, 0.87);
    font-size: 13px;
    font-weight: 500;
    padding-left: 4px;
}
QPushButton#btn_min, QPushButton#btn_max {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.60);
    font-size: 13px;
}
QPushButton#btn_min:hover, QPushButton#btn_max:hover {
    background: #262626;
    color: rgba(255, 255, 255, 0.87);
}
QPushButton#btn_close {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.60);
    font-size: 13px;
}
QPushButton#btn_close:hover {
    background: #CF6679;
    color: #000000;
}
QMenuBar {
    background: #1E1E1E;
    color: rgba(255, 255, 255, 0.87);
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    padding: 2px 0;
    font-size: 13px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 12px;
}
QMenuBar::item:selected {
    background: rgba(255, 255, 255, 0.08);
}
QMenuBar::item:pressed {
    background: rgba(255, 255, 255, 0.12);
}
QMenu {
    background: #2D2D2D;
    color: rgba(255, 255, 255, 0.87);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
}
QMenu::item:selected {
    background: rgba(255, 255, 255, 0.08);
}
QMenu::item:disabled {
    color: rgba(255, 255, 255, 0.38);
}
QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.12);
    margin: 4px 0;
}
"""


# ── 工具函式 ─────────────────────────────────────────────────────────────────
def _make_icon(size: int = 16) -> QPixmap:
    """建立簡易佔位圓形圖示"""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor("#90CAF9")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return px


# ── 標題列 ───────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    """自訂標題列：拖曳移動、雙擊最大化、三個控制按鈕"""

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
        icon.setPixmap(_make_icon(16))
        icon.setFixedSize(20, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Watchmaker")
        self.title_label.setObjectName("title_label")

        def _make_btn(name: str, text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setObjectName(name)
            btn.setFixedSize(46, 36)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return btn

        self.btn_min   = _make_btn("btn_min",   "—")
        self.btn_max   = _make_btn("btn_max",   "□")
        self.btn_close = _make_btn("btn_close", "✕")

        self.btn_min.clicked.connect(self.window().showMinimized)
        self.btn_max.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(self.window().close)

        layout.addWidget(icon)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def _toggle_maximize(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self.btn_max.setText("□")
        else:
            win.showMaximized()
            self.btn_max.setText("❐")

    # ── 拖曳移動 ──
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
                # 還原後將拖曳基準點對齊視窗中央，使游標不跳離標題列
                self._drag_pos = QPoint(win.width() // 2, self.height() // 2)
            win.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


# ── Windows 原生縮放事件過濾器（QAbstractNativeEventFilter）─────────────────
class _WinResizeFilter(QAbstractNativeEventFilter):
    """
    攔截 WM_NCHITTEST，回傳對應的 HT* 值讓 OS 處理邊緣縮放。
    使用 QAbstractNativeEventFilter 而非 nativeEvent override，
    避免 PyQt6 6.x 的已知 crash 問題。

    注意：不可在 nativeEventFilter 內呼叫 winId()，
    因為 FramelessWindowHint 下會觸發重入式訊息處理導致 crash。
    改以 refresh_hwnd() 在 show() 後快取 HWND。
    """

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._win = window
        self._hwnd: int | None = None  # 在 show() 後由 refresh_hwnd() 設定

    def refresh_hwnd(self, hwnd: int):
        """在視窗 show() 後呼叫，快取 HWND 供 filter 使用"""
        self._hwnd = hwnd

    def nativeEventFilter(self, event_type: bytes, message) -> tuple[bool, int]:
        if event_type != b"windows_generic_MSG":
            return False, 0
        # HWND 尚未快取（show() 前）或視窗已最大化 → 不攔截
        if self._hwnd is None or self._win.isMaximized():
            return False, 0
        msg = ctypes.wintypes.MSG.from_address(int(message))
        # 只處理本視窗
        if msg.hWnd != self._hwnd:
            return False, 0
        if msg.message != 0x0084:   # WM_NCHITTEST
            return False, 0

        # lParam 低位 = 螢幕 X，高位 = 螢幕 Y（有符號 16 位元）
        x = ctypes.c_int16(msg.lParam & 0xFFFF).value
        y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value

        # GetWindowRect 取得實際像素座標，避免 DPI 縮放誤差
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(
            ctypes.wintypes.HWND(self._hwnd), ctypes.byref(rect)
        )
        dpr = self._win.devicePixelRatio()
        m = int(RESIZE_MARGIN * dpr)
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


# ── Linux / macOS 縮放事件過濾器 ─────────────────────────────────────────────
class _ResizeFilter(QObject):
    """
    安裝在 QApplication 層級，在任何子元件收到事件之前攔截滑鼠操作。
    確保視窗邊緣縮放不受內部元件干擾。
    """

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
        self._win = window
        self.direction: str | None = None
        self._start_global: QPoint | None = None
        self._start_geo: QRect | None = None

    def eventFilter(self, obj, event) -> bool:
        if not isinstance(obj, QWidget) or self._win.isMaximized():
            return False
        if not self._is_descendant(obj):
            return False

        t = event.type()

        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            direction = self._direction_at(event.globalPosition().toPoint())
            if direction:
                self.direction      = direction
                self._start_global  = event.globalPosition().toPoint()
                self._start_geo     = QRect(self._win.geometry())
                self._win.grabMouse()   # 確保後續 move/release 都能收到
                return True

        elif t == QEvent.Type.MouseMove:
            if self.direction:
                self._do_resize(event.globalPosition().toPoint())
                return True

        elif t == QEvent.Type.MouseButtonRelease:
            if self.direction:
                self.direction      = None
                self._start_global  = None
                self._start_geo     = None
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
        m = RESIZE_MARGIN
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
        dx = current.x() - self._start_global.x()
        dy = current.y() - self._start_global.y()
        geo  = QRect(self._start_geo)
        minw = self._win.minimumWidth()
        minh = self._win.minimumHeight()

        if "left" in self.direction:
            if geo.width() - dx >= minw:
                geo.setLeft(geo.left() + dx)
        if "right" in self.direction:
            geo.setRight(max(geo.left() + minw, geo.right() + dx))
        if "top" in self.direction:
            if geo.height() - dy >= minh:
                geo.setTop(geo.top() + dy)
        if "bottom" in self.direction:
            geo.setBottom(max(geo.top() + minh, geo.bottom() + dy))

        self._win.setGeometry(geo)


# ── 主視窗 ───────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """
    無邊框主視窗。

    Windows：透過 QAbstractNativeEventFilter 攔截 WM_NCHITTEST，
             將邊緣縮放委由 OS 處理，子元件完全無法干擾。
    Linux/macOS：在 QApplication 層安裝 QObject 事件過濾器，
                 子元件收到事件之前已攔截，同樣不受子元件影響。
    游標提示：以 QTimer 定期輪詢游標位置並切換形狀（僅 Linux/macOS）。
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 500)
        self.resize(1280, 800)
        self.setStyleSheet(_STYLESHEET)
        self._undo_group = QUndoGroup(self)
        self._build_ui()
        self._setup_platform_resize()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central_widget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar    = TitleBar(self)
        self.tab_manager  = TabWidgetManager()
        self.app_menu_bar = self._build_menu_bar()

        layout.addWidget(self.title_bar)
        layout.addWidget(self.app_menu_bar)
        layout.addWidget(self.tab_manager)

        self.tab_manager.active_window_changed.connect(self._on_active_window_changed)

        cabinet = WatchCabinet()
        cabinet.setWindowTitle("My Watches")
        self.tab_manager.add_tab(cabinet)
        cabinet.watch_selected.connect(self._open_watch)
        cabinet.add_watch_requested.connect(self._add_watch)

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

        edit_menu = bar.addMenu("Edit")
        self._act_undo = self._undo_group.createUndoAction(self, "Undo")
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_redo = self._undo_group.createRedoAction(self, "Redo")
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(self._act_undo)
        edit_menu.addAction(self._act_redo)

        view_menu = bar.addMenu("View")
        view_menu.addAction("Merge All Tabs").triggered.connect(
            self.tab_manager.merge_all_tabs
        )
        view_menu.addAction("Delete All Tabs").triggered.connect(
            self.tab_manager.delete_all_tabs
        )
        view_menu.addSeparator()
        recently_closed = view_menu.addMenu("Recently Closed Tabs")
        recently_closed.aboutToShow.connect(
            lambda: self._rebuild_recently_closed_menu(recently_closed)
        )

        settings_menu = bar.addMenu("Settings")
        settings_menu.addAction("Preferences")

        about_menu = bar.addMenu("About")
        about_menu.addAction("About Watchmaker")

        return bar

    def _on_active_window_changed(self, window: QWidget):
        if isinstance(window, PanelWidgetManager):
            window.undo_stack.setActive(True)
        else:
            self._undo_group.setActiveStack(None)

    def _add_watch(self):
        existing = {
            tab._window.windowTitle()
            for tw in self.tab_manager._widgets
            for tab in tw._tabs
        }
        name = "Untitled"
        n = 2
        while name in existing:
            name = f"Untitled {n}"
            n += 1
        self._open_watch(name)

    def _open_watch(self, name: str):
        title = name or "Untitled"
        for tw in self.tab_manager._widgets:
            for tab in tw._tabs:
                if tab._window.windowTitle() == title:
                    tw._activate(tab._window)
                    return
        panel = PanelWidgetManager()
        panel.setWindowTitle(title)
        self._undo_group.addStack(panel.undo_stack)
        panel.lua_requested.connect(
            lambda inst_id, obj_name, field, value, numeric, expr_mode, p=panel:
                self._open_lua_script(inst_id, obj_name, field, value, numeric, expr_mode, p)
        )
        self.tab_manager.add_tab(panel)

    def _open_lua_script(self, inst_id: int, obj_name: str,
                         field: str, value: str, numeric: bool,
                         expression_mode: bool,
                         panel_mgr: PanelWidgetManager) -> None:
        title = f"{obj_name}  —  {field}"
        if self.tab_manager.focus_tab_by_title(title):
            return
        lua = LuaScriptPanel(obj_name, field, value, panel_mgr,
                             numeric=numeric, expression_mode=expression_mode)
        lua.script_committed.connect(
            lambda v, _id=inst_id, _f=field, _pm=panel_mgr:
                _pm.lua_field_committed(_id, _f, v)
        )
        self.tab_manager.add_tab(lua)

    def _rebuild_recently_closed_menu(self, menu: QMenu):
        menu.clear()
        history = self.tab_manager._closed_history
        if not history:
            no_item = menu.addAction("(No recently closed tabs)")
            no_item.setEnabled(False)
            return
        for title, window in history:
            menu.addAction(title).triggered.connect(
                lambda checked, w=window: self.tab_manager.restore_closed_tab(w)
            )

    # ── 平台縮放設定 ────────────────────────────────────────────────────────
    def _setup_platform_resize(self):
        app = QApplication.instance()
        if sys.platform == "win32": #and False:
            # Windows：原生事件過濾器，OS 接管邊緣縮放
            self._win_resize_filter = _WinResizeFilter(self)
            app.installNativeEventFilter(self._win_resize_filter)
            return

        # Linux / macOS：QObject 事件過濾器
        self._resize_filter = _ResizeFilter(self)
        app.installEventFilter(self._resize_filter)

        # 定期輪詢游標位置以更新游標形狀（無需子元件啟用 mouse tracking）
        self._cursor_override = False
        self._last_direction: str | None = None
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(30)
        self._cursor_timer.timeout.connect(self._update_hover_cursor)
        self._cursor_timer.start()

    def _update_hover_cursor(self):
        """非 Windows 平台：根據游標位置更新縮放提示游標"""
        if self.isMaximized() or self._resize_filter.direction:
            return

        pos = QCursor.pos()
        direction = self._resize_filter._direction_at(pos)

        if direction == self._last_direction:
            return
        self._last_direction = direction

        # 避免 setOverrideCursor 堆疊
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
        # 視窗 show() 後 winId() 已有效，快取給 Windows native filter 使用
        if sys.platform == "win32" and hasattr(self, "_win_resize_filter"):
            self._win_resize_filter.refresh_hwnd(int(self.winId()))

    def closeEvent(self, event):
        # 清除游標覆蓋，避免關閉後殘留
        if hasattr(self, "_cursor_override") and self._cursor_override:
            QApplication.restoreOverrideCursor()
        super().closeEvent(event)


# ── 入口 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
