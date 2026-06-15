"""_AttrFieldWidget color 欄位的 QColorDialog 樣式隔離測試。

修正背景：swatch 使用裸屬性 QSS（無類別選擇器），避免
「Could not parse stylesheet of object QPushButton」警告。
但裸屬性會沿 parent-child hierarchy 繼承至 QColorDialog
的內部控件，造成 QSpinBox/QLineEdit 破版。

解法：QColorDialog(parent=None)，使其不繼承任何 QSS。
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QColorDialog, QPushButton

from edit_watch import _AttrFieldWidget


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def color_field(qtbot):
    """建立 color schema 的 _AttrFieldWidget，初始值為紅色。"""
    w = _AttrFieldWidget("Color", "ff0000", "color")
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def _find_swatch(field: _AttrFieldWidget) -> QPushButton:
    """取得 color 欄位中的色塊按鈕（唯一的 QPushButton）。"""
    btn = field.findChild(QPushButton)
    assert btn is not None, "找不到 swatch QPushButton"
    return btn


# ── 測試 ──────────────────────────────────────────────────────────────────────

class TestColorDialogIsolation:

    def test_dialog_has_no_parent(self, qtbot, monkeypatch, color_field):
        """點擊 swatch 時開啟的 QColorDialog 必須無父層，
        確保不繼承 swatch 的裸屬性 QSS。"""
        captured: dict = {}

        def mock_exec(self):
            captured["dialog"] = self
            return False  # 模擬取消，不觸發顏色更新

        monkeypatch.setattr(QColorDialog, "exec", mock_exec)

        swatch = _find_swatch(color_field)
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)

        assert "dialog" in captured, "點擊 swatch 後未建立 QColorDialog"
        assert captured["dialog"].parent() is None, (
            "QColorDialog 不應有父層——有父層會讓 swatch 的裸屬性 QSS"
            "（background-color / border-radius）繼承至 dialog 內部控件"
        )

    def test_swatch_stylesheet_uses_bare_properties(self, qtbot, color_field):
        """swatch stylesheet 必須使用裸屬性（無類別/ID 選擇器），
        避免 'Could not parse stylesheet of object QPushButton' 警告。"""
        swatch = _find_swatch(color_field)
        ss = swatch.styleSheet()

        assert "background-color" in ss, "swatch 應設定 background-color"
        assert "border-radius" in ss,    "swatch 應設定 border-radius"

        # 不應出現類別或 ID 選擇器（會觸發 parse 警告）
        assert "QPushButton" not in ss, "swatch QSS 不應含 QPushButton 選擇器"
        assert "#" not in ss.split(":")[0], (
            "swatch QSS 不應含 ID 選擇器（#...）"
        )

    def test_swatch_color_updates_after_pick(self, qtbot, monkeypatch, color_field):
        """選色確認後，swatch 的背景色應更新為新顏色。"""
        from PyQt6.QtGui import QColor

        new_color = QColor("#1a2b3c")

        def mock_exec(self):
            return True  # 模擬確認

        def mock_selected_color(self):
            return new_color

        monkeypatch.setattr(QColorDialog, "exec", mock_exec)
        monkeypatch.setattr(QColorDialog, "selectedColor", mock_selected_color)

        swatch = _find_swatch(color_field)
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)

        assert "1a2b3c" in swatch.styleSheet().lower(), (
            "選色後 swatch 的 background-color 應更新為新的 hex 值"
        )
