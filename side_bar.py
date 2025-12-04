import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon, QKeyEvent


def load_style():
    """載入側邊欄樣式"""
    style_path = os.path.join(os.path.dirname(__file__), "style", "side_bar.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Style file not found: {style_path}")
        return ""

class SwitchButton(QPushButton):
    def __init__(self,parent=None,call_view=0,view_name="",signal=None,change_view=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setObjectName("switchButton")
        self.call_view=call_view
        self.view_name=view_name
        self.tip=signal
        self.toggle_view=change_view

    def mousePressEvent(self, event):
        super(SwitchButton, self).mousePressEvent(event)
        change_color(self,self.isChecked())
        self.toggle_view.emit(self.call_view if self.isChecked() else 0)

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self.isChecked():
            self.tip.emit("Press to close "+self.view_name+" page.")
        else:
            self.tip.emit("Press to open "+self.view_name+" page.")

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.tip.emit("")

def colorize_icon(icon, color):
    """将图标着色为指定颜色"""
    if icon.isNull():
        return icon

    # 获取图标的 pixmap
    pixmap = icon.pixmap(icon.actualSize(QSize(256, 256)))

    # 创建着色后的 pixmap
    colored_pixmap = QPixmap(pixmap.size())
    colored_pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

    painter = QPainter(colored_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_Source)
    painter.drawPixmap(0, 0, pixmap)

    # 应用颜色
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(colored_pixmap.rect(), QColor(color))
    painter.end()

    return QIcon(colored_pixmap)

def change_color(obj, state, color="#0078D4"):
    """改变按钮图标的颜色"""
    if not hasattr(obj, '_original_icon'):
        # 保存原始图标
        obj._original_icon = obj.icon()

    if state:
        # 应用着色的图标
        colored_icon = colorize_icon(obj._original_icon, color)
        obj.setIcon(colored_icon)
    else:
        # 恢复原始图标
        obj.setIcon(obj._original_icon)

class SideBar(QWidget):
    toggle_view=pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(60)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(load_style())
        self.set_ui()
        
    def set_ui(self):
        self.side_layout=QVBoxLayout(self)
        self.side_layout.setContentsMargins(0, 0, 0, 0)
        self.side_layout.setAlignment(Qt.AlignTop)
        self.side_layout.setSpacing(0)

    def add_button(self,call,name,signal,img_path):
        self.my_watch_btn = SwitchButton(call_view=call,view_name=name,signal=signal,change_view=self.toggle_view)
        self.my_watch_btn.setIcon(QIcon(img_path))
        self.my_watch_btn.setIconSize(QSize(40, 40))
        self.my_watch_btn.setFixedSize(60, 60)
        self.side_layout.addWidget(self.my_watch_btn)
