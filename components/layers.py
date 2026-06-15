"""
layers.py — LayerMixin、LayeredGraphicsScene、TextLayer
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QRectF, QPointF, QSizeF
from .utils import to_float, to_str
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QTransform
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem

_NON_LAYER_Z: float = 1e8

_GIT_STATE_RGBA: dict[str, int] = {
    "add":    0x26A5D6A7,
    "modify": 0x26FFAB91,
    "delete": 0x26EF9A9A,
}


class LayerMixin:
    """
    混入類別，賦予 QGraphicsItem 圖層排序能力。
    繼承時須同時繼承某個 QGraphicsItem 子類，並在 __init__ 內呼叫 __init_layer__()。
    """

    def __init_layer__(self) -> None:
        self._layer_value: int = 0
        self._insertion_seq: int = -1
        self._git_state: str = ""
        self.can_scale: bool = False

    def set_git_state(self, state: str) -> None:
        self._git_state = state
        self.update()  # type: ignore[attr-defined]

    def set_layer_value(self, value: int) -> None:
        """更新圖層值並通知 scene 重新排序。"""
        self._layer_value = value
        scene = self.scene()  # type: ignore[attr-defined]
        if isinstance(scene, LayeredGraphicsScene):
            scene._reorder()

    def layer_value(self) -> int:
        return self._layer_value

    def _get_manager(self):
        scene = self.scene()  # type: ignore[attr-defined]
        if isinstance(scene, LayeredGraphicsScene):
            return scene._manager
        return None

    def emit_object_selected(self, object_type: str) -> None:
        m = self._get_manager()
        if m is not None:
            m.object_selected.emit(object_type)

    def emit_attr_changed(self, field: str, value) -> None:
        m = self._get_manager()
        if m is not None:
            m.attr_changed.emit(field, value)

    def connect_object_selected(self, slot) -> None:
        m = self._get_manager()
        if m is not None:
            m.object_selected.connect(slot)

    def connect_attr_changed(self, slot) -> None:
        m = self._get_manager()
        if m is not None:
            m.attr_changed.connect(slot)

    def apply_attr(self, field: str, value) -> None:
        """子類覆寫以處理屬性變更的視覺更新。"""
        pass

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        """以 base_vals 為起點套用縮放，回傳更新後的 field→value dict。子類覆寫。"""
        return {}


class LayeredGraphicsScene(QGraphicsScene):
    """
    特殊 QGraphicsScene：
    - 非 LayerMixin item（從 Python 呼叫 addItem 加入）：z = _NON_LAYER_Z，始終顯示在最上層
    - LayerMixin item：依 (layer_value, insertion_seq) 升序排列，值越大越上層
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seq_counter: int = 0
        self._manager = None
        self._overlay: "_SelectionOverlay | None" = None

    def set_manager(self, manager) -> None:
        self._manager = manager
        self._overlay = _SelectionOverlay()
        self.addItem(self._overlay)
        self._overlay.setZValue(_NON_LAYER_Z + 1)
        self._overlay.hide()
        self._multi_overlay = _MultiSelectOverlay()
        self.addItem(self._multi_overlay)
        self._multi_overlay.setZValue(_NON_LAYER_Z + 2)
        self._multi_overlay.hide()
        manager.instance_selected.connect(self._on_instance_selected)
        manager.instance_deselected.connect(self._on_instance_deselected)
        manager.multi_selection_changed.connect(self._on_multi_selection_changed)

    def _on_instance_deselected(self) -> None:
        if self._overlay is not None:
            self._overlay.detach()
            self._overlay.hide()

    def _on_multi_selection_changed(self, ids: list) -> None:
        if len(ids) <= 1:
            self._multi_overlay.set_items([])
            self._multi_overlay.hide()
            return
        items = []
        for iid in ids:
            inst = self._manager._instances.get(iid)
            if inst:
                ci = inst.get("canvas_item")
                if ci is not None:
                    items.append(ci)
        # 多選時隱藏單選 overlay
        self._overlay.detach()
        self._overlay.hide()
        if items:
            self._multi_overlay.set_items(items, self._manager)
            self._multi_overlay.show()
        else:
            self._multi_overlay.set_items([])
            self._multi_overlay.hide()

    def _on_instance_selected(self, object_type, values, instance_id) -> None:
        # 多選模式下不切換單選 overlay
        if len(self._manager._selected_ids) > 1:
            return
        inst = self._manager._instances.get(instance_id)
        if inst is None:
            self._overlay.detach()
            self._overlay.hide()
            return
        ci = inst.get("canvas_item")
        if isinstance(ci, LayerMixin):
            self._overlay.attach(ci, self._manager)
            self._overlay.show()
        else:
            self._overlay.detach()
            self._overlay.hide()

    def mousePressEvent(self, event) -> None:
        if self._manager is None:
            super().mousePressEvent(event)
            return

        scene_pos = event.scenePos()
        overlay = getattr(self, "_overlay", None)
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # 若單選 overlay 可見，先判斷是否由 overlay 處理
        if overlay and overlay.isVisible() and not ctrl:
            lp = overlay.mapFromScene(scene_pos)
            if (overlay._hit_handle(lp) >= 0
                    or overlay._is_rotation_zone(lp)
                    or overlay._rect.contains(lp)):
                super().mousePressEvent(event)
                return

        # multi overlay：move/scale handle 交給 overlay 處理，防止觸發框選
        mo = getattr(self, "_multi_overlay", None)
        if mo and mo.isVisible() and not ctrl:
            lp = mo.mapFromScene(scene_pos)
            if mo._hit_move_handle(lp) or mo._hit_scale_handle(lp) >= 0:
                super().mousePressEvent(event)
                return

        # 找點擊位置下的所有 item（z 由高至低）
        for item in self.items(scene_pos):
            if overlay and item is overlay:
                continue
            if mo and item is mo:
                continue
            if isinstance(item, LayerMixin):
                for iid, inst in self._manager._instances.items():
                    if inst.get("canvas_item") is item:
                        if ctrl:
                            # Ctrl+click：toggle 選取
                            selected = self._manager._selected_ids
                            if iid in selected:
                                selected.discard(iid)
                                if not selected:
                                    self._manager._current_instance_id = None
                                    self._manager._attr_panel._on_deselected()
                                    return
                                # 更新 current 為剩餘任一
                                self._manager._current_instance_id = next(iter(selected))
                            else:
                                selected.add(iid)
                                self._manager._current_instance_id = iid
                            self._manager.multi_selection_changed.emit(list(selected))
                        else:
                            # 普通點擊 → 單選
                            self._manager._selected_ids = {iid}
                            self._manager._current_instance_id = iid
                            self._manager.instance_selected.emit(
                                inst.get("object_type", ""),
                                inst.get("values", {}),
                                iid,
                            )
                            self._manager.multi_selection_changed.emit([iid])
                        event.accept()
                        return
                break

        # 點擊空白處 → 取消選取
        if ctrl:
            super().mousePressEvent(event)
            return
        if overlay and overlay.isVisible():
            overlay.detach()
            overlay.hide()
        if mo and mo.isVisible():
            mo.set_items([])
            mo.hide()
        self._manager._attr_panel._on_deselected()
        super().mousePressEvent(event)

    def addItem(self, item: QGraphicsItem) -> None:
        super().addItem(item)
        if isinstance(item, LayerMixin):
            item._insertion_seq = self._seq_counter
            self._seq_counter += 1
            self._reorder()
        else:
            item.setZValue(_NON_LAYER_Z)

    def _reorder(self) -> None:
        """重新計算所有 LayerMixin item 的 z-value。"""
        layer_items = [it for it in self.items() if isinstance(it, LayerMixin)]
        layer_items.sort(key=lambda it: (it._layer_value, it._insertion_seq))
        for z, item in enumerate(layer_items):
            item.setZValue(float(z))


# ── TextLayer ─────────────────────────────────────────────────────────────────

class TextLayer(QGraphicsTextItem, LayerMixin):
    """
    繼承 LayerMixin 的文字 item。
    X/Y 為錨點座標；錨點位置由 Alignment 欄位決定。
    """

    # Alignment 選項 → (水平係數, 垂直係數)，乘以 boundingRect 寬高後加到 X/Y
    _ANCHOR: dict[str, tuple[float, float]] = {
        "Center":        (-0.5, -0.5),
        "Top left":      ( 0.0,  0.0),
        "Top center":    (-0.5,  0.0),
        "Top right":     (-1.0,  0.0),
        "Center left":   ( 0.0, -0.5),
        "Center right":  (-1.0, -0.5),
        "Bottom left":   ( 0.0, -1.0),
        "Bottom center": (-0.5, -1.0),
        "Bottom right":  (-1.0, -1.0),
    }

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x            = to_float(values.get("X", 0))
        self._y            = to_float(values.get("Y", 0))
        self._alignment    = str(values.get("Alignment", "Center"))
        self._font_name    = str(values.get("Font", ""))
        self._font_size    = int(to_float(values.get("Text size", 40), 40.0))
        self._rotation     = to_float(values.get("Rotation", 0))
        self._skew_x       = to_float(values.get("Skew X", 0))
        self._skew_y       = to_float(values.get("Skew Y", 0))
        self._anim_scale_x = to_float(values.get("Anim scale X", 100), 100.0)
        self._anim_scale_y = to_float(values.get("Anim scale Y", 100), 100.0)

        self.setPlainText(to_str(str(values.get("Text", ""))))
        self._apply_font()
        self._apply_color(values.get("Color", "ffffff"))
        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _apply_font(self) -> None:
        # 延遲匯入避免 components → special_ui 的循環依賴
        from special_ui import FontManager
        family = FontManager().get_font_family(self._font_name) or self._font_name
        font = QFont(family)
        font.setPixelSize(self._font_size)
        self.setFont(font)

    def _apply_color(self, hex_val) -> None:
        s = str(hex_val).strip().lstrip("#")
        color = QColor(f"#{s}") if QColor(f"#{s}").isValid() else QColor(Qt.GlobalColor.white)
        self.setDefaultTextColor(color)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜 → 對齊 → 縮放 → 旋轉。
        傾斜以文字中心為軸；縮放、旋轉以對齊錨點為軸。
        與 preview_obj.py textLayer.setLayerTransform 邏輯一致。
        """
        br = self.boundingRect()
        w, h = br.width(), br.height()
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        # ax = fx*w，anchor 局部座標 = (-ax, -ay)
        ax, ay = fx * w, fy * h

        sx = self._anim_scale_x / 100.0
        sy = self._anim_scale_y / 100.0
        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        # QTransform.op() 為 prepend（t = Op * t），以 row vector 計算時
        # 「最後呼叫 = 最先套用至點」，故呼叫順序須與套用順序相反。
        # 套用順序：T(-w/2,-h/2) → Shear → T(ax+w/2,ay+h/2) → Scale → Rotate → T(X,Y)
        # 呼叫順序（反向）：
        t = QTransform()
        t.translate(self._x, self._y)          # 最後套用：移至最終位置
        t.rotate(self._rotation)               # 旋轉（繞錨點）
        t.scale(sx, sy)                        # 縮放（繞錨點）
        t.translate(ax + w / 2, ay + h / 2)   # 對齊：將錨點移至原點
        t.shear(sh_x, sh_y)                    # 傾斜（繞文字中心）
        t.translate(-w / 2, -h / 2)           # 最先套用：文字中心移至原點
        self.setTransform(t)

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "Text":
            self.setPlainText(to_str(str(value)))
            self._apply_transform()
        elif field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Font":
            self._font_name = str(value)
            self._apply_font()
            self._apply_transform()
        elif field == "Text size":
            self._font_size = int(to_float(value, self._font_size))
            self._apply_font()
            self._apply_transform()
        elif field == "Color":
            self._apply_color(value)
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Anim scale X":
            self._anim_scale_x = to_float(value, self._anim_scale_x)
            self._apply_transform()
        elif field == "Anim scale Y":
            self._anim_scale_y = to_float(value, self._anim_scale_y)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_anim_sx = float(base_vals.get("Anim scale X", self._anim_scale_x)) * sx
        new_anim_sy = float(base_vals.get("Anim scale Y", self._anim_scale_y)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Anim scale X": int(round(max(-2048.0, min(2048.0, new_anim_sx)))),
            "Anim scale Y": int(round(max(-2048.0, min(2048.0, new_anim_sy)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result


# ── 可排序的橢圓圖層 item ──────────────────────────────────────────────────────

class LayerEllipseItem(QGraphicsEllipseItem, LayerMixin):
    """繼承 LayerMixin 的橢圓 item，z-value 由 LayeredGraphicsScene 管理。"""

    def __init__(self, rect: QRectF, pen=None, brush=None, parent=None):
        super().__init__(rect, parent)
        self.__init_layer__()
        if pen is not None:
            self.setPen(pen)
        if brush is not None:
            self.setBrush(brush)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self._git_state in _GIT_STATE_RGBA:
            painter.save()
            painter.setBrush(QBrush(QColor.fromRgba(_GIT_STATE_RGBA[self._git_state])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.rect())
            painter.restore()

    def apply_attr(self, field: str, value) -> None:
        r = self.rect()
        hw, hh = r.width() / 2, r.height() / 2
        if field == "X":
            cx = to_float(value, r.center().x())
            cy = r.center().y()
            self.setRect(QRectF(cx - hw, cy - hh, r.width(), r.height()))
        elif field == "Y":
            cx = r.center().x()
            cy = to_float(value, r.center().y())
            self.setRect(QRectF(cx - hw, cy - hh, r.width(), r.height()))
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))


# ── _SelectionOverlay ─────────────────────────────────────────────────────────

class _SelectionOverlay(QGraphicsItem):
    """
    Figma 風格選取框：8 個縮放把手 + 角把手外側旋轉區。
    以獨立 item 放置於 scene 頂層，跟隨選取的 TextLayer。
    """

    _HANDLE_SIZE  = 6
    _HANDLE_HALF  = 3
    _ROT_ZONE     = 10   # 角把手外側幾 px 為旋轉區
    _MARGIN       = 16   # boundingRect 向外延伸（容納旋轉區 + 把手）

    # TL=0  TC=1  TR=2 / ML=3  MR=4 / BL=5  BC=6  BR=7
    _CORNER_HANDLES = frozenset({0, 2, 5, 7})
    _H_ONLY_HANDLES = frozenset({3, 4})
    _V_ONLY_HANDLES = frozenset({1, 6})

    # 拖曳某把手時，對面的固定把手索引
    _PIVOT_FOR_HANDLE = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1, 7: 0}

    # 拖曳方向符號：(sign_x, sign_y)，0 表示該軸不變
    # 正方向 = d_w / d_h 增大；delta = unrotate(drag - pivot)，new_d = sign * delta
    _SIGN_FOR_HANDLE = {
        0: (-1, -1),  # TL
        1: ( 0, -1),  # TC
        2: (+1, -1),  # TR
        3: (-1,  0),  # ML
        4: (+1,  0),  # MR
        5: (-1, +1),  # BL
        6: ( 0, +1),  # BC
        7: (+1, +1),  # BR
    }

    # 各把手在局部座標系的縮放方向角（0°=水平，mod 180°）
    # 旋轉後的實際方向 = base_angle + item_rotation
    _BASE_HANDLE_ANGLE = {0: 45, 1: 90, 2: 135, 3: 0, 4: 0, 5: 135, 6: 90, 7: 45}

    # 角度 → 游標（閾值單位：度，角度已取 mod 180）
    _RESIZE_CURSORS = [
        (22.5,  Qt.CursorShape.SizeHorCursor),
        (67.5,  Qt.CursorShape.SizeFDiagCursor),
        (112.5, Qt.CursorShape.SizeVerCursor),
        (157.5, Qt.CursorShape.SizeBDiagCursor),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target: "TextLayer | None" = None
        self._manager = None
        self._drag_mode: str = ""
        self._drag_start_scene  = QPointF()
        self._drag_start_center = QPointF()
        self._drag_start_vals: dict = {}
        self._drag_handle_idx   = -1
        self._rect = QRectF()

        # 縮放拖曳用的預計算資料（mousePressEvent 填入）
        self._drag_R: float       = 0.0   # 弧度
        self._drag_W: float       = 0.0   # 文字 boundingRect 寬（不含 scale）
        self._drag_H: float       = 0.0
        self._drag_d_w0: float    = 0.0   # 拖曳起始顯示寬
        self._drag_d_h0: float    = 0.0
        self._drag_pivot_scene    = QPointF()
        self._drag_px_fac: float  = 0.0   # pivot 把手在未旋轉座標系中的 X 係數（相對 anchor）
        self._drag_py_fac: float  = 0.0
        self._drag_sign_x: int    = 0
        self._drag_sign_y: int    = 0

        self._show_handles: bool = True   # False = 只顯示外框，無縮放/旋轉把手
        self._drag_iid: "int | None" = None  # 拖曳中的 instance id（用於暫停 refresh）

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    # ── 連接管理 ──────────────────────────────────────────────────────────────

    def attach(self, item: "LayerMixin", manager) -> None:
        if self._manager is not None:
            try:
                self._manager.attr_changed.disconnect(self._on_attr_changed)
            except RuntimeError:
                pass
        self._target       = item
        self._manager      = manager
        self._show_handles = isinstance(item, TextLayer)
        manager.attr_changed.connect(self._on_attr_changed)
        self._update_geometry()

    def detach(self) -> None:
        self._end_drag_pause()
        if self._manager is not None:
            try:
                self._manager.attr_changed.disconnect(self._on_attr_changed)
            except RuntimeError:
                pass
        self._target  = None
        self._manager = None
        self._drag_mode = ""

    def _on_attr_changed(self, field: str, value) -> None:
        self._update_geometry()

    # ── 幾何計算 ──────────────────────────────────────────────────────────────

    def _update_geometry(self) -> None:
        if self._target is None:
            return
        self.prepareGeometryChange()

        if self._show_handles:
            # TextLayer：含旋轉 / scale / shear 的完整計算
            br_local = self._target.boundingRect()
            corners = [
                self._target.mapToScene(p) for p in (
                    br_local.topLeft(), br_local.topRight(),
                    br_local.bottomLeft(), br_local.bottomRight(),
                )
            ]

            ax, ay = self._target._x, self._target._y
            R       = math.radians(self._target._rotation)
            cos_nr, sin_nr = math.cos(-R), math.sin(-R)

            unrot = []
            for p in corners:
                dx, dy = p.x() - ax, p.y() - ay
                unrot.append(QPointF(
                    cos_nr * dx - sin_nr * dy + ax,
                    sin_nr * dx + cos_nr * dy + ay,
                ))

            xs = [p.x() for p in unrot]
            ys = [p.y() for p in unrot]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            rect_w, rect_h = max_x - min_x, max_y - min_y

            cx_u = (min_x + max_x) / 2 - ax
            cy_u = (min_y + max_y) / 2 - ay
            cos_r, sin_r = math.cos(R), math.sin(R)
            center = QPointF(
                cos_r * cx_u - sin_r * cy_u + ax,
                sin_r * cx_u + cos_r * cy_u + ay,
            )

            self.setPos(center)
            self.setRotation(self._target._rotation)
            self._rect = QRectF(-rect_w / 2, -rect_h / 2, rect_w, rect_h)
        else:
            # 無旋轉的簡單 item（如 LayerEllipseItem）
            br = self._target.boundingRect()
            center = self._target.mapToScene(br.center())
            self.setPos(center)
            self.setRotation(0)
            self._rect = QRectF(-br.width() / 2, -br.height() / 2, br.width(), br.height())

        self.update()

    def _handle_positions(self) -> list[QPointF]:
        r  = self._rect
        cx = r.center().x()
        cy = r.center().y()
        l, t, ri, b = r.left(), r.top(), r.right(), r.bottom()
        return [
            QPointF(l,  t),   # 0 TL
            QPointF(cx, t),   # 1 TC
            QPointF(ri, t),   # 2 TR
            QPointF(l,  cy),  # 3 ML
            QPointF(ri, cy),  # 4 MR
            QPointF(l,  b),   # 5 BL
            QPointF(cx, b),   # 6 BC
            QPointF(ri, b),   # 7 BR
        ]

    def _hit_handle(self, local_pos: QPointF) -> int:
        if not self._show_handles:
            return -1
        h = self._HANDLE_HALF + 3
        for i, pos in enumerate(self._handle_positions()):
            if abs(local_pos.x()-pos.x()) <= h and abs(local_pos.y()-pos.y()) <= h:
                return i
        return -1

    def _is_rotation_zone(self, local_pos: QPointF) -> bool:
        if not self._show_handles:
            return False
        for i in self._CORNER_HANDLES:
            pos  = self._handle_positions()[i]
            dist = math.sqrt((local_pos.x()-pos.x())**2 + (local_pos.y()-pos.y())**2)
            if self._HANDLE_HALF + 1 < dist <= self._HANDLE_HALF + self._ROT_ZONE:
                return True
        return False

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        m = self._MARGIN
        return self._rect.adjusted(-m, -m, m, m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None) -> None:
        if self._target is None:
            return

        pen = QPen(QColor("#90CAF9"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._rect)

        if self._show_handles:
            h = self._HANDLE_HALF
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(QBrush(QColor("#90CAF9")))
            for pos in self._handle_positions():
                painter.drawRect(QRectF(pos.x()-h, pos.y()-h, self._HANDLE_SIZE, self._HANDLE_SIZE))

    # ── 游標 ──────────────────────────────────────────────────────────────────

    def _handle_cursor(self, handle_idx: int) -> "Qt.CursorShape":
        """依把手索引與物件旋轉角決定雙向箭頭游標。"""
        base  = self._BASE_HANDLE_ANGLE.get(handle_idx, 0)
        angle = (base + (self._target._rotation if self._target else 0)) % 180
        for threshold, cur in self._RESIZE_CURSORS:
            if angle < threshold:
                return cur
        return Qt.CursorShape.SizeHorCursor

    def hoverMoveEvent(self, event) -> None:
        lp = event.pos()
        if self._is_rotation_zone(lp):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            h = self._hit_handle(lp)
            if h >= 0:
                self.setCursor(self._handle_cursor(h))
            elif self._rect.contains(lp):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.unsetCursor()
        super().hoverMoveEvent(event)

    # ── 滑鼠事件 ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if self._target is None:
            event.ignore()
            return

        lp = event.pos()

        if not self._show_handles:
            # 無縮放/旋轉把手的 item（如 LayerEllipseItem）：只支援 move
            r = self._target.rect()  # type: ignore[attr-defined]
            self._drag_start_vals  = {"X": r.center().x(), "Y": r.center().y()}
            self._drag_start_scene = event.scenePos()
            if self._rect.contains(lp):
                self._drag_mode = "move"
            else:
                self._drag_mode = ""
                event.ignore()
                return
            self._begin_drag_pause()
            event.accept()
            return

        handle_idx = self._hit_handle(lp)
        is_rot     = self._is_rotation_zone(lp)

        self._drag_start_vals = {
            "X":            self._target._x,
            "Y":            self._target._y,
            "Rotation":     self._target._rotation,
            "Anim scale X": self._target._anim_scale_x,
            "Anim scale Y": self._target._anim_scale_y,
        }
        self._drag_start_scene  = event.scenePos()
        self._drag_start_center = self.scenePos()
        self._drag_handle_idx   = handle_idx

        if is_rot and handle_idx < 0:
            self._drag_mode = "rotate"
        elif handle_idx >= 0:
            self._drag_mode = f"scale_{handle_idx}"
            self._init_scale_drag(handle_idx)
        elif self._rect.contains(lp):
            self._drag_mode = "move"
        else:
            self._drag_mode = ""
            event.ignore()
            return

        self._begin_drag_pause()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._target is None or not self._drag_mode:
            event.ignore()
            return

        if self._drag_mode == "move":
            self._do_move(event)
        elif self._drag_mode == "rotate":
            self._do_rotate(event)
        elif self._drag_mode.startswith("scale_"):
            self._do_scale(event)

        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._target is None or not self._drag_mode or self._manager is None:
            self._drag_mode = ""
            return

        from edit_watch import _AttrChangeCommand  # 延遲匯入避免循環依賴

        iid = None
        inst = None
        for _iid, _inst in self._manager._instances.items():
            if _inst.get("canvas_item") is self._target:
                iid, inst = _iid, _inst
                break

        if iid is None or inst is None:
            self._drag_mode = ""
            return

        if not self._show_handles:
            # LayerEllipseItem：只追蹤 X / Y
            r = self._target.rect()  # type: ignore[attr-defined]
            end_vals = {
                "X": int(round(r.center().x())),
                "Y": int(round(r.center().y())),
            }
        else:
            end_vals = {
                "X":            int(round(self._target._x)),
                "Y":            int(round(self._target._y)),
                "Rotation":     int(round(self._target._rotation)),
                "Anim scale X": int(round(self._target._anim_scale_x)),
                "Anim scale Y": int(round(self._target._anim_scale_y)),
            }
        changed = [f for f in end_vals
                   if abs(end_vals[f] - self._drag_start_vals.get(f, 0)) > 1e-6]

        if changed:
            for field in changed:
                inst["values"][field] = end_vals[field]
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())

            label = "Move" if self._drag_mode == "move" else "Transform"
            if len(changed) > 1:
                self._manager.undo_stack.beginMacro(label)
            for field in changed:
                self._manager.undo_stack.push(_AttrChangeCommand(
                    self._manager, iid, field,
                    self._drag_start_vals[field], end_vals[field],
                ))
            if len(changed) > 1:
                self._manager.undo_stack.endMacro()

        self._drag_mode = ""
        self._end_drag_pause()
        event.accept()

    # ── 拖曳暫停 refresh ──────────────────────────────────────────────────────

    def _begin_drag_pause(self) -> None:
        """拖曳開始：將目前 target 的 instance id 加入 _editing_instance_ids，暫停定時刷新。"""
        if self._manager is None or self._target is None:
            return
        for iid, inst in self._manager._instances.items():
            if inst.get("canvas_item") is self._target:
                self._drag_iid = iid
                self._manager._editing_instance_ids.add(iid)
                return

    def _end_drag_pause(self) -> None:
        """拖曳結束：從 _editing_instance_ids 移除，恢復定時刷新。"""
        if self._drag_iid is not None and self._manager is not None:
            self._manager._editing_instance_ids.discard(self._drag_iid)
        self._drag_iid = None

    # ── 拖曳實作 ──────────────────────────────────────────────────────────────

    def _do_move(self, event) -> None:
        delta = event.scenePos() - self._drag_start_scene
        new_x = int(round(max(-1280.0, min(1280.0, self._drag_start_vals["X"] + delta.x()))))
        new_y = int(round(max(-1280.0, min(1280.0, self._drag_start_vals["Y"] + delta.y()))))
        self._target.apply_attr("X", new_x)
        self._target.apply_attr("Y", new_y)
        self._push_live("X", new_x)
        self._push_live("Y", new_y)
        self._update_geometry()

    def _do_rotate(self, event) -> None:
        center = self._drag_start_center
        sp     = self._drag_start_scene
        ep     = event.scenePos()
        start_a = math.degrees(math.atan2(sp.y()-center.y(), sp.x()-center.x()))
        cur_a   = math.degrees(math.atan2(ep.y()-center.y(), ep.x()-center.x()))
        new_rot = int(round(max(-720.0, min(720.0, self._drag_start_vals["Rotation"] + (cur_a - start_a)))))
        self._target.apply_attr("Rotation", new_rot)
        self._push_live("Rotation", new_rot)
        self._update_geometry()

    def _init_scale_drag(self, handle_idx: int) -> None:
        """mousePressEvent 時預計算縮放拖曳所需的固定數值。"""
        t  = self._target
        br = t.boundingRect()
        W, H = br.width(), br.height()
        if W < 0.5 or H < 0.5:
            return

        R   = math.radians(t._rotation)
        d_w = W * t._anim_scale_x / 100.0   # 純 scale、不含 skew 的顯示寬（anchor 公式用）
        d_h = H * t._anim_scale_y / 100.0

        # ── pivot 取 overlay 實際把手的 scene 座標 ──────────────────────────────
        # 必須用 overlay 的真實把手，不能用代數公式——有 skew 時兩者不一致，
        # 使用代數公式會導致第一幀 delta 不等於 overlay 尺寸，造成瞬間跳動。
        pivot_idx  = self._PIVOT_FOR_HANDLE[handle_idx]
        pivot_scene = self.mapToScene(self._handle_positions()[pivot_idx])

        # pivot 反旋轉到 rotation-removed 座標系，計算 px_fac / py_fac
        # 使得 anchor recomputation 公式成立：
        #   pivot_unrot = (px_fac * d_w, py_fac * d_h)
        cos_nr, sin_nr = math.cos(-R), math.sin(-R)
        pdx = pivot_scene.x() - t._x
        pdy = pivot_scene.y() - t._y
        pivot_unrot_x = cos_nr * pdx - sin_nr * pdy
        pivot_unrot_y = sin_nr * pdx + cos_nr * pdy
        px_fac = (pivot_unrot_x / d_w) if abs(d_w) > 0.5 else 0.0
        py_fac = (pivot_unrot_y / d_h) if abs(d_h) > 0.5 else 0.0

        # _drag_d_w0 / h0 = overlay bounding-box 尺寸（含 skew 效果）
        # 用於 _do_scale 的比例縮放：確保拖曳起始時 delta = d_w0，scale 不變
        self._drag_R           = R
        self._drag_W           = W    # 文字 bounding rect 原始寬（anchor 公式用）
        self._drag_H           = H
        self._drag_d_w0        = abs(self._rect.width())
        self._drag_d_h0        = abs(self._rect.height())
        self._drag_pivot_scene = pivot_scene
        self._drag_px_fac      = px_fac
        self._drag_py_fac      = py_fac
        sign_x, sign_y         = self._SIGN_FOR_HANDLE[handle_idx]
        self._drag_sign_x      = sign_x
        self._drag_sign_y      = sign_y

    def _do_scale(self, event) -> None:
        if self._drag_W < 0.5 or self._drag_H < 0.5:
            return

        pivot = self._drag_pivot_scene
        drag  = event.scenePos()

        # 將 pivot → drag 向量旋轉 -R，消除物件旋轉，得到「軸對齊」位移
        R = self._drag_R
        cos_r, sin_r = math.cos(-R), math.sin(-R)
        dx = drag.x() - pivot.x()
        dy = drag.y() - pivot.y()
        delta_ux =  cos_r * dx - sin_r * dy   # 未旋轉後的 X 分量
        delta_uy =  sin_r * dx + cos_r * dy   # 未旋轉後的 Y 分量

        # 根據方向符號計算新的顯示尺寸（允許負值以支援鏡像翻轉）
        if self._drag_sign_x != 0:
            raw = self._drag_sign_x * delta_ux
            new_d_w = math.copysign(max(1.0, abs(raw)), raw) if raw != 0.0 else 1.0
        else:
            new_d_w = self._drag_d_w0

        if self._drag_sign_y != 0:
            raw = self._drag_sign_y * delta_uy
            new_d_h = math.copysign(max(1.0, abs(raw)), raw) if raw != 0.0 else 1.0
        else:
            new_d_h = self._drag_d_h0

        # Shift = 等比（僅角把手）
        h_idx = self._drag_handle_idx
        if (h_idx in self._CORNER_HANDLES
                and self._drag_d_w0 > 0
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            factor = new_d_w / self._drag_d_w0
            raw_h  = self._drag_d_h0 * factor
            new_d_h = math.copysign(max(1.0, abs(raw_h)), raw_h) if raw_h != 0.0 else 1.0

        # 換算成 scale %：比例縮放，以 drag-start 的 overlay 尺寸為基準
        # new_sx = start_sx * (new_d_w / overlay_w0)，確保起始幀 scale 不變
        start_sx = self._drag_start_vals["Anim scale X"]
        start_sy = self._drag_start_vals["Anim scale Y"]
        raw_sx = start_sx * new_d_w / self._drag_d_w0
        raw_sy = start_sy * new_d_h / self._drag_d_h0
        new_sx = int(round(max(-2048.0, min(2048.0, raw_sx))))
        new_sy = int(round(max(-2048.0, min(2048.0, raw_sy))))
        if new_sx == 0:
            new_sx = 1 if raw_sx >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if raw_sy >= 0 else -1

        # 實際夾合後的顯示尺寸（用於計算新 anchor）
        act_d_w = self._drag_W * new_sx / 100.0
        act_d_h = self._drag_H * new_sy / 100.0

        # 根據 pivot 固定，反求新 anchor (X, Y)
        cos_r2, sin_r2 = math.cos(R), math.sin(R)
        px, py = self._drag_px_fac, self._drag_py_fac
        new_x = pivot.x() - (px * act_d_w * cos_r2 - py * act_d_h * sin_r2)
        new_y = pivot.y() - (px * act_d_w * sin_r2 + py * act_d_h * cos_r2)

        new_x = int(round(max(-1280.0, min(1280.0, new_x))))
        new_y = int(round(max(-1280.0, min(1280.0, new_y))))

        self._target.apply_attr("Anim scale X", new_sx)
        self._target.apply_attr("Anim scale Y", new_sy)
        self._target.apply_attr("X", new_x)
        self._target.apply_attr("Y", new_y)
        self._push_live("Anim scale X", new_sx)
        self._push_live("Anim scale Y", new_sy)
        self._push_live("X", new_x)
        self._push_live("Y", new_y)
        self._update_geometry()

    def _push_live(self, field: str, value) -> None:
        """拖曳期間即時更新屬性面板（不 emit attr_changed，避免迴圈）。"""
        if self._manager is not None and hasattr(self._manager, "_attr_panel"):
            self._manager._attr_panel.update_field(field, value)


# ── _MultiSelectOverlay ───────────────────────────────────────────────────────

class _MultiSelectOverlay(QGraphicsItem):
    """
    多選 overlay：每個選取 item 各自顯示 highlight border，
    所有 item 的 union bounding box 頂邊中央顯示 move handle。
    """

    _HANDLE_SIZE = 10
    _MOVE_CURSOR = Qt.CursorShape.SizeAllCursor

    _SCALE_HANDLE_SIZE = 6
    _SCALE_HANDLE_HALF = 3
    _CORNER_HANDLES    = frozenset({0, 2, 5, 7})
    _PIVOT_FOR_HANDLE  = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1, 7: 0}
    # (sign_x, sign_y)：0 表示該軸不縮放
    _SIGN_FOR_HANDLE   = {
        0: (-1, -1), 1: (0, -1), 2: (1, -1),
        3: (-1,  0),             4: (1,  0),
        5: (-1,  1), 6: (0,  1), 7: (1,  1),
    }
    _HANDLE_CURSORS    = {
        0: Qt.CursorShape.SizeFDiagCursor,
        1: Qt.CursorShape.SizeVerCursor,
        2: Qt.CursorShape.SizeBDiagCursor,
        3: Qt.CursorShape.SizeHorCursor,
        4: Qt.CursorShape.SizeHorCursor,
        5: Qt.CursorShape.SizeBDiagCursor,
        6: Qt.CursorShape.SizeVerCursor,
        7: Qt.CursorShape.SizeFDiagCursor,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list = []
        self._manager = None
        self._union_rect = QRectF()
        self._dragging   = False
        self._drag_start = QPointF()
        self._drag_start_positions: dict = {}  # iid -> (x, y)

        self._show_scale_handles: bool  = False
        self._scale_dragging: bool      = False
        self._scale_drag_handle_idx: int = -1
        self._scale_drag_start_scene    = QPointF()
        self._scale_drag_corner_start   = QPointF()
        self._scale_drag_pivot          = QPointF()
        self._scale_drag_union_start    = QRectF()
        self._scale_drag_start_data: dict = {}  # iid -> {field: start_val}
        self._scale_shift_axis: bool | None = None  # True=X驅動, False=Y驅動, None=未鎖定

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,   False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable,  False)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def set_items(self, items: list, manager=None) -> None:
        if self._manager is not None:
            try:
                self._manager.attr_changed.disconnect(self._on_attr_changed)
            except RuntimeError:
                pass
        self._items   = list(items)
        self._manager = manager
        self._show_scale_handles = bool(items) and all(
            getattr(item, "can_scale", False) for item in items
        )
        if manager is not None and items:
            manager.attr_changed.connect(self._on_attr_changed)
        self.prepareGeometryChange()
        self._compute_union()
        self.update()

    def _on_attr_changed(self, _field, _value) -> None:
        self.prepareGeometryChange()
        self._compute_union()
        self.update()

    def _compute_union(self) -> None:
        if not self._items:
            self._union_rect = QRectF()
            return
        rects = []
        for item in self._items:
            br = item.mapToScene(item.boundingRect()).boundingRect()
            rects.append(br)
        left   = min(r.left()   for r in rects)
        top    = min(r.top()    for r in rects)
        right  = max(r.right()  for r in rects)
        bottom = max(r.bottom() for r in rects)
        self._union_rect = QRectF(left, top, right - left, bottom - top)

    def _move_handle_rect(self) -> QRectF:
        if self._union_rect.isNull():
            return QRectF()
        h = self._HANDLE_SIZE
        cx = self._union_rect.center().x()
        ty = self._union_rect.top()
        return QRectF(cx - h / 2, ty - h - 2, h, h)

    def _hit_move_handle(self, scene_pos: QPointF) -> bool:
        local = self.mapFromScene(scene_pos)
        hr = self._move_handle_rect()
        return hr.contains(local)

    def _scale_handle_positions(self) -> list[QPointF]:
        r  = self._union_rect
        cx, cy = r.center().x(), r.center().y()
        return [
            QPointF(r.left(),  r.top()),     # TL=0
            QPointF(cx,        r.top()),     # TC=1
            QPointF(r.right(), r.top()),     # TR=2
            QPointF(r.left(),  cy),          # ML=3
            QPointF(r.right(), cy),          # MR=4
            QPointF(r.left(),  r.bottom()),  # BL=5
            QPointF(cx,        r.bottom()),  # BC=6
            QPointF(r.right(), r.bottom()),  # BR=7
        ]

    def _hit_scale_handle(self, local_pos: QPointF) -> int:
        """回傳命中的把手索引（0-7），未命中回傳 -1。"""
        if not self._show_scale_handles or self._union_rect.isNull():
            return -1
        h = self._SCALE_HANDLE_HALF + 3
        for i, pos in enumerate(self._scale_handle_positions()):
            if abs(local_pos.x() - pos.x()) <= h and abs(local_pos.y() - pos.y()) <= h:
                return i
        return -1

    def boundingRect(self) -> QRectF:
        if self._union_rect.isNull():
            return QRectF()
        m = self._HANDLE_SIZE + 4
        return self._union_rect.adjusted(-m, -m - self._HANDLE_SIZE, m, m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None) -> None:
        if not self._items:
            return

        # 各 item 的 highlight border
        hi_pen = QPen(QColor("#90CAF9"), 1, Qt.PenStyle.DashLine)
        painter.setPen(hi_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for item in self._items:
            sr = item.mapToScene(item.boundingRect()).boundingRect()
            painter.drawRect(sr)

        if self._union_rect.isNull():
            return

        # combined bounding box
        box_pen = QPen(QColor("#90CAF9"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(box_pen)
        painter.drawRect(self._union_rect)

        # move handle（頂邊中央白色正方形）
        hr = self._move_handle_rect()
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.setBrush(QBrush(QColor("#90CAF9")))
        painter.drawRect(hr)

        # 縮放把手（8 個）
        if self._show_scale_handles:
            h = self._SCALE_HANDLE_HALF
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(QBrush(QColor("#90CAF9")))
            for pos in self._scale_handle_positions():
                painter.drawRect(QRectF(pos.x() - h, pos.y() - h,
                                        self._SCALE_HANDLE_SIZE, self._SCALE_HANDLE_SIZE))

    def hoverMoveEvent(self, event) -> None:
        lp = event.pos()
        h_idx = self._hit_scale_handle(lp)
        if h_idx >= 0:
            self.setCursor(self._HANDLE_CURSORS[h_idx])
        elif self._hit_move_handle(event.scenePos()):
            self.setCursor(self._MOVE_CURSOR)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        lp    = self.mapFromScene(event.scenePos())
        h_idx = self._hit_scale_handle(lp)

        if h_idx >= 0 and self._manager is not None:
            self._scale_dragging        = True
            self._scale_drag_handle_idx = h_idx
            self._scale_shift_axis      = None
            self._scale_drag_start_scene = event.scenePos()
            self._scale_drag_union_start  = QRectF(self._union_rect)
            handles = self._scale_handle_positions()
            self._scale_drag_corner_start = handles[h_idx]
            self._scale_drag_pivot        = handles[self._PIVOT_FOR_HANDLE[h_idx]]
            self._scale_drag_start_data   = {}
            for iid in self._manager._selected_ids:
                inst = self._manager._instances.get(iid)
                if inst:
                    vals = inst.get("values", {})
                    self._scale_drag_start_data[iid] = {
                        "X":            float(vals.get("X", 0)),
                        "Y":            float(vals.get("Y", 0)),
                        "Anim scale X": float(vals.get("Anim scale X", 100)),
                        "Anim scale Y": float(vals.get("Anim scale Y", 100)),
                    }
            event.accept()
        elif self._hit_move_handle(lp) and self._manager is not None:
            self._dragging   = True
            self._drag_start = event.scenePos()
            self._drag_start_positions = {}
            for iid in self._manager._selected_ids:
                inst = self._manager._instances.get(iid)
                if inst:
                    vals = inst.get("values", {})
                    self._drag_start_positions[iid] = (
                        float(vals.get("X", 0)),
                        float(vals.get("Y", 0)),
                    )
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event) -> None:
        if self._scale_dragging and self._manager is not None:
            self._do_scale_move(event)
            event.accept()
            return
        if not self._dragging or self._manager is None:
            event.ignore()
            return
        delta = event.scenePos() - self._drag_start
        for iid, (ox, oy) in self._drag_start_positions.items():
            inst = self._manager._instances.get(iid)
            if inst is None:
                continue
            nx = max(-1280, min(1280, ox + delta.x()))
            ny = max(-1280, min(1280, oy + delta.y()))
            inst["values"]["X"] = int(nx)
            inst["values"]["Y"] = int(ny)
            ci = inst.get("canvas_item")
            if ci is not None:
                ci.apply_attr("X", int(nx))
                ci.apply_attr("Y", int(ny))
        self.prepareGeometryChange()
        self._compute_union()
        self.update()
        event.accept()

    def _do_scale_move(self, event) -> None:
        delta = event.scenePos() - self._scale_drag_start_scene
        h_idx   = self._scale_drag_handle_idx
        sign_x, sign_y = self._SIGN_FOR_HANDLE[h_idx]
        old_w   = self._scale_drag_union_start.width()
        old_h   = self._scale_drag_union_start.height()
        pivot_x = self._scale_drag_pivot.x()
        pivot_y = self._scale_drag_pivot.y()

        if sign_x != 0 and old_w > 0.5:
            driven_x = self._scale_drag_corner_start.x() + delta.x()
            raw_dx   = sign_x * (driven_x - pivot_x)
            sx       = math.copysign(max(1.0, abs(raw_dx)), raw_dx) / old_w
        else:
            sx = 1.0

        if sign_y != 0 and old_h > 0.5:
            driven_y = self._scale_drag_corner_start.y() + delta.y()
            raw_dy   = sign_y * (driven_y - pivot_y)
            sy       = math.copysign(max(1.0, abs(raw_dy)), raw_dy) / old_h
        else:
            sy = 1.0

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if h_idx in self._CORNER_HANDLES and shift:
            # 第一次偏差超過門檻時鎖定主導軸，之後不再切換
            if self._scale_shift_axis is None:
                if abs(sx - 1.0) > 0.02 or abs(sy - 1.0) > 0.02:
                    self._scale_shift_axis = abs(sx - 1.0) >= abs(sy - 1.0)
            if self._scale_shift_axis is True:
                sy = sx
            elif self._scale_shift_axis is False:
                sx = sy
            else:
                if abs(sx - 1.0) >= abs(sy - 1.0):
                    sy = sx
                else:
                    sx = sy
        else:
            self._scale_shift_axis = None

        for iid, base_vals in self._scale_drag_start_data.items():
            inst = self._manager._instances.get(iid)
            if inst is None:
                continue
            ci = inst.get("canvas_item")
            if ci is None:
                continue
            new_vals = ci.apply_scale_factor(sx, sy, pivot_x, pivot_y, base_vals)
            for field, val in new_vals.items():
                inst["values"][field] = val

        self.prepareGeometryChange()
        self._compute_union()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._scale_dragging and self._manager is not None:
            self._scale_dragging = False
            from edit_watch import _AttrChangeCommand  # 延遲 import 避免循環
            self._manager.undo_stack.beginMacro("Scale Multi")
            for iid, base_vals in self._scale_drag_start_data.items():
                inst = self._manager._instances.get(iid)
                if inst is None:
                    continue
                ti = inst.get("tree_item")
                if ti is not None:
                    ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
                for field, old_val in base_vals.items():
                    new_val = inst["values"].get(field, old_val)
                    if abs(float(new_val) - float(old_val)) > 1e-6:
                        self._manager.undo_stack.push(
                            _AttrChangeCommand(self._manager, iid, field, old_val, new_val)
                        )
            self._manager.undo_stack.endMacro()
            self._scale_drag_start_data = {}
            event.accept()
        elif self._dragging and self._manager is not None:
            self._dragging = False
            from edit_watch import _MoveMultiCommand  # 延遲 import 避免循環
            deltas = {}
            for iid, (ox, oy) in self._drag_start_positions.items():
                inst = self._manager._instances.get(iid)
                if inst:
                    nx = float(inst["values"].get("X", ox))
                    ny = float(inst["values"].get("Y", oy))
                    deltas[iid] = (ox, oy, nx, ny)
            if deltas:
                self._manager.undo_stack.push(
                    _MoveMultiCommand(self._manager, deltas)
                )
            event.accept()
        else:
            event.ignore()


# ── CanvasGroupLayer ──────────────────────────────────────────────────────────

class CanvasGroupLayer(QGraphicsRectItem, LayerMixin):
    """
    Canvas 上的群組容器：顯示虛線外框，子物件為其 Qt parent item。
    """

    def __init__(self, rect: QRectF, parent=None):
        super().__init__(rect, parent)
        self.__init_layer__()
        pen = QPen(QColor("#90CAF9"), 1, Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,   False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def child_canvas_items(self) -> list:
        return [c for c in self.childItems() if isinstance(c, LayerMixin)]

    def apply_attr(self, field: str, value) -> None:
        pass
