import os
import re
import math
import functools
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QScrollArea,
    QSizePolicy,
    QPushButton,
    QGridLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QGraphicsProxyWidget,
    QGraphicsTextItem,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QGraphicsView,
    QLineEdit,
    QComboBox,
    QColorDialog,
    QGraphicsOpacityEffect,
    QGraphicsScene,
)
from PyQt5.QtCore import (
    Qt,
    QPoint,
    QMimeData,
    pyqtSignal,
    QSize,
    QThread,
    QTimer,
    QEvent,
    QRectF,
    QPointF,
    QRect,
    QPropertyAnimation,
    QEasingCurve,
    QObject,
)
from PyQt5.QtGui import (
    QPen,
    QPixmap,
    QIcon,
    QDrag,
    QCursor,
    QColor,
    QBrush,
    QPainter,
    QPainterPath,
    QTransform,
    QFontMetrics,
    QMouseEvent,
    QFont,
    QVector2D,
)
from script_view import ScriptView
from common import FlowLayout, StackWidget, FontManager
import components
import numpy as np

_HANDLE_Z_BASE = 9_000_000.0

_ANGLE_CURSORS = [
    (  0.0, Qt.SizeHorCursor),        # ←→  East / West
    ( 45.0, Qt.SizeBDiagCursor),      # ↙↗  NE  / SW
    ( 90.0, Qt.SizeVerCursor),        # ↑↓  North / South
    (135.0, Qt.SizeFDiagCursor),      # ↖↘  NW  / SE
]


def _cursor_for_angle(deg: float) -> Qt.CursorShape:
    """
    Map an arbitrary angle (degrees, 0 = right, CW-positive) to the closest
    resize cursor.  Because each cursor represents two opposite directions the
    effective period is 180°, so we fold into [0, 180) first.
    """
    deg = deg % 180.0          # fold: NW↔SE share one cursor, etc.
    best_cursor = Qt.SizeHorCursor
    best_dist = 360.0
    for base_angle, cursor in _ANGLE_CURSORS:
        dist = abs(deg - base_angle)
        dist = min(dist, 180.0 - dist)   # wrap-around distance inside [0,180)
        if dist < best_dist:
            best_dist = dist
            best_cursor = cursor
    return best_cursor

# comunicate obj
class Signal(QObject):
    thisF = pyqtSignal(float)
    thisS = pyqtSignal(str)
    thisB = pyqtSignal(bool)
    macro = pyqtSignal(bool)
    finish= pyqtSignal()

    def __init__(self, parent=None):
        self._emit = None
        super().__init__(parent)

    def connect(self, method):
        if method is self.connect or method is self.emit:
            raise RecursionError("connect method cannot be method of Signal.")
        self.thisF.connect(method)
        self.thisS.connect(method)
        self.thisB.connect(method)
        if self._emit is not None:
            self.emit(self._emit)

    def disconnect(self, method):
        self.thisF.disconnect(method)
        self.thisS.disconnect(method)

    def emit(self, value):
        self._emit = value
        if isinstance(value, bool):
            self.thisB.emit(value)
        elif isinstance(value, float) or isinstance(value, int):
            self.thisF.emit(float(value))
        else:
            try:
                self.thisS.emit(value)
            except:
                pass

    def edit_finish(self,value=True):
        if value:
            self.finish.emit()


class OrderlyTransform(QTransform):
    def __init__(self, inherit=None):
        super().__init__()
        self.new = inherit
        try:
            self.push()
        except TypeError:
            pass

    def next_step(self, matrix=None):
        if self.new is not None:
            self.push()
        if matrix is None:
            self.new = QTransform()
            return
        self.new = matrix

    def push(self):
        self *= self.new
        self.new = None

    def rotate(self, angle, axis=Qt.ZAxis):
        if self.new is None:
            return super().rotate(angle, axis)
        self.new.rotate(angle, axis)

    def rotateRadians(self, angle, axis=Qt.ZAxis):
        if self.new is None:
            return super().rotateRadians(angle, axis)
        self.new.rotateRadians(angle, axis)

    def scale(self, sx, sy):
        if self.new is None:
            return super().scale(sx, sy)
        self.new.scale(sx, sy)

    def setMatrix(self, m11, m12, m13, m21, m22, m23, m31, m32, m33):
        if self.new is None:
            return super().setMatrix(m11, m12, m13, m21, m22, m23, m31, m32, m33)
        self.new.setMatrix(m11, m12, m13, m21, m22, m23, m31, m32, m33)

    def shear(self, sh, sv):
        if self.new is None:
            return super().shear(sh, sv)
        self.new.shear(sh, sv)

    def translate(self, dx, dy):
        if self.new is None:
            return super().translate(dx, dy)
        self.new.translate(dx, dy)


class BatchProcessContainer:
    def __init__(self, container):
        iter(container)
        self._container = container

    def __getitem__(self, key):
        return self._container[key]

    def __len__(self):
        return len(self._container)

    def __iter__(self):
        return iter(self._container)

    def __contains__(self, item):
        return item in self._container

    def __setitem__(self, key, value):
        self._container[key] = value

    def __delitem__(self, key):
        del self._container[key]

    def __repr__(self):
        return f"{self.__class__.__name__}({self._container!r})"

    def __getattr__(self, name):
        if hasattr(self._container, name):
            return getattr(self._container, name)

        is_callable_feature = None

        if isinstance(self._container, dict):
            result_dict = {}
            for key, value in self._container.items():
                var = getattr(value, name)

                current_is_callable = callable(var)
                if is_callable_feature is None:
                    is_callable_feature = current_is_callable
                elif is_callable_feature != current_is_callable:
                    raise AttributeError(
                        f"All elements of {type(self)} should have the same feature type for '{name}'"
                    )

                result_dict[key] = var

            return BatchProcessContainer(result_dict)

        result_list = []
        for item in self._container:
            var = getattr(item, name)

            current_is_callable = callable(var)
            if is_callable_feature is None:
                is_callable_feature = current_is_callable
            elif is_callable_feature != current_is_callable:
                raise AttributeError(
                    f"All elements of {type(self)} should have the same feature type for '{name}'"
                )

            result_list.append(var)

        return BatchProcessContainer(result_list)

    def __call__(self, *args, **kwargs):
        if isinstance(self._container, dict):
            result_dict = {}
            for key, func in self._container.items():
                if not callable(func):
                    raise TypeError(f"Item at key '{key}' is not callable")
                result_dict[key] = func(*args, **kwargs)
            return BatchProcessContainer(result_dict)

        result_list = []
        for func in self._container:
            if not callable(func):
                raise TypeError(f"Item {func!r} inside container is not callable")
            result_list.append(func(*args, **kwargs))
        return BatchProcessContainer(result_list)


# =============================================================================
# Base Layer Class
# =============================================================================
class SelectionBox(QGraphicsRectItem):
    def __init__(self, parent):
        super().__init__(QRectF(0, 0, 0, 0), parent)
        self.parent: Component | QGraphicsItem = parent
        self.parent_rect = QRectF(0, 0, 0, 0)
        self.setFlags(
            QGraphicsItem.ItemIgnoresParentOpacity
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsFocusable
        )
        self.updating = False
        self.selected = False
        dashed_pen = QPen(QColor(80, 150, 220), 1)
        dashed_pen.setStyle(Qt.DashLine)
        dashed_pen.setCosmetic(True)
        self.setPen(dashed_pen)
        self.setBrush(QBrush(Qt.transparent))
        self.alignment = False
        self.ctrl = False

        rotate_method = getattr(self.parent, "set_rotate", False)
        bounding_rect = self.boundingRect()
        if rotate_method:
            self.rotate = RotateHandle(self,rotate_method)
            self.rotate.setPos(bounding_rect.width() // 2, -50)
            self.rotate.setZValue(0)

        scale_method = getattr(self.parent, "set_scale", False)
        if scale_method:
            self.scale_handle = ScaleHandle.create_Handle(scale_method, self)
            self.scale_handle.setZValue(1)
            self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        if hasattr(self.parent, "setAlignment"):
            self.alignment = True

    def edit_finish(self,*args):
        self.parent.edit_finish(*args)

    def update_child_state(self):
        self.scale_handle.update_pos(self.rect().width(), self.rect().height())
        self.rotate.update_pos(self.parent.x_offset,self.parent.y_offset)
        self.scale_handle.update_transform()

    # ▼ 新增這個方法：動態計算控制點位置，抵消父元件縮放
    def update_scale(self):
        if self.updating:
            return
        x_offset=0
        y_offset=0
        self.updating = True
        parent_rotate = self.parent.rotation()
        self.parent.rotate(0)
        self.parent.setLayerTransform()
        rect = self.parent.sceneBoundingRect()
        transform = QTransform()
        transform.translate(rect.width() / 2, rect.height() / 2)
        self.setTransform(transform)
        self.setPos(rect.x(), rect.y())
        rect.moveTo(-rect.width() / 2, -rect.height() / 2)
        self.setRect(rect)
        if self.alignment:
            pb_rect=self.parent.boundingRect()
            x_offset=self.parent.x_offset
            y_offset=self.parent.y_offset
            align_dx = pb_rect.width() * x_offset
            align_dy = pb_rect.height() * y_offset
            self.setTransformOriginPoint(align_dx,align_dy)
        self.setRotation(parent_rotate)
        self.update_child_state()
        self.parent.rotate(parent_rotate)
        self.parent.setLayerTransform()
        self.updating = False

    def set_scale(self,direction: str, delta: QPointF):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("Please create a QApplication instance first.")
        screen = app.primaryScreen()
        dpi = screen.logicalDotsPerInch()  # 取得邏輯 DPI（通常 96 或 144 等）

        # pt → px 公式: px = pt * dpi / 72
        # 反推: pt = px * 72 / dpi
        point_size = delta * 72.0 / dpi

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.ctrl = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.ctrl = False
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        self.selected = True
        super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        rect = self.boundingRect()
        if not self.ctrl:
            self.setPos(int(self.x()), int(self.y()))
            self.parent.set_pos(
                int(self.x() + rect.width() / 2), int(self.y() + rect.height() / 2)
            )
            return
        self.parent.set_pos(
            round(self.x() + rect.width() / 2, 2),
            round(self.y() + rect.height() / 2, 2),
        )

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.selected = False
        if "X" in self.parent.attribute and "Y" in self.parent.attribute:
            self.parent.edit_finish(self.parent.set_pos,self.parent.x(), self.parent.y())

    def itemChange(self, change, value):
        if (change == QGraphicsItem.ItemVisibleChange) and value:
            self.update_scale()
        return super().itemChange(change, value)


class RotateHandle(QGraphicsEllipseItem):
    def __init__(self, parent:SelectionBox, method):
        super().__init__(-6, -6, 12, 12, parent)
        self.parent = parent
        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(80, 150, 220), 1.5))
        self.method=method
        self.radius = None
        self.start_angle = None
        self.pie_chart = None
        self.radius = None

    def update_pos(self,x_offset,y_offset):
        # 1. 取得 Item 相對於場景的縮放 (sy_item)
        t_item = self.parent.sceneTransform()
        sy_item = math.hypot(t_item.m21(), t_item.m22())
        # 2. 取得 View 相對於場景的縮放 (sy_view)
        # 假設只有一個 View
        sy_view = 1.0
        if self.scene() and self.scene().views():
            t_view = self.scene().views()[0].viewportTransform()
            sy_view = math.hypot(t_view.m21(), t_view.m22())
        # 3. 總合縮放比例
        total_sy = sy_item * sy_view
        if total_sy == 0:
            total_sy = 1.0

        visual_distance = 30
        rect = self.parent.boundingRect()
        reverse=-1
        if y_offset==0.5:
            reverse=1
        else:
            y_offset=-0.5
        # 抵消後的 Y 座標
        self.setPos(rect.width()*x_offset, reverse*visual_distance / total_sy + rect.height()*y_offset)

    def mousePressEvent(self, event):
        self.parent.selected = True
        super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self, event):
        center = self.parent.mapToScene(self.parent.transformOriginPoint())
        current_pos = event.scenePos()
        diff = current_pos - center
        # 使用 math.atan2(y, x)，注意 Qt Y 軸向下，角度計算需謹慎
        current_mouse_angle = math.degrees(math.atan2(diff.y(), diff.x()))

        if self.radius is None:
            # 初始點角度：手柄中心到旋轉中心的角度
            start_diff = self.scenePos() - center
            self.start_angle = math.degrees(math.atan2(start_diff.y(), start_diff.x()))
            self.radius = math.hypot(start_diff.x(), start_diff.y())
            # 紀錄圖層當前的旋轉值，作為基礎
            self.initial_layer_rotation = self.parent.rotation()

        # 計算旋轉增量 (滑鼠轉了幾度)
        delta_angle = current_mouse_angle - self.start_angle
        
        # 更新圖層：原始角度 + 增量
        new_rotation = self.initial_layer_rotation + delta_angle
        self.method(new_rotation) 

        # 更新 Pie Chart
        if self.pie_chart:
            self.scene().removeItem(self.pie_chart)

        color = QColor(80, 150, 220, 180)
        self.pie_chart = QGraphicsEllipseItem(
            center.x() - self.radius,
            center.y() - self.radius,
            self.radius * 2,
            self.radius * 2,
        )
        self.scene().addItem(self.pie_chart)
        self.pie_chart.setZValue(_HANDLE_Z_BASE + 1)
        self.pie_chart.setBrush(QBrush(color))
        self.pie_chart.setPen(QPen(Qt.NoPen))
        
        # Qt 的角度是逆時針為正，且起始於 3 點鐘方向
        # setStartAngle/setSpanAngle 需乘以 16
        self.pie_chart.setStartAngle(int(-self.start_angle * 16))
        self.pie_chart.setSpanAngle(int(-delta_angle * 16))

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.parent.selected = False
        if self.radius is not None:
            self.parent.edit_finish(self.method,self.parent.rotation())
        self.radius = None
        self.start_angle = None
        if self.pie_chart:
            self.scene().removeItem(self.pie_chart)
            self.pie_chart = None


class ScaleHandle(QGraphicsRectItem):
    handle_direction = {
        "tl": (-0.5, -0.5),
        "tc": (0.0, -0.5),
        "tr": (0.5, -0.5),
        "cl": (-0.5, 0.0),
        "cr": (0.5, 0.0),
        "bl": (-0.5, 0.5),
        "bc": (0.0, 0.5),
        "br": (0.5, 0.5),
    }

    def __init__(self, direction, method, parent: SelectionBox):
        super().__init__(QRectF(-5, -5, 10, 10), parent)
        self.setBrush(QBrush(QColor(100, 180, 255)))
        self.setPen(QPen(Qt.white, 1))
        self.direction = direction
        self.set_scale=method
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)

        self._drag_start_scene: QPointF | None = None

    def update_transform(self):
        p = self.parentItem()  # SelectionBox
        if not p or not self.scene() or not self.scene().views():
            return

        # 1. 取得 View 的縮放比例 (注意：這不包含 Item 自身的變換)
        view = self.scene().views()[0]
        view_t = view.viewportTransform()

        # 計算 View 在 X 和 Y 軸上的視覺縮放倍率
        view_sx = math.hypot(view_t.m11(), view_t.m12())
        view_sy = math.hypot(view_t.m21(), view_t.m22())

        # 2. 取得 Item (Component) 自身的縮放比例
        # 這是為了確保手柄也不會因為你拉大圖層而變形
        item_t = p.sceneTransform()
        item_sx = math.hypot(item_t.m11(), item_t.m12())
        item_sy = math.hypot(item_t.m21(), item_t.m22())

        # 3. 總合抵銷倍率
        # 我們要抵銷 (View縮放 * Item縮放)，讓手柄在螢幕上永遠是固定像素大小
        total_sx = view_sx * item_sx
        total_sy = view_sy * item_sy

        inv_sx = 1.0 / total_sx if total_sx != 0 else 1.0
        inv_sy = 1.0 / total_sy if total_sy != 0 else 1.0

        # 4. 僅套用縮放抵消，保留旋轉繼承
        # 注意：不要使用 setScale()，因為那會影響座標定位
        # 使用 setTransform 並保持矩陣的旋轉部分為 0 (因為旋轉由父元件繼承)
        t = QTransform()
        t.scale(inv_sx, inv_sy)
        self.setTransform(t)

    def update_pos(self, w, h):
        x = self.handle_direction[self.direction][0] * w
        y = self.handle_direction[self.direction][1] * h
        self.setPos(x, y)

    def _compute_cursor(self) -> Qt.CursorShape:
        """
        Rotate the handle's nominal direction vector by the parent's current
        scene rotation, then choose the closest resize cursor.
        """
        dx, dy = self.handle_direction[self.direction]

        # For center-edge handles (dx or dy == 0) use the non-zero axis.
        # atan2(y, x) gives angle in radians, 0 = East, CCW-positive in math
        # but Qt's rotation is CW-positive, so we negate dy to convert.
        raw_angle_rad = math.atan2(-dy, dx)   # CW-positive, 0 = East
        raw_angle_deg = math.degrees(raw_angle_rad)

        # Add parent's visual rotation (scene transform)
        parent = self.parentItem()
        if parent:
            scene_t  = parent.sceneTransform()
            # Extract rotation from the scene transform matrix
            parent_angle_deg = math.degrees(
                math.atan2(-scene_t.m12(), scene_t.m11())
            )
        else:
            parent_angle_deg = 0.0

        final_angle = raw_angle_deg + parent_angle_deg
        return _cursor_for_angle(final_angle)

    def hoverEnterEvent(self, event):
        self.setCursor(QCursor(self._compute_cursor()))
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        # Re-evaluate in case the parent was rotated while hovering
        self.setCursor(QCursor(self._compute_cursor()))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_scene = event.scenePos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_scene is not None:
            delta = event.scenePos() - self._drag_start_scene
            # Pass the direction key and the scene-space delta to the callback.
            # Signature: set_scale(direction: str, delta: QPointF)
            self.set_scale(self.direction, delta)
            # Update the drag origin so deltas are incremental, not cumulative.
            self._drag_start_scene = event.scenePos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drag_start_scene is not None:
                delta = event.scenePos() - self._drag_start_scene
                self.parentItem().edit_finish(self.set_scale,self.direction, delta)
            self._drag_start_scene = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    @classmethod
    def create_Handle(cls, method, parent):
        handles = {}
        w, h = parent.boundingRect().width(), parent.boundingRect().height()
        for direction in cls.handle_direction:
            handle = cls(direction, method, parent)
            x = cls.handle_direction[direction][0] * w
            y = cls.handle_direction[direction][1] * h
            handle.setPos(x, y)
            handles[direction] = handle
        return BatchProcessContainer(handles)


class GraphicsScene(QGraphicsScene):
    view_transform = pyqtSignal(QTransform)
    selection_changed = pyqtSignal(object)  # emits hash_id (int) or None

    def __init__(self, parent=None, signal=None):
        super().__init__(parent)
        self.signal = signal
        self._insertion_counter = 0
        self._insertion_map = {}  # component.id → insertion_index (stable across undo/redo)
        if signal is not None:
            self.signal.connect(self.viewChangeEvent)
        self.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        items = self.selectedItems()
        if items and hasattr(items[0], 'id'):
            self.selection_changed.emit(items[0].id)
        else:
            self.selection_changed.emit(None)

    def addItem(self, item):
        super().addItem(item)
        if isinstance(item, Component):
            if item.id not in self._insertion_map:
                self._insertion_map[item.id] = self._insertion_counter
                self._insertion_counter += 1
            item.setZValue(item.z_order + self._insertion_map[item.id] / 1_000_000)
        elif isinstance(item, SelectionBox):
            item.setZValue(_HANDLE_Z_BASE)
            self.view_transform.connect(item.update_child_state)

    def removeItem(self, item):
        super().removeItem(item)
        if isinstance(item, SelectionBox):
            self.view_transform.disconnect(item.update_child_state)

    def _recompute_z(self, component: 'Component'):
        idx = self._insertion_map.get(component.id, 0)
        component.setZValue(component.z_order + idx / 1_000_000)

    def viewChangeEvent(self, view, transform):
        self.view_transform.emit(transform)


# ============================================================================
# Base Component Class
# ============================================================================
class Component:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # 取得子類別原本定義的 __init__
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)  # 執行原本的初始化
            self._after_init()                     # 觸發目標方法
            
        cls.__init__ = new_init

    def init_component(self, attribute: dict, id, parent: QGraphicsScene = None):
        self.parent = parent
        self.start_drag_pos = None
        self.attribute = attribute
        self.start_drag_pos = None
        self.draging = False
        self.id = id
        self.z_order = 0
        self.name = ""
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.rotate_value = 0
        self.skew_x_value = 0
        self.skew_y_value = 0
        self._connected_signal=[]
        self.last_emit={}
        self.recording=False
        self.controller = SelectionBox(self)
        self.controller.setVisible(False)
        self.connect("Layer", self.order)
        self.connect("X", self.move_x)
        self.connect("Y", self.move_y)
        self.connect("Skew X", self.skew_x)
        self.connect("Skew Y", self.skew_y)
        self.connect("Rotation", self.rotate)
        self.connect("Opacity", self.setLayerOpacity)
        self.connect("Display", self.display)
        self.connect("Skew X", self.setLayerTransform)
        self.connect("Skew Y", self.setLayerTransform)
        self.connect("Rotation", self.setLayerTransform)

    def _after_init(self):
        del self._connected_signal

    def lua_translator(self):
        pass

    def order(self, value):
        self.z_order = value
        scene = self.scene()
        if scene:
            scene._recompute_z(self)


    def rename(self, value):
        self.name = value

    def move_x(self, value):
        self.setPos(float(value), self.y())
        self.controller.update_scale()

    def move_y(self, value):
        self.setPos(self.x(), float(value))
        self.controller.update_scale()

    def gyro(self, value):
        return

    def skew_x(self, value):
        self.skew_x_value = value

    def skew_y(self, value):
        self.skew_y_value = value

    def rotate(self, value):
        self.rotate_value = value

    def rotation(self):
        return self.rotate_value

    def setLayerTransform(self, _=None, matrix: OrderlyTransform = None, combine=False):
        if matrix is None:
            matrix = OrderlyTransform()
        matrix.next_step()
        matrix.shear(
            np.tan(np.deg2rad(self.skew_x_value)), np.tan(np.deg2rad(self.skew_y_value))
        )
        matrix.next_step()
        matrix.rotate(float(self.rotate_value))
        matrix.push()
        QGraphicsItem.setTransform(self, matrix, combine)
        self.controller.update_scale()

    def setLayerOpacity(self, opacity):
        opacity = float(opacity) / 100
        QGraphicsItem.setOpacity(self, opacity)

    def display(self, value):
        if value == "Always":
            pass
        if value == "Bright only":
            pass
        if value == "Dimmed only":
            pass
        if value == "Never":
            pass

    def set_pos(self, x, y):
        self.attribute["X"].emit(x)
        self.attribute["Y"].emit(y)

    def set_rotate(self,angle):
        self.attribute["Rotation"].emit(angle)

    def record(self,name,value):
        if self.recording:
            self.last_emit[name]=value
            print(name,value)

    def edit_finish(self,method,*args):
        self.recording=True
        method(*args)
        self.recording=False
        now=1
        end=len(self.last_emit.items())
        for key,value in self.last_emit.items():
            if now==1:
                self.attribute[key].macro.emit(True)
            self.attribute[key].edit_finish()
            self.attribute[key].emit(value)
            if now==end:
                self.attribute[key].macro.emit(False)
            now+=1
        self.last_emit.clear()

    def connect(self, key, method):
        if key in self.attribute:
            self.attribute[key].connect(method)
            if key not in self._connected_signal:
                self._connected_signal.append(key)
                self.attribute[key].connect(lambda v:self.record(key,v))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.controller.setVisible(bool(value) or self.controller.selected)

        if change == QGraphicsItem.ItemSceneChange:
            if value:
                print(value,change)
                value.addItem(self.controller)
            else:
                self.scene().removeItem(self.controller)
        return QGraphicsItem.itemChange(self, change, value)
    
class Group(Component):
    #pos offset
    #
    pass

class textLayer(Component, QGraphicsTextItem):
    # text
    # animation
    # font
    # text_size
    # color
    # color_dim
    # anim_scale_x
    # anim_scale_y
    # alignment
    # transform
    # shader
    # tap_action
    # text_effect
    def __init__(self, attribute: dict, id, parent=None):
        self.x_offset = 0
        self.y_offset = 0
        QGraphicsTextItem.__init__(self)
        Component.init_component(self, attribute, id, parent)
        self.setLayerTransform()
        self.connect("Text", self.setPlainText)
        self.connect("Font", self.setFontStyle)
        self.connect("Text size", self.setTextSize)
        self.connect("Color", self.setColor)
        self.connect("Alignment", self.setAlignment)
        self.connect("Font", self.setLayerTransform)
        self.connect("Text size", self.setLayerTransform)
        self.connect("Alignment", self.setLayerTransform)
        # color_dim
        # animation
        # anim_scale_x
        # anim_scale_y
        # transform
        # shader
        # tap_action
        # text_effect

    def setLayerTransform(self, _=None, matrix: OrderlyTransform = None, combine=False):
        if matrix is None:
            matrix = OrderlyTransform()
        matrix.next_step()
        rect = self.boundingRect()
        matrix.translate(-rect.width() / 2, -rect.height() / 2)
        matrix.next_step()
        matrix.shear(
            np.tan(np.deg2rad(self.skew_x_value)),
            np.tan(np.deg2rad(self.skew_y_value)),
        )
        matrix.next_step(self.layerAlignment(QTransform()))
        matrix.next_step()
        matrix.rotate(self.rotate_value)
        matrix.push()
        QGraphicsItem.setTransform(self, matrix, combine)
        self.controller.update_scale()

    def layerAlignment(self, matrix):
        rect = self.boundingRect()
        align_dx = -rect.width() * self.x_offset
        align_dy = -rect.height() * self.y_offset
        matrix.translate(align_dx, align_dy)
        return matrix

    def setPlainText(self, value):
        QGraphicsTextItem.setPlainText(self, value)
        self.controller.update_scale()

    def setFontStyle(self, value):
        font_manager = FontManager()
        current_size = self.font().pointSize()
        if current_size <= 0:
            current_size = 12  # 預設大小
        font = font_manager.get_font(value, current_size)
        self.setFont(font)

    def setTextSize(self, value):
        current_font = self.font()
        size = int(value) if value else 12
        if size <= 0:
            size = 12
        current_font.setPointSize(size)
        self.setFont(current_font)

    def setColor(self, value):
        if not value:
            value = "ffffff"
        # 確保顏色值格式正確
        color_str = value if value.startswith("#") else f"#{value}"
        self.setDefaultTextColor(QColor(color_str))

    def setAlignment(self, value):
        if "c" in value.lower():
            self.x_offset = 0
            self.y_offset = 0
        if "l" in value:
            self.x_offset = -0.5
        elif "i" in value:
            self.x_offset = 0.5
        if "B" in value:
            self.y_offset = 0.5
        elif "p" in value:
            self.y_offset = -0.5

    def set_pos(self, x, y):
        rect = self.boundingRect()
        align_dx = rect.width() * self.x_offset
        align_dy = rect.height() * self.y_offset
        self.attribute["X"].emit(x + align_dx)
        self.attribute["Y"].emit(y + align_dy)

    def set_scale(self, direction, delta):
        rect = self.controller.boundingRect()
        W = rect.width()+math.tan(-self.skew_x_value)
        H = rect.height()+math.tan(-self.skew_y_value)
        if W <= 0 or H <= 0:
            return
        current_size = self.font().pointSize()
        if current_size <= 0:
            current_size = 12

        hx, hy = ScaleHandle.handle_direction[direction]

        # Project scene delta onto item's local axes (inverse of CW rotation by rotate_value)
        theta = math.radians(self.rotate_value)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        d_local_x =  delta.x() * cos_t + delta.y() * sin_t
        d_local_y = -delta.x() * sin_t + delta.y() * cos_t

        # Corner and vertical handles: use local Y ("頂線/底線為基準")
        # Horizontal-only handles (cl, cr): use local X then convert via aspect ratio
        if hy != 0:
            d_eff = d_local_y * (1 if hy > 0 else -1)
            ref_dim = H
        else:
            d_eff = d_local_x * (1 if hx > 0 else -1)
            ref_dim = W

        delta_size = d_eff * current_size / ref_dim

        # Float accumulator avoids stalling at integer boundaries
        if not hasattr(self, '_scale_size') or abs(self._scale_size - current_size) > 1.0:
            self._scale_size = float(current_size)
        self._scale_size = max(1.0, self._scale_size + delta_size)

        actual_new = max(1, int(self._scale_size))
        #f actual_new == current_size:
        #   return  # sub-integer change; accumulate only, no emit to avoid drift

        s = actual_new / current_size
        dW = W * (s - 1)
        dH = H * (s - 1)

        # Keep the fixed point (opposite handle) in place.
        # In pre-rotation local space: delta_anchor = (x_offset + hx)*dW, (y_offset + hy)*dH
        # Then rotate to scene space via Qt CW rotation: R*(x,y) = (x*cos-y*sin, x*sin+y*cos)
        local_dpx = (self.x_offset + hx) * dW
        local_dpy = (self.y_offset + hy) * dH
        scene_dpx = local_dpx * cos_t - local_dpy * sin_t
        scene_dpy = local_dpx * sin_t + local_dpy * cos_t

        self.attribute["Text size"].emit(actual_new)
        self.attribute["X"].emit(self.x() + scene_dpx)
        self.attribute["Y"].emit(self.y() + scene_dpy)


# ============================================================================
# Image Layer (圖片圖層)
# ============================================================================
class imageLayer(QGraphicsPixmapItem, Component):
    def __init__(self, attribute: dict, parent=None):
        self.x_offset = 0.5
        self.y_offset = 0.5
        QGraphicsPixmapItem.__init__(self, parent)
        Component.init_component(self, attribute)
        self.setPixmap(self.attribute["Custom image"])
        self.connect("Custom image", self.setPixmap)
        self.connect("Width", self.setLayerTransform)
        self.connect("Height", self.setLayerTransform)
        # TODO: Load actual image from Custom image path

    def setPixmap(self, pixmap):
        pixmap = QPixmap(pixmap)
        super().setPixmap(pixmap)
        self.setLayerTransform()

    def setLayerTransform(self, value=None, matrix=None, combine=False):
        if matrix is None:
            matrix = QTransform()
        matrix = self.shear(
            matrix,
            np.tan(np.deg2rad(self.attribute["Skew X"])),
            np.tan(np.deg2rad(self.attribute["Skew Y"])),
        )
        matrix2 = QTransform()
        try:
            pixmap = self.pixmap()
            sw = self.attribute["Width"] / pixmap.width()
            sh = self.attribute["Height"] / pixmap.height()
            matrix2.scale(sw, sh)
        except:
            pass
        self.rotate(matrix2)
        matrix2 = self.layerAlignment(matrix2)
        matrix3 = matrix * matrix2
        QGraphicsItem.setTransform(self, matrix3)
        self.controller.update_scale()

    def layerAlignment(self, matrix):
        rect = self.boundingRect()
        align_dx = -rect.width() * self.x_offset
        align_dy = -rect.height() * self.y_offset
        matrix.translate(align_dx, align_dy)
        return matrix

    def setAlignment(self, value):
        if "c" in value.lower():
            self.x_offset = 0.5
            self.y_offset = 0.5
        if "l" in value:
            self.x_offset = 0
        elif "i" in value:
            self.x_offset = 1
        if "B" in value:
            self.y_offset = 1
        elif "p" in value:
            self.y_offset = 0
        self.setLayerTransform()


# ============================================================================
# Curved Text Layer (曲線文字圖層)
# ============================================================================
class curvedTextLayer(QGraphicsTextItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsTextItem.__init__(self, parent)
        Component.__init__(self, attribute)
        self.setPlainText(attribute.get("Text", ""))
        # TODO: Implement curved text rendering with radius


# ============================================================================
# Shape Layer (形狀圖層)
# ============================================================================
class shapeLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 100)
        height = attribute.get("Height", 100)
        self.setRect(-width / 2, -height / 2, width, height)
        color = attribute.get("Color", "#ffffff")
        if not color.startswith("#"):
            color = f"#{color}"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(Qt.NoPen))


# ============================================================================
# Marker Layer (標記圖層)
# ============================================================================
class markerLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        radius = attribute.get("Radius", 256)
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        self.setPen(QPen(QColor("#888888"), 1, Qt.DashLine))
        self.setBrush(Qt.NoBrush)
        # TODO: Draw markers around the circle


# ============================================================================
# Tachymeter Layer (測速計圖層)
# ============================================================================
class tachymeterLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        radius = attribute.get("Radius", 230)
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        self.setPen(QPen(QColor("#888888"), 1, Qt.DashLine))
        self.setBrush(Qt.NoBrush)
        # TODO: Draw tachymeter scale


# ============================================================================
# Map Layer (地圖圖層)
# ============================================================================
class mapLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 512)
        height = attribute.get("Height", 512)
        self.setRect(-width / 2, -height / 2, width, height)
        self.setBrush(QBrush(QColor("#3a3a3a")))
        self.setPen(QPen(QColor("#555555"), 1))
        # TODO: Load map tile from lat/lon


# ============================================================================
# Slideshow Layer (幻燈片圖層)
# ============================================================================
class slideshowLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 300)
        height = attribute.get("Height", 300)
        self.setRect(-width / 2, -height / 2, width, height)
        self.setBrush(QBrush(QColor("#444444")))
        self.setPen(QPen(QColor("#666666"), 1))
        # TODO: Implement slideshow functionality


# ============================================================================
# Text Ring Layer (環形文字圖層)
# ============================================================================
class textRingLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        radius = attribute.get("Radius", 200)
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        self.setPen(QPen(QColor("#888888"), 1, Qt.DashLine))
        self.setBrush(Qt.NoBrush)
        # TODO: Draw numbers around the ring


# ============================================================================
# Rounded Rectangle Layer (圓角矩形圖層)
# ============================================================================
class roundedRectangleLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 300)
        height = attribute.get("Height", 200)
        self.setRect(-width / 2, -height / 2, width, height)
        color = attribute.get("Color", "#ffffff")
        if not color.startswith("#"):
            color = f"#{color}"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(Qt.NoPen))
        # TODO: Apply corner radius


# ============================================================================
# Series Layer (數據系列圖層)
# ============================================================================
class seriesLayer(QGraphicsTextItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsTextItem.__init__(self, parent)
        Component.__init__(self, attribute)
        self.setPlainText("MON\nTUE\nWED")
        # TODO: Implement series data display


# ============================================================================
# Complication Layer (複雜功能圖層)
# ============================================================================
class complicationLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 100)
        height = attribute.get("Height", 100)
        self.setRect(-width / 2, -height / 2, width, height)
        bg_color = attribute.get("Color background", "#494949")
        if not bg_color.startswith("#"):
            bg_color = f"#{bg_color}"
        self.setBrush(QBrush(QColor(bg_color)))
        self.setPen(QPen(QColor("#666666"), 1))


# ============================================================================
# Chart Layer (圖表圖層)
# ============================================================================
class chartLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 205)
        height = attribute.get("Height", 76)
        self.setRect(-width / 2, -height / 2, width, height)
        self.setBrush(QBrush(QColor("#2a2a2a")))
        self.setPen(QPen(QColor("#444444"), 1))
        # TODO: Draw chart


# ============================================================================
# Image Condition Layer (條件圖片圖層)
# ============================================================================
class imageCondLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 80)
        height = attribute.get("Height", 80)
        self.setRect(-width / 2, -height / 2, width, height)
        self.setBrush(QBrush(QColor("#555555")))
        self.setPen(QPen(QColor("#777777"), 1))
        # TODO: Implement conditional image selection


# ============================================================================
# Image GIF Layer (GIF圖片圖層)
# ============================================================================
class imageGifLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 100)
        height = attribute.get("Height", 100)
        self.setRect(-width / 2, -height / 2, width, height)
        self.setBrush(QBrush(QColor("#4a4a4a")))
        self.setPen(QPen(QColor("#666666"), 1))
        # TODO: Load and animate GIF


# ============================================================================
# Progress Layer (進度條圖層)
# ============================================================================
class progressLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        QGraphicsRectItem.__init__(self, parent)
        Component.__init__(self, attribute)
        width = attribute.get("Width", 114)
        height = attribute.get("Height", 24)
        self.setRect(-width / 2, -height / 2, width, height)
        bg_color = attribute.get("Color 3", "#525151")
        if not bg_color.startswith("#"):
            bg_color = f"#{bg_color}"
        self.setBrush(QBrush(QColor(bg_color)))
        self.setPen(QPen(Qt.NoPen))
        # TODO: Draw progress indicator


# ============================================================================
# Ring Layer (圓環圖層)
# ============================================================================
class ringLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        super().__init__(parent)
        Component.__init__(self, attribute)
        radius = attribute.get("Radius outer", 57)
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        color = attribute.get("Color", "#ffffff")
        if not color.startswith("#"):
            color = f"#{color}"
        self.setPen(QPen(QColor(color), 4))
        self.setBrush(Qt.NoBrush)
        # TODO: Draw ring arc


# ============================================================================
# Markers HM Layer (時分標記圖層)
# ============================================================================
class markersHMLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        super().__init__(parent)
        Component.__init__(self, attribute)
        radius = attribute.get("Radius", 256)
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        self.setPen(QPen(QColor("#888888"), 1, Qt.DashLine))
        self.setBrush(Qt.NoBrush)
        # TODO: Draw hour/minute markers


# ============================================================================
# Directional Light Layer (方向光源圖層)
# ============================================================================
class directionalLightLayer(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        super().__init__(parent)
        Component.__init__(self, attribute)
        self.setRect(-30, -30, 60, 60)
        color = attribute.get("Color", "#ffffff")
        if not color.startswith("#"):
            color = f"#{color}"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor("#ffff00"), 2))
        # Light indicator


# ============================================================================
# 3D Layer (3D圖層)
# ============================================================================
class layer3D(QGraphicsRectItem, Component):
    def __init__(self, attribute: dict, parent=None):
        super().__init__(parent)
        Component.__init__(self, attribute)
        scale_x = attribute.get("Scale X", 40)
        scale_y = attribute.get("Scale Y", 40)
        self.setRect(-scale_x / 2, -scale_y / 2, scale_x, scale_y)
        self.setBrush(QBrush(QColor("#666666")))
        self.setPen(QPen(QColor("#888888"), 2))
        # TODO: Implement 3D rendering


# ============================================================================
# Layer Type Mapping (圖層類型映射)
# ============================================================================
LAYER_CLASS_MAP = {
    "textLayer": textLayer,
    "imageLayer": imageLayer,
    "curvedTextLayer": curvedTextLayer,
    "shapeLayer": shapeLayer,
    "markerLayer": markerLayer,
    "tachymeterLayer": tachymeterLayer,
    "mapLayer": mapLayer,
    "slideshowLayer": slideshowLayer,
    "textRingLayer": textRingLayer,
    "roundedRectangleLayer": roundedRectangleLayer,
    "seriesLayer": seriesLayer,
    "complicationLayer": complicationLayer,
    "chartLayer": chartLayer,
    "imageCondLayer": imageCondLayer,
    "imageGifLayer": imageGifLayer,
    "progressLayer": progressLayer,
    "ringLayer": ringLayer,
    "markersHMLayer": markersHMLayer,
    "directionalLightLayer": directionalLightLayer,
    "layer3D": layer3D,
    "3DLayer": layer3D,
}


def create_layer(layer_type: str, signal_dict: dict, id: int, parent=None):
    """根據圖層類型創建對應的圖層實例"""
    layer_class = LAYER_CLASS_MAP.get(layer_type, textLayer)
    return layer_class(signal_dict, id, parent)
