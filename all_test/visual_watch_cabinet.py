"""
WatchCabinet 視覺測試 — 手動執行：
    python all_test/visual_watch_cabinet.py

可測試：
  - My Watches 標題與右側排序 / 搜尋工具列
  - 手錶卡片格（FlowLayout 自動換行）
  - Time / Name 排序切換
  - ↑ / ↓ 升降冪切換
  - 搜尋即時過濾
  - 點擊 Add Watch 與手錶卡片的 signal 輸出
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from watch_cabinet import WatchCabinet


def main():
    app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowTitle("WatchCabinet Visual Test")
    win.resize(900, 600)
    win.setStyleSheet("background-color: #121212;")

    layout = QVBoxLayout(win)
    layout.setContentsMargins(0, 0, 0, 0)

    cabinet = WatchCabinet()
    cabinet.watch_selected.connect(lambda name: print(f"watch_selected: {name}"))
    cabinet.add_watch_requested.connect(lambda: print("add_watch_requested"))
    layout.addWidget(cabinet)

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
