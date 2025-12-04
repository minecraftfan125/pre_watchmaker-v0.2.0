import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSplitter,
                             QScrollArea, QGridLayout, QFrame, QStackedWidget,
                             QSizePolicy)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from PyQt5.QtGui import QFont, QIcon, QMouseEvent, QPixmap
from edit_view import EditView
from menu import MenuBar
from tip_bar import TipBar
from side_bar import SideBar
from my_watches_view import WatchesView
from common import StackWidget

app=QApplication(sys.argv)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 設置無邊框視窗
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setMinimumSize(300,200)

        # 視窗初始大小
        self.resize(1000, 700)

        # 用於拖曳視窗的變量
        self.dragging = False
        self.drag_position = QPoint()

        # 用於調整大小的變量
        self.resizing = False
        self.resize_edge = None
        self.resize_margin = 6

        # 儲存視窗狀態
        self.is_maximized = False
        self.previous_geometry = None

        self.scrapbook=[]

        # 建立UI
        self.setup_ui()

    def setup_ui(self):
        """設置使用者介面"""
        # 主容器
        self.tip_bar=TipBar()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 建立標題列
        self.create_title_bar()
        main_layout.addWidget(self.title_bar)

        # 建立菜單欄
        self.menu_bar = MenuBar(self)
        main_layout.addWidget(self.menu_bar)

        # 內容區域
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        main_layout.addWidget(content_widget)
        content_layout=QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.setAlignment(Qt.AlignLeft)
        #側邊欄
        self.side_bar=SideBar()
        self.side_bar.add_button(1,"\"My watches\"",self.tip_bar.set_text,"img/my_watches/btn_wm.png")
        content_layout.addWidget(self.side_bar)

        view_layout=QVBoxLayout(content_widget)
        content_layout.addLayout(view_layout)

        # 創建主內容區域
        self.main_content_area = StackWidget()
        self.side_bar.toggle_view.connect(self.main_content_area.setCurrentIndex)
        self.main_content_area.setObjectName("mainContentArea")
        view_layout.addWidget(self.main_content_area)

        # 預設不顯示任何視圖（顯示空白）
        empty_widget = QWidget()
        empty_widget.setObjectName("emptyWidget")
        self.main_content_area.addWidget(empty_widget)
        # 創建 My Watches 視圖
        self.my_watches=WatchesView(signal=self.tip_bar.set_text, scrapbook=self.scrapbook)
        self.main_content_area.addWidget(self.my_watches,False)
        self.my_watches.summon_view.connect(
            lambda obj, data: self.main_content_area.addWidget(
                EditView(data=data, tip_signal=self.tip_bar.set_text), obj
            )
        )
        
        view_layout.addWidget(self.tip_bar)

        # 應用深色主題樣式
        self.apply_dark_theme()

        #使子元件偵測滑鼠移動
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)

    def create_title_bar(self):
        self.title_bar = QWidget()
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setFixedHeight(40)

        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 0, 0)
        title_layout.setSpacing(0)

        # 應用程式標題
        self.title_label = QLabel("WatchMaker-PC")
        self.title_label.setObjectName("titleLabel")
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        # 視窗控制按鈕
        button_size = 40

        # 最小化按鈕
        self.min_button = QPushButton("−")
        self.min_button.setObjectName("minButton")
        self.min_button.setFixedSize(button_size, button_size)
        self.min_button.clicked.connect(self.showMinimized)
        title_layout.addWidget(self.min_button)

        # 最大化/還原按鈕
        self.max_button = QPushButton("□")
        self.max_button.setObjectName("maxButton")
        self.max_button.setFixedSize(button_size, button_size)
        self.max_button.clicked.connect(self.toggle_maximize)
        title_layout.addWidget(self.max_button)

        # 關閉按鈕
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(button_size, button_size)
        self.close_button.clicked.connect(self.close)
        title_layout.addWidget(self.close_button)

    def on_file_imported(self, file_path):
        """處理文件導入"""
        print(f"Main window received file: {file_path}")
        # TODO: 實現文件導入邏輯
        # 例如：解析文件、加載手錶數據等

    def mouseDoubleClickEvent(self, event):
        """處理滑鼠雙擊事件（雙擊標題列最大化/還原）"""
        if event.button() == Qt.LeftButton and event.y() <= self.title_bar.height():
            self.toggle_maximize()
            event.accept()

    def toggle_maximize(self):
        """切換最大化/還原視窗"""
        if self.is_maximized:
            # 還原視窗
            if self.previous_geometry:
                self.setGeometry(self.previous_geometry)
            self.is_maximized = False
            self.max_button.setText("□")
        else:
            # 最大化視窗
            self.previous_geometry = self.geometry()
            desktop = QApplication.desktop()
            available_geometry = desktop.availableGeometry(self)
            self.setGeometry(available_geometry)
            self.is_maximized = True
            self.max_button.setText("❐")

    def mousePressEvent(self, event):
        """處理滑鼠按下事件"""
        if event.button() == Qt.LeftButton:
            # 檢查是否點擊在邊緣上（用於調整大小）
            edge = self.get_resize_edge(event.pos())
            if edge and not self.is_maximized:
                self.resizing = True
                self.resize_edge = edge
                self.resize_start_pos = event.globalPos()
                self.resize_start_geometry = self.geometry()
                event.accept()
            # 檢查是否點擊在標題列上（用於拖曳視窗）
            elif event.y() <= self.title_bar.height():
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()      

    def mouseMoveEvent(self, event):
        """處理滑鼠移動事件"""
        if event.buttons() == Qt.LeftButton:
            # 拖曳視窗
            if self.dragging and not self.is_maximized:
                self.move(event.globalPos() - self.drag_position)
                event.accept()
            # 調整視窗大小
            elif self.resizing:
                self.resize_window(event.globalPos())
                event.accept()
        elif not self.is_maximized:
            # 更新滑鼠游標樣式
            edge = self.get_resize_edge(event.pos())
            self.update_cursor(edge)
        
    def mouseReleaseEvent(self, event):
        """處理滑鼠釋放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_edge = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()

    def get_resize_edge(self, pos):
        """判斷滑鼠位置是否在可調整大小的邊緣"""
        rect = self.rect()
        margin = self.resize_margin

        on_left = pos.x() <= margin
        on_right = pos.x() >= rect.width() - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= rect.height() - margin

        if on_top and on_left:
            return 'top-left'
        elif on_top and on_right:
            return 'top-right'
        elif on_bottom and on_left:
            return 'bottom-left'
        elif on_bottom and on_right:
            return 'bottom-right'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        return None

    def update_cursor(self, edge):
        """根據邊緣位置更新游標樣式"""
        if edge in ['top', 'bottom']:
            self.setCursor(Qt.SizeVerCursor)
        elif edge in ['left', 'right']:
            self.setCursor(Qt.SizeHorCursor)
        elif edge in ['top-left', 'bottom-right']:
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in ['top-right', 'bottom-left']:
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def resize_window(self, global_pos):
        """調整視窗大小"""
        if not self.resize_edge:
            return

        delta = global_pos - self.resize_start_pos
        geometry = QRect(self.resize_start_geometry)

        if 'left' in self.resize_edge:
            new_width = geometry.width() - delta.x()
            if new_width >= self.minimumWidth():
                geometry.setLeft(self.resize_start_geometry.left() + delta.x())
        elif 'right' in self.resize_edge:
            new_width = geometry.width() + delta.x()
            if new_width >= self.minimumWidth():
                geometry.setRight(self.resize_start_geometry.right() + delta.x())

        if 'top' in self.resize_edge:
            new_height = geometry.height() - delta.y()
            if new_height >= self.minimumHeight():
                geometry.setTop(self.resize_start_geometry.top() + delta.y())
        elif 'bottom' in self.resize_edge:
            new_height = geometry.height() + delta.y()
            if new_height >= self.minimumHeight():
                geometry.setBottom(self.resize_start_geometry.bottom() + delta.y())

        self.setGeometry(geometry)

    def apply_dark_theme(self):
        """應用深色主題樣式，從外部 QSS 檔案載入"""
        import os
        style_path = os.path.join(os.path.dirname(__file__), "style", "app.qss")
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                style = f.read()
            self.setStyleSheet(style)
        except FileNotFoundError:
            print(f"Warning: Style file not found: {style_path}")


# 啟動應用程式
if __name__ == "__main__":
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
