from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLayout, QLabel, QStackedWidget
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QFont, QFontDatabase, QColor, QPainter, QPainterPath, QRegion, QDrag
import os

def get_data(obj):
    return ""

def Dragable(cls):
    original_mousePress = cls.mousePressEvent
    original_mouseMove = cls.mouseMoveEvent
    original_mouseRelease = cls.mouseReleaseEvent

    def mousePressEvent(self,event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self,event):
        original_mouseMove(self,event)
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.drag_start_position is None:
            return
        # 检查移动距离是否超过启动拖拽的阈值
        if (event.pos() - self.drag_start_position).manhattanLength() < 5:
            return
        # 创建拖拽对象
        drag = QDrag(self)
        mime_data = QMimeData()
        # 存储组件信息（tooltip）
        mime_data.setText(self.name)
        drag.setMimeData(mime_data)
        self.signal.emit(self.name)
        # 执行拖拽
        result=drag.exec_(Qt.CopyAction)
        if result==Qt.IgnoreAction:
            self.signal.emit("drop")
        # 重置拖拽起始位置
        self.drag_start_position = None
        self.draged=True

    def mouseReleaseEvent(self, event):
        original_mouseRelease(self,event)
        if self.draged is False:
            original_mousePress(self,event)
            self.draged=False

    cls.mousePressEvent=mousePressEvent
    cls.mouseMoveEvent=mouseMoveEvent
    cls.mouseReleaseEvent=mouseReleaseEvent
    return cls

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = []
        self._cached_height = 0

    def addItem(self, item):
        self.itemList.append(item)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        margin = self.contentsMargins()
        size = QSize(0, 0)
        if self.itemList:
            # 計算最小寬度（至少容納一個 item）
            first_hint = self.itemList[0].sizeHint()
            size.setWidth(first_hint.width() + margin.left() + margin.right())
            # 高度使用緩存的計算高度
            size.setHeight(self._cached_height + margin.top() + margin.bottom())
        return size
        
    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect)

    def doLayout(self, rect, testOnly=False):
        margin = self.contentsMargins()
        x = rect.x() + margin.left()
        y = rect.y() + margin.top()
        lineHeight = 0

        for item in self.itemList:
            hint = item.sizeHint()
            spaceX = self.spacing()
            spaceY = self.spacing()

            nextX = x + hint.width() + spaceX

            # 換行
            if nextX > rect.right() - margin.right() and lineHeight > 0:
                x = rect.x() + margin.left()
                y += lineHeight + spaceY
                nextX = x + hint.width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = nextX
            lineHeight = max(lineHeight, hint.height())

        total_height = y + lineHeight - rect.y() + margin.bottom()
        self._cached_height = total_height
        return total_height

class FontManager:
    """字型管理器，負責載入和管理自訂字型"""

    _instance = None
    _fonts_loaded = False
    _font_families = {}  # 字型檔名 -> 字型家族名稱 的映射

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not FontManager._fonts_loaded:
            self._load_fonts()
            FontManager._fonts_loaded = True

    def _load_fonts(self):
        """載入 font 目錄中的所有 TTF 字型"""
        # 取得 font 目錄路徑
        base_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(base_dir, "font")

        if not os.path.exists(font_dir):
            print(f"Warning: Font directory not found: {font_dir}")
            return

        # 遍歷 font 目錄中的所有 TTF 檔案
        for filename in os.listdir(font_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(font_dir, filename)
                self._load_font_file(font_path, filename)

    def _load_font_file(self, font_path, filename):
        """載入單個字型檔案"""
        font_id = QFontDatabase.addApplicationFont(font_path)

        if font_id == -1:
            print(f"Warning: Failed to load font: {font_path}")
            return

        # 取得字型家族名稱
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family_name = families[0]
            # 使用不含副檔名的檔名作為 key
            font_key = os.path.splitext(filename)[0]
            FontManager._font_families[font_key] = family_name
            FontManager._font_families[filename] = family_name  # 也支援完整檔名

    def get_font_family(self, font_name):
        """根據字型名稱取得字型家族名稱

        Args:
            font_name: 字型檔名（可含或不含副檔名）

        Returns:
            字型家族名稱，若找不到則回傳 None
        """
        # 先嘗試直接匹配
        if font_name in FontManager._font_families:
            return FontManager._font_families[font_name]

        # 嘗試不區分大小寫的匹配
        font_name_lower = font_name.lower()
        for key, family in FontManager._font_families.items():
            if key.lower() == font_name_lower:
                return family

        return None

    def get_available_fonts(self):
        """取得所有可用字型的列表

        Returns:
            list: 字型名稱列表（不含副檔名）
        """
        # 只回傳不含副檔名的 key
        return [k for k in FontManager._font_families.keys()
                if not k.lower().endswith(('.ttf', '.otf'))]

    def get_font(self, font_name, size=12):
        """取得 QFont 物件

        Args:
            font_name: 字型檔名
            size: 字型大小

        Returns:
            QFont 物件
        """
        family = self.get_font_family(font_name)
        if family:
            return QFont(family, size)
        else:
            # 回傳預設字型
            return QFont("Arial", size)

class WatchFaceText(QLabel):
    """錶面文字元件

    支援自訂字型、顏色、大小等屬性的文字標籤。
    可用於顯示時間、日期、天氣等資訊。

    Signals:
        text_changed: 文字內容改變時發出
        font_changed: 字型改變時發出
    """

    text_changed = pyqtSignal(str)
    font_changed = pyqtSignal(str)

    def __init__(self, text="", parent=None):
        """初始化 Watch_Face_Text

        Args:
            text: 初始文字內容
            parent: 父元件
        """
        super().__init__(text, parent)

        # 初始化字型管理器
        self._font_manager = FontManager()

        # 預設屬性
        self._font_name = ""
        self._font_size = 12
        self._text_color = QColor(255, 255, 255)  # 預設白色

        # 設定基本樣式
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: transparent;")

    def set_font(self, font_name, size=None):
        """設定字型

        Args:
            font_name: 字型檔名（來自 font 目錄）
            size: 字型大小（可選，若不指定則使用當前大小）
        """
        if size is not None:
            self._font_size = size

        self._font_name = font_name
        font = self._font_manager.get_font(font_name, self._font_size)
        super().setFont(font)

        self.font_changed.emit(font_name)

    def set_font_size(self, size):
        """設定字型大小

        Args:
            size: 字型大小
        """
        self._font_size = size
        if self._font_name:
            self.set_font(self._font_name, size)
        else:
            font = self.font()
            font.setPointSize(size)
            super().setFont(font)

    def set_text_color(self, color):
        """設定文字顏色

        Args:
            color: QColor 或顏色字串（如 "#FFFFFF" 或 "white"）
        """
        if isinstance(color, str):
            self._text_color = QColor(color)
        elif isinstance(color, QColor):
            self._text_color = color
        else:
            return

        self.setStyleSheet(f"color: {self._text_color.name()}; background-color: transparent;")

    def setText(self, text):
        """設定文字內容

        Args:
            text: 文字內容
        """
        super().setText(text)
        self.text_changed.emit(text)

    def get_font_name(self):
        """取得當前字型名稱"""
        return self._font_name

    def get_font_size(self):
        """取得當前字型大小"""
        return self._font_size

    def get_text_color(self):
        """取得當前文字顏色"""
        return self._text_color

    @staticmethod
    def get_available_fonts():
        """取得所有可用字型列表

        Returns:
            list: 可用字型名稱列表
        """
        return FontManager().get_available_fonts()

class CircularButton(QPushButton):
    """圓形按鈕

    只有點擊圓形區域內的像素才會觸發按鈕事件。
    按鈕會自動根據寬高中較小的值來決定圓形直徑。
    """

    def __init__(self, text="", parent=None):
        """初始化圓形按鈕

        Args:
            text: 按鈕文字
            parent: 父元件
        """
        super().__init__(text, parent)

        # 設定透明背景，讓圓形外的區域不顯示
        self.setAttribute(Qt.WA_TranslucentBackground)

    def mousePressEvent(self, event):
        # 取得按鈕中心點
        center_x = self.width() / 2
        center_y = self.height() / 2

        # 計算圓形半徑（取寬高較小值的一半）
        radius = min(self.width(), self.height()) / 2

        # 計算點擊位置到中心的距離
        dx = event.x() - center_x
        dy = event.y() - center_y
        distance = (dx * dx + dy * dy) ** 0.5

        # 判斷是否在圓形內
        if distance <= radius:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        """繪製圓形按鈕

        Args:
            event: 繪圖事件
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 計算圓形區域
        diameter = min(self.width(), self.height())
        x = (self.width() - diameter) / 2
        y = (self.height() - diameter) / 2

        # 設定裁剪區域為圓形
        path = QPainterPath()
        path.addEllipse(x, y, diameter, diameter)
        painter.setClipPath(path)

        # 繪製背景
        if self.isDown():
            painter.setBrush(QColor("#1a5fb4"))  # 按下時的顏色
        elif self.underMouse():
            painter.setBrush(QColor("#3584e4"))  # 懸停時的顏色
        else:
            painter.setBrush(QColor("#2a2a2a"))  # 預設顏色

        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(x), int(y), int(diameter), int(diameter))

        # 繪製邊框
        painter.setPen(QColor("#4a4a4a"))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(int(x), int(y), int(diameter), int(diameter))

        # 繪製文字
        painter.setPen(QColor("#ffffff"))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())

        painter.end()

    def setCircularStyleSheet(self, normal_color="#2a2a2a", hover_color="#3584e4",
                               pressed_color="#1a5fb4", border_color="#4a4a4a",
                               text_color="#ffffff"):
        """設定圓形按鈕的顏色樣式

        Args:
            normal_color: 預設背景色
            hover_color: 懸停時背景色
            pressed_color: 按下時背景色
            border_color: 邊框顏色
            text_color: 文字顏色
        """
        self._normal_color = QColor(normal_color)
        self._hover_color = QColor(hover_color)
        self._pressed_color = QColor(pressed_color)
        self._border_color = QColor(border_color)
        self._text_color = QColor(text_color)
        self.update()

class StackWidget(QStackedWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.correspond={}

    def addWidget(self, widget,obj=None , switch=True):
        if obj in self.correspond:
            self.setCurrentWidget(self.correspond[obj])
            return 1
        self.correspond[obj]=widget
        index=super().addWidget(widget)
        if switch:
            self.setCurrentIndex(index)
        return 0
    
    def insertWidget(self, index, widget, obj=None, switch=True):
        if obj in self.correspond:
            super().removeWidget(widget)
        else:
            self.correspond[obj]=widget
        super().insertWidget(index, widget)
        if switch:
            self.setCurrentIndex(index)

    def removeWidget(self, widget):
        new_correspond=[]
        for i in self.correspond.items():
            if not widget in i:
                new_correspond.append(i)
        self.correspond=dict(new_correspond)
        return super().removeWidget(widget)