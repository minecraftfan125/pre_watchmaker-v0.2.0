"""
test_selection_overlay.py — _SelectionOverlay 選取框功能測試

決策記錄：
- manager: PanelWidgetManager（真實環境）
- drag: 直接呼叫 _do_move/_do_scale/_do_rotate + MagicMock event
- scene click: 真實 QGraphicsSceneMouseEvent
- 斷言: 相對比較（方向正確），pivot 固定用 ±2px 容差
- scale 把手: 每類一個代表（BR/ML/TC）
- undo: canUndo()
"""

import math
import pytest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt, QPointF, QPoint

from edit_watch import PanelWidgetManager
from components.layers import _SelectionOverlay, TextLayer


# ── helpers ───────────────────────────────────────────────────────────────────

def _scene(mgr: PanelWidgetManager):
    return mgr._edit_view._canvas._scene

def _overlay(mgr: PanelWidgetManager) -> _SelectionOverlay:
    return _scene(mgr)._overlay

def _layer(mgr: PanelWidgetManager, iid: int = 0) -> TextLayer:
    return mgr._instances[iid]["canvas_item"]

def _click_scene(qtbot, mgr: PanelWidgetManager, scene_pos: QPointF) -> None:
    """在 canvas viewport 點擊，座標為 scene 空間（轉換為 view 像素）。"""
    canvas = mgr._edit_view._canvas
    vp     = canvas.viewport()
    pt = canvas.mapFromScene(scene_pos)   # PyQt6: mapFromScene 回傳 QPoint
    qtbot.mouseClick(vp, Qt.MouseButton.LeftButton, pos=pt)


def _click_viewport_corner(qtbot, mgr: PanelWidgetManager) -> None:
    """點擊 canvas viewport 左上角（(2,2) px），通常是空白處。"""
    vp = mgr._edit_view._canvas.viewport()
    qtbot.mouseClick(vp, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))

def _mock_event(scene_pos: QPointF,
                modifiers=Qt.KeyboardModifier.NoModifier) -> MagicMock:
    ev = MagicMock()
    ev.scenePos.return_value = scene_pos
    ev.modifiers.return_value = modifiers
    return ev


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mgr(qtbot):
    m = PanelWidgetManager()
    qtbot.addWidget(m)
    m.show()
    qtbot.waitExposed(m)
    return m


@pytest.fixture
def mgr_with_text(qtbot):
    """place_object("text") 並設定文字內容，確保 boundingRect 有效尺寸。"""
    m = PanelWidgetManager()
    qtbot.addWidget(m)
    m.show()
    qtbot.waitExposed(m)
    m.place_object("text")
    layer = m._instances[0]["canvas_item"]
    layer.apply_attr("Text", "Hello")
    _scene(m)._overlay._update_geometry()
    return m


# ── TestLifecycle ─────────────────────────────────────────────────────────────

class TestLifecycle:
    """attach / detach 生命週期。"""

    def test_place_text_shows_overlay(self, mgr_with_text):
        assert _overlay(mgr_with_text).isVisible()

    def test_place_text_attaches_to_textlayer(self, mgr_with_text):
        assert _overlay(mgr_with_text)._target is _layer(mgr_with_text)

    def test_place_text_sets_manager(self, mgr_with_text):
        assert _overlay(mgr_with_text)._manager is mgr_with_text

    def test_detach_clears_target(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        ov.detach()
        assert ov._target is None

    def test_detach_clears_manager(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        ov.detach()
        assert ov._manager is None

    def test_detach_clears_drag_mode(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        ov._drag_mode = "move"
        ov.detach()
        assert ov._drag_mode == ""

    def test_double_attach_does_not_crash(self, mgr_with_text):
        """重複 attach 相同 manager 不應 crash 或重複連接 signal。"""
        ov = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)
        ov.attach(layer, mgr_with_text)
        ov.attach(layer, mgr_with_text)
        assert ov._target is layer


# ── TestGeometry ──────────────────────────────────────────────────────────────

class TestGeometry:
    """_update_geometry 幾何計算正確性。"""

    def test_overlay_position_near_anchor(self, mgr_with_text):
        """Center 對齊、X=0、Y=0 → overlay 中心應在 (0, 0) 附近（±10px）。"""
        pos = _overlay(mgr_with_text).scenePos()
        assert abs(pos.x()) < 10
        assert abs(pos.y()) < 10

    def test_overlay_rotation_matches_layer(self, mgr_with_text):
        layer = _layer(mgr_with_text)
        ov    = _overlay(mgr_with_text)
        layer.apply_attr("Rotation", 45.0)
        ov._update_geometry()
        assert abs(ov.rotation() - 45.0) < 0.01

    def test_overlay_rect_nonzero(self, mgr_with_text):
        r = _overlay(mgr_with_text)._rect
        assert abs(r.width())  > 0
        assert abs(r.height()) > 0

    def test_overlay_contains_all_skewed_corners(self, mgr_with_text):
        """Skew X 後，TextLayer 四角映射到 overlay 局部座標，應在 _rect 內（±1px）。"""
        layer = _layer(mgr_with_text)
        ov    = _overlay(mgr_with_text)
        layer.apply_attr("Skew X", 30.0)
        ov._update_geometry()

        br = layer.boundingRect()
        for corner_local in (br.topLeft(), br.topRight(),
                             br.bottomLeft(), br.bottomRight()):
            lp = ov.mapFromScene(layer.mapToScene(corner_local))
            assert ov._rect.left()   - 1 <= lp.x() <= ov._rect.right()  + 1, \
                f"corner x={lp.x():.2f} 超出 overlay x 範圍"
            assert ov._rect.top()    - 1 <= lp.y() <= ov._rect.bottom() + 1, \
                f"corner y={lp.y():.2f} 超出 overlay y 範圍"

    def test_skew_makes_overlay_wider(self, mgr_with_text):
        """Skew X 45° 後 overlay 寬度應大於無 skew 時。"""
        layer  = _layer(mgr_with_text)
        ov     = _overlay(mgr_with_text)
        w_before = abs(ov._rect.width())

        layer.apply_attr("Skew X", 45.0)
        ov._update_geometry()

        assert abs(ov._rect.width()) > w_before

    def test_move_layer_shifts_overlay(self, mgr_with_text):
        """TextLayer X 改變後，_update_geometry 應讓 overlay 位置跟著移動。"""
        ov      = _overlay(mgr_with_text)
        layer   = _layer(mgr_with_text)
        before  = QPointF(ov.scenePos())

        layer.apply_attr("X", 100.0)
        ov._update_geometry()

        assert abs(ov.scenePos().x() - before.x()) > 1.0


# ── TestHandlePositions ───────────────────────────────────────────────────────

class TestHandlePositions:
    """_handle_positions() 回傳正確的 8 個把手座標。"""

    def test_count(self, mgr_with_text):
        assert len(_overlay(mgr_with_text)._handle_positions()) == 8

    def test_tl_at_rect_topleft(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        r  = ov._rect
        assert ov._handle_positions()[0] == QPointF(r.left(), r.top())

    def test_br_at_rect_bottomright(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        r  = ov._rect
        assert ov._handle_positions()[7] == QPointF(r.right(), r.bottom())

    def test_tc_at_top_center(self, mgr_with_text):
        ov      = _overlay(mgr_with_text)
        r       = ov._rect
        handles = ov._handle_positions()
        assert abs(handles[1].x() - r.center().x()) < 0.01
        assert abs(handles[1].y() - r.top()) < 0.01

    def test_ml_at_mid_left(self, mgr_with_text):
        ov      = _overlay(mgr_with_text)
        r       = ov._rect
        handles = ov._handle_positions()
        assert abs(handles[3].x() - r.left())         < 0.01
        assert abs(handles[3].y() - r.center().y())   < 0.01


# ── TestHitTesting ────────────────────────────────────────────────────────────

class TestHitTesting:
    """_hit_handle() 和 _is_rotation_zone() 點擊偵測。"""

    def test_hit_tl(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        assert ov._hit_handle(ov._handle_positions()[0]) == 0

    def test_hit_br(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        assert ov._hit_handle(ov._handle_positions()[7]) == 7

    def test_hit_center_miss(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        assert ov._hit_handle(ov._rect.center()) == -1

    def test_hit_within_tolerance(self, mgr_with_text):
        """把手中心偏移 (HANDLE_HALF + 2) px 仍應 hit。"""
        ov  = _overlay(mgr_with_text)
        tl  = ov._handle_positions()[0]
        tol = _SelectionOverlay._HANDLE_HALF + 2
        assert ov._hit_handle(QPointF(tl.x() + tol - 1, tl.y())) == 0

    def test_hit_beyond_tolerance_miss(self, mgr_with_text):
        ov  = _overlay(mgr_with_text)
        tl  = ov._handle_positions()[0]
        tol = _SelectionOverlay._HANDLE_HALF + 4
        assert ov._hit_handle(QPointF(tl.x() + tol, tl.y())) == -1

    def test_rotation_zone_outside_corner(self, mgr_with_text):
        """角把手外側 (HANDLE_HALF < dist ≤ HANDLE_HALF + ROT_ZONE) 應為旋轉區。"""
        ov   = _overlay(mgr_with_text)
        tl   = ov._handle_positions()[0]
        dist = _SelectionOverlay._HANDLE_HALF + 5   # 在旋轉區範圍內
        p    = QPointF(tl.x() - dist * 0.7, tl.y() - dist * 0.7)
        assert ov._is_rotation_zone(p)

    def test_not_rotation_zone_on_handle_center(self, mgr_with_text):
        """把手正中心（距離 = 0）不是旋轉區。"""
        ov = _overlay(mgr_with_text)
        assert not ov._is_rotation_zone(ov._handle_positions()[0])

    def test_not_rotation_zone_far_away(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        assert not ov._is_rotation_zone(QPointF(-500, -500))


# ── TestCursor ────────────────────────────────────────────────────────────────

class TestCursor:
    """_handle_cursor() 依把手與旋轉角回傳正確游標。"""

    @pytest.mark.parametrize("handle_idx,rotation,expected", [
        (3,  0.0,  Qt.CursorShape.SizeHorCursor),    # ML, base=0°         → 0° → Hor
        (1,  0.0,  Qt.CursorShape.SizeVerCursor),    # TC, base=90°        → 90° → Ver
        (0,  0.0,  Qt.CursorShape.SizeFDiagCursor),  # TL, base=45°        → 45° → FDiag
        (2,  0.0,  Qt.CursorShape.SizeBDiagCursor),  # TR, base=135°       → 135° → BDiag
        (3,  90.0, Qt.CursorShape.SizeVerCursor),    # ML, (0+90)%180=90   → Ver
        (1,  90.0, Qt.CursorShape.SizeHorCursor),    # TC, (90+90)%180=0   → Hor
        (7,  45.0, Qt.CursorShape.SizeVerCursor),    # BR, (45+45)%180=90  → Ver
    ])
    def test_handle_cursor(self, mgr_with_text, handle_idx, rotation, expected):
        layer = _layer(mgr_with_text)
        ov    = _overlay(mgr_with_text)
        layer.apply_attr("Rotation", rotation)
        ov._update_geometry()
        assert ov._handle_cursor(handle_idx) == expected


# ── TestSceneInteraction ──────────────────────────────────────────────────────

class TestSceneInteraction:
    """LayeredGraphicsScene.mousePressEvent 的點擊偵測。"""

    def test_click_layer_emits_instance_selected(self, qtbot, mgr_with_text):
        """overlay 隱藏時，點擊 TextLayer → instance_selected 被 emit。"""
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)

        ov.detach()
        ov.hide()

        with qtbot.waitSignal(mgr_with_text.instance_selected, timeout=500):
            _click_scene(qtbot, mgr_with_text, layer.sceneBoundingRect().center())

    def test_click_layer_sets_current_instance(self, qtbot, mgr_with_text):
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)

        ov.detach()
        ov.hide()
        mgr_with_text._current_instance_id = None

        with qtbot.waitSignal(mgr_with_text.instance_selected, timeout=500):
            _click_scene(qtbot, mgr_with_text, layer.sceneBoundingRect().center())

        assert mgr_with_text._current_instance_id is not None

    def test_click_empty_hides_overlay(self, qtbot, mgr_with_text):
        ov = _overlay(mgr_with_text)
        assert ov.isVisible()

        _click_viewport_corner(qtbot, mgr_with_text)

        assert not ov.isVisible()

    def test_click_empty_clears_current_instance(self, qtbot, mgr_with_text):
        _click_viewport_corner(qtbot, mgr_with_text)
        assert mgr_with_text._current_instance_id is None

    def test_instance_selected_signal_shows_overlay(self, mgr):
        """instance_selected emit TextLayer instance → overlay.show()。"""
        mgr.place_object("text")
        ov    = _overlay(mgr)
        layer = _layer(mgr)
        iid   = 0

        ov.detach()
        ov.hide()

        mgr.instance_selected.emit("text", mgr._instances[iid]["values"], iid)
        assert ov.isVisible()
        assert ov._target is layer

    def test_instance_selected_unknown_id_hides_overlay(self, mgr_with_text):
        ov = _overlay(mgr_with_text)
        ov.show()
        mgr_with_text.instance_selected.emit("text", {}, 9999)
        assert not ov.isVisible()


# ── TestMoveOp ────────────────────────────────────────────────────────────────

class TestMoveOp:
    """move drag：X/Y 更新、限位、overlay 跟隨、undo。"""

    def _setup(self, mgr):
        ov    = _overlay(mgr)
        layer = _layer(mgr)
        ov._drag_mode         = "move"
        ov._drag_start_scene  = QPointF(layer._x, layer._y)
        ov._drag_start_center = ov.scenePos()
        ov._drag_start_vals   = {
            "X": layer._x, "Y": layer._y, "Rotation": layer._rotation,
            "Anim scale X": layer._anim_scale_x,
            "Anim scale Y": layer._anim_scale_y,
        }
        return ov, layer

    def test_updates_xy(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text)
        ov._do_move(_mock_event(QPointF(30.0, 20.0)))
        assert abs(layer._x - 30.0) < 0.01
        assert abs(layer._y - 20.0) < 0.01

    def test_clamps_max(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text)
        ov._do_move(_mock_event(QPointF(9999.0, -9999.0)))
        assert layer._x <=  1280.0
        assert layer._y >= -1280.0

    def test_overlay_position_follows(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text)
        before = QPointF(ov.scenePos())
        ov._do_move(_mock_event(QPointF(80.0, 60.0)))
        assert abs(ov.scenePos().x() - before.x()) > 1.0

    def test_push_live_does_not_crash(self, mgr_with_text):
        """_do_move 含 _push_live 呼叫，不應 crash。"""
        ov, layer = self._setup(mgr_with_text)
        ov._do_move(_mock_event(QPointF(10.0, 10.0)))  # 不 crash 即通過

    def test_release_pushes_undo(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text)
        layer.apply_attr("X", 50.0)
        layer.apply_attr("Y", 30.0)
        ov.mouseReleaseEvent(MagicMock())
        assert mgr_with_text.undo_stack.canUndo()

    def test_release_no_change_no_undo(self, mgr_with_text):
        """起始與結束相同則不推新的 undo command。"""
        ov, layer = self._setup(mgr_with_text)
        mgr_with_text.undo_stack.clear()   # 清除 place_object 留下的命令
        # 不改變 layer 的屬性
        ov.mouseReleaseEvent(MagicMock())
        assert not mgr_with_text.undo_stack.canUndo()


# ── TestScaleOp ───────────────────────────────────────────────────────────────

class TestScaleOp:
    """scale drag：各類把手縮放方向、pivot 固定、Shift 等比、undo。"""

    def _setup(self, mgr, handle_idx: int):
        ov    = _overlay(mgr)
        layer = _layer(mgr)
        ov._drag_handle_idx = handle_idx
        ov._drag_start_vals = {
            "X": layer._x, "Y": layer._y, "Rotation": layer._rotation,
            "Anim scale X": layer._anim_scale_x,
            "Anim scale Y": layer._anim_scale_y,
        }
        ov._drag_mode = f"scale_{handle_idx}"
        ov._init_scale_drag(handle_idx)
        return ov, layer

    # ── BR (角把手) ────────────────────────────────────────────────────────────

    def test_br_increases_both_scales(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text, 7)
        pivot = ov._drag_pivot_scene
        old_sx, old_sy = layer._anim_scale_x, layer._anim_scale_y
        # 拖曳量為 overlay 目前尺寸的 3 倍，確保超過起始尺寸使 scale 增大
        far_x = pivot.x() + ov._drag_d_w0 * 3
        far_y = pivot.y() + ov._drag_d_h0 * 3
        ov._do_scale(_mock_event(QPointF(far_x, far_y)))
        assert layer._anim_scale_x > old_sx
        assert layer._anim_scale_y > old_sy

    def test_br_pivot_tl_stays_fixed(self, mgr_with_text):
        """拖曳 BR 後，TL 把手的 scene 座標應與拖曳前相同（±2px）。"""
        ov, layer = self._setup(mgr_with_text, 7)
        pivot_before = QPointF(ov._drag_pivot_scene)

        ov._do_scale(_mock_event(QPointF(pivot_before.x() + 80, pivot_before.y() + 80)))
        ov._update_geometry()

        tl_after = ov.mapToScene(ov._handle_positions()[0])
        assert abs(tl_after.x() - pivot_before.x()) < 2.0, \
            f"pivot x 偏移：{pivot_before.x():.2f} → {tl_after.x():.2f}"
        assert abs(tl_after.y() - pivot_before.y()) < 2.0, \
            f"pivot y 偏移：{pivot_before.y():.2f} → {tl_after.y():.2f}"

    def test_shift_proportional_scale(self, mgr_with_text):
        """Shift 鍵角把手縮放：起始 scale X == scale Y → 縮放後仍相等（±0.5%）。"""
        ov, layer = self._setup(mgr_with_text, 7)
        pivot = ov._drag_pivot_scene
        ov._do_scale(_mock_event(
            QPointF(pivot.x() + 100, pivot.y() + 100),
            Qt.KeyboardModifier.ShiftModifier,
        ))
        assert abs(layer._anim_scale_x - layer._anim_scale_y) < 0.5

    # ── ML (水平邊把手) ────────────────────────────────────────────────────────

    def test_ml_changes_only_scale_x(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text, 3)
        old_sy = layer._anim_scale_y
        pivot  = ov._drag_pivot_scene
        ov._do_scale(_mock_event(QPointF(pivot.x() - 80, pivot.y())))
        assert abs(layer._anim_scale_y - old_sy) < 0.01

    # ── TC (垂直邊把手) ────────────────────────────────────────────────────────

    def test_tc_changes_only_scale_y(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text, 1)
        old_sx = layer._anim_scale_x
        pivot  = ov._drag_pivot_scene
        ov._do_scale(_mock_event(QPointF(pivot.x(), pivot.y() - 80)))
        assert abs(layer._anim_scale_x - old_sx) < 0.01

    # ── undo ──────────────────────────────────────────────────────────────────

    def test_release_pushes_undo(self, mgr_with_text):
        ov, layer = self._setup(mgr_with_text, 7)
        layer.apply_attr("Anim scale X", 150.0)
        layer.apply_attr("Anim scale Y", 150.0)
        ov.mouseReleaseEvent(MagicMock())
        assert mgr_with_text.undo_stack.canUndo()

    def test_scale_clamps_min(self, mgr_with_text):
        """正向微拖（幾乎在 pivot 上）：scale 應為正整數（>= 1）。"""
        ov, layer = self._setup(mgr_with_text, 7)
        pivot = ov._drag_pivot_scene
        ov._do_scale(_mock_event(QPointF(pivot.x() + 0.001, pivot.y() + 0.001)))
        assert layer._anim_scale_x >= 1
        assert layer._anim_scale_y >= 1


# ── TestRotateOp ──────────────────────────────────────────────────────────────

class TestRotateOp:
    """rotate drag：角度計算、限位、undo。"""

    def _setup(self, mgr):
        ov    = _overlay(mgr)
        layer = _layer(mgr)
        center = ov.scenePos()
        ov._drag_mode         = "rotate"
        ov._drag_start_center = center
        ov._drag_start_scene  = QPointF(center.x() + 50.0, center.y())
        ov._drag_start_vals   = {
            "X": layer._x, "Y": layer._y, "Rotation": 0.0,
            "Anim scale X": layer._anim_scale_x,
            "Anim scale Y": layer._anim_scale_y,
        }
        return ov, layer, center

    def test_rotate_90_clockwise(self, mgr_with_text):
        """從正東拖到正南 → 旋轉 90°。"""
        ov, layer, center = self._setup(mgr_with_text)
        ov._do_rotate(_mock_event(QPointF(center.x(), center.y() + 50.0)))
        assert abs(layer._rotation - 90.0) < 1.0

    def test_rotate_ccw(self, mgr_with_text):
        """從正東拖到正北 → 旋轉 -90°。"""
        ov, layer, center = self._setup(mgr_with_text)
        ov._do_rotate(_mock_event(QPointF(center.x(), center.y() - 50.0)))
        assert abs(layer._rotation - (-90.0)) < 1.0

    def test_rotate_clamps_max(self, mgr_with_text):
        ov, layer, center = self._setup(mgr_with_text)
        ov._drag_start_vals["Rotation"] = 710.0
        ov._do_rotate(_mock_event(QPointF(center.x(), center.y() + 50.0)))
        assert layer._rotation <= 720.0

    def test_rotate_clamps_min(self, mgr_with_text):
        ov, layer, center = self._setup(mgr_with_text)
        ov._drag_start_vals["Rotation"] = -710.0
        ov._do_rotate(_mock_event(QPointF(center.x(), center.y() - 50.0)))
        assert layer._rotation >= -720.0

    def test_overlay_rotation_updates_after_rotate(self, mgr_with_text):
        ov, layer, center = self._setup(mgr_with_text)
        ov._do_rotate(_mock_event(QPointF(center.x(), center.y() + 50.0)))
        assert abs(ov.rotation() - layer._rotation) < 0.1

    def test_release_pushes_undo(self, mgr_with_text):
        ov, layer, center = self._setup(mgr_with_text)
        layer.apply_attr("Rotation", 45.0)
        ov.mouseReleaseEvent(MagicMock())
        assert mgr_with_text.undo_stack.canUndo()


# ── TestAttrSync ──────────────────────────────────────────────────────────────

class TestAttrSync:
    """_on_attr_changed 確保任何屬性變更都觸發 _update_geometry。"""

    def test_x_change_moves_overlay(self, mgr_with_text):
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)
        before = QPointF(ov.scenePos())
        layer.apply_attr("X", 100.0)
        ov._on_attr_changed("X", 100.0)
        assert abs(ov.scenePos().x() - before.x()) > 1.0

    def test_rotation_change_rotates_overlay(self, mgr_with_text):
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)
        layer.apply_attr("Rotation", 30.0)
        ov._on_attr_changed("Rotation", 30.0)
        assert abs(ov.rotation() - 30.0) < 0.1

    def test_skew_change_updates_rect(self, mgr_with_text):
        ov     = _overlay(mgr_with_text)
        layer  = _layer(mgr_with_text)
        w_before = abs(ov._rect.width())
        layer.apply_attr("Skew X", 45.0)
        ov._on_attr_changed("Skew X", 45.0)
        assert abs(ov._rect.width()) > w_before

    def test_attr_changed_signal_updates_overlay(self, qtbot, mgr_with_text):
        """manager.attr_changed emit 後，overlay 幾何應更新（透過 signal 連接）。"""
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)
        before = QPointF(ov.scenePos())

        layer.apply_attr("X", 80.0)
        mgr_with_text.attr_changed.emit("X", 80.0)

        assert abs(ov.scenePos().x() - before.x()) > 1.0

    def test_detached_overlay_ignores_attr_changed(self, qtbot, mgr_with_text):
        """detach 後 overlay 不再響應 attr_changed。"""
        ov    = _overlay(mgr_with_text)
        layer = _layer(mgr_with_text)
        ov.detach()

        pos_before = QPointF(ov.scenePos())
        layer.apply_attr("X", 200.0)
        mgr_with_text.attr_changed.emit("X", 200.0)

        assert abs(ov.scenePos().x() - pos_before.x()) < 0.01
