"""
edit_watch.py 操作流程測試。
涵蓋 place_object、Undo/Redo 命令、Name 衝突、sticky 預設值、
面板訊號傳遞、_AttrFieldWidget commit 行為。
"""
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QCheckBox, QLineEdit, QSpinBox

from edit_watch import (
    PanelWidgetManager,
    _AttrFieldWidget,
)
from components.layers import ImageLayer, LayerEllipseItem, LayerMixin


# ── helpers ───────────────────────────────────────────────────────────────────

def _layer_items(mgr: PanelWidgetManager) -> list:
    """場景中所有 LayerMixin item（排除非 LayerMixin 的背景圓框）。"""
    scene = mgr._edit_view._canvas._scene
    return [i for i in scene.items() if isinstance(i, LayerMixin)]


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mgr(qtbot):
    m = PanelWidgetManager()
    qtbot.addWidget(m)
    m.show()
    qtbot.waitExposed(m)
    return m


# ── place_object 基本行為 ──────────────────────────────────────────────────────

class TestPlaceObject:
    def test_adds_to_instances(self, mgr):
        mgr.place_object("watchBackground")
        assert len(mgr._instances) == 1

    def test_adds_canvas_item(self, mgr):
        mgr.place_object("watchBackground")
        assert len(_layer_items(mgr)) == 1

    def test_adds_tree_item(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr._obj_explorer._tree.topLevelItemCount() == 1

    def test_sets_current_instance_id(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr._current_instance_id == 0

    def test_sets_current_object_type(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr._current_object_type == "watchBackground"

    def test_second_place_increments_id(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        assert set(mgr._instances.keys()) == {0, 1}

    def test_pushes_to_undo_stack(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr.undo_stack.count() == 1

    def test_two_places_two_commands(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        assert mgr.undo_stack.count() == 2

    def test_with_pos_overrides_x(self, mgr):
        mgr.place_object("watchBackground", QPointF(100, 200))
        assert mgr._instances[0]["values"]["X"] == 100

    def test_with_pos_overrides_y(self, mgr):
        mgr.place_object("watchBackground", QPointF(100, 200))
        assert mgr._instances[0]["values"]["Y"] == 200

    def test_without_pos_keeps_default_xy(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr._instances[0]["values"]["X"] == 0
        assert mgr._instances[0]["values"]["Y"] == 0

    def test_stores_object_type(self, mgr):
        mgr.place_object("watchBackground")
        assert mgr._instances[0]["object_type"] == "watchBackground"

    def test_canvas_item_is_image_layer(self, mgr):
        """watchBackground 的 TYPE 為 imageLayer，canvas item 應為真正的 ImageLayer。"""
        mgr.place_object("watchBackground")
        assert isinstance(_layer_items(mgr)[0], ImageLayer)

    def test_template_mode_uses_saved_defaults(self, mgr):
        """Template 模式顯示同型別且有 _type_defaults 時，place 沿用已儲存的值。"""
        mgr._type_defaults["watchBackground"] = {
            "Layer": 7, "Name": "bg", "X": 0, "Y": 0,
        }
        mgr.object_selected.emit("watchBackground")
        assert mgr._current_instance_id is None
        mgr.place_object("watchBackground")
        assert mgr._instances[0]["values"]["Layer"] == 7

    def test_different_type_placed_correctly(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("text")
        assert mgr._instances[1]["object_type"] == "text"

    def test_instance_mode_after_place(self, mgr):
        """place 後切換到 instance 模式（_current_instance_id 不為 None）。"""
        mgr.place_object("watchBackground")
        assert mgr._current_instance_id is not None


# ── _PlaceCommand undo / redo ─────────────────────────────────────────────────

class TestPlaceCommandUndoRedo:
    def test_undo_removes_from_instances(self, mgr):
        mgr.place_object("watchBackground")
        iid = mgr._current_instance_id
        mgr.undo_stack.undo()
        assert iid not in mgr._instances

    def test_undo_removes_canvas_item(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        assert len(_layer_items(mgr)) == 0

    def test_undo_removes_tree_item(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        assert mgr._obj_explorer._tree.topLevelItemCount() == 0

    def test_undo_clears_current_instance_id(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        assert mgr._current_instance_id is None

    def test_undo_switches_to_template_mode(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        assert mgr._current_object_type == "watchBackground"
        assert mgr._current_instance_id is None

    def test_redo_restores_instances(self, mgr):
        mgr.place_object("watchBackground")
        iid = mgr._current_instance_id
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert iid in mgr._instances

    def test_redo_restores_canvas_item(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert len(_layer_items(mgr)) == 1

    def test_redo_restores_tree_item(self, mgr):
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert mgr._obj_explorer._tree.topLevelItemCount() == 1

    def test_undo_redo_reuses_same_canvas_object(self, mgr):
        """undo/redo 重用同一個 canvas item 參考，不重新建立。"""
        mgr.place_object("watchBackground")
        item_before = _layer_items(mgr)[0]
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert _layer_items(mgr)[0] is item_before

    def test_undo_removes_name_from_used_names(self, mgr):
        mgr.place_object("watchBackground")
        name = mgr._instances[0]["values"]["Name"]
        mgr.undo_stack.undo()
        assert name not in mgr._obj_explorer._used_names

    def test_redo_readds_name_to_used_names(self, mgr):
        mgr.place_object("watchBackground")
        iid = mgr._current_instance_id
        name = mgr._instances[iid]["values"]["Name"]
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert name in mgr._obj_explorer._used_names

    def test_undo_second_preserves_first(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        assert 0 in mgr._instances
        assert 1 not in mgr._instances

    def test_undo_both_clears_all(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        mgr.undo_stack.undo()
        mgr.undo_stack.undo()
        assert len(mgr._instances) == 0
        assert len(_layer_items(mgr)) == 0


# ── Name 衝突 ─────────────────────────────────────────────────────────────────

class TestNameConflict:
    def test_second_place_gets_unique_name(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        n0 = mgr._instances[0]["values"]["Name"]
        n1 = mgr._instances[1]["values"]["Name"]
        assert n0 != n1

    def test_three_places_all_unique(self, mgr):
        for _ in range(3):
            mgr.place_object("watchBackground")
        names = [inst["values"]["Name"] for inst in mgr._instances.values()]
        assert len(set(names)) == 3

    def test_used_names_populated(self, mgr):
        mgr.place_object("watchBackground")
        name = mgr._instances[0]["values"]["Name"]
        assert name in mgr._obj_explorer._used_names

    def test_both_names_in_used_names(self, mgr):
        mgr.place_object("watchBackground")
        mgr.place_object("watchBackground")
        for inst in mgr._instances.values():
            assert inst["values"]["Name"] in mgr._obj_explorer._used_names

    def test_tree_item_text_matches_name(self, mgr):
        mgr.place_object("watchBackground")
        name = mgr._instances[0]["values"]["Name"]
        assert mgr._obj_explorer._tree.topLevelItem(0).text(0) == name

    def test_undo_releases_name(self, mgr):
        mgr.place_object("watchBackground")
        name = mgr._instances[0]["values"]["Name"]
        mgr.undo_stack.undo()
        assert name not in mgr._obj_explorer._used_names

    def test_redo_reclaims_name(self, mgr):
        mgr.place_object("watchBackground")
        iid = mgr._current_instance_id
        name = mgr._instances[iid]["values"]["Name"]
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert name in mgr._obj_explorer._used_names

    def test_after_undo_second_place_reuses_first_name(self, mgr):
        """undo 後再 place，_used_names 已清空，可取得相同名稱（無多餘後綴）。"""
        mgr.place_object("watchBackground")
        first_name = mgr._instances[0]["values"]["Name"]
        mgr.undo_stack.undo()
        mgr.place_object("watchBackground")
        new_name = next(iter(mgr._instances.values()))["values"]["Name"]
        assert new_name == first_name


# ── sticky 預設值（_type_defaults）────────────────────────────────────────────

class TestStickyDefaults:
    def test_template_commit_writes_to_type_defaults(self, mgr):
        """B 路徑：template 模式 commit 欄位 → 寫入 _type_defaults。"""
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 5)
        assert mgr._type_defaults.get("watchBackground", {}).get("Layer") == 5

    def test_direct_defaults_loaded_by_object_selected(self, mgr):
        """A 路徑：直接寫 _type_defaults → emit object_selected → 面板顯示該值。"""
        mgr._type_defaults["watchBackground"] = {
            "Layer": 9, "Name": "Layer", "X": 0, "Y": 0,
        }
        mgr.object_selected.emit("watchBackground")
        values = mgr._attr_panel.get_current_values()
        assert values.get("Layer") == 9

    def test_direct_defaults_used_on_place(self, mgr):
        """A 路徑：direct _type_defaults + place → instance 帶入該值。"""
        mgr._type_defaults["watchBackground"] = {
            "Layer": 9, "Name": "Layer", "X": 0, "Y": 0,
        }
        mgr.object_selected.emit("watchBackground")
        mgr.place_object("watchBackground")
        assert mgr._instances[0]["values"]["Layer"] == 9

    def test_switching_type_saves_current_template_values(self, mgr):
        """切換型別前，舊型別的 template 值（面板顯示值）存入 _type_defaults。"""
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel.update_field("Layer", 3)  # 模擬使用者已將 Layer 改為 3
        mgr.object_selected.emit("text")
        assert mgr._type_defaults.get("watchBackground", {}).get("Layer") == 3

    def test_on_object_selected_loads_saved_defaults(self, mgr):
        """GroupLayer 路徑：_on_object_selected 從 _type_defaults 載入。"""
        mgr._type_defaults["watchBackground"] = {
            "Layer": 4, "Name": "Layer", "X": 0, "Y": 0,
        }
        mgr._attr_panel._on_object_selected("watchBackground")
        values = mgr._attr_panel.get_current_values()
        assert values.get("Layer") == 4

    def test_same_type_template_retains_edited_value(self, mgr):
        """同型別 template 模式下 commit 後，_type_defaults 保留編輯值。"""
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 6)
        assert mgr._type_defaults["watchBackground"]["Layer"] == 6
        assert mgr._current_instance_id is None
        assert mgr._current_object_type == "watchBackground"

    def test_group_layer_always_resets(self, mgr):
        """GroupLayer（object mime）直接呼叫 _on_object_selected，不保留目前編輯。"""
        mgr._type_defaults["watchBackground"] = {
            "Layer": 2, "Name": "Layer", "X": 0, "Y": 0,
        }
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 8)
        # GroupLayer drop 呼叫 _on_object_selected（無 early-return 保護）
        mgr._attr_panel._on_object_selected("watchBackground")
        # 面板應從 _type_defaults 重新載入
        values = mgr._attr_panel.get_current_values()
        # _on_field_committed 已把 _type_defaults["watchBackground"]["Layer"]=8
        # _on_object_selected 再次載入，所以顯示 8（已儲存的值）
        assert values.get("Layer") == 8


# ── _TemplateAttrChangeCommand ─────────────────────────────────────────────────

class TestTemplateAttrChangeCommand:
    def test_commit_pushes_command(self, mgr):
        mgr.object_selected.emit("watchBackground")
        before = mgr.undo_stack.count()
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        assert mgr.undo_stack.count() == before + 1

    def test_undo_restores_type_defaults(self, mgr):
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.undo_stack.undo()
        assert mgr._type_defaults.get("watchBackground", {}).get("Layer") == 0

    def test_redo_reapplies_type_defaults(self, mgr):
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert mgr._type_defaults.get("watchBackground", {}).get("Layer") == 3

    def test_undo_updates_panel_when_showing_same_type(self, mgr):
        """undo 時面板正顯示同型別 template → 面板 widget 同步更新。"""
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.undo_stack.undo()
        assert mgr._attr_panel.get_current_values().get("Layer") == 0

    def test_undo_no_panel_update_when_not_showing(self, mgr):
        """undo 時面板顯示不同型別 → 只還原 _type_defaults，不影響面板顯示。"""
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.object_selected.emit("text")
        mgr.undo_stack.undo()
        assert mgr._type_defaults.get("watchBackground", {}).get("Layer") == 0
        assert mgr._current_object_type == "text"

    def test_multiple_commits_push_separate_commands(self, mgr):
        mgr.object_selected.emit("watchBackground")
        mgr._attr_panel._on_field_committed("Layer", 0, 1)
        mgr._attr_panel._on_field_committed("X", 0, 50)
        assert mgr.undo_stack.count() == 2


# ── _AttrChangeCommand ────────────────────────────────────────────────────────

class TestInstanceAttrChangeCommand:
    @pytest.fixture
    def placed(self, mgr):
        """放置一個 watchBackground，回傳 (manager, instance_id=0)。"""
        mgr.place_object("watchBackground")
        return mgr, 0

    def test_commit_pushes_command(self, placed):
        mgr, iid = placed
        before = mgr.undo_stack.count()
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        assert mgr.undo_stack.count() == before + 1

    def test_commit_updates_instances_values(self, placed):
        mgr, iid = placed
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        assert mgr._instances[iid]["values"]["Layer"] == 3

    def test_undo_restores_value(self, placed):
        mgr, iid = placed
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.undo_stack.undo()
        assert mgr._instances[iid]["values"]["Layer"] == 0

    def test_redo_reapplies_value(self, placed):
        mgr, iid = placed
        mgr._attr_panel._on_field_committed("Layer", 0, 3)
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert mgr._instances[iid]["values"]["Layer"] == 3

    def test_undo_restores_canvas_layer_value(self, placed):
        """undo 後 canvas item layer_value 還原。"""
        mgr, iid = placed
        canvas_item = mgr._instances[iid]["canvas_item"]
        canvas_item.set_layer_value(5)
        mgr._attr_panel._on_field_committed("Layer", 0, 5)
        mgr.undo_stack.undo()
        assert canvas_item.layer_value() == 0

    def test_redo_reapplies_canvas_layer_value(self, placed):
        mgr, iid = placed
        canvas_item = mgr._instances[iid]["canvas_item"]
        canvas_item.set_layer_value(5)
        mgr._attr_panel._on_field_committed("Layer", 0, 5)
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert canvas_item.layer_value() == 5

    def test_undo_restores_canvas_x_position(self, placed):
        """undo X 變更 → canvas item 水平位置還原。"""
        mgr, iid = placed
        canvas_item = mgr._instances[iid]["canvas_item"]
        canvas_item.apply_attr("X", 50)
        mgr._attr_panel._on_field_committed("X", 0, 50)
        mgr.undo_stack.undo()
        assert abs(canvas_item._x - 0) < 1e-3

    def test_redo_reapplies_canvas_x_position(self, placed):
        mgr, iid = placed
        canvas_item = mgr._instances[iid]["canvas_item"]
        canvas_item.apply_attr("X", 50)
        mgr._attr_panel._on_field_committed("X", 0, 50)
        mgr.undo_stack.undo()
        mgr.undo_stack.redo()
        assert abs(canvas_item._x - 50) < 1e-3

    def test_name_commit_updates_tree_text(self, placed):
        mgr, iid = placed
        old_name = mgr._instances[iid]["values"]["Name"]
        mgr._attr_panel._on_field_committed("Name", old_name, "MyLayer")
        assert mgr._obj_explorer._tree.topLevelItem(0).text(0) == "MyLayer"

    def test_name_commit_updates_used_names(self, placed):
        mgr, iid = placed
        old_name = mgr._instances[iid]["values"]["Name"]
        mgr._attr_panel._on_field_committed("Name", old_name, "NewName")
        assert "NewName" in mgr._obj_explorer._used_names
        assert old_name not in mgr._obj_explorer._used_names

    def test_name_undo_restores_used_names(self, placed):
        mgr, iid = placed
        old_name = mgr._instances[iid]["values"]["Name"]
        mgr._attr_panel._on_field_committed("Name", old_name, "NewName")
        mgr.undo_stack.undo()
        assert old_name in mgr._obj_explorer._used_names
        assert "NewName" not in mgr._obj_explorer._used_names

    def test_name_conflict_gets_unique_name(self, mgr):
        """commit Name 到已存在的名稱時，自動加後綴以確保唯一性。"""
        mgr.place_object("watchBackground")  # iid=0, name="Layer"
        mgr.place_object("watchBackground")  # iid=1, name="Layer 2"
        name0 = mgr._instances[0]["values"]["Name"]
        # instance 1 為目前選取；嘗試改名為 instance 0 的名稱
        mgr._attr_panel._on_field_committed(
            "Name", mgr._instances[1]["values"]["Name"], name0
        )
        result = mgr._instances[1]["values"]["Name"]
        assert result != name0
        assert result in mgr._obj_explorer._used_names

    def test_tree_item_data_updated_on_commit(self, placed):
        """commit 後 tree item 的 UserRole+1 資料同步更新。"""
        mgr, iid = placed
        mgr._attr_panel._on_field_committed("Layer", 0, 7)
        ti = mgr._instances[iid]["tree_item"]
        stored = ti.data(0, Qt.ItemDataRole.UserRole + 1)
        assert stored.get("Layer") == 7


# ── 面板間訊號傳遞 ────────────────────────────────────────────────────────────

class TestPanelSignals:
    def test_object_selected_sets_template_mode(self, mgr):
        mgr.object_selected.emit("watchBackground")
        assert mgr._current_instance_id is None
        assert mgr._current_object_type == "watchBackground"

    def test_instance_selected_sets_instance_mode(self, mgr):
        mgr.place_object("watchBackground")
        iid = mgr._current_instance_id
        values = mgr._instances[iid]["values"]
        mgr.instance_selected.emit("watchBackground", values, iid)
        assert mgr._current_instance_id == iid

    def test_place_emits_instance_selected(self, qtbot, mgr):
        with qtbot.waitSignal(mgr.instance_selected, timeout=1000) as sig:
            mgr.place_object("watchBackground")
        obj_type, vals, iid = sig.args
        assert obj_type == "watchBackground"
        assert iid == 0

    def test_attr_changed_updates_canvas(self, mgr):
        """attr_changed → EditViewPanel → canvas apply_attr。"""
        mgr.place_object("watchBackground")
        canvas_item = mgr._instances[0]["canvas_item"]
        mgr.attr_changed.emit("Layer", 7)
        assert canvas_item.layer_value() == 7

    def test_attr_changed_only_affects_current_instance(self, mgr):
        """attr_changed 只更新目前選取 instance 的 canvas item。"""
        mgr.place_object("watchBackground")   # iid=0
        mgr.place_object("watchBackground")   # iid=1（目前選取）
        item0 = mgr._instances[0]["canvas_item"]
        item1 = mgr._instances[1]["canvas_item"]
        mgr.attr_changed.emit("Layer", 9)
        assert item1.layer_value() == 9
        assert item0.layer_value() == 0

    def test_attr_changed_no_effect_in_template_mode(self, mgr):
        """template 模式（無 instance）時 attr_changed 不更新任何 canvas item。"""
        mgr.place_object("watchBackground")
        item = mgr._instances[0]["canvas_item"]
        mgr.undo_stack.undo()                # 切回 template 模式
        mgr.attr_changed.emit("Layer", 9)
        # item 已從 scene 移除，layer_value 不因 attr_changed 改變
        assert item.layer_value() == 0

    def test_object_selected_signal_connects_attr_panel(self, mgr):
        mgr.object_selected.emit("text")
        assert mgr._current_object_type == "text"

    def test_explorer_click_emits_instance_selected(self, qtbot, mgr):
        """點擊 ObjectExplorer 節點應 emit instance_selected。"""
        mgr.place_object("watchBackground")
        tree = mgr._obj_explorer._tree
        with qtbot.waitSignal(mgr.instance_selected, timeout=1000):
            qtbot.mouseClick(
                tree.viewport(),
                Qt.MouseButton.LeftButton,
                pos=tree.visualItemRect(tree.topLevelItem(0)).center(),
            )


# ── _AttrFieldWidget commit 行為 ──────────────────────────────────────────────

class TestAttrFieldWidget:
    @pytest.fixture
    def str_field(self, qtbot):
        w = _AttrFieldWidget("Name", "hello", "str")
        qtbot.addWidget(w)
        w.show()
        return w

    @pytest.fixture
    def bool_field(self, qtbot):
        w = _AttrFieldWidget("Visible", False, "bool")
        qtbot.addWidget(w)
        w.show()
        return w

    @pytest.fixture
    def range_field(self, qtbot):
        w = _AttrFieldWidget("Layer", 0, (0, 99, 1))
        qtbot.addWidget(w)
        w.show()
        return w

    def test_str_initial_value(self, str_field):
        assert str_field.get_value() == "hello"

    def test_str_commit_emits_value_committed(self, qtbot, str_field):
        edit = str_field.findChild(QLineEdit)
        with qtbot.waitSignal(str_field.value_committed, timeout=1000) as sig:
            edit.setText("world")
            edit.editingFinished.emit()
        field, old, new = sig.args
        assert field == "Name"
        assert old == "hello"
        assert new == "world"

    def test_str_same_value_no_commit(self, qtbot, str_field):
        """值未改變時 editingFinished 不 emit value_committed。"""
        signals = []
        str_field.value_committed.connect(lambda *a: signals.append(a))
        edit = str_field.findChild(QLineEdit)
        edit.editingFinished.emit()
        assert len(signals) == 0

    def test_bool_commit_on_toggle(self, qtbot, bool_field):
        cb = bool_field.findChild(QCheckBox)
        with qtbot.waitSignal(bool_field.value_committed, timeout=1000) as sig:
            cb.setChecked(True)
        field, old, new = sig.args
        assert field == "Visible"
        assert old is False
        assert new is True

    def test_bool_toggle_back_emits_again(self, qtbot, bool_field):
        cb = bool_field.findChild(QCheckBox)
        cb.setChecked(True)
        with qtbot.waitSignal(bool_field.value_committed, timeout=1000) as sig:
            cb.setChecked(False)
        _, old, new = sig.args
        assert old is True
        assert new is False

    def test_range_field_initial_value_is_int(self, range_field):
        """range tuple (default=1) 初始值為 int。"""
        val = range_field.get_value()
        assert isinstance(val, int)

    def test_range_slider_string_value_parsed_correctly(self, qtbot):
        """X/Y bug fix：range tuple 使用字串初始值不應顯示 default=0。"""
        w = _AttrFieldWidget("Layer", "5", (0, 99, 1))
        qtbot.addWidget(w)
        spin = w.findChild(QSpinBox)
        assert spin is not None
        assert spin.value() == 5

    def test_range_input_string_value_parsed_correctly(self, qtbot):
        """非 slider range（step≠1）使用字串初始值不應顯示 default=0。"""
        w = _AttrFieldWidget("X", "100", (0, 450, 10))
        qtbot.addWidget(w)
        edit = w.findChild(QLineEdit)
        assert edit is not None
        assert edit.text() == "100"

    def test_set_value_does_not_emit_value_changed(self, qtbot, str_field):
        signals = []
        str_field.value_changed.connect(lambda *a: signals.append(a))
        str_field.set_value("silent")
        assert len(signals) == 0

    def test_set_value_does_not_emit_value_committed(self, qtbot, str_field):
        signals = []
        str_field.value_committed.connect(lambda *a: signals.append(a))
        str_field.set_value("silent")
        assert len(signals) == 0

    def test_set_value_updates_field_value(self, str_field):
        str_field.set_value("updated")
        assert str_field._field_value == "updated"

    def test_set_value_updates_committed_value(self, str_field):
        str_field.set_value("updated")
        assert str_field._committed_value == "updated"

    def test_range_commit_emits_value_committed(self, qtbot, range_field):
        spin = range_field.findChild(QSpinBox)
        with qtbot.waitSignal(range_field.value_committed, timeout=1000) as sig:
            spin.setValue(5)
            spin.editingFinished.emit()
        field, old, new = sig.args
        assert field == "Layer"
        assert new == 5

    def test_range_commit_correct_old_value(self, qtbot, range_field):
        spin = range_field.findChild(QSpinBox)
        with qtbot.waitSignal(range_field.value_committed, timeout=1000) as sig:
            spin.setValue(5)
            spin.editingFinished.emit()
        _, old, _ = sig.args
        assert old == 0

    def test_set_value_prevents_subsequent_spurious_commit(self, qtbot, str_field):
        """set_value 後再 editingFinished → _committed_value 已更新，不再 emit。"""
        signals = []
        str_field.value_committed.connect(lambda *a: signals.append(a))
        str_field.set_value("preset")
        edit = str_field.findChild(QLineEdit)
        edit.editingFinished.emit()
        assert len(signals) == 0
