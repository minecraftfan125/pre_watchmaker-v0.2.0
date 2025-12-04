import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon, QKeyEvent


def load_style():
    """載入提示列樣式"""
    style_path = os.path.join(os.path.dirname(__file__), "style", "tip_bar.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Style file not found: {style_path}")
        return ""


class TipBar(QWidget):
    set_text=pyqtSignal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.set_ui()
        self.set_text.connect(self.change_text)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(load_style())
    
    def set_ui(self):
        self.setObjectName("tipBar")
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tip=QLabel()
        self.tip.setObjectName("tipLabel")
        layout.addWidget(self.tip)

    def enterEvent(self,event):
        super().enterEvent(event)
        self.set_text.emit("Any annotations for any object will be written here.")

    def leaveEvent(self,event):
        super().leaveEvent(event)
        self.set_text.emit("")

    @pyqtSlot(str)
    def change_text(self,text=""):
        self.tip.setText(text)