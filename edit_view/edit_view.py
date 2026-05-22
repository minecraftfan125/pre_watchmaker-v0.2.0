from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSplitter,
)
from PyQt5.QtCore import (
    Qt,
    QPoint,
    pyqtSignal,
    QEvent,
    QRect,
)
from PyQt5.QtGui import (
    QCursor,
)
from common import load_style, UndoGroupStack
from edit_view.drag_effect import DragVisual
from edit_view.attribute_panel import AttributePanal, DelWidget
from edit_view.components_panel import ComponentPanel
from edit_view.explorer import Exploror, DelExplorerItem
from edit_view.watch_preview import WatchPreview, DelLayer

class EditView(QWidget):
    exp_singal = pyqtSignal(object, object, object)
    summon_script_view = pyqtSignal(object, object)  # (edit_view, container)

    def __init__(self, parent=None, undo_stack :UndoGroupStack|None=None, tip_signal=None):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.tip_signal = tip_signal
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.is_dragging = False
        self._sync_guard = False
        self.id_stack = [2]
        self.set_ui()
        self.setStyleSheet(load_style())

    def set_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.explorer = Exploror(self.undo_stack, self.id_stack, self.exp_singal)
        self.watch_preview = WatchPreview(self.undo_stack, self.id_stack)

        component_related = QSplitter(Qt.Vertical)
        self.components = ComponentPanel(self.undo_stack)
        self.attribute = AttributePanal(self.undo_stack, self.id_stack, self.tip_signal)
        self.drag_box = DragVisual(self)
        component_related.setObjectName("objectSplitter")
        component_related.setHandleWidth(2)
        component_related.addWidget(self.components)
        component_related.addWidget(self.attribute)
        component_related.setSizes([250, 250])

        main_layout.addWidget(self.explorer)
        main_layout.addWidget(self.watch_preview)
        main_layout.addWidget(component_related)

        # 安裝事件過濾器到所有可拖放區域
        self.explorer.installEventFilter(self)
        self.explorer.installEventFilter(self)
        self.watch_preview.installEventFilter(self)
        self.watch_preview.viewport().installEventFilter(self)
        self.components.installEventFilter(self)
        self.components.viewport().installEventFilter(self)
        self.attribute.installEventFilter(self)

        self.watch_preview.summon.connect(self.pre_call)
        self.components.button_trigger.connect(self.com_call)
        self.attribute.send_obj.connect(self.att_call)
        # 連接腳本編輯器請求信號
        self.attribute.request_script_editor.connect(
            lambda container: self.summon_script_view.emit(self, container)
        )
        self.watch_preview.select.connect(self._on_preview_selected)
        self.explorer.item_selected.connect(self._on_explorer_item_selected)
        self.explorer.delete.connect(self._delete_layer)
        self.watch_preview.delete.connect(self._delete_layer)

    def _on_preview_selected(self, hash_id):
        if self._sync_guard or hash_id is None:
            return
        self._sync_guard = True
        try:
            self.attribute.toggle_widget(hash_id)
            self.explorer.select_item(hash_id)
        finally:
            self._sync_guard = False

    def _on_explorer_item_selected(self, hash_id):
        if self._sync_guard:
            return
        self._sync_guard = True
        try:
            self.attribute.toggle_widget(hash_id)
            layer = self.watch_preview.hash_table.get(hash_id)
            if layer:
                self.watch_preview.sence.clearSelection()
                layer.setSelected(True)
        finally:
            self._sync_guard = False

    def _delete_layer(self, hash_id):
        widget = self.attribute.find(hash_id)
        layer = self.watch_preview.hash_table.get(hash_id)
        explorer_item = self.explorer.items.get(str(hash_id))
        if not (widget and layer and explorer_item):
            return
        self.undo_stack.beginMacro("Delete Layer")
        self.undo_stack.push(DelWidget(widget, self.attribute, hash_id))
        self.undo_stack.push(DelLayer(self.watch_preview.sence, layer, self.watch_preview.hash_table))
        self.undo_stack.push(DelExplorerItem(explorer_item, self.explorer.tree, self.explorer.items))
        self.undo_stack.endMacro()

    def delete_component(self, obj):
        self.id_stack.append(obj.hash_id)

    def att_call(self, layer_type, signal_dict, hash_id):
        self.watch_preview.receive.emit(layer_type, signal_dict, hash_id)
        self.explorer.receive.emit(layer_type, signal_dict, hash_id)

    def com_call(self, data):
        self.attribute.summon_widget.emit([data])

    def pre_call(self, obj_type, pos, hash_id):
        if hash_id == 0:
            hash_id = self.get_hash_id()
        self.attribute.summon_widget.emit([obj_type, pos, hash_id])

    def get_hash_id(self):
        if self.id_stack[-1] is self.id_stack[0]:
            out = self.id_stack.pop()
            self.id_stack.append(out + 1)
            return out
        else:
            return self.id_stack.pop()

    def show_all_overrides(self):
        """顯示所有 OverrideWidget"""
        self.explorer.override.show()
        self.watch_preview.override.show()
        self.components.override.show()
        self.attribute.override.show()

    def hide_all_overrides(self):
        """隱藏所有 OverrideWidget"""
        self.explorer.override.hide()
        self.watch_preview.override.hide()
        self.components.override.hide()
        self.attribute.override.hide()

    def _get_drop_target(self, watched):
        """取得拖放目標 widget（處理 viewport 的情況）"""
        # 如果 watched 是 viewport，返回其父 widget
        parent = watched.parent()
        if parent in [
            self.explorer,
            self.watch_preview,
            self.components,
            self.attribute,
        ]:
            return parent
        return watched

    def eventFilter(self, watched, event):
        target = self._get_drop_target(watched)

        if event.type() == QEvent.DragEnter:
            if not self.is_dragging:
                self.is_dragging = True
                self.show_all_overrides()
            if hasattr(target, "override"):
                target.override.hide()

        if event.type() == QEvent.DragMove:
            if hasattr(target, "required_visual_effects"):
                pos, size = target.required_visual_effects(event)
                pos = self.mapFromGlobal(target.mapToGlobal(pos))
                self.drag_box.change(pos, size)

        if event.type() == QEvent.DragLeave:
            # 檢查滑鼠是否真的離開了該元件的邊界
            cursor_pos = QCursor.pos()
            target_rect = QRect(target.mapToGlobal(QPoint(0, 0)), target.size())
            # 只有當滑鼠真正離開 target 邊界時才顯示 override
            if not target_rect.contains(cursor_pos) and hasattr(target, "override"):
                target.override.show()

        if event.type() == QEvent.Drop:
            self.dropEvent(event)

        return False

    def dragEnterEvent(self, event):
        """處理拖曳進入 EditView 本身"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            if not self.is_dragging:
                self.is_dragging = True
                self.show_all_overrides()

    def dragMoveEvent(self, event):
        """處理拖曳在 EditView 移動"""
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """處理拖曳離開 EditView - 這是真正離開整個區域"""
        self.is_dragging = False
        self.hide_all_overrides()
        self.drag_box.hide()

    def item_drop(self):
        self.is_dragging = False
        self.hide_all_overrides()
        self.drag_box.hide()

    def dropEvent(self, event):
        """處理放下事件"""
        self.item_drop()


# TODO:
# 元件選擇的觸發效果
# 實作contsainer的lua編譯架構
