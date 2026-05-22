from PyQt5.QtWidgets import (
    QSizePolicy,
    QPushButton,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsEllipseItem,
    QUndoCommand,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent, QRectF
from PyQt5.QtGui import (
    QPixmap,
    QIcon,
    QColor,
    QPen,
    QBrush,
    QKeySequence,
    QTransform
)
from PyQt5.QtWidgets import QShortcut
import common
import edit_view.preview_obj as preview_obj
from edit_view.drag_effect import *


class AddLayer(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, layer):
        super().__init__()
        self.scene = scene
        self.layer = layer

    def redo(self):
        self.scene.addItem(self.layer)

    def undo(self):
        self.scene.removeItem(self.layer)


class DelLayer(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, layer, hash_table: dict):
        super().__init__()
        self.scene = scene
        self.layer = layer
        self.hash_table = hash_table

    def redo(self):
        self.scene.removeItem(self.layer)
        self.hash_table.pop(self.layer.id, None)

    def undo(self):
        self.scene.addItem(self.layer)
        self.hash_table[self.layer.id] = self.layer


class WatchPreview(QGraphicsView):
    select = pyqtSignal(object)
    summon = pyqtSignal(object, object, object)
    receive = pyqtSignal(object, object, object)
    view_change = pyqtSignal(QGraphicsView,QTransform)
    delete = pyqtSignal(int)

    # 場景固定大小 (錶面尺寸)
    SCENE_SIZE = 512

    def __init__(
        self,
        undo_stack: common.UndoGroupStack | None = None,
        id_stack=None,
        parent=None,
    ):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.hash_table = {}
        self.id_stack = id_stack
        self.camara_view = QRect(-256, -256, 512, 512)
        self.sence = preview_obj.GraphicsScene(self,self.view_change)
        self.sence.selection_changed.connect(self.select.emit)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # 設定固定的場景範圍
        self.sence.setSceneRect(
            -self.SCENE_SIZE / 2, -self.SCENE_SIZE / 2, self.SCENE_SIZE, self.SCENE_SIZE
        )
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setAcceptDrops(True)
        self.receive.connect(self.summon_component)
        self.setScene(self.sence)
        self.scene()
        # 隱藏滾動條但仍可用於平移
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 設置拖放模式
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.view_topleft=self.mapToScene(self.viewport().rect().topLeft())
        self._background_circle = None
        self.set_ui()

    def set_ui(self):
        self.override = OverrideWidget(
            "drop here\nadd new item", "img/edit/view_drag.png", self
        )
        self._create_background_circle()
        self._create_undo_redo_buttons()
        self._setup_shortcuts()

    def _create_undo_redo_buttons(self):
        base_path = "img/edit"

        self.btn_undo = QPushButton(self)
        self.btn_undo.mouseMoveEvent = lambda event: event.ignore()
        self.btn_undo.setIcon(QIcon(QPixmap(f"{base_path}/undo-alt.png")))
        self.btn_undo.setIconSize(QSize(24, 24))
        self.btn_undo.setFixedSize(28, 28)
        self.btn_undo.setStyleSheet(
            "QPushButton { border: none; background: transparent; }"
        )
        self.btn_undo.setToolTip("Undo (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo_action)
        self.btn_undo.move(10, 10)
        self.btn_undo.show()

        self.btn_redo = QPushButton(self)
        self.btn_redo.mouseMoveEvent = lambda event: event.ignore()
        self.btn_redo.setIcon(QIcon(QPixmap(f"{base_path}/redo-alt.png")))
        self.btn_redo.setIconSize(QSize(24, 24))
        self.btn_redo.setFixedSize(28, 28)
        self.btn_redo.setStyleSheet(
            "QPushButton { border: none; background: transparent; }"
        )
        self.btn_redo.setToolTip("Redo (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.redo_action)
        self.btn_redo.move(44, 10)
        self.btn_redo.show()
        self.btn_redo.installEventFilter(self)
        self.btn_undo.installEventFilter(self)

    def _setup_shortcuts(self):
        self.shortcut_undo = QShortcut(QKeySequence.Undo, self)
        self.shortcut_undo.activated.connect(self.undo_action)

        self.shortcut_redo = QShortcut(QKeySequence.Redo, self)
        self.shortcut_redo.activated.connect(self.redo_action)

    def undo_action(self):
        if self.undo_stack:
            self.undo_stack.undo()

    def redo_action(self):
        if self.undo_stack:
            self.undo_stack.redo()

    def _create_background_circle(self):
        """創建背景圓形"""
        self._background_circle = QGraphicsEllipseItem()
        self._background_circle.setBrush(QBrush(QColor("#0e0e0e")))
        self._background_circle.setPen(QPen(Qt.NoPen))
        self._background_circle.setZValue(-1000)  # 確保在最底層
        self._background_circle.setAcceptDrops(False)  # 不接受拖放事件
        self._background_circle.setAcceptedMouseButtons(Qt.NoButton)  # 不接受滑鼠事件
        self.sence.addItem(self._background_circle)
        self._update_background_circle()

    def _update_background_circle(self):
        """更新背景圓形的大小和位置（使用場景座標）"""
        if self._background_circle is None:
            return

        margin = 50
        # 使用場景尺寸計算
        diameter = self.SCENE_SIZE - margin * 2

        # 設置圓形的位置和大小
        self._background_circle.setRect(
            -diameter / 2, -diameter / 2, diameter, diameter
        )

    def resizeEvent(self, event):
        view = QRect(self.view_topleft.toPoint(), event.oldSize())
        super().resizeEvent(event)
        self.override.resize(self.size())
        rect = self.mapToScene(view).boundingRect()
        self.fitInView(QRectF(rect), Qt.AspectRatioMode.KeepAspectRatio)
        self.view_change.emit(self,self.transform())

    def showEvent(self, event):
        super().showEvent(event)
        # 首次顯示時也要調整縮放
        self.fitInView(self.sence.sceneRect(), Qt.KeepAspectRatio)
        self.view_change.emit(self,self.transform())

    def paintEvent(self, a0):
        super().paintEvent(a0)

    def push_undo_command(self, layer):
        command = AddLayer(self.sence, layer)
        self.undo_stack.push(command)

    def summon_component(self, layer_type, signal_dict, hash_id):
        """根據屬性和圖層類型創建元件並顯示在預覽區"""
        # 使用 summon_obj 的 create_layer 函數創建對應的圖層
        layer = preview_obj.create_layer(layer_type, signal_dict, hash_id, self.sence)
        self.push_undo_command(layer)
        # 儲存到 hash_table
        self.hash_table[hash_id] = layer

    def eventFilter(self, watched, event):
        if event.type() == QEvent.DragMove:
            self.dragMoveEvent(event)
        return False

    def dragEnterEvent(self, event):
        """拖拽進入時接受事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.is_drag_over = True
            self.override.hide()

    def dragLeaveEvent(self, event):
        """拖拽離開時重置"""
        self.is_drag_over = False
        self.override.show()

    def dragMoveEvent(self, event):
        """必須顯式接受移動事件，否則 dropEvent 不會觸發"""
        if event.mimeData().hasText():
            event.acceptProposedAction()  # 關鍵：直接告訴 Qt 這裡可以放
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            # 將視窗座標轉換為場景座標，並計算相對於中心的位置
            scene_pos = self.mapToScene(event.pos())
            x = int(scene_pos.x())
            y = int(scene_pos.y())
            self.summon.emit(event.mimeData().text(), (x, y), 0)
            event.acceptProposedAction()
        self.override.hide()

    def wheelEvent(self, event):
        # 檢查是否按下了 Ctrl 鍵
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.1 if angle > 0 else 0.9
            self.scale(factor, factor)
            self.view_change.emit(self,self.transform())
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            items = self.sence.selectedItems()
            if items and hasattr(items[0], 'id'):
                self.delete.emit(items[0].id)
                return
        if event.key() == Qt.Key.Key_Control:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            # 鬆開 Ctrl，切換回框選模式
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.view_topleft=self.mapToScene(self.viewport().rect().topLeft())

    def required_visual_effects(self, event):
        return event.pos(), QSize(60, 60)