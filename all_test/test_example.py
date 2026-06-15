"""範例測試：確認 pytest-qt 環境與 PyQt6 Widget 能正常運作。"""

import pytest
from PyQt6.QtWidgets import QLabel


@pytest.fixture
def label(qtbot):
    w = QLabel("Hello")
    qtbot.addWidget(w)  # 確保測試結束後自動清理
    w.show()
    return w


def test_placeholder(label):
    """確認 Widget 能正常建立並顯示文字。"""
    assert label.text() == "Hello"
    assert label.isVisible()
