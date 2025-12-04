"""
菜單欄模組

包含應用程序的菜單欄和相關功能
"""

import os
from PyQt5.QtWidgets import QWidget, QPushButton, QAction, QFileDialog, QMenu, QHBoxLayout
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QCursor


def load_style():
    """載入菜單樣式"""
    style_path = os.path.join(os.path.dirname(__file__), "style", "menu.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Style file not found: {style_path}")
        return ""


class MenuBar(QWidget):
    """自定義菜單欄類"""

    # 定義信號
    file_imported = pyqtSignal(str)  # 當文件被導入時發出信號，傳遞文件路徑

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setObjectName("menuBar")
        self.setFixedHeight(30)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(load_style())
        self.setup_ui()
        self.setup_menus()

    def setup_ui(self):
        """設置UI佈局"""
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignLeft)

    def setup_menus(self):
        """設置所有菜單"""
        self.create_file_menu()

    def create_file_menu(self):
        """創建 File 菜單"""
        # 創建 File 按鈕
        self.file_button = QPushButton("File")
        self.file_button.setObjectName("menuButton")
        self.file_button.setFixedHeight(30)

        # 創建下拉菜單
        self.file_menu = QMenu(self)
        self.file_menu.setObjectName("fileMenu")

        # Import 動作
        self.import_action = QAction("Import", self)
        self.import_action.setShortcut("Ctrl+I")
        self.import_action.setStatusTip("Import a watch file")
        self.import_action.triggered.connect(self.import_file)
        self.file_menu.addAction(self.import_action)

        # 可以在這裡添加更多菜單項
        # 例如：
        # self.file_menu.addSeparator()
        # export_action = QAction("Export", self)
        # export_action.setShortcut("Ctrl+E")
        # self.file_menu.addAction(export_action)

        # 綁定按鈕點擊事件
        self.file_button.clicked.connect(self.show_file_menu)

        # 添加到佈局
        self.layout.addWidget(self.file_button)

    def show_file_menu(self):
        """顯示 File 菜單"""
        # 在按鈕下方顯示菜單
        button_pos = self.file_button.mapToGlobal(self.file_button.rect().bottomLeft())
        self.file_menu.exec_(button_pos)

    def import_file(self):
        """打開文件選擇對話框"""
        file_dialog = QFileDialog(self.parent_window)
        file_dialog.setWindowTitle("Import Watch File")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Watch Files (*.watch);;All Files (*)")

        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                print(f"Selected file: {file_path}")
                # 發出信號通知主窗口
                self.file_imported.emit(file_path)
                # 返回文件路徑
                return file_path
        return None
