"""special_ui.py 的自動化測試：TabWidget.window_activated、TabWidgetManager.active_window_changed。"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from special_ui import TabWidget, TabWidgetManager


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tab_widget(qtbot):
    tw = TabWidget()
    qtbot.addWidget(tw)
    tw.show()
    qtbot.waitExposed(tw)
    return tw


@pytest.fixture
def tab_manager(qtbot):
    mgr = TabWidgetManager()
    qtbot.addWidget(mgr)
    mgr.show()
    qtbot.waitExposed(mgr)
    return mgr


# ── TabWidget.window_activated ────────────────────────────────────────────────

class TestTabWidgetWindowActivated:
    def test_emitted_on_add_tab(self, qtbot, tab_widget):
        w = QWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(tab_widget.window_activated, timeout=1000) as blocker:
            tab_widget.add_tab(w)
        assert blocker.args[0] is w

    def test_emitted_with_correct_window_on_tab_click(self, qtbot, tab_widget):
        w1, w2 = QWidget(), QWidget()
        qtbot.addWidget(w1)
        qtbot.addWidget(w2)
        tab_widget.add_tab(w1)
        tab_widget.add_tab(w2)   # w2 現在 active
        with qtbot.waitSignal(tab_widget.window_activated, timeout=1000) as blocker:
            qtbot.mouseClick(tab_widget._tabs[0], Qt.MouseButton.LeftButton)
        assert blocker.args[0] is w1

    def test_emitted_on_close_reveals_previous(self, qtbot, tab_widget):
        w1, w2 = QWidget(), QWidget()
        qtbot.addWidget(w1)
        qtbot.addWidget(w2)
        tab_widget.add_tab(w1)
        tab_widget.add_tab(w2)   # w2 active
        with qtbot.waitSignal(tab_widget.window_activated, timeout=1000) as blocker:
            qtbot.mouseClick(tab_widget._tabs[1]._close_btn, Qt.MouseButton.LeftButton)
        assert blocker.args[0] is w1


# ── TabWidgetManager.active_window_changed ────────────────────────────────────

class TestTabWidgetManagerActiveWindowChanged:
    def test_emitted_on_add_tab(self, qtbot, tab_manager):
        w = QWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(tab_manager.active_window_changed, timeout=1000) as blocker:
            tab_manager.add_tab(w)
        assert blocker.args[0] is w

    def test_emitted_on_tab_switch(self, qtbot, tab_manager):
        w1, w2 = QWidget(), QWidget()
        qtbot.addWidget(w1)
        qtbot.addWidget(w2)
        tab_manager.add_tab(w1)
        tab_manager.add_tab(w2)   # w2 active
        tw = tab_manager._widgets[0]
        with qtbot.waitSignal(tab_manager.active_window_changed, timeout=1000) as blocker:
            qtbot.mouseClick(tw._tabs[0], Qt.MouseButton.LeftButton)
        assert blocker.args[0] is w1
