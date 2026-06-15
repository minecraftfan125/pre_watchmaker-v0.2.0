"""main.py 的自動化測試：TitleBar、MainWindow、_ResizeFilter。"""

import pytest
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtWidgets import QSizePolicy, QWidget

from main import MainWindow, TitleBar, _ResizeFilter


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def win(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture
def resize_filter(win):
    """建立 _ResizeFilter 並設定視窗到已知位置，方便邊緣座標計算。"""
    f = _ResizeFilter(win)
    # 使用超過 MainWindow 最小尺寸（800×500）的幾何以免被 Qt 截斷
    win.setGeometry(200, 200, 900, 600)
    return f


# ── MainWindow ────────────────────────────────────────────────────────────────

class TestMainWindow:
    def test_frameless_flag(self, win):
        assert win.windowFlags() & Qt.WindowType.FramelessWindowHint

    def test_minimum_width(self, win):
        assert win.minimumWidth() == 800

    def test_minimum_height(self, win):
        assert win.minimumHeight() == 500

    def test_initial_width(self, win):
        assert win.width() == 1280

    def test_initial_height(self, win):
        assert win.height() == 800

    def test_has_title_bar(self, win):
        assert hasattr(win, "title_bar")
        assert isinstance(win.title_bar, TitleBar)

    def test_is_visible(self, win):
        assert win.isVisible()


# ── TitleBar ──────────────────────────────────────────────────────────────────

class TestTitleBar:
    def test_height(self, win):
        assert win.title_bar.height() == 36

    def test_title_text(self, win):
        assert win.title_bar.title_label.text() == "Watchmaker"

    def test_has_btn_min(self, win):
        assert hasattr(win.title_bar, "btn_min")

    def test_has_btn_max(self, win):
        assert hasattr(win.title_bar, "btn_max")

    def test_has_btn_close(self, win):
        assert hasattr(win.title_bar, "btn_close")

    def test_btn_max_initial_text(self, win):
        assert win.title_bar.btn_max.text() == "□"

    def test_maximize_button(self, win, qtbot):
        qtbot.mouseClick(win.title_bar.btn_max, Qt.MouseButton.LeftButton)
        assert win.isMaximized()
        assert win.title_bar.btn_max.text() == "❐"

    def test_restore_button(self, win, qtbot):
        # 先最大化
        qtbot.mouseClick(win.title_bar.btn_max, Qt.MouseButton.LeftButton)
        assert win.isMaximized()
        # 再還原
        qtbot.mouseClick(win.title_bar.btn_max, Qt.MouseButton.LeftButton)
        assert not win.isMaximized()
        assert win.title_bar.btn_max.text() == "□"

    def test_minimize_button(self, win, qtbot):
        qtbot.mouseClick(win.title_bar.btn_min, Qt.MouseButton.LeftButton)
        assert win.isMinimized()

    def test_double_click_maximize(self, win, qtbot):
        qtbot.mouseDClick(win.title_bar, Qt.MouseButton.LeftButton)
        assert win.isMaximized()

    def test_double_click_restore(self, win, qtbot):
        # 先最大化再雙擊還原
        qtbot.mouseClick(win.title_bar.btn_max, Qt.MouseButton.LeftButton)
        assert win.isMaximized()
        qtbot.mouseDClick(win.title_bar, Qt.MouseButton.LeftButton)
        assert not win.isMaximized()


# ── _ResizeFilter 邊緣方向判斷 ────────────────────────────────────────────────

class TestResizeFilterDirection:
    """使用固定幾何 (200,200,900,600)：right=1098, bottom=799, margin=8。"""

    def test_center_is_none(self, resize_filter, win):
        center = QPoint(win.geometry().center())
        assert resize_filter._direction_at(center) is None

    def test_left_edge(self, resize_filter, win):
        pos = QPoint(204, 500)   # 200+4 ≤ 200+8
        assert resize_filter._direction_at(pos) == "left"

    def test_right_edge(self, resize_filter, win):
        pos = QPoint(1095, 500)  # 1099-4 ≥ 1099-8  (right=200+900-1=1099)
        assert resize_filter._direction_at(pos) == "right"

    def test_top_edge(self, resize_filter, win):
        pos = QPoint(600, 204)   # 200+4 ≤ 200+8
        assert resize_filter._direction_at(pos) == "top"

    def test_bottom_edge(self, resize_filter, win):
        pos = QPoint(600, 796)   # 799-3 ≥ 799-8  (bottom=200+600-1=799)
        assert resize_filter._direction_at(pos) == "bottom"

    def test_top_left_corner(self, resize_filter, win):
        pos = QPoint(204, 204)
        assert resize_filter._direction_at(pos) == "top-left"

    def test_top_right_corner(self, resize_filter, win):
        pos = QPoint(1095, 204)
        assert resize_filter._direction_at(pos) == "top-right"

    def test_bottom_left_corner(self, resize_filter, win):
        pos = QPoint(204, 796)
        assert resize_filter._direction_at(pos) == "bottom-left"

    def test_bottom_right_corner(self, resize_filter, win):
        pos = QPoint(1095, 796)
        assert resize_filter._direction_at(pos) == "bottom-right"


# ── _ResizeFilter 縮放計算 ────────────────────────────────────────────────────

class TestResizeFilterResize:
    """起始幾何 (200,200,900,600)：right=1099, bottom=799。"""

    def _setup(self, f, win, direction: str, start: QPoint):
        f.direction = direction
        f._start_global = start
        f._start_geo = QRect(win.geometry())

    def test_resize_right_increases_width(self, resize_filter, win):
        self._setup(resize_filter, win, "right", QPoint(1099, 500))
        resize_filter._do_resize(QPoint(1149, 500))   # 向右拖 50px
        assert win.geometry().width() == 950

    def test_resize_bottom_increases_height(self, resize_filter, win):
        self._setup(resize_filter, win, "bottom", QPoint(600, 799))
        resize_filter._do_resize(QPoint(600, 849))    # 向下拖 50px
        assert win.geometry().height() == 650

    def test_resize_left_decreases_width(self, resize_filter, win):
        self._setup(resize_filter, win, "left", QPoint(200, 500))
        resize_filter._do_resize(QPoint(250, 500))    # 向右拖（縮小）50px
        assert win.geometry().width() == 850
        assert win.geometry().x() == 250             # 左邊界右移

    def test_resize_top_decreases_height(self, resize_filter, win):
        self._setup(resize_filter, win, "top", QPoint(600, 200))
        resize_filter._do_resize(QPoint(600, 250))    # 向下拖（縮小）50px
        assert win.geometry().height() == 550
        assert win.geometry().y() == 250

    def test_resize_respects_min_width(self, resize_filter, win):
        """左邊縮小超過 minimumWidth 時，幾何不變。"""
        geo_before = QRect(win.geometry())
        self._setup(resize_filter, win, "left", QPoint(200, 500))
        # 向右拖 200px：新寬度 700 < minimumWidth 800，應被拒絕
        resize_filter._do_resize(QPoint(400, 500))
        assert win.geometry().width() == geo_before.width()
        assert win.geometry().x() == geo_before.x()

    def test_resize_respects_min_height(self, resize_filter, win):
        """上邊縮小超過 minimumHeight 時，幾何不變。"""
        geo_before = QRect(win.geometry())
        self._setup(resize_filter, win, "top", QPoint(600, 200))
        # 向下拖 200px：新高度 400 < minimumHeight 500，應被拒絕
        resize_filter._do_resize(QPoint(600, 400))
        assert win.geometry().height() == geo_before.height()
        assert win.geometry().y() == geo_before.y()


# ── _ResizeFilter._is_descendant ─────────────────────────────────────────────

class TestResizeFilterDescendant:
    def test_main_window_is_own_descendant(self, resize_filter, win):
        assert resize_filter._is_descendant(win)

    def test_title_bar_is_descendant(self, resize_filter, win):
        assert resize_filter._is_descendant(win.title_bar)

    def test_unrelated_widget_is_not_descendant(self, resize_filter, qtbot):
        other = QWidget()
        qtbot.addWidget(other)
        assert not resize_filter._is_descendant(other)


# ── UndoGroup 整合 ────────────────────────────────────────────────────────────

class TestUndoGroupIntegration:
    def test_has_undo_group(self, win):
        from PyQt6.QtGui import QUndoGroup
        assert hasattr(win, '_undo_group')
        assert isinstance(win._undo_group, QUndoGroup)

    def test_edit_menu_exists(self, win):
        titles = [a.text() for a in win.app_menu_bar.actions()]
        assert "Edit" in titles

    def test_has_undo_redo_actions(self, win):
        assert hasattr(win, '_act_undo')
        assert hasattr(win, '_act_redo')

    def test_undo_action_initially_disabled(self, win):
        assert not win._act_undo.isEnabled()

    def test_redo_action_initially_disabled(self, win):
        assert not win._act_redo.isEnabled()

    def test_open_watch_adds_stack_to_group(self, win):
        win._open_watch("Test Watch")
        assert len(win._undo_group.stacks()) >= 1

    def test_open_watch_sets_active_stack(self, win):
        win._open_watch("Test Watch")
        panel = next(
            t._window
            for tw in win.tab_manager._widgets
            for t in tw._tabs
            if t._window.windowTitle() == "Test Watch"
        )
        assert win._undo_group.activeStack() is panel.undo_stack

    def test_switch_to_cabinet_clears_active_stack(self, qtbot, win):
        win._open_watch("Test Watch")
        tab = next(
            t
            for tw in win.tab_manager._widgets
            for t in tw._tabs
            if t._window.windowTitle() == "My Watches"
        )
        qtbot.mouseClick(tab, Qt.MouseButton.LeftButton)
        assert win._undo_group.activeStack() is None

    def test_undo_action_enabled_after_push(self, win):
        from PyQt6.QtGui import QUndoCommand
        win._open_watch("Test Watch")
        panel = next(
            t._window
            for tw in win.tab_manager._widgets
            for t in tw._tabs
            if t._window.windowTitle() == "Test Watch"
        )
        panel.push_command(QUndoCommand("test"))
        assert win._act_undo.isEnabled()
