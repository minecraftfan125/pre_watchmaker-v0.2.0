"""
TabWidgetManager 視覺測試 — 手動執行：
    python all_test/visual_tabwidget_manager.py

可測試：
  - 點擊 tab 切換內容
  - 將 tab 拖出 tab bar → DropOverlay 出現
  - 懸停方向圖標 → 白色預覽方塊顯示分割位置
  - 放開 → 執行分割（inner/outer）或合併（center）
  - 關閉 tab → 空的 TabWidget 自動移除
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from special_ui import TabWidgetManager


def make_content(title: str, color: str) -> QWidget:
    w = QWidget()
    w.setWindowTitle(title)
    w.setStyleSheet(f"background-color: {color};")
    layout = QVBoxLayout(w)
    label = QLabel(title)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("color: rgba(255,255,255,0.87); font-size: 20px;")
    layout.addWidget(label)
    return w


def main():
    app = QApplication(sys.argv)

    container = QWidget()
    container.setWindowTitle("TabWidgetManager Visual Test")
    container.resize(1000, 600)
    container.setStyleSheet("background-color: #121212;")

    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    manager = TabWidgetManager()
    layout.addWidget(manager)

    manager.add_tab(make_content("Alpha",  "#1A237E"))
    manager.add_tab(make_content("Beta",   "#1B5E20"))
    manager.add_tab(make_content("Gamma",  "#4A148C"))
    manager.add_tab(make_content("Delta",  "#BF360C"))

    container.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
