"""
layers.py — LayerMixin、LayeredGraphicsScene、TextLayer
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QRectF, QPointF, QSizeF
from .utils import to_float, to_str
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem

_NON_LAYER_Z: float = 1e8

_GIT_STATE_RGBA: dict[str, int] = {
    "add":    0x26A5D6A7,
    "modify": 0x26FFAB91,
    "delete": 0x26EF9A9A,
}


def _parse_hex_color(value) -> QColor:
    """將 hex 字串（可含 #、可為 None）轉為 QColor；無效時退回白色。"""
    s = str(value or "").strip().lstrip("#")
    color = QColor(f"#{s}")
    return color if color.isValid() else QColor(Qt.GlobalColor.white)


def _scale_and_tint(src: QPixmap, w: int, h: int, tint_hex) -> QPixmap:
    """依 w/h 縮放 src，並選擇性套用 tint（乘色）；src 為 null 時回傳 null pixmap。"""
    if src.isNull():
        return QPixmap()
    scaled = src.scaled(
        max(1, w), max(1, h),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    tint = str(tint_hex or "").strip().lstrip("#")
    tint_color = QColor(f"#{tint}") if tint else None
    if tint_color is None or not tint_color.isValid():
        return scaled

    result = QPixmap(scaled.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.drawPixmap(0, 0, scaled)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    painter.fillRect(result.rect(), tint_color)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return result


def _scale_crop_fill(src: QPixmap, w: int, h: int) -> QPixmap:
    """依 w/h 裁切式縮放 src（KeepAspectRatioByExpanding 後置中裁切至精確 w×h)，
    避免內容因拉伸而變形；src 為 null 時回傳 null pixmap。
    """
    if src.isNull():
        return QPixmap()
    w, h = max(1, w), max(1, h)
    scaled = src.scaled(
        w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    return scaled.copy(x, y, w, h)


# Photo clip 圓角比例（相對於 min(w, h)）
_PHOTO_CLIP_CORNER_RATIO: dict[str, float] = {
    "Corner 1": 0.15,
    "Corner 2": 0.30,
}


def _clip_pixmap(src: QPixmap, w: int, h: int, clip: str) -> QPixmap:
    """依 Photo clip 選項（None/Circle/Corner 1/Corner 2）裁切 src 為對應形狀，
    形狀外部變透明；"None" 或未知值直接回傳原圖（不裁切）。src 為 null 時回傳 null pixmap。
    """
    if src.isNull() or not clip or clip == "None":
        return src
    path = QPainterPath()
    if clip == "Circle":
        path.addEllipse(0, 0, w, h)
    elif clip in _PHOTO_CLIP_CORNER_RATIO:
        r = min(w, h) * _PHOTO_CLIP_CORNER_RATIO[clip]
        r = min(r, min(w, h) / 2.0)
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
    else:
        return src

    result = QPixmap(w, h)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return result


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

    def _refresh_display(self) -> None:
        """依 self._display 與 manager.is_dark_mode 決定是否顯示。
        建構當下尚未加入 scene，manager 會是 None，此時先視為亮屏；
        待加入 scene 後 _place_from_values 會再呼叫一次以套用實際模式。
        """
        manager = self._get_manager()
        is_dark = bool(manager.is_dark_mode) if manager is not None else False
        display = self._display  # type: ignore[attr-defined]
        if display == "Never":
            self.setVisible(False)  # type: ignore[attr-defined]
        elif display == "Bright only":
            self.setVisible(not is_dark)  # type: ignore[attr-defined]
        elif display == "Dimmed only":
            self.setVisible(is_dark)  # type: ignore[attr-defined]
        else:
            self.setVisible(True)  # type: ignore[attr-defined]

    def apply_attr(self, field: str, value) -> None:
        """子類覆寫以處理屬性變更的視覺更新。"""
        pass

    def tick(self) -> None:
        """每秒由 PanelWidgetManager.refresh_all_instances() 呼叫一次，供需要自主動畫
        （如 SlideshowLayer 輪播）的子類覆寫；預設不做任何事。"""
        pass

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        """以 base_vals 為起點套用縮放，回傳更新後的 field→value dict。子類覆寫（供多選縮放使用）。"""
        return {}

    # ── 單選 _SelectionOverlay 拖曳縮放用的泛型 hook ────────────────────────────
    # 不同圖層的「縮放」語意不同：TextLayer 用 Anim scale 百分比（字體本身不變），
    # ImageLayer 直接改 Width/Height 像素值。以下 hook 讓 _SelectionOverlay 的
    # 拖曳幾何運算保持通用，實際欄位語意交給子類決定。

    def scale_geom(self) -> tuple[float, float]:
        """回傳縮放拖曳基準用的『內在』寬高（未受目前縮放百分比影響）。預設為 boundingRect。"""
        br = self.boundingRect()  # type: ignore[attr-defined]
        return br.width(), br.height()

    def get_scale_pct(self) -> tuple[float, float]:
        """回傳目前縮放百分比（相對 scale_geom()）。預設 100%（無獨立縮放百分比概念）。"""
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        """回傳實際會套用的縮放百分比（依子類欄位範圍夾合），供 overlay 在套用前算出正確錨點位置。"""
        return sx_pct, sy_pct

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        """套用單選拖曳縮放的絕對目標值，回傳實際套用的 field→value dict。子類覆寫。"""
        return {}

    def scale_result_values(self) -> dict:
        """回傳目前 X/Y/Rotation 與縮放相關欄位的值快照，供 undo 追蹤比對。子類覆寫。"""
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
        self._color_day = values.get("Color", "ffffff")
        self._color_dim = values.get("Color dim", "ffffff")
        self._refresh_color()
        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()

        self._display = str(values.get("Display", "Always"))
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _apply_font(self) -> None:
        # 延遲匯入避免 components → special_ui 的循環依賴
        from special_ui import FontManager
        family = FontManager().get_font_family(self._font_name) or self._font_name
        font = QFont(family)
        font.setPixelSize(self._font_size)
        self.setFont(font)

    def _apply_color(self, hex_val) -> None:
        self.setDefaultTextColor(_parse_hex_color(hex_val))

    def _refresh_color(self) -> None:
        """依 manager.is_dark_mode 決定顯示 Color（day）或 Color dim（night）。
        建構當下尚未加入 scene，manager 會是 None，此時先以 day color 顯示，
        待 _place_from_values 加入 scene 後會再呼叫一次以套用實際模式。
        """
        manager = self._get_manager()
        is_night = bool(manager.is_dark_mode) if manager is not None else False
        self._apply_color(self._color_dim if is_night else self._color_day)

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
            self._color_day = value
            self._refresh_color()
        elif field == "Color dim":
            self._color_dim = value
            self._refresh_color()
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
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
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

    # ── 單選拖曳縮放 hook（Anim scale 百分比語意）───────────────────────────────

    def get_scale_pct(self) -> tuple[float, float]:
        return self._anim_scale_x, self._anim_scale_y

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = max(-2048.0, min(2048.0, sx_pct))
        csy = max(-2048.0, min(2048.0, sy_pct))
        if csx == 0:
            csx = 1.0 if sx_pct >= 0 else -1.0
        if csy == 0:
            csy = 1.0 if sy_pct >= 0 else -1.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_sx = int(round(max(-2048.0, min(2048.0, new_sx_pct))))
        new_sy = int(round(max(-2048.0, min(2048.0, new_sy_pct))))
        if new_sx == 0:
            new_sx = 1 if new_sx_pct >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if new_sy_pct >= 0 else -1
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Anim scale X", new_sx)
        self.apply_attr("Anim scale Y", new_sy)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Anim scale X": new_sx, "Anim scale Y": new_sy, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Anim scale X": self._anim_scale_x, "Anim scale Y": self._anim_scale_y,
        }


class CurvedTextLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的圓弧文字 item。
    X/Y 為圓心；文字依 Radius 沿圓周排列，Direction 決定彎曲方向：
    "Up" 為圓心上方弧線（字頂朝外，類似拱形招牌）；"Down" 為圓心下方弧線（字頂朝內，類似徽章下緣文字）。
    文字永遠由左至右沿弧排列；Alignment 依水平分量分三組：
    *left → 文字起點對齊 Direction 錨點角度；*right → 文字終點對齊；其餘（含 Center）置中對齊。
    """

    _H_GROUP: dict[str, str] = {
        "Top left": "left", "Center left": "left", "Bottom left": "left",
        "Center": "center", "Top center": "center", "Bottom center": "center",
        "Top right": "right", "Center right": "right", "Bottom right": "right",
    }

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x            = to_float(values.get("X", 0))
        self._y            = to_float(values.get("Y", 0))
        self._radius        = max(1.0, to_float(values.get("Radius", 200), 200.0))
        self._direction     = str(values.get("Direction", "Up"))
        self._alignment     = str(values.get("Alignment", "Center"))
        self._font_name     = str(values.get("Font", ""))
        self._font_size     = int(to_float(values.get("Text size", 40), 40.0))
        self._rotation      = to_float(values.get("Rotation", 0))
        self._skew_x        = to_float(values.get("Skew X", 0))
        self._skew_y        = to_float(values.get("Skew Y", 0))
        self._anim_scale_x  = to_float(values.get("Anim scale X", 100), 100.0)
        self._anim_scale_y  = to_float(values.get("Anim scale Y", 100), 100.0)
        self._text          = to_str(str(values.get("Text", "")))
        self._color_day     = values.get("Color", "ffffff")
        self._color_dim     = values.get("Color dim", "ffffff")
        self._display       = str(values.get("Display", "Always"))

        self._font = QFont()
        self._brush_color = QColor(Qt.GlobalColor.white)
        self._chars: list[tuple[str, float, float, float, float]] = []  # (char, cx, cy, rot_deg, width)
        self._bounding_rect = QRectF()

        self._apply_font()
        self._refresh_color()
        self._rebuild_layout()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _apply_font(self) -> None:
        # 延遲匯入避免 components → special_ui 的循環依賴
        from special_ui import FontManager
        family = FontManager().get_font_family(self._font_name) or self._font_name
        font = QFont(family)
        font.setPixelSize(self._font_size)
        self._font = font

    def _apply_color(self, hex_val) -> None:
        self._brush_color = _parse_hex_color(hex_val)
        self.update()

    def _refresh_color(self) -> None:
        """依 manager.is_dark_mode 決定顯示 Color（day）或 Color dim（night）。"""
        manager = self._get_manager()
        is_night = bool(manager.is_dark_mode) if manager is not None else False
        self._apply_color(self._color_dim if is_night else self._color_day)

    def _rebuild_layout(self) -> None:
        """依 Text/Font/Text size/Radius/Direction/Alignment 重新計算每個字元沿圓弧的
        位置與旋轉角，並算出精確 boundingRect（原點＝圓心，未套用 Rotation/Skew/Anim scale）。
        角度慣例：0°＝三點鐘方向，正值順時針；-90°＝圓心正上方，+90°＝圓心正下方。
        """
        fm = QFontMetricsF(self._font)
        text = self._text
        widths = [fm.horizontalAdvance(ch) for ch in text]
        radius = self._radius
        total_width = sum(widths)
        total_angle = (total_width / radius) if radius > 0 else 0.0

        is_up = self._direction != "Down"
        anchor_angle = math.radians(-90.0 if is_up else 90.0)
        dir_sign = 1.0 if is_up else -1.0

        h_group = self._H_GROUP.get(self._alignment, "center")
        if h_group == "left":
            start_angle = anchor_angle
        elif h_group == "right":
            start_angle = anchor_angle - dir_sign * total_angle
        else:
            start_angle = anchor_angle - dir_sign * total_angle / 2.0

        ascent, descent = fm.ascent(), fm.descent()
        chars: list[tuple[str, float, float, float, float]] = []
        bounds = QRectF()
        running = start_angle
        for ch, w in zip(text, widths):
            span = (w / radius) if radius > 0 else 0.0
            center_angle = running + dir_sign * span / 2.0
            running += dir_sign * span

            cx = radius * math.cos(center_angle)
            cy = radius * math.sin(center_angle)
            angle_deg = math.degrees(center_angle)
            rot_deg = angle_deg + 90.0 if is_up else angle_deg - 90.0
            chars.append((ch, cx, cy, rot_deg, w))

            t = QTransform()
            t.translate(cx, cy)
            t.rotate(rot_deg)
            local_rect = QRectF(-w / 2.0, -ascent, w, ascent + descent)
            bounds = bounds.united(t.mapRect(local_rect))

        self._chars = chars
        self._bounding_rect = bounds

    def _apply_transform(self) -> None:
        """縮放/旋轉/傾斜一律以圓心（局部原點）為軸，最後平移至 (X,Y)。"""
        sx = self._anim_scale_x / 100.0
        sy = self._anim_scale_y / 100.0
        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.scale(sx, sy)
        t.shear(sh_x, sh_y)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(self, painter, option, widget=None) -> None:
        if not self._chars:
            return
        painter.setFont(self._font)
        painter.setPen(QPen(self._brush_color))
        for ch, cx, cy, rot_deg, w in self._chars:
            if ch.isspace():
                continue
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            fm = painter.fontMetrics()
            rect = QRectF(-w / 2.0, -fm.ascent(), w, fm.ascent() + fm.descent())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)
            painter.restore()

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field in ("Text", "Radius", "Direction", "Alignment"):
            self.prepareGeometryChange()
            if field == "Text":
                self._text = to_str(str(value))
            elif field == "Radius":
                self._radius = max(1.0, to_float(value, self._radius))
            elif field == "Direction":
                self._direction = str(value)
            elif field == "Alignment":
                self._alignment = str(value)
            self._rebuild_layout()
        elif field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Font":
            self._font_name = str(value)
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Text size":
            self._font_size = int(to_float(value, self._font_size))
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Color":
            self._color_day = value
            self._refresh_color()
        elif field == "Color dim":
            self._color_dim = value
            self._refresh_color()
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
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
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

    # ── 單選拖曳縮放 hook（Anim scale 百分比語意）───────────────────────────────

    def get_scale_pct(self) -> tuple[float, float]:
        return self._anim_scale_x, self._anim_scale_y

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = max(-2048.0, min(2048.0, sx_pct))
        csy = max(-2048.0, min(2048.0, sy_pct))
        if csx == 0:
            csx = 1.0 if sx_pct >= 0 else -1.0
        if csy == 0:
            csy = 1.0 if sy_pct >= 0 else -1.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_sx = int(round(max(-2048.0, min(2048.0, new_sx_pct))))
        new_sy = int(round(max(-2048.0, min(2048.0, new_sy_pct))))
        if new_sx == 0:
            new_sx = 1 if new_sx_pct >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if new_sy_pct >= 0 else -1
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Anim scale X", new_sx)
        self.apply_attr("Anim scale Y", new_sy)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Anim scale X": new_sx, "Anim scale Y": new_sy, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Anim scale X": self._anim_scale_x, "Anim scale Y": self._anim_scale_y,
        }


# ── TextRingLayer（環形文字／Numbers）───────────────────────────────────────────

class TextRingLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的環形文字（Numbers）item。
    依 Ring type 產生一組標籤，等距分布於 Angle start ~ Angle end 之間
    （角度慣例：0°＝正上方，順時針遞增）。
    Squarify 依超橢圓公式 r(θ) = R / (|cosθ|^n + |sinθ|^n)^(1/n) 將圓形路徑往方形擠壓
    （扁平邊固定於半徑 R，對角隨 n 增大逐漸外擴；n 隨 Squarify 1~100 由 2 遞增至 12）。
    Show every／Hide text 依 1-based 原始序位篩選要顯示的項目；
    Text rotation 決定每個標籤相對其環上位置的自轉方式；每個標籤永遠置中於其環上位置。
    """

    _ROMAN     = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    _WEEKDAY_2 = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    _WEEKDAY_3 = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _MONTHS    = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    _LAYOUT_FIELDS = frozenset({
        "Ring type", "Custom start", "Custom end", "Show every", "Hide text",
        "Angle start", "Angle end", "Squarify", "Text rotation",
    })

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x             = to_float(values.get("X", 0))
        self._y             = to_float(values.get("Y", 0))
        self._radius        = max(1.0, to_float(values.get("Radius", 200), 200.0))
        self._ring_type      = str(values.get("Ring type", "1-12"))
        self._custom_start  = int(round(to_float(values.get("Custom start", 1), 1.0)))
        self._custom_end    = int(round(to_float(values.get("Custom end", 12), 12.0)))
        self._show_every    = max(1, int(round(to_float(values.get("Show every", 1), 1.0))))
        self._hide_text     = str(values.get("Hide text", "") or "")
        self._text_rotation = str(values.get("Text rotation", "Upright"))
        self._angle_start   = to_float(values.get("Angle start", 0))
        self._angle_end     = to_float(values.get("Angle end", 360))
        self._squarify      = max(1.0, min(100.0, to_float(values.get("Squarify", 1), 1.0)))
        self._font_name     = str(values.get("Font", ""))
        self._font_size     = int(to_float(values.get("Text size", 40), 40.0))
        self._rotation      = to_float(values.get("Rotation", 0))
        self._skew_x        = to_float(values.get("Skew X", 0))
        self._skew_y        = to_float(values.get("Skew Y", 0))
        self._anim_scale_x  = to_float(values.get("Anim scale X", 100), 100.0)
        self._anim_scale_y  = to_float(values.get("Anim scale Y", 100), 100.0)
        self._color_day     = values.get("Color", "ffffff")
        self._color_dim     = values.get("Color dim", "ffffff")
        self._display       = str(values.get("Display", "Always"))

        self._font = QFont()
        self._brush_color = QColor(Qt.GlobalColor.white)
        self._items: list[tuple[str, float, float, float, QRectF]] = []  # (text, cx, cy, rot_deg, local_rect)
        self._bounding_rect = QRectF()

        self._apply_font()
        self._refresh_color()
        self._rebuild_layout()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _apply_font(self) -> None:
        # 延遲匯入避免 components → special_ui 的循環依賴
        from special_ui import FontManager
        family = FontManager().get_font_family(self._font_name) or self._font_name
        font = QFont(family)
        font.setPixelSize(self._font_size)
        self._font = font

    def _apply_color(self, hex_val) -> None:
        self._brush_color = _parse_hex_color(hex_val)
        self.update()

    def _refresh_color(self) -> None:
        """依 manager.is_dark_mode 決定顯示 Color（day）或 Color dim（night）。"""
        manager = self._get_manager()
        is_night = bool(manager.is_dark_mode) if manager is not None else False
        self._apply_color(self._color_dim if is_night else self._color_day)

    def _generate_labels(self) -> list[str]:
        rt = self._ring_type
        if rt == "1-12":
            return [str(i) for i in range(1, 13)]
        if rt == "1-24":
            return [str(i) for i in range(1, 25)]
        if rt == "1-30":
            return [str(i) for i in range(1, 31)]
        if rt == "1-31":
            return [str(i) for i in range(1, 32)]
        if rt == "1-60":
            return [str(i) for i in range(1, 61)]
        if rt == "1-100":
            return [str(i) for i in range(1, 101)]
        if rt == "Custom (x to y)":
            a, b = self._custom_start, self._custom_end
            step = 1 if b >= a else -1
            return [str(i) for i in range(a, b + step, step)]
        if rt == "I-XII":
            return list(self._ROMAN)
        if rt == "Mo-Su":
            return list(self._WEEKDAY_2)
        if rt == "Mon-Sun":
            return list(self._WEEKDAY_3)
        if rt == "Jan-Dec":
            return list(self._MONTHS)
        return [str(i) for i in range(1, 13)]

    def _hidden_positions(self) -> set[int]:
        """解析 Hide text（逗號分隔的 1-based 序位字串）；格式錯誤的片段直接略過。"""
        result: set[int] = set()
        for part in self._hide_text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                result.add(int(part))
            except ValueError:
                pass
        return result

    def _squarify_radius(self, angle_deg: float) -> float:
        """依超橢圓（Lamé curve）公式將圓形半徑往方形擠壓；Squarify=1 為圓形下限（n=2）。"""
        t = (self._squarify - 1.0) / 99.0
        n = 2.0 + 10.0 * (t ** 2)
        rad = math.radians(angle_deg)
        c, s = abs(math.cos(rad)), abs(math.sin(rad))
        denom = (c ** n + s ** n) ** (1.0 / n)
        return self._radius / denom if denom > 1e-9 else self._radius

    def _item_rotation(self, angle_deg: float) -> float:
        style = self._text_rotation
        if style == "Rotate":
            return angle_deg
        if style == "Rotate Inverse":
            return angle_deg + 180.0
        if style == "Rotate Upright":
            a = angle_deg % 360.0
            return angle_deg if (a <= 90.0 or a >= 270.0) else angle_deg + 180.0
        return 0.0  # "Upright"

    def _rebuild_layout(self) -> None:
        """依 Ring type/Custom start-end/Show every/Hide text/Angle start-end/Squarify/
        Text rotation 重新計算每個可見標籤的位置、旋轉與繪製用 local rect
        （每個標籤永遠置中於其環上位置），並算出精確 boundingRect
        （原點＝圓心，未套用 Rotation/Skew/Anim scale）。
        """
        fm = QFontMetricsF(self._font)
        labels = self._generate_labels()
        total = len(labels)
        hidden = self._hidden_positions()
        span = self._angle_end - self._angle_start
        step = (span / total) if total else 0.0
        fx, fy = -0.5, -0.5  # 每個標籤置中於其環上位置
        ascent, descent = fm.ascent(), fm.descent()
        h = ascent + descent

        items: list[tuple[str, float, float, float, QRectF]] = []
        bounds = QRectF()
        for idx, text in enumerate(labels):
            pos = idx + 1
            if pos % self._show_every != 0 or pos in hidden:
                continue

            angle = self._angle_start + idx * step
            r = self._squarify_radius(angle)
            rad = math.radians(angle)
            cx = r * math.sin(rad)
            cy = -r * math.cos(rad)
            rot_deg = self._item_rotation(angle)

            w = fm.horizontalAdvance(text)
            local_rect = QRectF(fx * w, fy * h, w, h)
            items.append((text, cx, cy, rot_deg, local_rect))

            t = QTransform()
            t.translate(cx, cy)
            t.rotate(rot_deg)
            bounds = bounds.united(t.mapRect(local_rect))

        self._items = items
        self._bounding_rect = bounds

    def _apply_transform(self) -> None:
        """縮放/旋轉/傾斜一律以圓心（局部原點）為軸，最後平移至 (X,Y)。
        與 CurvedTextLayer._apply_transform 邏輯一致。
        """
        sx = self._anim_scale_x / 100.0
        sy = self._anim_scale_y / 100.0
        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.scale(sx, sy)
        t.shear(sh_x, sh_y)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(self, painter, option, widget=None) -> None:
        if not self._items:
            return
        painter.setFont(self._font)
        painter.setPen(QPen(self._brush_color))
        for text, cx, cy, rot_deg, local_rect in self._items:
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            painter.drawText(local_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Radius":
            self.prepareGeometryChange()
            self._radius = max(1.0, to_float(value, self._radius))
            self._rebuild_layout()
        elif field in self._LAYOUT_FIELDS:
            self.prepareGeometryChange()
            if field == "Ring type":
                self._ring_type = str(value)
            elif field == "Custom start":
                self._custom_start = int(round(to_float(value, self._custom_start)))
            elif field == "Custom end":
                self._custom_end = int(round(to_float(value, self._custom_end)))
            elif field == "Show every":
                self._show_every = max(1, int(round(to_float(value, self._show_every))))
            elif field == "Hide text":
                self._hide_text = str(value or "")
            elif field == "Angle start":
                self._angle_start = to_float(value, self._angle_start)
            elif field == "Angle end":
                self._angle_end = to_float(value, self._angle_end)
            elif field == "Squarify":
                self._squarify = max(1.0, min(100.0, to_float(value, self._squarify)))
            elif field == "Text rotation":
                self._text_rotation = str(value)
            self._rebuild_layout()
        elif field == "Font":
            self._font_name = str(value)
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Text size":
            self._font_size = int(to_float(value, self._font_size))
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Color":
            self._color_day = value
            self._refresh_color()
        elif field == "Color dim":
            self._color_dim = value
            self._refresh_color()
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
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
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

    # ── 單選拖曳縮放 hook（Anim scale 百分比語意）───────────────────────────────

    def get_scale_pct(self) -> tuple[float, float]:
        return self._anim_scale_x, self._anim_scale_y

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = max(-2048.0, min(2048.0, sx_pct))
        csy = max(-2048.0, min(2048.0, sy_pct))
        if csx == 0:
            csx = 1.0 if sx_pct >= 0 else -1.0
        if csy == 0:
            csy = 1.0 if sy_pct >= 0 else -1.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_sx = int(round(max(-2048.0, min(2048.0, new_sx_pct))))
        new_sy = int(round(max(-2048.0, min(2048.0, new_sy_pct))))
        if new_sx == 0:
            new_sx = 1 if new_sx_pct >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if new_sy_pct >= 0 else -1
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Anim scale X", new_sx)
        self.apply_attr("Anim scale Y", new_sy)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Anim scale X": new_sx, "Anim scale Y": new_sy, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Anim scale X": self._anim_scale_x, "Anim scale Y": self._anim_scale_y,
        }


# ── ImageLayer ────────────────────────────────────────────────────────────────

class ImageLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的圖片 item。
    X/Y 為錨點座標；錨點位置由 Alignment 欄位決定（與 TextLayer 共用同一套 _ANCHOR）。
    Width/Height 直接是顯示尺寸（無獨立縮放百分比概念）。
    """

    _ANCHOR = TextLayer._ANCHOR

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x         = to_float(values.get("X", 0))
        self._y         = to_float(values.get("Y", 0))
        self._width     = max(1.0, to_float(values.get("Width", 100), 100.0))
        self._height    = max(1.0, to_float(values.get("Height", 100), 100.0))
        self._alignment = str(values.get("Alignment", "Center"))
        self._rotation  = to_float(values.get("Rotation", 0))
        self._skew_x    = to_float(values.get("Skew X", 0))
        self._skew_y    = to_float(values.get("Skew Y", 0))
        self._tint      = values.get("Tint", "")
        self._image_path = str(values.get("Custom image", "") or "")
        self._display   = str(values.get("Display", "Always"))

        self._src_pixmap: QPixmap = QPixmap()
        self._render_pixmap: QPixmap = QPixmap()
        self._load_pixmap()
        self._rebuild_pixmap()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _load_pixmap(self) -> None:
        pm = QPixmap()
        if self._image_path and pm.load(self._image_path):
            self._src_pixmap = pm
        else:
            self._src_pixmap = QPixmap()

    def _rebuild_pixmap(self) -> None:
        """依目前 Width/Height/Tint 重新產生繪製用快取 pixmap；無來源圖片時保持空白（完全不畫）。"""
        w = max(1, int(round(self._width)))
        h = max(1, int(round(self._height)))
        self._render_pixmap = _scale_and_tint(self._src_pixmap, w, h, self._tint)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜(繞中心) → 對齊(錨點移至原點) → 旋轉 → 平移(X,Y)。
        與 TextLayer._apply_transform 邏輯一致，但無獨立縮放步驟（Width/Height 已是實際尺寸）。
        """
        w, h = self._width, self._height
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        ax, ay = fx * w, fy * h

        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.translate(ax + w / 2, ay + h / 2)
        t.shear(sh_x, sh_y)
        t.translate(-w / 2, -h / 2)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None) -> None:
        if self._render_pixmap.isNull():
            return
        painter.drawPixmap(QRectF(0, 0, self._width, self._height), self._render_pixmap,
                           QRectF(self._render_pixmap.rect()))

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Width":
            self.prepareGeometryChange()
            self._width = max(1.0, to_float(value, self._width))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Height":
            self.prepareGeometryChange()
            self._height = max(1.0, to_float(value, self._height))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Tint":
            self._tint = value
            self._rebuild_pixmap()
            self.update()
        elif field == "Custom image":
            self._image_path = str(value or "")
            self._load_pixmap()
            self._rebuild_pixmap()
            self.update()
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_w = float(base_vals.get("Width", self._width)) * sx
        new_h = float(base_vals.get("Height", self._height)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Width":  int(round(max(1.0, min(2048.0, new_w)))),
            "Height": int(round(max(1.0, min(2048.0, new_h)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result

    # ── 單選拖曳縮放 hook（Width/Height 像素語意）──────────────────────────────

    def scale_geom(self) -> tuple[float, float]:
        return self._width, self._height

    def get_scale_pct(self) -> tuple[float, float]:
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = sx_pct
        csy = sy_pct
        if geom_w > 0.5:
            csx = max(1.0, min(2048.0, geom_w * sx_pct / 100.0)) / geom_w * 100.0
        if geom_h > 0.5:
            csy = max(1.0, min(2048.0, geom_h * sy_pct / 100.0)) / geom_h * 100.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_w = int(round(max(1.0, min(2048.0, geom_w * new_sx_pct / 100.0))))
        new_h = int(round(max(1.0, min(2048.0, geom_h * new_sy_pct / 100.0))))
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Width", new_w)
        self.apply_attr("Height", new_h)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Width": new_w, "Height": new_h, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Width": self._width, "Height": self._height,
        }


# ── SlideshowLayer（幻燈片）─────────────────────────────────────────────────────

class SlideshowLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的幻燈片 item。
    幾何模型與 ImageLayer 相同（X/Y 為錨點座標，Alignment 決定錨點位置，
    Width/Height 為實際顯示尺寸）；差異在於 Photo 為逗號分隔的多張圖片路徑清單，
    每隔 Photo duration 秒（由 PanelWidgetManager 每秒呼叫一次 tick() 累計）自動切換至下一張，
    循環至清單開頭。無法載入的路徑直接略過；清單為空或全部載入失敗時不繪製任何內容。
    """

    _ANCHOR = TextLayer._ANCHOR

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x         = to_float(values.get("X", 0))
        self._y         = to_float(values.get("Y", 0))
        self._width     = max(1.0, to_float(values.get("Width", 100), 100.0))
        self._height    = max(1.0, to_float(values.get("Height", 100), 100.0))
        self._alignment = str(values.get("Alignment", "Center"))
        self._rotation  = to_float(values.get("Rotation", 0))
        self._skew_x    = to_float(values.get("Skew X", 0))
        self._skew_y    = to_float(values.get("Skew Y", 0))
        self._tint      = values.get("Tint", "")
        self._photo_str      = str(values.get("Photo", "") or "")
        self._photo_duration = max(1.0, to_float(values.get("Photo duration", 5), 5.0))
        self._photo_clip     = str(values.get("Photo clip", "None") or "None")
        self._display   = str(values.get("Display", "Always"))

        self._src_pixmaps: list[QPixmap] = []
        self._current_index = 0
        self._elapsed_secs = 0.0
        self._render_pixmap: QPixmap = QPixmap()
        self._load_pixmaps()
        self._rebuild_pixmap()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _load_pixmaps(self) -> None:
        """依 Photo（逗號分隔路徑清單）載入所有可成功讀取的圖片；重設目前索引與計時。"""
        pixmaps: list[QPixmap] = []
        for path in self._photo_str.split(","):
            path = path.strip()
            if not path:
                continue
            pm = QPixmap()
            if pm.load(path):
                pixmaps.append(pm)
        self._src_pixmaps = pixmaps
        self._current_index = 0
        self._elapsed_secs = 0.0

    def _current_pixmap(self) -> QPixmap:
        if not self._src_pixmaps:
            return QPixmap()
        return self._src_pixmaps[self._current_index % len(self._src_pixmaps)]

    def _rebuild_pixmap(self) -> None:
        """依目前 Width/Height/Tint/Photo clip/目前索引重新產生繪製用快取 pixmap；無圖片時保持空白。
        先以裁切式縮放（KeepAspectRatioByExpanding + 置中裁切）避免內容變形，再套用 Tint，
        最後依 Photo clip 裁切為 None/Circle/Corner 1/Corner 2 形狀。
        """
        w = max(1, int(round(self._width)))
        h = max(1, int(round(self._height)))
        cropped = _scale_crop_fill(self._current_pixmap(), w, h)
        tinted = _scale_and_tint(cropped, w, h, self._tint)
        self._render_pixmap = _clip_pixmap(tinted, w, h, self._photo_clip)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜(繞中心) → 對齊(錨點移至原點) → 旋轉 → 平移(X,Y)。
        與 ImageLayer._apply_transform 邏輯一致。
        """
        w, h = self._width, self._height
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        ax, ay = fx * w, fy * h

        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.translate(ax + w / 2, ay + h / 2)
        t.shear(sh_x, sh_y)
        t.translate(-w / 2, -h / 2)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None) -> None:
        if self._render_pixmap.isNull():
            return
        painter.drawPixmap(QRectF(0, 0, self._width, self._height), self._render_pixmap,
                           QRectF(self._render_pixmap.rect()))

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def tick(self) -> None:
        """每秒累計一次；達到 Photo duration 秒數即切換至下一張圖片（循環）。"""
        if len(self._src_pixmaps) <= 1:
            return
        self._elapsed_secs += 1.0
        if self._elapsed_secs >= self._photo_duration:
            self._elapsed_secs = 0.0
            self._current_index = (self._current_index + 1) % len(self._src_pixmaps)
            self._rebuild_pixmap()
            self.update()

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Width":
            self.prepareGeometryChange()
            self._width = max(1.0, to_float(value, self._width))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Height":
            self.prepareGeometryChange()
            self._height = max(1.0, to_float(value, self._height))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Tint":
            self._tint = value
            self._rebuild_pixmap()
            self.update()
        elif field == "Photo":
            new_str = str(value or "")
            if new_str == self._photo_str:
                return
            self._photo_str = new_str
            self._load_pixmaps()
            self._rebuild_pixmap()
            self.update()
        elif field == "Photo duration":
            self._photo_duration = max(1.0, to_float(value, self._photo_duration))
        elif field == "Photo clip":
            self._photo_clip = str(value or "None")
            self._rebuild_pixmap()
            self.update()
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_w = float(base_vals.get("Width", self._width)) * sx
        new_h = float(base_vals.get("Height", self._height)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Width":  int(round(max(1.0, min(2048.0, new_w)))),
            "Height": int(round(max(1.0, min(2048.0, new_h)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result

    # ── 單選拖曳縮放 hook（Width/Height 像素語意）──────────────────────────────

    def scale_geom(self) -> tuple[float, float]:
        return self._width, self._height

    def get_scale_pct(self) -> tuple[float, float]:
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = sx_pct
        csy = sy_pct
        if geom_w > 0.5:
            csx = max(1.0, min(2048.0, geom_w * sx_pct / 100.0)) / geom_w * 100.0
        if geom_h > 0.5:
            csy = max(1.0, min(2048.0, geom_h * sy_pct / 100.0)) / geom_h * 100.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_w = int(round(max(1.0, min(2048.0, geom_w * new_sx_pct / 100.0))))
        new_h = int(round(max(1.0, min(2048.0, geom_h * new_sy_pct / 100.0))))
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Width", new_w)
        self.apply_attr("Height", new_h)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Width": new_w, "Height": new_h, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Width": self._width, "Height": self._height,
        }


# ── ImageCondLayer（Sprite／條件圖片，如 Battery、Weather、Moon phase）───────────

class ImageCondLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的條件圖片（sprite）item。
    Custom image 為一張依 Image grid（如 "3x3"，cols x rows）切分的雪碧圖，
    Image selection 為 Lua 表達式，求值後取整數作為 1-based 格號
    （左上為 1，由左至右、由上至下遞增），裁出對應格再依 Width/Height 縮放顯示。
    其餘欄位語意與 ImageLayer 相同。
    """

    _ANCHOR = TextLayer._ANCHOR

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x         = to_float(values.get("X", 0))
        self._y         = to_float(values.get("Y", 0))
        self._width     = max(1.0, to_float(values.get("Width", 100), 100.0))
        self._height    = max(1.0, to_float(values.get("Height", 100), 100.0))
        self._alignment = str(values.get("Alignment", "Center"))
        self._rotation  = to_float(values.get("Rotation", 0))
        self._skew_x    = to_float(values.get("Skew X", 0))
        self._skew_y    = to_float(values.get("Skew Y", 0))
        self._tint      = values.get("Tint", "")
        self._image_path = str(values.get("Custom image", "") or "")
        self._image_grid = str(values.get("Image grid", "3x3") or "3x3")
        self._selection  = self._eval_selection(values.get("Image selection", 1))
        self._display   = str(values.get("Display", "Always"))

        self._src_pixmap: QPixmap = QPixmap()
        self._cell_pixmap: QPixmap = QPixmap()
        self._render_pixmap: QPixmap = QPixmap()
        self._load_pixmap()
        self._rebuild_cell()
        self._rebuild_pixmap()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _eval_selection(value) -> int:
        return int(round(to_float(value, 1.0)))

    @staticmethod
    def _parse_grid(grid: str) -> tuple[int, int]:
        """解析 "WxH" 字串為 (cols, rows)；格式錯誤時回退 (3, 3)。"""
        try:
            cols_s, rows_s = str(grid).lower().split("x")
            cols, rows = int(cols_s), int(rows_s)
            if cols > 0 and rows > 0:
                return cols, rows
        except (ValueError, TypeError):
            pass
        return 3, 3

    def _load_pixmap(self) -> None:
        pm = QPixmap()
        if self._image_path and pm.load(self._image_path):
            self._src_pixmap = pm
        else:
            self._src_pixmap = QPixmap()

    def _rebuild_cell(self) -> None:
        """依 Image grid 與 Image selection 從來源雪碧圖裁出目前格。"""
        if self._src_pixmap.isNull():
            self._cell_pixmap = QPixmap()
            return
        cols, rows = self._parse_grid(self._image_grid)
        total = cols * rows
        idx = max(1, min(total, self._selection)) - 1
        row, col = divmod(idx, cols)
        sw, sh = self._src_pixmap.width(), self._src_pixmap.height()
        x0 = round(col * sw / cols)
        x1 = round((col + 1) * sw / cols)
        y0 = round(row * sh / rows)
        y1 = round((row + 1) * sh / rows)
        self._cell_pixmap = self._src_pixmap.copy(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    def _rebuild_pixmap(self) -> None:
        """依目前 Width/Height/Tint 重新產生繪製用快取 pixmap；無來源圖片時保持空白（完全不畫）。"""
        w = max(1, int(round(self._width)))
        h = max(1, int(round(self._height)))
        self._render_pixmap = _scale_and_tint(self._cell_pixmap, w, h, self._tint)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜(繞中心) → 對齊(錨點移至原點) → 旋轉 → 平移(X,Y)。
        與 ImageLayer._apply_transform 邏輯一致。
        """
        w, h = self._width, self._height
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        ax, ay = fx * w, fy * h

        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.translate(ax + w / 2, ay + h / 2)
        t.shear(sh_x, sh_y)
        t.translate(-w / 2, -h / 2)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None) -> None:
        if self._render_pixmap.isNull():
            return
        painter.drawPixmap(QRectF(0, 0, self._width, self._height), self._render_pixmap,
                           QRectF(self._render_pixmap.rect()))

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Width":
            self.prepareGeometryChange()
            self._width = max(1.0, to_float(value, self._width))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Height":
            self.prepareGeometryChange()
            self._height = max(1.0, to_float(value, self._height))
            self._rebuild_pixmap()
            self._apply_transform()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Tint":
            self._tint = value
            self._rebuild_pixmap()
            self.update()
        elif field == "Custom image":
            self._image_path = str(value or "")
            self._load_pixmap()
            self._rebuild_cell()
            self._rebuild_pixmap()
            self.update()
        elif field == "Image grid":
            self._image_grid = str(value or "3x3")
            self._rebuild_cell()
            self._rebuild_pixmap()
            self.update()
        elif field == "Image selection":
            self._selection = self._eval_selection(value)
            self._rebuild_cell()
            self._rebuild_pixmap()
            self.update()
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_w = float(base_vals.get("Width", self._width)) * sx
        new_h = float(base_vals.get("Height", self._height)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Width":  int(round(max(1.0, min(2048.0, new_w)))),
            "Height": int(round(max(1.0, min(2048.0, new_h)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result

    # ── 單選拖曳縮放 hook（Width/Height 像素語意）──────────────────────────────

    def scale_geom(self) -> tuple[float, float]:
        return self._width, self._height

    def get_scale_pct(self) -> tuple[float, float]:
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = sx_pct
        csy = sy_pct
        if geom_w > 0.5:
            csx = max(1.0, min(2048.0, geom_w * sx_pct / 100.0)) / geom_w * 100.0
        if geom_h > 0.5:
            csy = max(1.0, min(2048.0, geom_h * sy_pct / 100.0)) / geom_h * 100.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_w = int(round(max(1.0, min(2048.0, geom_w * new_sx_pct / 100.0))))
        new_h = int(round(max(1.0, min(2048.0, geom_h * new_sy_pct / 100.0))))
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Width", new_w)
        self.apply_attr("Height", new_h)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Width": new_w, "Height": new_h, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Width": self._width, "Height": self._height,
        }


class ShapeLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的形狀 item。
    X/Y 為錨點座標；錨點位置由 Alignment 欄位決定（與 TextLayer/ImageLayer 共用同一套 _ANCHOR）。
    Width/Height 直接是顯示尺寸；依 Shape 欄位以 QPainterPath 繪出對應幾何形狀並填滿 Color。
    """

    _ANCHOR = TextLayer._ANCHOR

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x         = to_float(values.get("X", 0))
        self._y         = to_float(values.get("Y", 0))
        self._width     = max(1.0, to_float(values.get("Width", 100), 100.0))
        self._height    = max(1.0, to_float(values.get("Height", 100), 100.0))
        self._alignment = str(values.get("Alignment", "Center"))
        self._rotation  = to_float(values.get("Rotation", 0))
        self._skew_x    = to_float(values.get("Skew X", 0))
        self._skew_y    = to_float(values.get("Skew Y", 0))
        self._shape     = str(values.get("Shape", "Square"))
        self._color     = values.get("Color", "ffffff")
        self._display   = str(values.get("Display", "Always"))

        self._path = QPainterPath()
        self._brush_color = QColor(Qt.GlobalColor.white)
        self._rebuild_path()
        self._refresh_brush_color()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _regular_polygon_path(w: float, h: float, sides: int) -> QPainterPath:
        """繪出內接於 (0,0,w,h) bounding box 的正多邊形，頂點朝上。"""
        cx, cy = w / 2.0, h / 2.0
        rx, ry = w / 2.0, h / 2.0
        path = QPainterPath()
        for i in range(sides):
            angle = math.radians(-90.0 + i * 360.0 / sides)
            x, y = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        return path

    @staticmethod
    def _star_path(w: float, h: float, points: int = 5, inner_ratio: float = 0.5) -> QPainterPath:
        """繪出內接於 (0,0,w,h) bounding box 的正星形，頂點朝上。"""
        cx, cy = w / 2.0, h / 2.0
        outer_rx, outer_ry = w / 2.0, h / 2.0
        inner_rx, inner_ry = outer_rx * inner_ratio, outer_ry * inner_ratio
        step = 360.0 / (points * 2)
        path = QPainterPath()
        for i in range(points * 2):
            angle = math.radians(-90.0 + i * step)
            rx, ry = (outer_rx, outer_ry) if i % 2 == 0 else (inner_rx, inner_ry)
            x, y = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        return path

    @staticmethod
    def _heart_path(w: float, h: float) -> QPainterPath:
        """雙圓弧上半（左右葉）＋二次貝茲曲線收尾至下方尖點，繪出完全內接於 (0,0,w,h) 的平滑心形。"""
        rx, ry = w / 4.0, h / 4.0
        cy = ry
        mid_y = (cy + h) / 2.0
        path = QPainterPath()
        path.moveTo(0.0, cy)
        path.arcTo(QRectF(0.0, 0.0, 2 * rx, 2 * ry), 180.0, -180.0)
        path.arcTo(QRectF(2 * rx, 0.0, 2 * rx, 2 * ry), 180.0, -180.0)
        path.quadTo(w, mid_y, w / 2.0, h)
        path.quadTo(0.0, mid_y, 0.0, cy)
        path.closeSubpath()
        return path

    def _rebuild_path(self) -> None:
        w, h = self._width, self._height
        shape = self._shape
        if shape == "Circle":
            path = QPainterPath()
            path.addEllipse(0, 0, w, h)
        elif shape == "Triangle":
            path = self._regular_polygon_path(w, h, 3)
        elif shape == "Pentagon":
            path = self._regular_polygon_path(w, h, 5)
        elif shape == "Hexagon":
            path = self._regular_polygon_path(w, h, 6)
        elif shape == "Star":
            path = self._star_path(w, h)
        elif shape == "Heart":
            path = self._heart_path(w, h)
        else:  # "Square" 及未知形狀 fallback
            path = QPainterPath()
            path.addRect(0, 0, w, h)
        self._path = path

    def _refresh_brush_color(self) -> None:
        self._brush_color = _parse_hex_color(self._color)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜(繞中心) → 對齊(錨點移至原點) → 旋轉 → 平移(X,Y)。
        與 ImageLayer._apply_transform 邏輯一致。
        """
        w, h = self._width, self._height
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        ax, ay = fx * w, fy * h

        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.translate(ax + w / 2, ay + h / 2)
        t.shear(sh_x, sh_y)
        t.translate(-w / 2, -h / 2)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._brush_color))
        painter.drawPath(self._path)

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Width":
            self.prepareGeometryChange()
            self._width = max(1.0, to_float(value, self._width))
            self._rebuild_path()
            self._apply_transform()
        elif field == "Height":
            self.prepareGeometryChange()
            self._height = max(1.0, to_float(value, self._height))
            self._rebuild_path()
            self._apply_transform()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Shape":
            self._shape = str(value)
            self._rebuild_path()
            self.update()
        elif field == "Color":
            self._color = value
            self._refresh_brush_color()
            self.update()
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_w = float(base_vals.get("Width", self._width)) * sx
        new_h = float(base_vals.get("Height", self._height)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Width":  int(round(max(1.0, min(2048.0, new_w)))),
            "Height": int(round(max(1.0, min(2048.0, new_h)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result

    # ── 單選拖曳縮放 hook（Width/Height 像素語意）──────────────────────────────

    def scale_geom(self) -> tuple[float, float]:
        return self._width, self._height

    def get_scale_pct(self) -> tuple[float, float]:
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = sx_pct
        csy = sy_pct
        if geom_w > 0.5:
            csx = max(1.0, min(2048.0, geom_w * sx_pct / 100.0)) / geom_w * 100.0
        if geom_h > 0.5:
            csy = max(1.0, min(2048.0, geom_h * sy_pct / 100.0)) / geom_h * 100.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_w = int(round(max(1.0, min(2048.0, geom_w * new_sx_pct / 100.0))))
        new_h = int(round(max(1.0, min(2048.0, geom_h * new_sy_pct / 100.0))))
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Width", new_w)
        self.apply_attr("Height", new_h)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Width": new_w, "Height": new_h, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Width": self._width, "Height": self._height,
        }


# ── MarkerLayer（環形標記）─────────────────────────────────────────────────────

class MarkerLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的環形標記 item。
    X/Y 為圓心；沿圓周等距放置 Marker count 個標記（0°＝正上方，順時針遞增），
    每個標記依所在角度徑向旋轉，使外緣（Marker height 方向）朝外，形成類似錶盤刻度的排列
    （角度／旋轉慣例與 TextRingLayer 一致：rot_deg = angle_deg 使標記隨位置角度同步旋轉）。
    Squarify 依超橢圓公式將圓形位置往方形擠壓，與 TextRingLayer._squarify_radius 邏輯一致。
    Shape（Square/Circle/Triangle）與 ShapeLayer 共用同一套視覺定義（Triangle 沿用
    ShapeLayer._regular_polygon_path，僅平移為以原點置中、頂點朝上）。
    """

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x            = to_float(values.get("X", 0))
        self._y            = to_float(values.get("Y", 0))
        self._radius       = max(1.0, to_float(values.get("Radius", 256), 256.0))
        self._rotation     = to_float(values.get("Rotation", 0))
        self._skew_x       = to_float(values.get("Skew X", 0))
        self._skew_y       = to_float(values.get("Skew Y", 0))
        self._anim_scale_x = to_float(values.get("Anim scale X", 100), 100.0)
        self._anim_scale_y = to_float(values.get("Anim scale Y", 100), 100.0)
        self._marker_w      = max(1.0, to_float(values.get("Marker width", 10), 10.0))
        self._marker_h      = max(1.0, to_float(values.get("Marker height", 35), 35.0))
        self._count         = max(1, int(round(to_float(values.get("Marker count", 12), 12.0))))
        self._shape          = str(values.get("Shape", "Square"))
        self._squarify       = max(0.0, min(100.0, to_float(values.get("Squarify", 0), 0.0)))
        self._color          = values.get("Color", "ffffff")
        self._display        = str(values.get("Display", "Always"))

        self._brush_color = QColor(Qt.GlobalColor.white)
        self._marker_path = QPainterPath()
        self._items: list[tuple[float, float, float]] = []  # (cx, cy, rot_deg)
        self._bounding_rect = QRectF()

        self._rebuild_marker_path()
        self._refresh_brush_color()
        self._rebuild_layout()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _marker_shape_path(shape: str, w: float, h: float) -> QPainterPath:
        """建立以原點為中心、朝上（-Y）為外緣方向的標記形狀路徑，與 ShapeLayer 共用相同 Shape 語意。"""
        if shape == "Circle":
            path = QPainterPath()
            path.addEllipse(-w / 2.0, -h / 2.0, w, h)
            return path
        if shape == "Triangle":
            # ShapeLayer._regular_polygon_path 頂點朝上（外側）；標記三角形尖端須朝內（圓心方向），
            # 故沿水平軸鏡射（三角形左右對稱，僅翻轉 Y 即等效於尖端上下對調）。
            path = ShapeLayer._regular_polygon_path(w, h, 3).translated(-w / 2.0, -h / 2.0)
            return QTransform().scale(1, -1).map(path)
        path = QPainterPath()  # "Square" 及未知形狀 fallback
        path.addRect(-w / 2.0, -h / 2.0, w, h)
        return path

    def _rebuild_marker_path(self) -> None:
        self._marker_path = self._marker_shape_path(self._shape, self._marker_w, self._marker_h)

    def _refresh_brush_color(self) -> None:
        self._brush_color = _parse_hex_color(self._color)

    def _squarify_radius(self, angle_deg: float) -> float:
        """依超橢圓（Lamé curve）公式將圓形半徑往方形擠壓；與 TextRingLayer._squarify_radius 一致。"""
        t = (self._squarify - 1.0) / 99.0
        n = 2.0 + 10.0 * (t ** 2)
        rad = math.radians(angle_deg)
        c, s = abs(math.cos(rad)), abs(math.sin(rad))
        denom = (c ** n + s ** n) ** (1.0 / n)
        return self._radius / denom if denom > 1e-9 else self._radius

    def _rebuild_layout(self) -> None:
        """重新計算每個標記的位置與徑向旋轉角，並算出精確 boundingRect
        （原點＝圓心，未套用 Rotation/Skew/Anim scale）。
        """
        count = self._count
        step = 360.0 / count
        local_bounds = self._marker_path.boundingRect()

        items: list[tuple[float, float, float]] = []
        bounds = QRectF()
        for i in range(count):
            angle = i * step
            r = self._squarify_radius(angle)
            rad = math.radians(angle)
            cx = r * math.sin(rad)
            cy = -r * math.cos(rad)
            items.append((cx, cy, angle))

            t = QTransform()
            t.translate(cx, cy)
            t.rotate(angle)
            bounds = bounds.united(t.mapRect(local_bounds))

        self._items = items
        self._bounding_rect = bounds

    def _apply_transform(self) -> None:
        """縮放/旋轉/傾斜一律以圓心（局部原點）為軸，最後平移至 (X,Y)。
        與 TextRingLayer._apply_transform 邏輯一致。
        """
        sx = self._anim_scale_x / 100.0
        sy = self._anim_scale_y / 100.0
        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.scale(sx, sy)
        t.shear(sh_x, sh_y)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(self, painter, option, widget=None) -> None:
        if not self._items:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._brush_color))
        for cx, cy, rot_deg in self._items:
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            painter.drawPath(self._marker_path)
            painter.restore()

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Radius":
            self.prepareGeometryChange()
            self._radius = max(1.0, to_float(value, self._radius))
            self._rebuild_layout()
        elif field == "Marker count":
            self.prepareGeometryChange()
            self._count = max(1, int(round(to_float(value, self._count))))
            self._rebuild_layout()
        elif field == "Squarify":
            self.prepareGeometryChange()
            self._squarify = max(0.0, min(100.0, to_float(value, self._squarify)))
            self._rebuild_layout()
        elif field == "Marker width":
            self.prepareGeometryChange()
            self._marker_w = max(1.0, to_float(value, self._marker_w))
            self._rebuild_marker_path()
            self._rebuild_layout()
        elif field == "Marker height":
            self.prepareGeometryChange()
            self._marker_h = max(1.0, to_float(value, self._marker_h))
            self._rebuild_marker_path()
            self._rebuild_layout()
        elif field == "Shape":
            self.prepareGeometryChange()
            self._shape = str(value)
            self._rebuild_marker_path()
            self._rebuild_layout()
        elif field == "Color":
            self._color = value
            self._refresh_brush_color()
            self.update()
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
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
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

    # ── 單選拖曳縮放 hook（Anim scale 百分比語意）───────────────────────────────

    def get_scale_pct(self) -> tuple[float, float]:
        return self._anim_scale_x, self._anim_scale_y

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = max(-2048.0, min(2048.0, sx_pct))
        csy = max(-2048.0, min(2048.0, sy_pct))
        if csx == 0:
            csx = 1.0 if sx_pct >= 0 else -1.0
        if csy == 0:
            csy = 1.0 if sy_pct >= 0 else -1.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_sx = int(round(max(-2048.0, min(2048.0, new_sx_pct))))
        new_sy = int(round(max(-2048.0, min(2048.0, new_sy_pct))))
        if new_sx == 0:
            new_sx = 1 if new_sx_pct >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if new_sy_pct >= 0 else -1
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Anim scale X", new_sx)
        self.apply_attr("Anim scale Y", new_sy)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Anim scale X": new_sx, "Anim scale Y": new_sy, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Anim scale X": self._anim_scale_x, "Anim scale Y": self._anim_scale_y,
        }


# ── TachymeterLayer（測速計）───────────────────────────────────────────────────

class TachymeterLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的測速計 item。
    X/Y 為圓心；Speeds 為逗號分隔的速度值列表，依真實測速計非線性公式
    angle_deg = 21600 / speed 換算每個速度對應的角度（0°＝正上方，順時針遞增；
    速度越高換算角度越小，越靠近頂部）。無法解析或 ≤0 的項目略過。
    每個速度位置繪出一個數字標籤（Text rotation 決定自轉方式，與 TextRingLayer 一致）
    與一個 Major marker 刻度；相鄰兩個速度之間的角度區間再均勻插入 4 個 Minor marker
    （角度最小與最大的兩個速度之間的缺口不補刻度，改放 Text 標題文字，沿圓弧彎曲排列，
    置中於缺口——與真實計時碼錶測速計錶圈上 "TACHYMETER" 字樣位置一致）。
    Major/Minor markers 的 None/Tiny/Small/Medium/Large/XLarge 為徑向矩形刻度的大小分級
    （依 _SIZE_MULT 縮放 Marker width/height）；Circle/Triangle 則改以 Med大小畫出對應形狀
    （沿用 MarkerLayer._marker_shape_path，Triangle 頂點徑向朝外）。
    Squarify 公式與 TextRingLayer._squarify_radius 一致。
    """

    _SIZE_MULT: dict[str, float] = {
        "Tiny": 0.4, "Small": 0.6, "Medium": 0.8, "Large": 1.0, "XLarge": 1.3,
    }

    _TEXT_MARKER_GAP: float = 10.0  # 數字標籤下緣與刻度外緣之間固定保留的像素間距

    _H_GROUP = CurvedTextLayer._H_GROUP

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x            = to_float(values.get("X", 0))
        self._y            = to_float(values.get("Y", 0))
        self._radius       = max(1.0, to_float(values.get("Radius", 230), 230.0))
        self._rotation     = to_float(values.get("Rotation", 0))
        self._skew_x       = to_float(values.get("Skew X", 0))
        self._skew_y       = to_float(values.get("Skew Y", 0))
        self._anim_scale_x = to_float(values.get("Anim scale X", 100), 100.0)
        self._anim_scale_y = to_float(values.get("Anim scale Y", 100), 100.0)
        self._text          = to_str(str(values.get("Text", "")))
        self._font_name      = str(values.get("Font", ""))
        self._font_size      = int(to_float(values.get("Text size", 25), 25.0))
        self._color_day       = values.get("Color", "ffffff")
        self._color_dim       = values.get("Color dim", "ffffff")
        self._alignment       = str(values.get("Alignment", "Center"))
        self._marker_w         = max(1.0, to_float(values.get("Marker width", 10), 10.0))
        self._marker_h         = max(1.0, to_float(values.get("Marker height", 10), 10.0))
        self._major_markers    = str(values.get("Major markers", "Medium"))
        self._minor_markers    = str(values.get("Minor markers", "Medium"))
        self._speeds_str        = str(values.get("Speeds", "") or "")
        self._custom_speeds      = str(values.get("Custom speeds", "") or "")
        self._text_rotation      = str(values.get("Text rotation", "Rotate Upright"))
        self._squarify           = max(1.0, min(100.0, to_float(values.get("Squarify", 1), 1.0)))
        self._display            = str(values.get("Display", "Always"))

        self._font = QFont()
        self._brush_color = QColor(Qt.GlobalColor.white)
        self._number_items: list[tuple[str, float, float, float, QRectF]] = []
        self._tick_items: list[tuple[QPainterPath, float, float, float]] = []
        self._chars: list[tuple[str, float, float, float, float, float, float]] = []
        self._bounding_rect = QRectF()

        self._apply_font()
        self._refresh_color()
        self._rebuild_layout()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    def _apply_font(self) -> None:
        # 延遲匯入避免 components → special_ui 的循環依賴
        from special_ui import FontManager
        family = FontManager().get_font_family(self._font_name) or self._font_name
        font = QFont(family)
        font.setPixelSize(self._font_size)
        self._font = font

    def _apply_color(self, hex_val) -> None:
        self._brush_color = _parse_hex_color(hex_val)
        self.update()

    def _refresh_color(self) -> None:
        """依 manager.is_dark_mode 決定顯示 Color（day）或 Color dim（night）。"""
        manager = self._get_manager()
        is_night = bool(manager.is_dark_mode) if manager is not None else False
        self._apply_color(self._color_dim if is_night else self._color_day)

    def _parse_speeds(self) -> list[tuple[float, float]]:
        """解析 Speeds（逗號分隔字串），回傳依角度升冪排序的 (speed, angle_deg) list；
        Speeds 選到 "Custom" 時改讀 Custom speeds 欄位的值（與 Numbers/textRingLayer
        的 Ring type="Custom (x to y)" 改讀 Custom start/end 邏輯一致）。
        無法解析成正數的片段直接略過。
        """
        speeds_str = self._custom_speeds if self._speeds_str == "Custom" else self._speeds_str
        result: list[tuple[float, float]] = []
        for tok in speeds_str.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                speed = float(tok)
            except ValueError:
                continue
            if speed <= 0:
                continue
            result.append((speed, 21600.0 / speed))
        result.sort(key=lambda p: p[1])
        return result

    def _marker_path_for(self, preset: str, base_w: float, base_h: float) -> "QPainterPath | None":
        """依 Major/Minor markers 選項建立刻度形狀路徑；None 回傳 None（不繪製）。
        外緣（朝外/-Y 側）固定距離數字標籤下緣 _TEXT_MARKER_GAP px，Marker height 變化時
        只向內（+Y，往圓心方向）延伸，避免刻度變長時往外蓋住數字標籤。
        """
        if not preset or preset == "None":
            return None
        if preset in ("Circle", "Triangle"):
            mult = self._SIZE_MULT["Medium"]
            w, h = base_w * mult, base_h * mult
            path = MarkerLayer._marker_shape_path(preset, w, h)
        else:
            mult = self._SIZE_MULT.get(preset, 1.0)
            w, h = base_w * mult, base_h * mult
            path = MarkerLayer._marker_shape_path("Square", w, h)
        descent = QFontMetricsF(self._font).descent()
        return path.translated(0.0, h / 2.0 + descent + self._TEXT_MARKER_GAP)

    def _squarify_radius(self, angle_deg: float) -> float:
        """依超橢圓（Lamé curve）公式將圓形半徑往方形擠壓；與 TextRingLayer._squarify_radius 一致。"""
        t = (self._squarify - 1.0) / 99.0
        n = 2.0 + 10.0 * (t ** 2)
        rad = math.radians(angle_deg)
        c, s = abs(math.cos(rad)), abs(math.sin(rad))
        denom = (c ** n + s ** n) ** (1.0 / n)
        return self._radius / denom if denom > 1e-9 else self._radius

    def _item_rotation(self, angle_deg: float) -> float:
        """數字標籤自轉方式；與 TextRingLayer._item_rotation 邏輯一致。"""
        style = self._text_rotation
        if style == "Rotate":
            return angle_deg
        if style == "Rotate Inverse":
            return angle_deg + 180.0
        if style == "Rotate Upright":
            a = angle_deg % 360.0
            return angle_deg if (a <= 90.0 or a >= 270.0) else angle_deg + 180.0
        return 0.0  # "Upright"

    def _layout_title(self, gap_start: float, gap_end: float) -> QRectF:
        """將 Text 標題文字沿圓弧置於 [gap_start, gap_end] 缺口內（依 Alignment 左/中/右對齊），
        回傳其 boundingRect（未套用 Rotation/Skew/Anim scale）。邏輯與 CurvedTextLayer
        Direction="Up" 時一致，只是排列範圍限縮在缺口內而非整個圓周。
        """
        fm = QFontMetricsF(self._font)
        text = self._text
        widths = [fm.horizontalAdvance(ch) for ch in text]
        radius = self._radius
        total_angle = math.degrees(sum(widths) / radius) if radius > 0 else 0.0

        span = gap_end - gap_start
        h_group = self._H_GROUP.get(self._alignment, "center")
        if h_group == "left":
            start_angle = gap_start
        elif h_group == "right":
            start_angle = gap_end - total_angle
        else:
            start_angle = gap_start + (span - total_angle) / 2.0

        ascent, descent = fm.ascent(), fm.descent()
        chars: list[tuple[str, float, float, float, float, float, float]] = []
        bounds = QRectF()
        running = start_angle
        for ch, w in zip(text, widths):
            span_deg = math.degrees(w / radius) if radius > 0 else 0.0
            center_angle = running + span_deg / 2.0
            running += span_deg

            rad = math.radians(center_angle)
            cx, cy = radius * math.sin(rad), -radius * math.cos(rad)
            chars.append((ch, cx, cy, center_angle, w, ascent, descent))

            t = QTransform()
            t.translate(cx, cy)
            t.rotate(center_angle)
            local_rect = QRectF(-w / 2.0, -ascent, w, ascent + descent)
            bounds = bounds.united(t.mapRect(local_rect))

        self._chars = chars
        return bounds

    def _rebuild_layout(self) -> None:
        """重新計算數字標籤、Major/Minor markers 刻度與標題文字的位置，並算出精確 boundingRect
        （原點＝圓心，未套用 Rotation/Skew/Anim scale）。
        """
        speeds = self._parse_speeds()
        fm = QFontMetricsF(self._font)
        ascent, descent = fm.ascent(), fm.descent()

        major_path = self._marker_path_for(self._major_markers, self._marker_w, self._marker_h)
        minor_path = self._marker_path_for(self._minor_markers, self._marker_w, self._marker_h)

        number_items: list[tuple[str, float, float, float, QRectF]] = []
        tick_items: list[tuple[QPainterPath, float, float, float]] = []
        bounds = QRectF()

        def _place_tick(path: "QPainterPath | None", angle: float) -> None:
            nonlocal bounds
            if path is None:
                return
            r = self._squarify_radius(angle)
            rad = math.radians(angle)
            cx, cy = r * math.sin(rad), -r * math.cos(rad)
            tick_items.append((path, cx, cy, angle))
            t = QTransform()
            t.translate(cx, cy)
            t.rotate(angle)
            bounds = bounds.united(t.mapRect(path.boundingRect()))

        h = ascent + descent
        for speed, angle in speeds:
            text = str(int(speed)) if speed == int(speed) else str(speed)
            r = self._squarify_radius(angle)
            rad = math.radians(angle)
            cx, cy = r * math.sin(rad), -r * math.cos(rad)
            rot_deg = self._item_rotation(angle)
            w = fm.horizontalAdvance(text)
            # 矩形須以原點（環上位置）垂直置中，而非依 ascent/descent 偏移；
            # 否則 Rotate Upright 下半部因額外 +180° 翻轉，文字中心會偏移到 Rotate 模式的對稱位置，造成錯位。
            local_rect = QRectF(-w / 2.0, -h / 2.0, w, h)
            number_items.append((text, cx, cy, rot_deg, local_rect))

            t = QTransform()
            t.translate(cx, cy)
            t.rotate(rot_deg)
            bounds = bounds.united(t.mapRect(local_rect))

            _place_tick(major_path, angle)

        for (_s1, a1), (_s2, a2) in zip(speeds, speeds[1:]):
            step = (a2 - a1) / 5.0
            for k in range(1, 5):
                _place_tick(minor_path, a1 + k * step)

        if len(speeds) >= 2:
            gap_start = speeds[-1][1]
            gap_end = speeds[0][1] + 360.0
        else:
            gap_start, gap_end = 0.0, 360.0
        bounds = bounds.united(self._layout_title(gap_start, gap_end))

        self._number_items = number_items
        self._tick_items = tick_items
        self._bounding_rect = bounds

    def _apply_transform(self) -> None:
        """縮放/旋轉/傾斜一律以圓心（局部原點）為軸，最後平移至 (X,Y)。
        與 TextRingLayer._apply_transform 邏輯一致。
        """
        sx = self._anim_scale_x / 100.0
        sy = self._anim_scale_y / 100.0
        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.scale(sx, sy)
        t.shear(sh_x, sh_y)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return self._bounding_rect

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._brush_color))
        for path, cx, cy, rot_deg in self._tick_items:
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            painter.drawPath(path)
            painter.restore()

        painter.setFont(self._font)
        painter.setPen(QPen(self._brush_color))
        for text, cx, cy, rot_deg, local_rect in self._number_items:
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            painter.drawText(local_rect, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
        for ch, cx, cy, rot_deg, w, chr_ascent, chr_descent in self._chars:
            if ch.isspace():
                continue
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rot_deg)
            rect = QRectF(-w / 2.0, -chr_ascent, w, chr_ascent + chr_descent)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)
            painter.restore()

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    _LAYOUT_FIELDS = frozenset({
        "Marker width", "Marker height", "Major markers", "Minor markers",
        "Speeds", "Custom speeds", "Text rotation", "Squarify", "Alignment",
    })

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Radius":
            self.prepareGeometryChange()
            self._radius = max(1.0, to_float(value, self._radius))
            self._rebuild_layout()
        elif field == "Text":
            self.prepareGeometryChange()
            self._text = to_str(str(value))
            self._rebuild_layout()
        elif field in self._LAYOUT_FIELDS:
            self.prepareGeometryChange()
            if field == "Marker width":
                self._marker_w = max(1.0, to_float(value, self._marker_w))
            elif field == "Marker height":
                self._marker_h = max(1.0, to_float(value, self._marker_h))
            elif field == "Major markers":
                self._major_markers = str(value)
            elif field == "Minor markers":
                self._minor_markers = str(value)
            elif field == "Speeds":
                self._speeds_str = str(value or "")
            elif field == "Custom speeds":
                self._custom_speeds = str(value or "")
            elif field == "Text rotation":
                self._text_rotation = str(value)
            elif field == "Squarify":
                self._squarify = max(1.0, min(100.0, to_float(value, self._squarify)))
            elif field == "Alignment":
                self._alignment = str(value)
            self._rebuild_layout()
        elif field == "Font":
            self._font_name = str(value)
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Text size":
            self._font_size = int(to_float(value, self._font_size))
            self._apply_font()
            self.prepareGeometryChange()
            self._rebuild_layout()
        elif field == "Color":
            self._color_day = value
            self._refresh_color()
        elif field == "Color dim":
            self._color_dim = value
            self._refresh_color()
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
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
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

    # ── 單選拖曳縮放 hook（Anim scale 百分比語意）───────────────────────────────

    def get_scale_pct(self) -> tuple[float, float]:
        return self._anim_scale_x, self._anim_scale_y

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = max(-2048.0, min(2048.0, sx_pct))
        csy = max(-2048.0, min(2048.0, sy_pct))
        if csx == 0:
            csx = 1.0 if sx_pct >= 0 else -1.0
        if csy == 0:
            csy = 1.0 if sy_pct >= 0 else -1.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_sx = int(round(max(-2048.0, min(2048.0, new_sx_pct))))
        new_sy = int(round(max(-2048.0, min(2048.0, new_sy_pct))))
        if new_sx == 0:
            new_sx = 1 if new_sx_pct >= 0 else -1
        if new_sy == 0:
            new_sy = 1 if new_sy_pct >= 0 else -1
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Anim scale X", new_sx)
        self.apply_attr("Anim scale Y", new_sy)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Anim scale X": new_sx, "Anim scale Y": new_sy, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Anim scale X": self._anim_scale_x, "Anim scale Y": self._anim_scale_y,
        }


# ── RoundedRectangleLayer（圓角矩形）───────────────────────────────────────────

# Corner type（1~15）：數值對應「非圓角（直角）」的角落組合。
# rt=右上(TR) lt=左上(TL) rb=右下(BR) lb=左下(BL)；! 前綴代表「除了該角以外都是直角」。
# 1=全部圓角 2=全部直角 3=rt 4=lt 5=rb 6=lb 7=rt+lt 8=rb+lb 9=rt+rb 10=lt+lb
# 11=lt+rb 12=rt+lb 13=!lb(即 lt+tr+rb 直角) 14=!rb 15=!lt
_CORNER_TYPE_SQUARE: dict[int, frozenset[str]] = {
    1:  frozenset(),
    2:  frozenset({"TR"}),
    3:  frozenset({"TL"}),
    4:  frozenset({"BR"}),
    5:  frozenset({"BL"}),
    6:  frozenset({"TR", "TL"}),
    7:  frozenset({"BR", "BL"}),
    8:  frozenset({"TR", "BR"}),
    9:  frozenset({"TL", "BL"}),
    10: frozenset({"TL", "BR"}),
    11: frozenset({"TR", "BL"}),
    12: frozenset({"TL", "TR", "BR"}),
    13: frozenset({"TL", "TR", "BL"}),
    14: frozenset({"TR", "BR", "BL"}),
    15: frozenset({"TL", "BR", "BL"}),
}


class RoundedRectangleLayer(QGraphicsItem, LayerMixin):
    """
    繼承 LayerMixin 的圓角矩形 item。
    X/Y 為錨點座標；錨點位置由 Alignment 欄位決定（與 ShapeLayer 共用同一套 _ANCHOR）。
    Corner radius 為圓角半徑，Corner type 決定哪些角落套用圓角、哪些維持直角
    （見 _CORNER_TYPE_SQUARE）。
    """

    _ANCHOR = TextLayer._ANCHOR

    def __init__(self, values: dict, parent=None):
        super().__init__(parent)
        self.__init_layer__()
        self.can_scale = True

        self._x         = to_float(values.get("X", 0))
        self._y         = to_float(values.get("Y", 0))
        self._width     = max(1.0, to_float(values.get("Width", 100), 100.0))
        self._height    = max(1.0, to_float(values.get("Height", 100), 100.0))
        self._radius    = max(0.0, to_float(values.get("Corner radius", 0)))
        self._corner_type = self._eval_corner_type(values.get("Corner type", 1))
        self._alignment = str(values.get("Alignment", "Center"))
        self._rotation  = to_float(values.get("Rotation", 0))
        self._skew_x    = to_float(values.get("Skew X", 0))
        self._skew_y    = to_float(values.get("Skew Y", 0))
        self._color     = values.get("Color", "ffffff")
        self._display   = str(values.get("Display", "Always"))

        self._path = QPainterPath()
        self._brush_color = QColor(Qt.GlobalColor.white)
        self._rebuild_path()
        self._refresh_brush_color()

        self.setOpacity(max(0.0, min(1.0, to_float(values.get("Opacity", 100), 100.0) / 100.0)))
        self._layer_value = int(to_float(values.get("Layer", 0)))
        self._apply_transform()
        self._refresh_display()

    # ── 內部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _eval_corner_type(value) -> int:
        return int(round(to_float(value, 1.0)))

    def _rebuild_path(self) -> None:
        w, h = self._width, self._height
        r = max(0.0, min(self._radius, w / 2.0, h / 2.0))
        square = _CORNER_TYPE_SQUARE.get(self._corner_type, frozenset())

        path = QPainterPath()
        if r <= 0.0 or square == frozenset({"TL", "TR", "BR", "BL"}):
            path.addRect(0, 0, w, h)
            self._path = path
            return

        if "TL" in square:
            path.moveTo(0, 0)
        else:
            path.moveTo(0, r)
            path.arcTo(QRectF(0, 0, 2 * r, 2 * r), 180, -90)
        if "TR" in square:
            path.lineTo(w, 0)
        else:
            path.lineTo(w - r, 0)
            path.arcTo(QRectF(w - 2 * r, 0, 2 * r, 2 * r), 90, -90)
        if "BR" in square:
            path.lineTo(w, h)
        else:
            path.lineTo(w, h - r)
            path.arcTo(QRectF(w - 2 * r, h - 2 * r, 2 * r, 2 * r), 0, -90)
        if "BL" in square:
            path.lineTo(0, h)
        else:
            path.lineTo(r, h)
            path.arcTo(QRectF(0, h - 2 * r, 2 * r, 2 * r), -90, -90)
        path.closeSubpath()
        self._path = path

    def _refresh_brush_color(self) -> None:
        self._brush_color = _parse_hex_color(self._color)

    def _apply_transform(self) -> None:
        """變換矩陣順序：傾斜(繞中心) → 對齊(錨點移至原點) → 旋轉 → 平移(X,Y)。
        與 ShapeLayer._apply_transform 邏輯一致。
        """
        w, h = self._width, self._height
        fx, fy = self._ANCHOR.get(self._alignment, (-0.5, -0.5))
        ax, ay = fx * w, fy * h

        sh_x = math.tan(math.radians(self._skew_x))
        sh_y = math.tan(math.radians(self._skew_y))

        t = QTransform()
        t.translate(self._x, self._y)
        t.rotate(self._rotation)
        t.translate(ax + w / 2, ay + h / 2)
        t.shear(sh_x, sh_y)
        t.translate(-w / 2, -h / 2)
        self.setTransform(t)

    # ── QGraphicsItem 必要覆寫 ────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._brush_color))
        painter.drawPath(self._path)

    # ── LayerMixin 覆寫 ────────────────────────────────────────────────────────

    def apply_attr(self, field: str, value) -> None:
        if field == "X":
            self._x = to_float(value)
            self._apply_transform()
        elif field == "Y":
            self._y = to_float(value)
            self._apply_transform()
        elif field == "Width":
            self.prepareGeometryChange()
            self._width = max(1.0, to_float(value, self._width))
            self._rebuild_path()
            self._apply_transform()
        elif field == "Height":
            self.prepareGeometryChange()
            self._height = max(1.0, to_float(value, self._height))
            self._rebuild_path()
            self._apply_transform()
        elif field == "Corner radius":
            self._radius = max(0.0, to_float(value, self._radius))
            self._rebuild_path()
            self.update()
        elif field == "Corner type":
            self._corner_type = self._eval_corner_type(value)
            self._rebuild_path()
            self.update()
        elif field == "Alignment":
            self._alignment = str(value)
            self._apply_transform()
        elif field == "Rotation":
            self._rotation = to_float(value)
            self._apply_transform()
        elif field == "Skew X":
            self._skew_x = to_float(value)
            self._apply_transform()
        elif field == "Skew Y":
            self._skew_y = to_float(value)
            self._apply_transform()
        elif field == "Opacity":
            self.setOpacity(max(0.0, min(1.0, to_float(value, 100.0) / 100.0)))
        elif field == "Color":
            self._color = value
            self._refresh_brush_color()
            self.update()
        elif field == "Display":
            self._display = str(value)
            self._refresh_display()
        elif field == "Layer":
            self.set_layer_value(int(to_float(value)))

    def apply_scale_factor(self, sx: float, sy: float, pivot_x: float, pivot_y: float,
                           base_vals: dict) -> dict:
        new_w = float(base_vals.get("Width", self._width)) * sx
        new_h = float(base_vals.get("Height", self._height)) * sy
        new_x = pivot_x + (float(base_vals.get("X", self._x)) - pivot_x) * sx
        new_y = pivot_y + (float(base_vals.get("Y", self._y)) - pivot_y) * sy
        result = {
            "Width":  int(round(max(1.0, min(2048.0, new_w)))),
            "Height": int(round(max(1.0, min(2048.0, new_h)))),
            "X": int(round(max(-1280.0, min(1280.0, new_x)))),
            "Y": int(round(max(-1280.0, min(1280.0, new_y)))),
        }
        for field, val in result.items():
            self.apply_attr(field, val)
        return result

    # ── 單選拖曳縮放 hook（Width/Height 像素語意）──────────────────────────────

    def scale_geom(self) -> tuple[float, float]:
        return self._width, self._height

    def get_scale_pct(self) -> tuple[float, float]:
        return 100.0, 100.0

    def clamp_scale_pct(self, sx_pct: float, sy_pct: float,
                        geom_w: float, geom_h: float) -> tuple[float, float]:
        csx = sx_pct
        csy = sy_pct
        if geom_w > 0.5:
            csx = max(1.0, min(2048.0, geom_w * sx_pct / 100.0)) / geom_w * 100.0
        if geom_h > 0.5:
            csy = max(1.0, min(2048.0, geom_h * sy_pct / 100.0)) / geom_h * 100.0
        return csx, csy

    def apply_drag_scale(self, new_sx_pct: float, new_sy_pct: float,
                         new_x: float, new_y: float,
                         geom_w: float, geom_h: float) -> dict:
        new_w = int(round(max(1.0, min(2048.0, geom_w * new_sx_pct / 100.0))))
        new_h = int(round(max(1.0, min(2048.0, geom_h * new_sy_pct / 100.0))))
        nx = int(round(max(-1280.0, min(1280.0, new_x))))
        ny = int(round(max(-1280.0, min(1280.0, new_y))))
        self.apply_attr("Width", new_w)
        self.apply_attr("Height", new_h)
        self.apply_attr("X", nx)
        self.apply_attr("Y", ny)
        return {"Width": new_w, "Height": new_h, "X": nx, "Y": ny}

    def scale_result_values(self) -> dict:
        return {
            "X": self._x, "Y": self._y, "Rotation": self._rotation,
            "Width": self._width, "Height": self._height,
        }


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
        self._show_handles = getattr(item, "can_scale", False)
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

        self._drag_start_vals   = self._target.scale_result_values()
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
                f: (int(round(v)) if isinstance(v, (int, float)) else v)
                for f, v in self._target.scale_result_values().items()
            }
        changed = [f for f in end_vals
                   if abs(float(end_vals[f]) - float(self._drag_start_vals.get(f, 0))) > 1e-6]

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
        W, H = t.scale_geom()
        if W < 0.5 or H < 0.5:
            return

        scale_x0, scale_y0 = t.get_scale_pct()
        R   = math.radians(t._rotation)
        d_w = W * scale_x0 / 100.0   # 純 scale、不含 skew 的顯示寬（anchor 公式用）
        d_h = H * scale_y0 / 100.0

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
        self._drag_W           = W    # scale_geom() 原始寬（anchor 公式用）
        self._drag_H           = H
        self._drag_scale_x0    = scale_x0   # 拖曳起始的縮放百分比（型別語意由子類決定）
        self._drag_scale_y0    = scale_y0
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
        start_sx = self._drag_scale_x0
        start_sy = self._drag_scale_y0
        raw_sx = start_sx * new_d_w / self._drag_d_w0
        raw_sy = start_sy * new_d_h / self._drag_d_h0

        # 先問子類「實際會套用的夾合後百分比」，錨點才會跟實際套用的尺寸一致
        # （避免拖到欄位範圍上限時，錨點以未夾合的尺寸計算而跟畫面實際大小對不上）
        clamp_sx, clamp_sy = self._target.clamp_scale_pct(
            raw_sx, raw_sy, self._drag_W, self._drag_H)
        act_d_w = self._drag_W * clamp_sx / 100.0
        act_d_h = self._drag_H * clamp_sy / 100.0

        # 根據 pivot 固定，反求新 anchor (X, Y)
        cos_r2, sin_r2 = math.cos(R), math.sin(R)
        px, py = self._drag_px_fac, self._drag_py_fac
        new_x = pivot.x() - (px * act_d_w * cos_r2 - py * act_d_h * sin_r2)
        new_y = pivot.y() - (px * act_d_w * sin_r2 + py * act_d_h * cos_r2)

        result = self._target.apply_drag_scale(
            clamp_sx, clamp_sy, new_x, new_y, self._drag_W, self._drag_H)
        for field, val in result.items():
            self._push_live(field, val)
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
