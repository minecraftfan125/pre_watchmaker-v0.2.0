"""
TabWidget 視覺測試 — 手動執行：
    python all_test/visual_tabwidget.py

可測試：
  - 點擊 tab 切換內容
  - 關閉 tab 後回退到上一個選中的 tab
  - 拖曳 tab 重新排列順序
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from special_ui import TabWidget


def make_content(title: str, color: str) -> QWidget:
    w = QWidget()
    w.setWindowTitle(title)
    w.setStyleSheet(f"background-color: {color};")
    layout = QVBoxLayout(w)
    label = QLabel(title)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("color: rgba(255,255,255,0.87); font-size: 18px;")
    layout.addWidget(label)
    return w


def main():
    app = QApplication(sys.argv)

    container = QWidget()
    container.setWindowTitle("TabWidget Visual Test")
    container.resize(800, 500)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    tab_widget = TabWidget()
    layout.addWidget(tab_widget)

    tab_widget.add_tab(make_content("Alpha",        "#1A237E"))
    tab_widget.add_tab(make_content("Beta",         "#1B5E20"))
    tab_widget.add_tab(make_content("Long Tab Name That Gets Clipped", "#4A148C"))
    tab_widget.add_tab(make_content("Delta",        "#BF360C"))

    container.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
