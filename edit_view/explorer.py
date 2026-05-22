from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QMenu,
    QAction,
    QUndoCommand,
)
from PyQt5.QtCore import (
    Qt,
    QPoint,
    pyqtSignal,
    QSize,
    QObject,
)
import re
from edit_view.drag_effect import *

class ItemSignals(QObject):
    level_change = pyqtSignal(object, int)
@Dragable("id")
class ExplororItem(QTreeWidgetItem):
    def __init__(self, layer_type, att_signal_dict, id, parent):
        if layer_type == "group":
            super().__init__(1001)
        else:
            super().__init__(1000)
        self.layer_type = layer_type
        self._parent = parent
        self.level = 0
        self.name = ""
        self.id = str(id)
        self.signals = ItemSignals()
        self.name_signal = att_signal_dict["Name"]
        self.level_signal = att_signal_dict["Layer"]
        self.setText(1, re.sub(r"Layer$", "", self.layer_type))
        self.level_signal.connect(self.change_z_order)

    def rename(self, name):
        self.setText(0, name)
        self.name = name

    def change_z_order(self, value):
        if value == self.level:
            return
        self.level = value
        self.level_signal.emit(value)

    def __lt__(self, other):
        condition = getattr(self._parent, "sort_basis", "layer")
        if condition == "layer":
            return self.level < other.level
        if condition == "name":
            return self.name < other.name
        if condition == "type":
            return self.layer_type < other.layer_type
        return self.name < other.name


class ExplororTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("explorerTree")
        self.setMaximumWidth(300)
        self.setColumnCount(2)
        self.setHeaderLabels(["Name", "Layer"])
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setIndentation(0)
        header = self.header()
        header.setStretchLastSection(True)
        self.setColumnWidth(0, 140)
        self.setColumnWidth(1, 70)
        self.reference_item = None
        self.setSortingEnabled(True)
        self.item_level = {}
        self.name_allocator = {}
        self.layer_allocator=[0 for i in range(5001)]
        self.undo_stack = None
        self.cache_idx=0

    def add_item(self, item: ExplororItem):
        self.setCurrentItem(item)
        self.addTopLevelItem(item)
        item.name_signal.connect(lambda name: self.set_name(item, name))

    def _release_name(self,name,base,num):
        current=self.name_allocator.get(name,False)
        if current:
            if current[0]==1:
                del current
                return
            current.append(0)
            return
        current=self.name_allocator.get(base,False)
        if current:
            if num==current[0]-1:
                current[0]-=1
                while current[0]-1 in current:
                    current.remove(current[0]-1)
                    current[0]-=1
                if current[0]==0:
                    del current
                return
            self.name_allocator[base].append(num)

    def _new_name(self,name,base,num):
        current=self.name_allocator.get(name,False)
        if current:
            num=current.pop()
            while len(current)==0:
                current.append(num+1)
                if name+f" {num}" in self.name_allocator:
                    num=current.pop()
            return name+f" {num}"
        current=self.name_allocator.get(base,False)
        if current and num<current[0]:
            if num in current[1:]:
                current.remove(num)
                return name
            num=current.pop()
            while len(current)==0:
                current.append(num+1)
                if base+f" {num}" in self.name_allocator:
                    num=current.pop()
            return base+f" {num}"
        self.name_allocator[name]=[1]
        return name
    
    def set_name(self, item, value):
        _int=re.compile(r" ([1-9]\d*)$")
        del_name=item.name
        if del_name==value:
            return
        serial_num=re.search(_int,value)
        base_name=re.sub(_int, "", value)
        del_serial_num=re.search(_int,del_name)
        del_base_name=re.sub(_int, "", del_name)
        serial_num= int(serial_num.group(1)) if serial_num else 0
        del_serial_num= int(del_serial_num.group(1)) if del_serial_num else 0

        self._release_name(del_name,del_base_name,del_serial_num)
        
        name=self._new_name(value,base_name,serial_num)

        item.rename(name)
        item.name_signal.edit_finish()
        item.name_signal.emit(name)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        try:
            self.currentItem().mouseMoveEvent(event)
        except AttributeError:
            pass

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        try:
            self.currentItem().mousePressEvent(event)
        except AttributeError:
            pass

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        try:
            self.currentItem().mouseReleaseEvent(event)
        except AttributeError:
            pass

    def get_absolute_last_item(self):
        count = self.topLevelItemCount()
        if count == 0:
            return None

        last_item = self.topLevelItem(count - 1)
        # 如果最後一個頂層節點展開了，就要找它的最後一個子節點
        while last_item.isExpanded() and last_item.childCount() > 0:
            last_item = last_item.child(last_item.childCount() - 1)
        return last_item

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            item = self.currentItem()
            if item and hasattr(item, 'id'):
                self.parent().request_delete(item.id)
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None or not hasattr(item, 'id'):
            return
        menu = QMenu(self)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.parent().request_delete(item.id))
        menu.addAction(delete_action)
        menu.exec_(event.globalPos())

    def required_visual_effects(self, pos):
        item = self.itemAt(pos)

        if item is None:
            if pos.y() < 0:
                return self.required_visual_effects(QPoint(1, 1))
            item = self.itemAt(QPoint(1, self.viewport().rect().height() - 1))
            if item is None:
                item = self.get_absolute_last_item()

        offset = (
            self.viewport().pos() + self.header().rect().bottomLeft() + QPoint(8, 0)
        )
        self.reference_item = item if item else None

        if item is None:
            rect = self.viewport().rect()
            return rect.topLeft() + offset, QSize(rect.width(), 5)
        rect = self.visualItemRect(item)

        if item.type() == 1000:
            if item is self.itemAt(
                1, pos.y() + self.visualItemRect(item).height() // 2
            ):
                return QPoint(rect.center().x(), rect.top()) + offset, QSize(
                    rect.width(), 5
                )
            else:
                return QPoint(rect.center().x(), rect.bottom()) + offset, QSize(
                    rect.width(), 5
                )
        return rect.center() + offset, rect.size()

    def drop(self, item):
        print(item.name, self.reference_item.name)
        if item is self.reference_item:
            return
        if self.reference_item.type() == 1001:
            self.reference_item.addChild(item)
        else:
            tmp = self.reference_item.level
            self.reference_item.level_signal.edit_finish()
            item.level_signal.edit_finish()
            self.reference_item.change_z_order(item.level)
            item.change_z_order(tmp)
        self.sortItems(0, Qt.AscendingOrder)


class Exploror(QWidget):
    receive = pyqtSignal(str, dict, int)
    rename = pyqtSignal(int, str)
    rearrange = pyqtSignal(int, int)
    inspection = pyqtSignal(int)
    copy = pyqtSignal(int)
    paste = pyqtSignal(int)
    cut = pyqtSignal(int)
    delete = pyqtSignal(int)
    item_selected = pyqtSignal(int)  # emits hash_id

    def __init__(self, undo_stack=None, id_stack=None, signal=None, parent=None):
        super().__init__(parent)
        self.setObjectName("explorer")
        self.setMaximumWidth(314)
        self._vlayout = QVBoxLayout(self)
        self._vlayout.setContentsMargins(7, 5, 7, 0)
        hlayout = QHBoxLayout(self)
        sort_label = QLabel("      Sort by")
        sort_label.setObjectName("explorerSortLabel")
        self.sort_option = QComboBox()
        self.sort_option.setObjectName("explorerCombo")
        self.sort_option.addItems(["layer", "name", "type"])
        self.sort_basis = "layer"
        self.sort_option.currentTextChanged.connect(self.sort_change)
        hlayout.addWidget(sort_label, 2)
        hlayout.addWidget(self.sort_option, 3)
        self._vlayout.addLayout(hlayout, 1)
        self.tree = ExplororTree(self)
        self.tree.undo_stack = undo_stack
        self._vlayout.addWidget(self.tree, 19)
        self.override = OverrideWidget(
            "drop here\nadd new item", "img/edit/exp_drag.png", self
        )
        self.setAcceptDrops(True)
        self.send_all = signal
        self.receive.connect(self.add_item)
        self.items = {}

        self.id_stack = id_stack
        self.tree.currentItemChanged.connect(self._on_current_item_changed)

    def _on_current_item_changed(self, current, previous):
        if current and hasattr(current, 'id'):
            self.item_selected.emit(int(current.id))

    def select_item(self, hash_id):
        item = self.items.get(str(hash_id))
        if item:
            self.tree.setCurrentItem(item)

    def sort_change(self, text):
        self.sort_basis = text
        self.tree.sortItems(0, Qt.AscendingOrder)

    def add_item(self, layer_type, signal_dict, hash_id):
        new = ExplororItem(layer_type, signal_dict, hash_id, self)
        self.tree.add_item(new)
        self.items[str(hash_id)] = new

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.override.resize(self.size())

    def dragEnterEvent(self, event):
        """拖拽進入時接受事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.is_drag_over = True
            self.override.hide()

    def dragMoveEvent(self, event):
        """拖拽移動時更新"""
        super().dragMoveEvent(event)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """拖拽離開時重置"""
        self.is_drag_over = False
        self.override.show()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text()
            try:
                self.tree.drop(self.items[text])
            except ValueError:
                pass
        self.override.hide()

    def request_delete(self, item_id):
        self.delete.emit(int(item_id))

    def required_visual_effects(self, event):
        pos = self.mapToGlobal(event.pos())
        pos = self.tree.viewport().mapFromGlobal(pos)
        pos, size = self.tree.required_visual_effects(pos)
        return pos, size


class DelExplorerItem(QUndoCommand):
    def __init__(self, item, tree: ExplororTree, items_dict: dict):
        super().__init__()
        self.item = item
        self.tree = tree
        self.items_dict = items_dict

    def redo(self):
        idx = self.tree.indexOfTopLevelItem(self.item)
        self.tree.takeTopLevelItem(idx)
        self.items_dict.pop(self.item.id, None)

    def undo(self):
        self.tree.addTopLevelItem(self.item)
        self.items_dict[self.item.id] = self.item
        self.tree.sortItems(0, Qt.AscendingOrder)