"""edit_watch.py 的自動化測試：PanelHeader、PanelWidget、PanelWidgetManager。"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QUndoCommand, QUndoStack
from PyQt6.QtWidgets import QWidget

from edit_watch import PanelHeader, PanelWidget, PanelWidgetManager


class _NullCmd(QUndoCommand):
    """redo/undo 皆無副作用的測試用 command。"""
    def redo(self): pass
    def undo(self): pass


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def manager(qtbot):
    mgr = PanelWidgetManager()
    qtbot.addWidget(mgr)
    mgr.show()
    qtbot.waitExposed(mgr)
    return mgr


@pytest.fixture
def two_panel_manager(qtbot):
    """初始 4 個面板中取前兩個，供需要多 panel 的測試使用。"""
    mgr = PanelWidgetManager()
    qtbot.addWidget(mgr)
    mgr.show()
    qtbot.waitExposed(mgr)
    panel_a = mgr._widgets[0]
    panel_b = mgr._widgets[1]
    return mgr, panel_a, panel_b


@pytest.fixture
def single_panel_manager(qtbot):
    """手動將 _widgets 縮減為一個，測試「最後一個面板不可關閉」。"""
    mgr = PanelWidgetManager()
    qtbot.addWidget(mgr)
    mgr.show()
    qtbot.waitExposed(mgr)
    mgr._widgets = mgr._widgets[:1]
    return mgr


# ── PanelHeader ───────────────────────────────────────────────────────────────

class TestPanelHeader:
    """PanelHeader 是 PanelWidget 的子元件，透過 PanelWidget 間接測試。"""

    @pytest.fixture
    def panel(self, qtbot):
        pw = PanelWidget(manager=None)
        qtbot.addWidget(pw)
        return pw

    def test_height(self, panel):
        assert panel._header.height() == 28

    def test_has_close_button(self, panel):
        assert hasattr(panel._header, '_close_btn')

    def test_cursor_is_size_all(self, panel):
        assert panel._header.cursor().shape() == Qt.CursorShape.SizeAllCursor

    def test_has_panel_mime_format(self, panel):
        assert panel._header.mime.hasFormat("panel")


# ── PanelWidget ───────────────────────────────────────────────────────────────

class TestPanelWidget:
    def test_has_panel_header(self, manager):
        panel = manager._widgets[0]
        assert isinstance(panel._header, PanelHeader)

    def test_manager_reference(self, manager):
        panel = manager._widgets[0]
        assert panel._manager is manager

    def test_initial_not_empty(self, manager):
        panel = manager._widgets[0]
        assert panel._empty is False

    def test_set_empty(self, manager):
        panel = manager._widgets[0]
        panel._set_empty()
        assert panel._empty is True

    def test_close_single_panel_does_nothing(self, qtbot, single_panel_manager):
        """只剩一個 panel 時，關閉鈕不移除 panel。"""
        mgr = single_panel_manager
        panel = mgr._widgets[0]
        qtbot.mouseClick(panel._header._close_btn, Qt.MouseButton.LeftButton)
        assert len(mgr._widgets) == 1

    def test_close_removes_panel_when_multiple(self, qtbot, two_panel_manager):
        mgr, panel_a, panel_b = two_panel_manager
        qtbot.mouseClick(panel_a._header._close_btn, Qt.MouseButton.LeftButton)
        assert panel_a not in mgr._widgets

    def test_close_leaves_other_panel(self, qtbot, two_panel_manager):
        mgr, panel_a, panel_b = two_panel_manager
        qtbot.mouseClick(panel_a._header._close_btn, Qt.MouseButton.LeftButton)
        assert panel_b in mgr._widgets


# ── PanelWidgetManager ────────────────────────────────────────────────────────

class TestPanelWidgetManager:
    def test_initial_widget_count(self, manager):
        assert len(manager._widgets) == 4

    def test_initial_widget_is_panel_widget(self, manager):
        assert isinstance(manager._widgets[0], PanelWidget)

    def test_accept_formats_contains_panel(self, manager):
        assert "panel" in manager._accept_formats

    def test_widget_is_empty_false(self, manager):
        panel = manager._widgets[0]
        assert manager._widget_is_empty(panel) is False

    def test_widget_is_empty_true_after_set_empty(self, manager):
        panel = manager._widgets[0]
        panel._set_empty()
        assert manager._widget_is_empty(panel) is True

    def test_widget_is_empty_rejects_plain_widget(self, manager):
        other = QWidget()
        assert manager._widget_is_empty(other) is False

    def test_widget_of_returns_known_panel(self, manager):
        panel = manager._widgets[0]
        assert manager._widget_of(panel) is panel

    def test_widget_of_returns_none_for_unknown(self, qtbot, manager):
        other = PanelWidget(manager=None)
        qtbot.addWidget(other)
        assert manager._widget_of(other) is None

    def test_move_item_extracts_from_splitter(self, qtbot, two_panel_manager):
        """_move_item(item, source, None) 應物理移除 panel 而非標記 empty。"""
        mgr, panel_a, panel_b = two_panel_manager
        qtbot.addWidget(panel_a)  # 避免孤立 widget 警告
        mgr._move_item(panel_a, panel_a, None)
        assert panel_a._empty is False
        assert panel_a.parentWidget() is None

    def test_move_item_target_side_noop(self, two_panel_manager):
        mgr, panel_a, panel_b = two_panel_manager
        mgr._move_item(panel_a, None, panel_b)
        assert panel_b._empty is False

    def test_two_panels_in_widgets(self, two_panel_manager):
        mgr, panel_a, panel_b = two_panel_manager
        assert len(mgr._widgets) == 4

    def test_close_reduces_widget_count(self, qtbot, two_panel_manager):
        mgr, panel_a, panel_b = two_panel_manager
        initial = len(mgr._widgets)
        qtbot.mouseClick(panel_a._header._close_btn, Qt.MouseButton.LeftButton)
        assert len(mgr._widgets) == initial - 1

    @pytest.mark.parametrize("zone", ["top", "bottom", "left", "right"])
    def test_cross_split_preserves_source_panel(self, manager, zone):
        """Panel A 拖到 Panel B 的分割圖示後，A 依然在 _widgets 且內容不消失。"""
        panel_a = manager._widgets[0]
        panel_b = manager._widgets[1]
        initial_count = len(manager._widgets)
        manager._execute_drop(zone, panel_a, panel_b)
        assert panel_a in manager._widgets
        assert panel_a._empty is False
        assert len(manager._widgets) == initial_count

    @pytest.mark.parametrize("zone", ["top", "bottom", "left", "right"])
    def test_self_split_inner_is_noop(self, manager, zone):
        """面板拖到自身內側任何非中心圖示，widget 數量與內容不變。"""
        panel = manager._widgets[0]
        initial_count = len(manager._widgets)
        manager._execute_drop(zone, panel, panel)
        assert len(manager._widgets) == initial_count
        assert panel in manager._widgets
        assert panel._empty is False

    @pytest.mark.parametrize("zone", ["outer_top", "outer_bottom", "outer_left", "outer_right"])
    def test_self_split_outer_is_noop(self, manager, zone):
        """面板拖到自身外側圖示（root split），widget 數量與內容不變。"""
        panel = manager._widgets[0]
        initial_count = len(manager._widgets)
        manager._execute_drop(zone, panel, panel)
        assert len(manager._widgets) == initial_count
        assert panel in manager._widgets
        assert panel._empty is False

    def test_outer_noop_when_already_at_position(self, manager):
        """已在 root_splitter 最左側的面板拖到 outer_left 應 no-op。"""
        # _obj_explorer 是 _root_splitter 的 widget(0)，方向為 Horizontal
        panel = manager._root_splitter.widget(0)
        initial_count = len(manager._widgets)
        manager._execute_drop('outer_left', panel, panel)
        assert len(manager._widgets) == initial_count
        assert panel in manager._widgets
        assert manager._root_splitter.widget(0) is panel


# ── UndoStack ─────────────────────────────────────────────────────────────────

class TestUndoStack:
    def test_has_undo_stack(self, manager):
        assert hasattr(manager, 'undo_stack')
        assert isinstance(manager.undo_stack, QUndoStack)

    def test_stack_parent_is_manager(self, manager):
        assert manager.undo_stack.parent() is manager

    def test_stack_initially_clean(self, manager):
        assert manager.undo_stack.isClean()

    def test_push_command_increments_count(self, manager):
        manager.push_command(_NullCmd("test"))
        assert manager.undo_stack.count() == 1

    def test_push_command_enables_undo(self, manager):
        manager.push_command(_NullCmd("test"))
        assert manager.undo_stack.canUndo()

    def test_undo_after_push_restores_clean(self, manager):
        manager.push_command(_NullCmd("test"))
        manager.undo_stack.undo()
        assert manager.undo_stack.isClean()

    def test_begin_end_macro_counts_as_one(self, manager):
        manager.begin_macro("batch")
        manager.push_command(_NullCmd("a"))
        manager.push_command(_NullCmd("b"))
        manager.end_macro()
        assert manager.undo_stack.count() == 1

    def test_macro_undoes_in_one_step(self, manager):
        manager.begin_macro("batch")
        manager.push_command(_NullCmd("a"))
        manager.push_command(_NullCmd("b"))
        manager.end_macro()
        manager.undo_stack.undo()
        assert manager.undo_stack.isClean()
