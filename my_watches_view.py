import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon, QKeyEvent
from common import FlowLayout


def load_style():
    """載入 My Watches 視圖樣式"""
    style_path = os.path.join(os.path.dirname(__file__), "style", "my_watches_view.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Style file not found: {style_path}")
        return ""

class WatchCard(QFrame):
    def __init__(self,img,name,parent=None,signal=None,scrapbook=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(140, 200)
        self.tip=signal[0]
        self.summon=signal[1]
        self.scrapbook=scrapbook
        self.watchface=""
        self.name=name
        self.img=img
        self.set_ui(img,name)

    def set_ui(self,img,name):
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(5, 5, 5, 5)
        card_layout.setSpacing(5)

        # 圖片區域
        image_label = QLabel()
        image_label.setObjectName("watchImage")
        image_label.setFixedSize(130, 160)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setScaledContents(True)

        # 載入圖片（如果路徑存在）
        pixmap = QPixmap(img)
        if not pixmap.isNull():
            image_label.setPixmap(pixmap)
        else:
            # 如果圖片不存在，顯示佔位符
            image_label.setText("No Image")
            image_label.setStyleSheet("background-color: #3d3d3d; color: #888888;")

        card_layout.addWidget(image_label)

        # 名稱標籤
        name_label = QLabel(name)
        name_label.setObjectName("watchName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setFixedHeight(30)
        card_layout.addWidget(name_label)

    def mousePressEvent(self, event):
        self.summon.emit(self,self.watchface)

    def change_watchface(self,watchface):
        self.watchface=watchface

    def enterEvent(self, event):
        super().enterEvent(event)
        self.tip.emit("Right-click to display menu.")

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.tip.emit("")

class WatchesView(QScrollArea):
    summon_view=pyqtSignal(object,list)
    def __init__(self,parent=None,signal=None,scrapbook=None):
        super().__init__(parent)
        self.tip=signal
        self.setObjectName("myWatchesContainer")
        self.setWidgetResizable(True)
        self.setMinimumWidth(180)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrapbook=scrapbook
        self.set_ui()

    def set_ui(self):
        # 創建內部容器 widget
        self.container = QWidget()
        self.container.setObjectName("watchesGridWidget")
        self.setWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)
        container_layout.setAlignment(Qt.AlignTop)

        title_layout=QHBoxLayout()
        container_layout.addLayout(title_layout)

        title_label = QLabel("my watches")
        title_label.setObjectName("myWatchesTitle")
        title_layout.addWidget(title_label)
        #sort

        # 創建卡片容器 widget

        self.cards_content = FlowLayout()
        self.cards_content.setObjectName("cardsContainer")
        self.cards_content.setContentsMargins(20,10,20,10)
        self.cards_content.setSpacing(20)
        container_layout.addLayout(self.cards_content)

        # 儲存手錶列表（目前為空）
        self.watches_list = []

        # 添加 "Add New Watch" 按鈕作為第一個卡片
        self.create_add_watch_card()
        self.setStyleSheet(load_style())

    def create_add_watch_card(self):
        """創建 'Add New Watch' 卡片（第一個卡片）"""
        # 卡片容器
        add_card = QFrame()
        add_card.setObjectName("card")
        add_card.setFrameShape(QFrame.StyledPanel)
        add_card.setFixedSize(140, 200)
        add_card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(add_card)
        card_layout.setContentsMargins(5, 5, 5, 5)
        card_layout.setSpacing(5)

        # 圖片區域
        image_label = QLabel()
        image_label.setObjectName("addWatchImage")
        image_label.setFixedSize(130, 160)
        image_label.setAlignment(Qt.AlignCenter)

        # 載入添加按鈕圖片
        pixmap = QPixmap("img/my_watches/btn_new_watch.png")
        pixmap = pixmap.scaled(80,80)
        if not pixmap.isNull():
            image_label.setPixmap(pixmap)
        else:
            # 如果圖片不存在，顯示文字
            image_label.setText("+")
            image_label.setStyleSheet("background-color: #3d3d3d; color: #0078D4; font-size: 48px;")
        card_layout.addWidget(image_label)

        text_label=QLabel()
        text_label.setText("add new watch")
        text_label.setObjectName("addWatchText")
        card_layout.addWidget(text_label)

        add_card.mousePressEvent=lambda event:self.summon_view.emit(add_card,[""])

        self.cards_content.addWidget(add_card)

    def add_watch(self,img,name):
        """添加新的手錶卡片"""
        new_card=WatchCard(img,name,parent=None,signal=[self.tip,self.summon_view],scrapbook=self.scrapbook)
        self.watches_list.append(new_card)
