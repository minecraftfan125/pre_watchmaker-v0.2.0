"""
edit_watch.py — 錶盤編輯頁面
四個面板：物件總管、主要編輯區、Layer 選擇區、屬性編輯區。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import QMimeData, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import (
    QAction,
    QBrush, QColor, QDrag, QIcon, QPainter, QPen, QPixmap, QShortcut,
    QUndoCommand, QUndoStack, QKeySequence,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPushButton, QRubberBand, QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QSplitter, QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from special_ui import AttrFlowLayout, FlowLayout, WidgetManager
from special_ux import DragManager, accept_drop, drag_data
from components.layers import CanvasGroupLayer, LayerEllipseItem, LayerMixin, LayeredGraphicsScene, TextLayer
from components.utils import to_float
import components.attributes as _attrs
import components.common as _common


# ── 顏色 Token ──────────────────────────────────────────────────────────────
_LAYER_COLORS: dict[str, str] = {
    "baseLayer":             "#90CAF9",
    "animationWidget":       "#CE93D8",
    "textLayer":             "#80CBC4",
    "directionalLightLayer": "#FFD54F",
    "curvedTextLayer":       "#A5D6A7",
    "imageLayer":            "#EF9A9A",
    "tachymeterLayer":       "#FFAB91",
    "shapeLayer":            "#FFF176",
    "markerLayer":           "#80DEEA",
    "mapLayer":              "#B0BEC5",
    "slideshowLayer":        "#F48FB1",
    "textRingLayer":         "#E6EE9C",
    "roundedRectangleLayer": "#BCAAA4",
    "seriesLayer":           "#FFE082",
    "complicationLayer":     "#9FA8DA",
    "chartLayer":            "#4DB6AC",
    "imageCondLayer":        "#FFCCBC",
    "imageGifLayer":         "#F8BBD0",
    "progressLayer":         "#DCEDC8",
    "ringLayer":             "#B3E5FC",
    "markersHMLayer":        "#D7CCC8",
}

_GIT_STATE_BG: dict[str, str] = {
    "add":    "#26A5D6A7",
    "modify": "#26FFAB91",
    "delete": "#26EF9A9A",
}
_GIT_STATE_RGBA: dict[str, int] = {
    "add":    0x26A5D6A7,
    "modify": 0x26FFAB91,
    "delete": 0x26EF9A9A,
}
_GIT_STATE_ROLE    = Qt.ItemDataRole.UserRole + 2
_INSTANCE_ID_ROLE  = Qt.ItemDataRole.UserRole + 3
_HOVER_ROLE        = Qt.ItemDataRole.UserRole + 4
_VISIBLE_ROLE      = Qt.ItemDataRole.UserRole + 5

_EYE_ICON_SIZE = 16
_EYE_PIXMAP: "QPixmap | None" = None
_EYE_CROSS_PIXMAP: "QPixmap | None" = None

def _get_eye_pixmaps() -> "tuple[QPixmap, QPixmap]":
    global _EYE_PIXMAP, _EYE_CROSS_PIXMAP
    if _EYE_PIXMAP is None:
        _EYE_PIXMAP       = QPixmap(str(_IMG_EDIT_DIR / "eye-light.png"))
        _EYE_CROSS_PIXMAP = QPixmap(str(_IMG_EDIT_DIR / "eye-crossed-light.png"))
    return _EYE_PIXMAP, _EYE_CROSS_PIXMAP

_IMG_EDIT_DIR = Path(__file__).parent / "img" / "edit"

_ALL_OBJECTS: list[str] = [
    name for name in _attrs.__all__ if name != "watchSetting"
]


# ── 輔助工具 ─────────────────────────────────────────────────────────────────
def _make_icon(color: str, size: int = 28) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    m = 2
    p.drawEllipse(m, m, size - 2 * m, size - 2 * m)
    p.end()
    return px


def _load_obj_icon(obj_name: str, size: int = 40) -> QPixmap:
    px = QPixmap(str(_IMG_EDIT_DIR / f"btn_{obj_name}.png"))
    if not px.isNull():
        return px.scaled(size, size,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    obj = getattr(_attrs, obj_name, None)
    layer_type = ""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        layer_type = obj[0].get("TYPE", "")
    return _make_icon(_LAYER_COLORS.get(layer_type, "#888888"), size)


def _find_attrs_for_layer(layer_type: str) -> list[dict]:
    """從 attributes.py 找出 TYPE == layer_type 的物件屬性列表（去除 TYPE 項）。"""
    for name in _attrs.__all__:
        obj = getattr(_attrs, name, None)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            if obj[0].get("TYPE") == layer_type:
                return obj[1:]
    return []


def _find_attrs_for_object(object_type: str) -> list[dict]:
    """從 attributes.py 取得 object_type 的屬性列表（去除 TYPE 項）。"""
    obj = getattr(_attrs, object_type, None)
    if not isinstance(obj, list) or not obj:
        return []
    start = 1 if (isinstance(obj[0], dict) and "TYPE" in obj[0]) else 0
    return obj[start:]


# ── Layer 卡片 ───────────────────────────────────────────────────────────────
@drag_data("mime", lambda self: self._object_name)
class LayerCard(QWidget):
    """可拖曳的 object 卡片；無關閉按鈕，拖曳 payload 為 attributes.py 變數名稱。"""
    _SIZE = 56
    clicked_card = pyqtSignal(str)

    def __init__(self, object_name: str, parent=None):
        super().__init__(parent)
        self._object_name = object_name
        self._click_start = None
        self.mime = QMimeData()
        self.mime.setData("layer", b"")
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setObjectName("LayerCard")
        self.setToolTip(object_name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel()
        icon.setPixmap(_load_obj_icon(object_name, 40))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        self.setStyleSheet("""
            #LayerCard {
                background-color: #1E1E1E;
                border: 1px solid #1FFFFFFF;
                border-radius: 10px;
            }
            #LayerCard:hover {
                background-color: #272727;
                border-color: #3390CAF9;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._click_start is not None
                and (event.position().toPoint() - self._click_start).manhattanLength() <= 5):
            self.clicked_card.emit(self._object_name)
        self._click_start = None
        super().mouseReleaseEvent(event)


# ── GroupLayer ───────────────────────────────────────────────────────────────
@drag_data("mime", lambda self: self._object_type)
class GroupLayer(QWidget):
    """代表一個 Object 的緊湊卡片（圖示 + 關閉鈕）；拖曳 payload 為 object 類型字串。"""
    _SIZE = 56

    def __init__(self, object_type: str, parent=None):
        super().__init__(parent)
        self._object_type = object_type
        self.mime = QMimeData()
        self.mime.setData("object", b"")
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setObjectName("GroupLayer")
        self.setToolTip(object_type)

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(0)

        # 關閉按鈕列
        top_bar = QWidget()
        top_bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addStretch()

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(14, 14)
        self._close_btn.setFlat(True)
        self._close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._close_btn.clicked.connect(self._remove)
        top_layout.addWidget(self._close_btn)
        root.addWidget(top_bar)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(_make_icon("#90CAF9", 24))
        root.addWidget(icon)
        root.addStretch()

        self.setStyleSheet("""
            #GroupLayer {
                background-color: #222222;
                border: 1px solid #4290CAF9;
                border-radius: 8px;
            }
            #GroupLayer:hover { background-color: #2D2D2D; }
            QPushButton {
                color: #99FFFFFF;
                background: transparent;
                border: none;
                font-size: 10px;
                border-radius: 7px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #CF6679; color: #000000; }
        """)

    def _remove(self):
        parent = self.parentWidget()
        if parent:
            layout = parent.layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() is self:
                        layout.takeAt(i)
                        break
        self.setParent(None)
        self.deleteLater()
        if parent:
            parent.updateGeometry()
            parent.update()


# ── PanelHeader ──────────────────────────────────────────────────────────────
@drag_data("mime", lambda self: self.parent())
class PanelHeader(QWidget):
    """可拖曳的 panel 標題列；顯示面板名稱，不可關閉，可透過 splitter 隱藏。"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.mime = QMimeData()
        self.mime.setData("panel", b"")
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setObjectName("PanelHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            "color: #61FFFFFF;"
            " font-size: 10px;"
            " font-weight: 600;"
            " letter-spacing: 1px;"
            " background: transparent;"
        )
        layout.addWidget(lbl)
        layout.addStretch()

        self.setStyleSheet("""
            #PanelHeader {
                background-color: #1E1E1E;
                border-bottom: 1px solid #1FFFFFFF;
            }
        """)


# ── PanelWidget ──────────────────────────────────────────────────────────────
class PanelWidget(QWidget):
    """基礎面板：PanelHeader（含名稱）+ 子類可覆寫的內容區。"""

    _panel_name: str = ""  # 子類覆寫

    def __init__(self, manager: "PanelWidgetManager", parent=None):
        super().__init__(parent)
        self._manager = manager
        self._empty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PanelHeader(self._panel_name, self)
        root.addWidget(self._header)

        self._content = self._build_content()
        self._content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        root.addWidget(self._content)

    def _build_content(self) -> QWidget:
        """子類覆寫以提供實際內容；預設為深色佔位區。"""
        w = QWidget()
        w.setStyleSheet("background-color: #121212;")
        return w

    def _set_empty(self):
        self._empty = True

    def _close(self):
        pass  # 不可關閉，透過 splitter 隱藏


# ── 物件總管面板 ──────────────────────────────────────────────────────────────
class ObjectExplorerPanel(PanelWidget):
    """左側物件總管：顯示錶盤上已放置的 Object 場景樹。"""

    _panel_name = "Objects"

    def _build_content(self) -> QWidget:
        self._sort_mode: str = "layer"
        self._used_names: set[str] = set()

        container = QWidget()
        container.setStyleSheet("background: #121212;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── 排序 toolbar ──
        toolbar = QWidget()
        toolbar.setFixedHeight(34)
        toolbar.setObjectName("SortToolbar")
        toolbar.setStyleSheet("""
            #SortToolbar {
                background: #1A1A1A;
                border-bottom: 1px solid #1FFFFFFF;
            }
        """)
        tbar = QHBoxLayout(toolbar)
        tbar.setContentsMargins(8, 6, 8, 6)
        tbar.setSpacing(4)

        _sort_btn_qss = """
            QPushButton {
                background: transparent;
                color: #61FFFFFF;
                border: 1px solid #1FFFFFFF;
                border-radius: 11px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 10px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                color: #DEFFFFFF;
                border-color: #2AFFFFFF;
                background: #0AFFFFFF;
            }
            QPushButton:checked {
                background: #1A90CAF9;
                color: #90CAF9;
                border-color: #4490CAF9;
            }
            QPushButton:checked:hover { background: #2690CAF9; border-color: #6690CAF9; }
        """
        self._sort_btns: dict[str, QPushButton] = {}
        for key, label in [("name", "Name"), ("layer", "Layer"), ("type", "Type")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "layer")
            btn.setStyleSheet(_sort_btn_qss)
            btn.clicked.connect(lambda _, k=key: self._on_sort_btn(k))
            self._sort_btns[key] = btn
            tbar.addWidget(btn)
        tbar.addStretch()
        vbox.addWidget(toolbar)

        # ── 場景樹 ──
        self._tree = _ObjectTreeWidget(explorer=self)
        self._tree.setHeaderLabel("Objects")
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setStyleSheet("""
            QTreeWidget {
                background-color: #121212;
                color: #DEFFFFFF;
                border: none;
                font-size: 13px;
                outline: none;
            }
            QTreeWidget::item {
                height: 32px;
                padding-left: 4px;
                padding-right: 28px;
                border-radius: 0px;
            }
            QTreeWidget::item:hover { background-color: #1FFFFFFF; }
            QTreeWidget::item:selected {
                background-color: #1C90CAF9;
                border-left: 2px solid #90CAF9;
                color: #DEFFFFFF;
            }
            QTreeWidget::item:selected:hover {
                background-color: #2890CAF9;
            }
            QHeaderView::section {
                background-color: #1A1A1A;
                color: #61FFFFFF;
                font-weight: 500;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid #1FFFFFFF;
                padding: 0px 12px;
                height: 28px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #26FFFFFF;
                border-radius: 2px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4AFFFFFF;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: transparent; }
        """)
        vbox.addWidget(self._tree)
        self._block_tree_signal = False
        self._manager.instance_selected.connect(self._on_canvas_instance_selected)
        self._manager.instance_deselected.connect(self._on_canvas_instance_deselected)
        self._manager.multi_selection_changed.connect(self._on_multi_selection_changed)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        return container

    def _on_sort_btn(self, key: str) -> None:
        if key == self._sort_mode:
            if key == "layer":
                return
            # 再按一次 → 回到 Layer 模式
            self._sort_mode = "layer"
            for k, btn in self._sort_btns.items():
                btn.setChecked(k == "layer")
            self._tree.set_sort_mode("layer")
            self._apply_sort()
            return
        self._sort_mode = key
        for k, btn in self._sort_btns.items():
            btn.setChecked(k == key)
        self._tree.set_sort_mode(key)
        self._apply_sort()

    def _apply_sort(self) -> None:
        tree = self._tree
        n = tree.topLevelItemCount()
        items = [tree.takeTopLevelItem(0) for _ in range(n)]
        if self._sort_mode == "name":
            items.sort(key=lambda it: it.text(0).lower())
        elif self._sort_mode == "type":
            items.sort(key=lambda it: (it.data(0, Qt.ItemDataRole.UserRole) or "").lower())
        else:  # layer
            def _layer_key(it: QTreeWidgetItem) -> int:
                try:
                    return int((it.data(0, Qt.ItemDataRole.UserRole + 1) or {}).get("Layer", 0))
                except (ValueError, TypeError):
                    return 0
            items.sort(key=_layer_key)
        for item in items:
            tree.addTopLevelItem(item)

    def _unique_name(self, base: str) -> str:
        if base not in self._used_names:
            return base
        i = 2
        while f"{base} {i}" in self._used_names:
            i += 1
        return f"{base} {i}"

    def add_instance(self, name: str, object_type: str, values: dict,
                     instance_id: int) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self._tree)
        item.setText(0, name)
        item.setData(0, Qt.ItemDataRole.UserRole, object_type)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, values.copy())
        item.setData(0, _GIT_STATE_ROLE, "")
        item.setData(0, _INSTANCE_ID_ROLE, instance_id)
        item.setData(0, _VISIBLE_ROLE, True)
        self._used_names.add(name)
        self._apply_sort()
        return item

    def set_item_git_state(self, name: str, state: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.text(0) == name:
                item.setData(0, _GIT_STATE_ROLE, state)
                break

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        object_type     = item.data(0, Qt.ItemDataRole.UserRole)
        instance_values = item.data(0, Qt.ItemDataRole.UserRole + 1)
        instance_id     = item.data(0, _INSTANCE_ID_ROLE)
        # group node（無 instance_id）→ 選取所有子物件
        if instance_id is None and item.childCount() > 0:
            child_ids = []
            for i in range(item.childCount()):
                child = item.child(i)
                cid   = child.data(0, _INSTANCE_ID_ROLE)
                if cid is not None:
                    child_ids.append(cid)
            if child_ids:
                self._manager._selected_ids        = set(child_ids)
                self._manager._current_instance_id = child_ids[-1]
                self._manager.multi_selection_changed.emit(child_ids)
            return
        if object_type:
            if instance_values is not None and instance_id is not None:
                self._manager.instance_selected.emit(object_type, instance_values, instance_id)
            else:
                self._manager.object_selected.emit(object_type)

    def _on_canvas_instance_selected(self, object_type: str, values: dict, instance_id: int):
        inst = self._manager._instances.get(instance_id)
        if inst is None:
            return
        tree_item = inst.get("tree_item")
        if tree_item is not None:
            self._block_tree_signal = True
            self._tree.setCurrentItem(tree_item)
            self._block_tree_signal = False

    def _on_canvas_instance_deselected(self):
        self._block_tree_signal = True
        self._tree.clearSelection()
        self._block_tree_signal = False

    def _on_multi_selection_changed(self, ids: list) -> None:
        self._block_tree_signal = True
        self._tree.clearSelection()
        for iid in ids:
            inst = self._manager._instances.get(iid)
            if inst:
                ti = inst.get("tree_item")
                if ti is not None:
                    ti.setSelected(True)
        self._block_tree_signal = False

    def _on_tree_selection_changed(self) -> None:
        if self._block_tree_signal:
            return
        selected = self._tree.selectedItems()
        new_ids  = [
            it.data(0, _INSTANCE_ID_ROLE)
            for it in selected
            if it.data(0, _INSTANCE_ID_ROLE) is not None
        ]
        cur = set(new_ids)
        if cur == self._manager._selected_ids:
            return
        if not new_ids:
            self._manager._attr_panel._on_deselected()
        elif len(new_ids) == 1:
            iid  = new_ids[0]
            inst = self._manager._instances.get(iid)
            if inst:
                self._manager._selected_ids        = {iid}
                self._manager._current_instance_id = iid
                self._manager.instance_selected.emit(
                    inst["object_type"], inst["values"], iid
                )
                self._manager.multi_selection_changed.emit([iid])
        else:
            self._manager._selected_ids        = cur
            self._manager._current_instance_id = new_ids[-1]
            self._manager.multi_selection_changed.emit(new_ids)


# ── 主要編輯區面板 ────────────────────────────────────────────────────────────
class EditViewPanel(PanelWidget):
    """中間主要編輯區：圓形錶盤 GraphicsView，接受 Layer 與 Object drop。"""

    _panel_name = "Edit View"

    def _build_content(self) -> QWidget:
        self._canvas = _EditCanvas()
        self._canvas._scene.set_manager(self._manager)
        self._manager.attr_changed.connect(self._on_attr_changed)
        return _EditViewContent(self._canvas, self._manager)

    def _on_attr_changed(self, field: str, value):
        ids = self._manager._selected_ids
        targets = ids if len(ids) > 1 else {self._manager._current_instance_id} - {None}
        for iid in targets:
            inst = self._manager._instances.get(iid)
            if inst:
                ci = inst.get("canvas_item")
                if ci is not None:
                    ci.apply_attr(field, value)
        if self._manager._current_instance_id is None and field == "Background":
            self._canvas.set_bg_color(str(value))


# ── Layer 選擇面板 ────────────────────────────────────────────────────────────
@accept_drop("drop_mime")
class LayerPickerPanel(PanelWidget):
    """右上 Layer 選擇區：預載所有 layer 類型卡片，接受 Object drop 建立 GroupLayer。"""

    _panel_name = "Layers"

    def __init__(self, manager: "PanelWidgetManager", parent=None):
        self.drop_mime = QMimeData()
        self.drop_mime.setData("object", b"")
        super().__init__(manager, parent)

    def _build_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(0)
        scroll.setStyleSheet(_SCROLL_QSS)

        self._flow_container = QWidget()
        self._flow_container.setStyleSheet("background: #121212;")
        flow = FlowLayout(self._flow_container,
                          left_margin=8, right_margin=8, v_spacing=8)
        self._flow_container.setLayout(flow)

        for obj_name in _ALL_OBJECTS:
            card = LayerCard(obj_name, self._flow_container)
            card.clicked_card.connect(self._on_card_clicked)
            flow.addWidget(card)

        scroll.setWidget(self._flow_container)
        return scroll

    def _on_card_clicked(self, object_name: str):
        self._manager.place_object(object_name)

    def dropEvent(self, event):
        object_type = self.drop_data
        if not isinstance(object_type, str):
            return
        group = GroupLayer(object_type, self._flow_container)
        self._flow_container.layout().addWidget(group)
        self._flow_container.updateGeometry()


# ── 屬性編輯面板 ──────────────────────────────────────────────────────────────
@accept_drop("drop_mime")
class AttributePanel(PanelWidget):
    """右下屬性編輯區：顯示 Layer 或 Object 的欄位預設值（可編輯）。"""

    _panel_name = "Attributes"

    def __init__(self, manager: "PanelWidgetManager", parent=None):
        self.drop_mime = ["layer", "object"]
        super().__init__(manager, parent)
        self._show_attrs(_find_attrs_for_layer("baseLayer"), "baseLayer",
                         instance_values=manager._watch_settings)
        manager.object_selected.connect(self._on_object_selected)
        manager.instance_selected.connect(self._on_instance_selected)
        manager.multi_selection_changed.connect(self._on_multi_selection_changed)

    def _build_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(0)
        scroll.setStyleSheet(_SCROLL_QSS)

        self._attr_container = QWidget()
        self._attr_container.setStyleSheet("background: #121212;")
        self._attr_layout = AttrFlowLayout(
            self._attr_container, left_margin=8, right_margin=8, v_spacing=6,
        )
        self._attr_container.setLayout(self._attr_layout)
        scroll.setWidget(self._attr_container)
        return scroll

    def dropEvent(self, event):
        obj_name = self.drop_data
        if not isinstance(obj_name, str):
            return
        # LayerCard（"layer" mime）才套用 sticky template；
        # GroupLayer（"object" mime）永遠重置為（已儲存的）預設值
        is_layer_card = event.mimeData().hasFormat("layer")
        if (is_layer_card
                and self._manager._current_instance_id is None
                and self._manager._current_object_type == obj_name):
            return  # 同型別 template 模式，保留目前已編輯的值
        self._on_object_selected(obj_name)

    def _on_multi_selection_changed(self, ids: list) -> None:
        if len(ids) > 1:
            self._show_multi_attrs(ids)

    def _show_multi_attrs(self, ids: list) -> None:
        """多選時顯示共同欄位；不同值的欄位顯示「—」混合占位。"""
        # 收集各 id 的 object_type 與 values
        type_values: list[tuple[str, dict]] = []
        for iid in ids:
            inst = self._manager._instances.get(iid)
            if inst:
                type_values.append((inst["object_type"], inst["values"]))
        if not type_values:
            return

        # 找各 type 的欄位 schema（field_name → schema）
        def _attrs_schema(object_type: str) -> dict:
            attrs = _find_attrs_for_object(object_type)
            result = {}
            obj = getattr(_attrs, object_type, None)
            layer_type = ""
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                layer_type = obj[0].get("TYPE", "")
            schema_map: dict = getattr(_common, layer_type, {}) if layer_type else {}
            for d in attrs:
                for k, v in d.items():
                    if k == "description":
                        continue
                    result[k] = schema_map.get(k, "str")
            return result

        schemas_list = [_attrs_schema(ot) for ot, _ in type_values]

        # 求交集 field names（schema 也要相同型別）
        common_keys: list[str] = []
        if schemas_list:
            for key, schema in schemas_list[0].items():
                if all(s.get(key) == schema for s in schemas_list[1:]):
                    common_keys.append(key)

        # 建立 attrs + instance_values（用第一個 instance 的值）
        first_vals = type_values[0][1]
        first_schema_map = schemas_list[0] if schemas_list else {}
        common_attrs = [{k: first_vals.get(k, "")} for k in common_keys]

        # 清空並重建 attr layout（借用 _show_attrs 但只顯示交集欄位）
        layout = self._attr_layout
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        self._manager._editing_instance_ids.clear()
        self._multi_ids = ids[:]
        ids_snap = ids[:]
        for key in common_keys:
            if key == "Name":
                continue
            val    = first_vals.get(key, "")
            schema = first_schema_map.get(key, "str")
            w = _AttrFieldWidget(key, val, schema, self._attr_container)
            # 若各 instance 值不一致，顯示「—」
            all_vals = [tv[1].get(key) for tv in type_values]
            if len(set(str(v) for v in all_vals)) > 1:
                w.set_mixed()
            w.value_changed.connect(self._manager.attr_changed)
            w.value_changed.connect(lambda _f, _v: self._attr_container.adjustSize())
            w.value_committed.connect(self._on_multi_field_committed)
            w.value_changed.connect(
                lambda _f, _v, _s=ids_snap: self._manager._editing_instance_ids.update(_s))
            w.editing_done.connect(
                lambda _s=ids_snap: self._manager._editing_instance_ids.difference_update(_s))
            layout.addWidget(w)
        self._attr_container.adjustSize()
        self._attr_container.update()

    def _on_multi_field_committed(self, field: str, old_val, new_val) -> None:
        ids = getattr(self, "_multi_ids", [])
        if not ids:
            return
        self._manager.undo_stack.beginMacro(f"Multi Edit {field}")
        for iid in ids:
            inst = self._manager._instances.get(iid)
            if inst is None or field not in inst["values"]:
                continue
            prev = inst["values"][field]
            inst["values"][field] = new_val
            ci = inst.get("canvas_item")
            if ci is not None:
                ci.apply_attr(field, new_val)
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            self._manager.undo_stack.push(
                _AttrChangeCommand(self._manager, iid, field, prev, new_val)
            )
        self._manager.undo_stack.endMacro()
        self._show_multi_attrs(ids)

    def _on_deselected(self):
        """取消選取 → 面板歸回 baseLayer 頁面，並同步 overlay 與 tree 選取狀態。"""
        if (self._manager._current_instance_id is None
                and self._manager._current_object_type is not None):
            self._manager._type_defaults[self._manager._current_object_type] = (
                self.get_current_values()
            )
        if self._manager._current_instance_id is not None:
            self._manager.instance_deselected.emit()
        self._manager._current_instance_id = None
        self._manager._current_object_type = None
        self._manager._selected_ids.clear()
        self._manager.multi_selection_changed.emit([])
        self._show_attrs(_find_attrs_for_layer("baseLayer"), "baseLayer",
                         instance_values=self._manager._watch_settings)

    def _on_object_selected(self, object_type: str):
        # 切換型別前，若目前是 template 模式，儲存目前已編輯的值
        if (self._manager._current_instance_id is None
                and self._manager._current_object_type is not None
                and self._manager._current_object_type != object_type):
            self._manager._type_defaults[self._manager._current_object_type] = (
                self.get_current_values()
            )
        if self._manager._current_instance_id is not None:
            self._manager.instance_deselected.emit()
        self._manager._current_instance_id = None
        self._manager._current_object_type = object_type
        attrs = _find_attrs_for_object(object_type)
        obj = getattr(_attrs, object_type, None)
        layer_type = ""
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            layer_type = obj[0].get("TYPE", "")
        saved = self._manager._type_defaults.get(object_type)
        self._show_attrs(attrs, layer_type, instance_values=saved)

    def _on_instance_selected(self, object_type: str, values: dict, instance_id: int):
        self._manager._current_instance_id = instance_id
        self._manager._current_object_type = object_type
        # 單選時同步（多選路徑由 multi_selection_changed 處理）
        if len(self._manager._selected_ids) <= 1:
            self._manager._selected_ids = {instance_id}
        attrs = _find_attrs_for_object(object_type)
        obj = getattr(_attrs, object_type, None)
        layer_type = ""
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            layer_type = obj[0].get("TYPE", "")
        self._show_attrs(attrs, layer_type, instance_values=values)

    def get_current_values(self) -> dict:
        values: dict = {}
        layout = self._attr_layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, _AttrFieldWidget) and not w._is_group:
                    values[w._field_name] = w.get_value()
        return values

    def _show_attrs(self, attrs: list[dict], layer_type: str = "",
                    instance_values: dict | None = None):
        self._manager._editing_instance_ids.clear()
        schema: dict = getattr(_common, layer_type, {}) if layer_type else {}
        layout = self._attr_layout
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        iid = self._manager._current_instance_id
        for attr_dict in attrs:
            for key, val in attr_dict.items():
                if key == "description":
                    continue
                actual_val = instance_values.get(key, val) if instance_values else val
                field_schema = schema.get(key, "str") if isinstance(schema, dict) else "str"
                w = _AttrFieldWidget(key, actual_val, field_schema, self._attr_container)
                w.value_changed.connect(self._manager.attr_changed)
                w.value_committed.connect(self._on_field_committed)
                w.lua_script_requested.connect(self._on_lua_requested)
                if iid is not None:
                    w.value_changed.connect(
                        lambda _f, _v, _i=iid: self._manager._editing_instance_ids.add(_i))
                    w.editing_done.connect(
                        lambda _i=iid: self._manager._editing_instance_ids.discard(_i))
                layout.addWidget(w)
        self._attr_container.updateGeometry()
        self._attr_container.update()

    def _on_field_committed(self, field: str, old_val, new_val):
        """屬性欄位 commit 時呼叫；處理名稱衝突並 push undo command。"""
        instance_id = self._manager._current_instance_id
        if instance_id is None:
            object_type = self._manager._current_object_type
            if object_type is None:
                # watchSetting 模式
                self._manager._watch_settings[field] = new_val
                self._manager.undo_stack.push(
                    _WatchSettingChangeCommand(self._manager, field, old_val, new_val)
                )
                return
            # Template 模式：更新 _type_defaults 並 push undo
            self._manager._type_defaults.setdefault(object_type, {})[field] = new_val
            self._manager.undo_stack.push(
                _TemplateAttrChangeCommand(self._manager, object_type, field, old_val, new_val)
            )
            return
        inst = self._manager._instances.get(instance_id)
        if inst is None:
            return

        actual_new_val = new_val

        if field == "Name":
            explorer     = self._manager._obj_explorer
            current_name = inst["values"].get("Name", "")
            explorer._used_names.discard(current_name)
            unique_name  = explorer._unique_name(str(new_val))
            explorer._used_names.add(unique_name)
            actual_new_val = unique_name
            inst["values"]["Name"] = unique_name
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setText(0, unique_name)
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            if unique_name != new_val:
                self.update_field("Name", unique_name)
        else:
            inst["values"][field] = actual_new_val
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())

        self._manager.undo_stack.push(
            _AttrChangeCommand(self._manager, instance_id, field, old_val, actual_new_val)
        )

    def update_field(self, field: str, value):
        """程式端更新指定欄位的顯示值（undo/redo 用）。"""
        for i in range(self._attr_layout.count()):
            item = self._attr_layout.itemAt(i)
            if item and isinstance(item.widget(), _AttrFieldWidget):
                w = item.widget()
                if not w._is_group and w._field_name == field:
                    w.set_value(value)
                    return

    def _on_lua_requested(self, field_name: str, value: str,
                          numeric: bool, expression_mode: bool):
        """">_" 按鈕點擊：組裝 lua_requested signal 並向上傳遞。"""
        inst_id = self._manager._current_instance_id
        if inst_id is not None:
            inst     = self._manager._instances.get(inst_id)
            obj_name = inst["values"].get("Name", "?") if inst else "?"
        else:
            obj_name = self._manager._current_object_type or "?"
            inst_id  = -1
        self._manager.lua_requested.emit(
            inst_id, obj_name, field_name, value, numeric, expression_mode)


# ── 屬性欄位卡片 ──────────────────────────────────────────────────────────────
_FONT_NAMES: list[str] = sorted({
    p.stem for p in (Path(__file__).parent / "font").iterdir()
    if p.suffix.lower() in (".ttf", ".fnt")
}) if (Path(__file__).parent / "font").is_dir() else []

_FIELD_QSS = """
    #AttrField {
        background-color: #1E1E1E;
        border: 1px solid #1FFFFFFF;
        border-radius: 8px;
    }
"""

_LABEL_QSS = "color: #99FFFFFF; font-size: 11px; font-weight: 500;"
_CTRL_QSS  = "color: #DEFFFFFF; font-size: 12px;"

_INPUT_QSS = """
    QLineEdit {
        background: #121212;
        border: 1px solid #1FFFFFFF;
        border-radius: 6px;
        color: #DEFFFFFF;
        font-size: 12px;
        padding: 3px 8px;
        selection-background-color: #90CAF9;
        selection-color: #000000;
        min-height: 24px;
    }
    QLineEdit:hover { border-color: #26FFFFFF; }
    QLineEdit:focus { border-color: #90CAF9; }
"""

_COMBO_QSS = """
    QComboBox {
        background: #121212;
        border: 1px solid #1FFFFFFF;
        border-radius: 6px;
        color: #DEFFFFFF;
        font-size: 12px;
        padding: 3px 24px 3px 8px;
        min-height: 26px;
    }
    QComboBox:hover { border-color: #26FFFFFF; }
    QComboBox:on { border-color: #90CAF9; }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 20px;
        border: none;
        border-left: 1px solid #1FFFFFFF;
        border-radius: 0 6px 6px 0;
        background: #1A1A1A;
    }
    QComboBox QAbstractItemView {
        background: #272727;
        border: 1px solid #26FFFFFF;
        border-radius: 6px;
        color: #DEFFFFFF;
        selection-background-color: #2090CAF9;
        selection-color: #DEFFFFFF;
        outline: none;
        padding: 4px;
    }
    QComboBox QAbstractItemView::item {
        padding: 4px 8px;
        border-radius: 4px;
        min-height: 24px;
    }
    QComboBox QAbstractItemView::item:hover { background-color: #3490CAF9; }
"""

_SPINBOX_QSS = """
    QSpinBox {
        background: #121212;
        border: 1px solid #1FFFFFFF;
        border-radius: 6px;
        color: #DEFFFFFF;
        font-size: 12px;
        padding: 3px 4px 3px 8px;
        min-height: 26px;
    }
    QSpinBox:hover { border-color: #26FFFFFF; }
    QSpinBox:focus { border-color: #90CAF9; }
    QSpinBox::up-button {
        border: none;
        border-left: 1px solid #1FFFFFFF;
        border-radius: 0 6px 0 0;
        width: 18px;
        background: #1A1A1A;
    }
    QSpinBox::down-button {
        border: none;
        border-left: 1px solid #1FFFFFFF;
        border-top: 1px solid #1FFFFFFF;
        border-radius: 0 0 6px 0;
        width: 18px;
        background: #1A1A1A;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background: #272727;
    }
"""

_SLIDER_QSS = """
    QSlider::groove:horizontal {
        height: 4px;
        background: #2AFFFFFF;
        border-radius: 2px;
    }
    QSlider::sub-page:horizontal {
        background: #90CAF9;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        width: 14px;
        height: 14px;
        margin: -5px 0;
        background: #90CAF9;
        border-radius: 7px;
        border: 2px solid #1E1E1E;
    }
    QSlider::handle:horizontal:hover { background: #BBDEFB; }
"""

_CHECK_QSS = """
    QCheckBox {
        color: #DEFFFFFF;
        font-size: 12px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 2px solid #61FFFFFF;
        border-radius: 3px;
        background: transparent;
    }
    QCheckBox::indicator:hover { border-color: #DEFFFFFF; }
    QCheckBox::indicator:checked {
        background-color: #90CAF9;
        border-color: #90CAF9;
    }
    QCheckBox::indicator:checked:hover {
        background-color: #BBDEFB;
        border-color: #BBDEFB;
    }
"""

_BTN_QSS = """
    QPushButton {
        background-color: transparent;
        color: #90CAF9;
        border: 1px solid #4490CAF9;
        border-radius: 6px;
        font-size: 11px;
        padding: 3px 8px;
        min-height: 24px;
    }
    QPushButton:hover {
        background-color: #1490CAF9;
        border-color: #90CAF9;
    }
    QPushButton:pressed { background-color: #2890CAF9; }
"""


class _NoScrollComboBox(QComboBox):
    """禁止滾輪切換選項的 ComboBox，避免在屬性面板捲動時誤觸。"""
    def wheelEvent(self, event):
        event.ignore()


def _schema_type(schema) -> str:
    """將 schema 對應到視覺型別字串，供 AttrFlowLayout 分群使用。"""
    if schema == "widget":        return "group"
    if schema == "str":           return "str"
    if schema == "text":          return "text"
    if schema == "script":        return "script"
    if schema == "bool":          return "bool"
    if schema == "color":         return "color"
    if schema in ("font", "file"): return schema
    if isinstance(schema, list):  return "combo"
    if isinstance(schema, tuple) and len(schema) == 3:
        return "range_slider" if schema[2] == 1 else "range_input"
    return "str"


class _AttrFieldWidget(QWidget):
    """單一屬性欄位卡片，依 schema 型別顯示對應控制元件。"""

    value_changed        = pyqtSignal(str, object)
    value_committed      = pyqtSignal(str, object, object)   # field, 舊值, 新值
    editing_done         = pyqtSignal()                       # editingFinished 後（無論有無改動）
    lua_script_requested = pyqtSignal(str, str, bool, bool)   # field_name, current_value, numeric, expression_mode

    def __init__(self, field_name: str, value, schema, parent=None):
        super().__init__(parent)
        self.setObjectName("AttrField")
        self.setStyleSheet(_FIELD_QSS)

        self._field_name      = field_name
        self._field_value     = value
        self._committed_value = value    # 上次 commit 的值，供 undo 基線使用
        self._in_set_value    = False    # 程式呼叫 set_value 時，抑制 commit/preview 訊號
        self._is_group        = (schema == "widget")
        self._field_type      = _schema_type(schema)
        self._git_state: str  = ""
        if self._is_group:
            self._build_widget_group(field_name, value)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        else:
            self._build_field(field_name, value, schema)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.value_changed.connect(lambda _f, v: setattr(self, '_field_value', v))

    def get_value(self):
        return self._field_value

    def set_git_state(self, state: str) -> None:
        self._git_state = state
        bg = _GIT_STATE_BG.get(state, "#1E1E1E")
        self.setStyleSheet(f"""
            #AttrField {{
                background-color: {bg};
                border: 1px solid #1FFFFFFF;
                border-radius: 8px;
            }}
        """)

    def _on_commit(self, new_val):
        """控件 commit 時（editingFinished / sliderReleased / 即時控件）呼叫。"""
        if self._in_set_value:
            return
        if new_val != self._committed_value:
            old = self._committed_value
            self._committed_value = new_val
            self.value_committed.emit(self._field_name, old, new_val)
        self.editing_done.emit()

    def set_value(self, val):
        """程式端靜默更新值（undo/redo、衝突修正用）；不 emit 任何訊號。"""
        self._field_value     = val
        self._committed_value = val
        self._in_set_value    = True
        try:
            fn = getattr(self, '_set_value_fn', None)
            if callable(fn):
                fn(val)
        finally:
            self._in_set_value = False

    def set_mixed(self) -> None:
        """顯示多選混合值佔位「—」。"""
        fn = getattr(self, "_set_mixed_fn", None)
        if callable(fn):
            fn()
        else:
            fn = getattr(self, "_set_value_fn", None)
            if callable(fn):
                fn("")

    # ── 一般欄位 ──────────────────────────────────────────────────

    def _build_field(self, name: str, value, schema):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        lbl = QLabel(name)
        lbl.setStyleSheet(_LABEL_QSS)
        lbl.setWordWrap(False)
        root.addWidget(lbl)
        root.addWidget(self._make_control(value, schema, name))

    def _make_control(self, value, schema, name: str = "") -> QWidget:
        if schema == "str":
            w = QLineEdit(str(value) if value else "")
            w.setStyleSheet(_INPUT_QSS)
            w.setFixedWidth(180)
            w.textChanged.connect(
                lambda t: None if self._in_set_value else self.value_changed.emit(name, t))
            w.editingFinished.connect(lambda: self._on_commit(w.text()))
            self._set_value_fn = lambda v: w.setText(str(v))
            self._set_mixed_fn = lambda: (w.clear(), w.setPlaceholderText("—"))
            return w

        if schema in ("text", "script"):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            edit = QLineEdit(str(value) if value else "")
            edit.setFixedWidth(140)
            edit.setStyleSheet(_INPUT_QSS)
            edit.textChanged.connect(
                lambda t: None if self._in_set_value else self.value_changed.emit(name, t))
            edit.editingFinished.connect(lambda: self._on_commit(edit.text()))
            self._set_value_fn = lambda v: edit.setText(str(v))
            btn = QPushButton(">_")
            btn.setFixedSize(30, 28)
            btn.setStyleSheet(_BTN_QSS)
            btn.setToolTip("Open Lua script editor")
            btn.clicked.connect(
                lambda _c=False, _n=name, _s=schema: self.lua_script_requested.emit(
                    _n, str(self._field_value or ""), False, _s != "script"))
            h.addWidget(edit)
            h.addWidget(btn)
            return container

        if schema == "bool":
            w = QCheckBox()
            w.setChecked(bool(value))
            w.setStyleSheet(_CHECK_QSS)
            def _toggled(checked):
                if self._in_set_value:
                    return
                self.value_changed.emit(name, checked)
                self._on_commit(checked)
            w.toggled.connect(_toggled)
            self._set_value_fn = lambda v: w.setChecked(bool(v))
            self._set_mixed_fn = lambda: (w.setTristate(True), w.setCheckState(Qt.CheckState.PartiallyChecked))
            return w

        if schema == "color":
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            hex_val = str(value).lstrip('#') if value else "ffffff"
            swatch = QPushButton()
            swatch.setFixedSize(28, 28)
            swatch.setStyleSheet(
                f"background-color: #{hex_val}; border-radius: 6px;"
                " border: 2px solid #2AFFFFFF;"
            )
            edit = QLineEdit(hex_val)
            edit.setFixedWidth(82)
            edit.setStyleSheet(_INPUT_QSS)
            edit.setPlaceholderText("rrggbb")
            def _update_swatch(t: str):
                swatch.setStyleSheet(
                    f"background-color: #{t}; border-radius: 6px;"
                    " border: 2px solid #2AFFFFFF;"
                )
                if not self._in_set_value:
                    self.value_changed.emit(name, t)
            edit.textChanged.connect(_update_swatch)
            edit.editingFinished.connect(lambda: self._on_commit(edit.text()))
            self._set_value_fn = lambda v: edit.setText(str(v).lstrip('#'))

            def _pick():
                # parent=None：QColorDialog 無父層，不繼承 swatch 的裸屬性 QSS
                dlg = QColorDialog(QColor(f"#{edit.text()}"))
                if dlg.exec():
                    c = dlg.selectedColor()
                    if c.isValid():
                        hv = c.name()[1:]
                        edit.setText(hv)
                        self._on_commit(hv)
            swatch.clicked.connect(_pick)
            h.addWidget(swatch)
            h.addWidget(edit)
            return container

        if isinstance(schema, tuple) and len(schema) == 3:
            mn, mx, default = schema
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            try:
                cur = int(value)
            except (ValueError, TypeError):
                cur = int(default)
            if default == 1:
                spin = QSpinBox()
                spin.setRange(int(mn), int(mx))
                spin.setValue(cur)
                spin.setStyleSheet(_SPINBOX_QSS)
                spin.valueChanged.connect(
                    lambda v: None if self._in_set_value else self.value_changed.emit(name, v))
                spin.editingFinished.connect(lambda: self._on_commit(spin.value()))
                self._set_value_fn = lambda v: spin.setValue(int(v))
                self._set_mixed_fn = lambda: (spin.setSpecialValueText("—"), spin.setValue(spin.minimum() - 1))
                if mx - mn <= 100:
                    slider = QSlider(Qt.Orientation.Horizontal)
                    slider.setRange(int(mn), int(mx))
                    slider.setValue(cur)
                    slider.setFixedWidth(110)
                    slider.setStyleSheet(_SLIDER_QSS)
                    spin.setFixedWidth(64)
                    slider.valueChanged.connect(spin.setValue)
                    spin.valueChanged.connect(slider.setValue)
                    slider.sliderReleased.connect(lambda: self._on_commit(spin.value()))
                    h.addWidget(slider)
                else:
                    spin.setFixedWidth(84)
                h.addWidget(spin)
            else:
                edit = QLineEdit(str(cur))
                edit.setFixedWidth(90)
                edit.setStyleSheet(_INPUT_QSS)
                edit.textChanged.connect(
                    lambda t: None if self._in_set_value else self.value_changed.emit(name, t))
                edit.editingFinished.connect(lambda: self._on_commit(edit.text()))
                self._set_value_fn = lambda v: edit.setText(str(v))
                btn = QPushButton(">_")
                btn.setFixedSize(30, 28)
                btn.setStyleSheet(_BTN_QSS)
                btn.setToolTip("Open Lua script editor")
                btn.clicked.connect(
                    lambda _c=False, _n=name: self.lua_script_requested.emit(
                        _n, str(self._field_value or ""), True, True))
                h.addWidget(edit)
                h.addWidget(btn)
            return container

        if isinstance(schema, list):
            w = _NoScrollComboBox()
            items = [str(x) for x in schema]
            w.addItems(items)
            sv = str(value) if value is not None else ""
            if sv in items:
                w.setCurrentText(sv)
            w.setFixedWidth(180)
            w.setStyleSheet(_COMBO_QSS)
            def _combo_changed(t):
                if self._in_set_value:
                    return
                self.value_changed.emit(name, t)
                self._on_commit(t)
            w.currentTextChanged.connect(_combo_changed)
            self._set_value_fn = lambda v: w.setCurrentText(str(v))
            return w

        if schema == "font":
            w = _NoScrollComboBox()
            w.addItems(_FONT_NAMES)
            sv = str(value) if value else ""
            if sv in _FONT_NAMES:
                w.setCurrentText(sv)
            w.setFixedWidth(180)
            w.setStyleSheet(_COMBO_QSS)
            def _font_changed(t):
                if self._in_set_value:
                    return
                self.value_changed.emit(name, t)
                self._on_commit(t)
            w.currentTextChanged.connect(_font_changed)
            self._set_value_fn = lambda v: w.setCurrentText(str(v))
            return w

        if schema == "file":
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            edit = QLineEdit(str(value) if value else "")
            edit.setFixedWidth(120)
            edit.setStyleSheet(_INPUT_QSS)
            edit.textChanged.connect(
                lambda t: None if self._in_set_value else self.value_changed.emit(name, t))
            edit.editingFinished.connect(lambda: self._on_commit(edit.text()))
            self._set_value_fn = lambda v: edit.setText(str(v))
            btn = QPushButton("Browse")
            btn.setFixedWidth(58)
            btn.setStyleSheet(_BTN_QSS)

            def _browse():
                path, _ = QFileDialog.getOpenFileName(btn, "Select File")
                if path:
                    edit.setText(path)
                    self._on_commit(path)
            btn.clicked.connect(_browse)
            h.addWidget(edit)
            h.addWidget(btn)
            return container

        lbl = QLabel(str(value))
        lbl.setStyleSheet(_CTRL_QSS)
        return lbl

    # ── 可展開子群組（schema == "widget"）────────────────────────

    def _build_widget_group(self, name: str, sub_list):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QPushButton(f"▶  {name}")
        header.setFlat(True)
        header.setFixedHeight(34)
        header.setStyleSheet("""
            QPushButton {
                color: #90CAF9;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
                padding: 0 10px;
                background-color: #1490CAF9;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2090CAF9; }
        """)
        root.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 4, 8, 8)
        body_layout.setSpacing(6)
        body.hide()

        sub_schema: dict = getattr(_common, "animationWidget", {})
        for item_dict in (sub_list if isinstance(sub_list, list) else []):
            if not isinstance(item_dict, dict):
                continue
            for k, v in item_dict.items():
                if k in ("TYPE", "description"):
                    continue
                body_layout.addWidget(
                    _AttrFieldWidget(k, v, sub_schema.get(k, "str"), body)
                )

        root.addWidget(body)
        self._expanded = False

        def _toggle():
            self._expanded = not self._expanded
            header.setText(f"{'▼' if self._expanded else '▶'}  {name}")
            body.setVisible(self._expanded)
            self.adjustSize()
            self.updateGeometry()
            p = self.parentWidget()
            if p and p.layout():
                p.layout().invalidate()
                p.updateGeometry()
                p.update()

        header.clicked.connect(_toggle)


# ── EditView 內容容器（畫布 + 浮動日/夜間切換按鈕）────────────────────────────
class _EditViewContent(QWidget):
    """包裹 _EditCanvas，並在右上角疊加日/夜間切換按鈕。"""

    _SUN_PIXMAP:  "QPixmap | None" = None
    _MOON_PIXMAP: "QPixmap | None" = None

    def __init__(self, canvas: "_EditCanvas", manager: "PanelWidgetManager", parent=None):
        super().__init__(parent)
        self._manager = manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(canvas)

        self._toggle_btn = QPushButton(self)
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setToolTip("Toggle Day / Night Mode")
        self._toggle_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 14px; }
            QPushButton:hover { background: #1AFFFFFF; }
        """)
        self._toggle_btn.clicked.connect(self._on_toggle)
        self._update_icon()
        manager.dark_mode_changed.connect(lambda _: self._update_icon())

    @classmethod
    def _get_sun_pixmap(cls) -> QPixmap:
        if cls._SUN_PIXMAP is None:
            cls._SUN_PIXMAP = QPixmap(str(_IMG_EDIT_DIR / "sun-amber.png"))
        return cls._SUN_PIXMAP

    @classmethod
    def _get_moon_pixmap(cls) -> QPixmap:
        if cls._MOON_PIXMAP is None:
            cls._MOON_PIXMAP = QPixmap(str(_IMG_EDIT_DIR / "moon-blue.png"))
        return cls._MOON_PIXMAP

    def _update_icon(self) -> None:
        px = self._get_moon_pixmap() if self._manager.is_dark_mode else self._get_sun_pixmap()
        icon_size = min(20, px.width(), px.height())
        self._toggle_btn.setIcon(QIcon(px))
        self._toggle_btn.setIconSize(px.size().scaled(icon_size, icon_size,
                                                       Qt.AspectRatioMode.KeepAspectRatio))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_btn()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reposition_btn()

    def _reposition_btn(self) -> None:
        margin = 8
        btn = self._toggle_btn
        btn.move(self.width() - btn.width() - margin, margin)
        btn.raise_()

    def _on_toggle(self) -> None:
        self._manager.is_dark_mode = not self._manager.is_dark_mode
        self._manager.dark_mode_changed.emit(self._manager.is_dark_mode)


# ── 錶盤 GraphicsView ─────────────────────────────────────────────────────────
class _EditCanvas(QGraphicsView):
    """圓形錶盤畫布：接受 Layer（定座標加入）與 Object（展開所有 layers）drop。"""
    _R = 256

    def __init__(self, parent=None):
        super().__init__(parent)
        r = self._R
        self._scene = LayeredGraphicsScene(self)
        self._rubberband: "QRubberBand | None" = None
        self._rb_origin: QPoint = QPoint()
        self._scene.setSceneRect(-r - 30, -r - 30, 2 * (r + 30), 2 * (r + 30))
        self.setScene(self._scene)

        # 背景圓框：addEllipse 走 C++ 路徑不觸發 addItem override，手動置底
        self._bg_ellipse = self._scene.addEllipse(
            QRectF(-r, -r, 2 * r, 2 * r),
            QPen(QColor("#1FFFFFFF"), 1),
            QBrush(QColor("#000000")),
        )
        self._bg_ellipse.setZValue(-1.0)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setAcceptDrops(True)
        self.setFrameStyle(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply_outer_bg(QColor("#000000"))

        QTimer.singleShot(0, self._fit)

    def _apply_outer_bg(self, watch_color: QColor) -> None:
        """依錶盤色計算外框背景：錶盤色 × 20% + 基底 #121212 × 80%。
        深色錶盤幾乎不變，亮色錶盤外框帶柔和色調，提供視覺過渡。
        """
        base = 0x12
        t = 0.20
        r = int(watch_color.red()   * t + base * (1 - t))
        g = int(watch_color.green() * t + base * (1 - t))
        b = int(watch_color.blue()  * t + base * (1 - t))
        outer = QColor(r, g, b)
        self.setBackgroundBrush(QBrush(outer))
        self.setStyleSheet(f"background: {outer.name()}; border: none;")

    def set_bg_color(self, hex_str: str) -> None:
        color = QColor(f"#{hex_str.lstrip('#')}")
        if color.isValid():
            self._bg_ellipse.setBrush(QBrush(color))
            self._apply_outer_bg(color)

    def _fit(self):
        r = self._R + 30
        self.fitInView(QRectF(-r, -r, 2 * r, 2 * r),
                       Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    # ── Drag & Drop ──────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if (event.mimeData().hasFormat("layer")
                or event.mimeData().hasFormat("object")):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if (event.mimeData().hasFormat("layer")
                or event.mimeData().hasFormat("object")):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        data = DragManager.get_data()
        if event.mimeData().hasFormat("layer") and isinstance(data, str):
            self._scene._manager.place_object(data, pos)
        elif event.mimeData().hasFormat("object") and isinstance(data, str):
            self._place_object(data, pos)
        event.acceptProposedAction()

    def _place_from_values(self, object_name: str, values: dict) -> "TextLayer | LayerEllipseItem | None":
        obj = getattr(_attrs, object_name, None)
        layer_type = "baseLayer"
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            layer_type = obj[0].get("TYPE", "baseLayer")
        if layer_type == "textLayer":
            item = TextLayer(values)
            self._scene.addItem(item)
            return item
        x = to_float(values.get("X", 0))
        y = to_float(values.get("Y", 0))
        return self._place_layer(layer_type, QPointF(x, y))

    def _place_layer(self, layer_type: str, pos: QPointF) -> "LayerEllipseItem":
        color = QColor(_LAYER_COLORS.get(layer_type, "#888888"))
        color.setAlpha(200)
        sz = 40
        item = LayerEllipseItem(
            QRectF(pos.x() - sz / 2, pos.y() - sz / 2, sz, sz),
            QPen(color.lighter(140), 1),
            QBrush(color),
        )
        item.setToolTip(layer_type)
        self._scene.addItem(item)
        return item

    def _place_object(self, object_type: str, pos: QPointF):
        obj = getattr(_attrs, object_type, None)
        if not isinstance(obj, list) or not obj:
            return
        layer_type = obj[0].get("TYPE", "baseLayer") if isinstance(obj[0], dict) else "baseLayer"
        for i in range(min(3, len(obj) - 1)):
            self._place_layer(layer_type, QPointF(pos.x() + i * 8, pos.y() + i * 8))

    # ── 鍵盤 / 框選 ──────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            manager = self._scene._manager
            if manager is None or not manager._selected_ids:
                return
            selected_items = [
                manager._instances[iid]["tree_item"]
                for iid in list(manager._selected_ids)
                if iid in manager._instances
            ]
            if selected_items and hasattr(manager, "_obj_explorer"):
                manager._obj_explorer._tree._do_delete(selected_items)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        scene_pos = self.mapToScene(event.pos())
        manager   = self._scene._manager
        hit_layer = None
        if manager is not None:
            for item in self._scene.items(scene_pos):
                ov  = getattr(self._scene, "_overlay", None)
                mov = getattr(self._scene, "_multi_overlay", None)
                if ov and item is ov:
                    continue
                if mov and item is mov:
                    continue
                if isinstance(item, LayerMixin):
                    hit_layer = item
                    break
        # 空白處且不是 Ctrl → 啟動 rubber-band
        # 但若點擊在單選 overlay 的有效區域（把手 / 旋轉區 / 框內），交給 scene 處理
        if hit_layer is None and not ctrl:
            ov = getattr(self._scene, "_overlay", None)
            if ov and ov.isVisible():
                lp = ov.mapFromScene(scene_pos)
                if (ov._hit_handle(lp) >= 0
                        or ov._is_rotation_zone(lp)
                        or ov._rect.contains(lp)):
                    super().mousePressEvent(event)
                    return
            mov = getattr(self._scene, "_multi_overlay", None)
            if mov and mov.isVisible():
                if (mov._hit_move_handle(scene_pos)
                        or mov._hit_scale_handle(scene_pos) >= 0
                        or mov._union_rect.contains(scene_pos)):
                    super().mousePressEvent(event)
                    return
            self._rb_origin  = event.pos()
            self._rubberband = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self._rubberband.setGeometry(QRect(self._rb_origin, QSize()))
            self._rubberband.show()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._rubberband is not None:
            self._rubberband.setGeometry(
                QRect(self._rb_origin, event.pos()).normalized()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._rubberband is not None and event.button() == Qt.MouseButton.LeftButton:
            rb_rect    = QRect(self._rb_origin, event.pos()).normalized()
            scene_rect = self.mapToScene(rb_rect).boundingRect()
            self._rubberband.hide()
            self._rubberband = None
            manager = self._scene._manager
            if manager is None:
                event.accept()
                return
            hit_items = [
                i for i in self._scene.items(
                    scene_rect, Qt.ItemSelectionMode.IntersectsItemBoundingRect
                )
                if isinstance(i, LayerMixin)
                and not isinstance(i, CanvasGroupLayer)
            ]
            new_ids = [
                iid for iid, inst in manager._instances.items()
                if inst.get("canvas_item") in hit_items
            ]
            if new_ids:
                manager._selected_ids        = set(new_ids)
                manager._current_instance_id = new_ids[-1]
                manager.multi_selection_changed.emit(new_ids)
                # 如果只選了 1 個，也 emit instance_selected 讓 attr panel 更新
                if len(new_ids) == 1:
                    iid  = new_ids[0]
                    inst = manager._instances[iid]
                    manager.instance_selected.emit(
                        inst["object_type"], inst["values"], iid
                    )
            else:
                manager._attr_panel._on_deselected()
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ── Undo Commands ────────────────────────────────────────────────────────────
class _AttrChangeCommand(QUndoCommand):
    """單一屬性變更的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", instance_id: int,
                 field: str, old_val, new_val):
        super().__init__(f"Change {field}")
        self._manager = manager
        self._iid     = instance_id
        self._field   = field
        self._old     = old_val
        self._new     = new_val
        self._skip_first = True  # 首次 push 時狀態已由呼叫端套用，跳過

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, val):
        inst = self._manager._instances.get(self._iid)
        if inst is None:
            return
        if self._field == "Name":
            explorer = self._manager._obj_explorer
            old_name = inst["values"].get("Name", "")
            explorer._used_names.discard(old_name)
            explorer._used_names.add(str(val))
        inst["values"][self._field] = val
        ci = inst.get("canvas_item")
        if ci is not None:
            ci.apply_attr(self._field, val)
        ti = inst.get("tree_item")
        if ti is not None:
            if self._field == "Name":
                ti.setText(0, str(val))
            ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
        if self._manager._current_instance_id == self._iid:
            self._manager._attr_panel.update_field(self._field, val)


class _WatchSettingChangeCommand(QUndoCommand):
    """watchSetting 欄位變更的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", field: str, old_val, new_val):
        super().__init__(f"Change watch {field}")
        self._manager    = manager
        self._field      = field
        self._old        = old_val
        self._new        = new_val
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, val):
        self._manager._watch_settings[self._field] = val
        if (self._manager._current_instance_id is None
                and self._manager._current_object_type is None):
            self._manager._attr_panel.update_field(self._field, val)
        if self._field == "Watch name":
            self._manager.setWindowTitle(str(val))
        elif self._field == "Background":
            self._manager._edit_view._canvas.set_bg_color(str(val))


class _TemplateAttrChangeCommand(QUndoCommand):
    """Template 模式下單一屬性欄位變更的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", object_type: str,
                 field: str, old_val, new_val):
        super().__init__(f"Change default {field}")
        self._manager     = manager
        self._object_type = object_type
        self._field       = field
        self._old         = old_val
        self._new         = new_val
        self._skip_first  = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, val):
        td = self._manager._type_defaults
        td.setdefault(self._object_type, {})[self._field] = val
        if (self._manager._current_instance_id is None
                and self._manager._current_object_type == self._object_type):
            self._manager._attr_panel.update_field(self._field, val)


class _PlaceCommand(QUndoCommand):
    """放置物件的 undo/redo 命令。持有 canvas item / tree item 參考，undo 移除、redo 重新加入。"""

    def __init__(self, manager: "PanelWidgetManager", instance_id: int):
        inst = manager._instances[instance_id]
        name = inst["values"].get("Name", "")
        super().__init__(f"Place {name}")
        self._manager     = manager
        self._iid         = instance_id
        self._canvas_item = inst["canvas_item"]
        self._tree_item   = inst["tree_item"]
        self._object_type = inst["object_type"]
        self._values      = inst["values"].copy()
        self._tree_index  = -1
        self._skip_first  = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._manager._edit_view._canvas._scene.addItem(self._canvas_item)
        tree = self._manager._obj_explorer._tree
        idx  = max(0, self._tree_index)
        tree.insertTopLevelItem(idx, self._tree_item)
        self._manager._instances[self._iid] = {
            "canvas_item": self._canvas_item,
            "tree_item":   self._tree_item,
            "object_type": self._object_type,
            "values":      self._values.copy(),
        }
        self._manager._obj_explorer._used_names.add(self._values.get("Name", ""))

    def undo(self):
        was_current = self._manager._current_instance_id == self._iid
        self._manager._edit_view._canvas._scene.removeItem(self._canvas_item)
        explorer = self._manager._obj_explorer
        tree     = explorer._tree
        self._tree_index = tree.indexOfTopLevelItem(self._tree_item)
        explorer._block_tree_signal = True
        tree.takeTopLevelItem(self._tree_index)
        explorer._block_tree_signal = False
        del self._manager._instances[self._iid]
        explorer._used_names.discard(self._values.get("Name", ""))
        if was_current:
            self._manager._selected_ids.clear()
            self._manager.instance_deselected.emit()
            self._manager.multi_selection_changed.emit([])
            self._manager._current_instance_id = None
            self._manager._attr_panel._on_object_selected(self._object_type)


class _SwapLayerCommand(QUndoCommand):
    """Layer 模式拖曳交換兩物件 Layer 值的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", src_id: int, tgt_id: int,
                 src_layer: int, tgt_layer: int):
        super().__init__("Swap Layer")
        self._manager   = manager
        self._src_id    = src_id
        self._tgt_id    = tgt_id
        self._src_layer = src_layer
        self._tgt_layer = tgt_layer
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._apply(self._tgt_layer, self._src_layer)

    def undo(self):
        self._apply(self._src_layer, self._tgt_layer)

    def _apply(self, new_src_layer: int, new_tgt_layer: int) -> None:
        manager = self._manager
        src_inst = manager._instances.get(self._src_id)
        tgt_inst = manager._instances.get(self._tgt_id)
        if src_inst is None or tgt_inst is None:
            return

        src_inst["values"]["Layer"] = new_src_layer
        tgt_inst["values"]["Layer"] = new_tgt_layer

        for inst, val in ((src_inst, new_src_layer), (tgt_inst, new_tgt_layer)):
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            ci = inst.get("canvas_item")
            if ci is not None:
                ci.apply_attr("Layer", val)

        explorer = manager._obj_explorer
        if explorer._sort_mode == "layer":
            explorer._apply_sort()

        cur_id = manager._current_instance_id
        if cur_id == self._src_id:
            manager._attr_panel.update_field("Layer", new_src_layer)
        elif cur_id == self._tgt_id:
            manager._attr_panel.update_field("Layer", new_tgt_layer)


# ── 右鍵選單 Undo 命令 ────────────────────────────────────────────────────────

class _DeleteCommand(QUndoCommand):
    """刪除物件 instance 的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", instance_id: int):
        inst = manager._instances[instance_id]
        name = inst["values"].get("Name", "")
        super().__init__(f"Delete {name}")
        self._manager     = manager
        self._iid         = instance_id
        self._canvas_item = inst["canvas_item"]
        self._tree_item   = inst["tree_item"]
        self._object_type = inst["object_type"]
        self._values      = inst["values"].copy()
        ti                = self._tree_item
        self._parent_item = ti.parent()
        if self._parent_item is None:
            self._tree_index = manager._obj_explorer._tree.indexOfTopLevelItem(ti)
        else:
            self._tree_index = self._parent_item.indexOfChild(ti)
        self._skip_first  = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        was_current = self._manager._current_instance_id == self._iid
        scene    = self._manager._edit_view._canvas._scene
        explorer = self._manager._obj_explorer
        scene.removeItem(self._canvas_item)
        tree = explorer._tree
        explorer._block_tree_signal = True
        if self._parent_item is None:
            i = tree.indexOfTopLevelItem(self._tree_item)
            if i >= 0:
                tree.takeTopLevelItem(i)
        else:
            i = self._parent_item.indexOfChild(self._tree_item)
            if i >= 0:
                self._parent_item.takeChild(i)
        explorer._block_tree_signal = False
        del self._manager._instances[self._iid]
        explorer._used_names.discard(self._values.get("Name", ""))
        if was_current:
            self._manager._attr_panel._on_deselected()

    def undo(self):
        self._manager._edit_view._canvas._scene.addItem(self._canvas_item)
        self._manager._instances[self._iid] = {
            "canvas_item": self._canvas_item,
            "tree_item":   self._tree_item,
            "object_type": self._object_type,
            "values":      self._values.copy(),
        }
        self._manager._obj_explorer._used_names.add(self._values.get("Name", ""))
        if self._parent_item is None:
            self._manager._obj_explorer._tree.insertTopLevelItem(
                self._tree_index, self._tree_item)
        else:
            self._parent_item.insertChild(self._tree_index, self._tree_item)


class _RenameCommand(QUndoCommand):
    """重新命名的 undo/redo 命令（instance item 或 group node 均適用）。"""

    def __init__(self, manager: "PanelWidgetManager", tree_item: QTreeWidgetItem,
                 old_name: str, new_name: str):
        super().__init__(f"Rename to {new_name}")
        self._manager   = manager
        self._tree_item = tree_item
        self._iid       = tree_item.data(0, _INSTANCE_ID_ROLE)
        self._old       = old_name
        self._new       = new_name
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, name: str) -> None:
        if self._iid is not None:
            inst = self._manager._instances.get(self._iid)
            if inst is None:
                return
            old = inst["values"].get("Name", "")
            self._manager._obj_explorer._used_names.discard(old)
            self._manager._obj_explorer._used_names.add(name)
            inst["values"]["Name"] = name
            self._tree_item.setText(0, name)
            self._tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            if self._manager._current_instance_id == self._iid:
                self._manager._attr_panel.update_field("Name", name)
        else:
            self._tree_item.setText(0, name)


class _CreateGroupCommand(QUndoCommand):
    """建立純視覺群組的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", group_item: QTreeWidgetItem,
                 items_data: list):
        # items_data: list of (item, original_parent, original_idx)
        super().__init__("Create Group")
        self._manager    = manager
        self._group_item = group_item
        self._items_data = items_data
        self._group_idx  = manager._obj_explorer._tree.indexOfTopLevelItem(group_item)
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        tree = self._manager._obj_explorer._tree
        for item, orig_parent, _ in reversed(self._items_data):
            if orig_parent is None:
                i = tree.indexOfTopLevelItem(item)
                if i >= 0:
                    tree.takeTopLevelItem(i)
            else:
                i = orig_parent.indexOfChild(item)
                if i >= 0:
                    orig_parent.takeChild(i)
        for item, _, _ in self._items_data:
            self._group_item.addChild(item)
        tree.insertTopLevelItem(self._group_idx, self._group_item)
        tree.expandItem(self._group_item)

    def undo(self):
        tree = self._manager._obj_explorer._tree
        while self._group_item.childCount():
            self._group_item.takeChild(0)
        i = tree.indexOfTopLevelItem(self._group_item)
        if i >= 0:
            tree.takeTopLevelItem(i)
        for item, orig_parent, orig_idx in reversed(self._items_data):
            if orig_parent is None:
                tree.insertTopLevelItem(orig_idx, item)
            else:
                orig_parent.insertChild(orig_idx, item)


class _LeaveGroupCommand(QUndoCommand):
    """脫離群組的 undo/redo 命令。"""

    def __init__(self, manager: "PanelWidgetManager", items_data: list):
        # items_data: list of (item, group_item, original_idx_in_group)
        super().__init__("Leave Group")
        self._manager    = manager
        self._items_data = items_data
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        tree = self._manager._obj_explorer._tree
        for item, group_item, _ in self._items_data:
            i = group_item.indexOfChild(item)
            if i >= 0:
                group_item.takeChild(i)
            tree.addTopLevelItem(item)

    def undo(self):
        tree = self._manager._obj_explorer._tree
        for item, group_item, idx in reversed(self._items_data):
            i = tree.indexOfTopLevelItem(item)
            if i >= 0:
                tree.takeTopLevelItem(i)
            group_item.insertChild(idx, item)


class _MoveMultiCommand(QUndoCommand):
    """多選移動的 undo/redo 命令。deltas: {iid: (old_x, old_y, new_x, new_y)}"""

    def __init__(self, manager: "PanelWidgetManager", deltas: dict):
        super().__init__("Move Multi")
        self._manager = manager
        self._deltas  = deltas  # {iid: (ox, oy, nx, ny)}
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        for iid, (_, _, nx, ny) in self._deltas.items():
            self._apply(iid, int(nx), int(ny))

    def undo(self):
        for iid, (ox, oy, _, _) in self._deltas.items():
            self._apply(iid, int(ox), int(oy))

    def _apply(self, iid: int, x: int, y: int) -> None:
        inst = self._manager._instances.get(iid)
        if inst is None:
            return
        inst["values"]["X"] = x
        inst["values"]["Y"] = y
        ci = inst.get("canvas_item")
        if ci is not None:
            ci.apply_attr("X", x)
            ci.apply_attr("Y", y)
        ti = inst.get("tree_item")
        if ti is not None:
            ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
        if self._manager._current_instance_id == iid:
            self._manager._attr_panel.update_field("X", x)
            self._manager._attr_panel.update_field("Y", y)


class _DeleteGroupNodeCommand(QUndoCommand):
    """刪除純視覺群組節點的 undo/redo 命令（子 instance 由各自的 _DeleteCommand 處理）。"""

    def __init__(self, tree: "QTreeWidget", group_item: QTreeWidgetItem):
        super().__init__("Delete Group")
        self._tree       = tree
        self._group_item = group_item
        self._tree_index = tree.indexOfTopLevelItem(group_item)
        self._skip_first = True

    def redo(self):
        if self._skip_first:
            self._skip_first = False
            return
        i = self._tree.indexOfTopLevelItem(self._group_item)
        if i >= 0:
            self._tree.takeTopLevelItem(i)

    def undo(self):
        self._tree.insertTopLevelItem(self._tree_index, self._group_item)
        self._tree.expandItem(self._group_item)


# ── 物件總管 TreeWidget ───────────────────────────────────────────────────────
class _GitStateDelegate(QStyledItemDelegate):
    """在 QTreeWidget item 上疊加 git_state 半透明色塊、Layer 模式拖曳 hover 色塊，以及顯示/隱藏圖示。"""

    def __init__(self, tree: "_ObjectTreeWidget"):
        super().__init__(tree)
        self._tree = tree

    @staticmethod
    def _eye_rect(item_rect: QRect) -> QRect:
        size   = _EYE_ICON_SIZE
        margin = 8
        x = item_rect.right() - size - margin
        y = item_rect.center().y() - size // 2
        return QRect(x, y, size, size)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        state = index.data(_GIT_STATE_ROLE)
        if state in _GIT_STATE_RGBA:
            painter.save()
            painter.fillRect(option.rect, QColor.fromRgba(_GIT_STATE_RGBA[state]))
            painter.restore()
        if index.data(_HOVER_ROLE):
            painter.save()
            painter.fillRect(option.rect, QColor.fromRgba(0x3090CAF9))
            painter.restore()
        is_visible = index.data(_VISIBLE_ROLE)
        if is_visible is None:
            return
        eye_px, cross_px = _get_eye_pixmaps()
        px = eye_px if is_visible else cross_px
        if px is None or px.isNull():
            return
        eye_rect = self._eye_rect(option.rect)
        scaled = px.scaled(
            _EYE_ICON_SIZE, _EYE_ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        if is_hovered:
            painter.setOpacity(0.85 if is_visible else 0.70)
        else:
            painter.setOpacity(0.25 if is_visible else 0.42)
        painter.drawPixmap(eye_rect, scaled)
        painter.restore()


class _ObjectTreeWidget(QTreeWidget):
    """自訂拖曳的場景樹；節點 UserRole 存放 object_type 字串。"""

    def __init__(self, explorer: "ObjectExplorerPanel | None" = None, parent=None):
        super().__init__(parent)
        self._explorer = explorer
        self._drag_start: "QPoint | None" = None
        self._drag_source_item: QTreeWidgetItem | None = None
        self._hover_target: QTreeWidgetItem | None = None
        self._sort_mode: str = "layer"
        self.setDragEnabled(False)  # 關閉內建拖曳，用 DragManager
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setItemDelegate(_GitStateDelegate(self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._renaming_item:     QTreeWidgetItem | None = None
        self._renaming_old_name: str = ""
        self.itemChanged.connect(self._on_item_changed)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos  = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None:
                eye_rect = _GitStateDelegate._eye_rect(self.visualItemRect(item))
                if eye_rect.contains(pos):
                    self._toggle_visibility(item)
                    return
            elif self._explorer is not None:
                self._explorer._manager._attr_panel._on_deselected()
            self._drag_start = pos
        super().mousePressEvent(event)

    def _toggle_visibility(self, item: QTreeWidgetItem) -> None:
        current = item.data(0, _VISIBLE_ROLE)
        if current is None:
            return
        new_visible = not current
        item.setData(0, _VISIBLE_ROLE, new_visible)
        if self._explorer is None:
            return
        instance_id = item.data(0, _INSTANCE_ID_ROLE)
        if instance_id is None:
            return
        inst = self._explorer._manager._instances.get(instance_id)
        if inst is None:
            return
        ci = inst.get("canvas_item")
        if ci is not None:
            ci.setVisible(new_visible)
        self.viewport().update()

    def set_sort_mode(self, mode: str) -> None:
        self._sort_mode = mode

    def _item_has_layer(self, item: QTreeWidgetItem) -> bool:
        """判斷 tree item 對應的 instance 是否具有 Layer 屬性。"""
        if self._explorer is None:
            return False
        instance_id = item.data(0, _INSTANCE_ID_ROLE)
        if instance_id is None:
            return False
        inst = self._explorer._manager._instances.get(instance_id)
        if inst is None:
            return False
        return "Layer" in inst["values"]

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton
                and self._drag_start is not None):
            if (event.position().toPoint() - self._drag_start).manhattanLength() > 5:
                node = self.itemAt(self._drag_start)
                if node is not None:
                    object_type = node.data(0, Qt.ItemDataRole.UserRole)
                    if object_type:
                        self._drag_source_item = node
                        mime = QMimeData()
                        mime.setData("object", b"")
                        DragManager.set_data(object_type)
                        drag = QDrag(self)
                        drag.setMimeData(mime)
                        self._drag_start = None
                        drag.exec(Qt.DropAction.CopyAction)
                        DragManager.clear()
                        self._drag_source_item = None
                        return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
        super().mouseReleaseEvent(event)

    # ── Layer 模式 intra-tree drag-and-drop ──────────────────────

    def dragEnterEvent(self, event):
        if (self._sort_mode == "layer"
                and event.source() is self
                and event.mimeData().hasFormat("object")
                and self._drag_source_item is not None
                and self._item_has_layer(self._drag_source_item)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if (self._sort_mode == "layer"
                and event.source() is self
                and event.mimeData().hasFormat("object")
                and self._drag_source_item is not None
                and self._item_has_layer(self._drag_source_item)):
            target = self.itemAt(event.position().toPoint())
            if target is not None and self._item_has_layer(target):
                self._set_hover(target)
                event.acceptProposedAction()
            else:
                self._set_hover(None)
                event.ignore()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_hover(None)
        event.accept()

    def dropEvent(self, event):
        self._set_hover(None)
        if (self._sort_mode == "layer"
                and event.source() is self
                and event.mimeData().hasFormat("object")):
            target = self.itemAt(event.position().toPoint())
            source = self._drag_source_item
            if target is not None and source is not None and target is not source:
                self._swap_items(source, target)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _set_hover(self, item: QTreeWidgetItem | None) -> None:
        if self._hover_target is not None and self._hover_target is not item:
            self._hover_target.setData(0, _HOVER_ROLE, False)
        self._hover_target = item
        if item is not None:
            item.setData(0, _HOVER_ROLE, True)
        self.viewport().update()

    def _swap_items(self, source: QTreeWidgetItem, target: QTreeWidgetItem) -> None:
        if self._explorer is None:
            return
        manager = self._explorer._manager
        src_id = source.data(0, _INSTANCE_ID_ROLE)
        tgt_id = target.data(0, _INSTANCE_ID_ROLE)
        if src_id is None or tgt_id is None:
            return
        src_inst = manager._instances.get(src_id)
        tgt_inst = manager._instances.get(tgt_id)
        if src_inst is None or tgt_inst is None:
            return
        if "Layer" not in src_inst["values"] or "Layer" not in tgt_inst["values"]:
            return

        try:
            src_layer = int(src_inst["values"].get("Layer", 0))
        except (ValueError, TypeError):
            src_layer = 0
        try:
            tgt_layer = int(tgt_inst["values"].get("Layer", 0))
        except (ValueError, TypeError):
            tgt_layer = 0

        # 立即套用交換
        src_inst["values"]["Layer"] = tgt_layer
        tgt_inst["values"]["Layer"] = src_layer
        source.setData(0, Qt.ItemDataRole.UserRole + 1, src_inst["values"].copy())
        target.setData(0, Qt.ItemDataRole.UserRole + 1, tgt_inst["values"].copy())

        src_ci = src_inst.get("canvas_item")
        tgt_ci = tgt_inst.get("canvas_item")
        if src_ci is not None:
            src_ci.apply_attr("Layer", tgt_layer)
        if tgt_ci is not None:
            tgt_ci.apply_attr("Layer", src_layer)

        self._explorer._apply_sort()

        cur_id = manager._current_instance_id
        if cur_id == src_id:
            manager._attr_panel.update_field("Layer", tgt_layer)
        elif cur_id == tgt_id:
            manager._attr_panel.update_field("Layer", src_layer)

        manager.undo_stack.push(_SwapLayerCommand(manager, src_id, tgt_id, src_layer, tgt_layer))

    # ── 右鍵選單 ──────────────────────────────────────────────────

    @staticmethod
    def _is_group_node(item: QTreeWidgetItem) -> bool:
        return item.data(0, _INSTANCE_ID_ROLE) is None

    def contextMenuEvent(self, event) -> None:
        pos          = event.pos()
        clicked_item = self.itemAt(pos)
        if clicked_item is None:
            return
        if clicked_item not in self.selectedItems():
            self.clearSelection()
            clicked_item.setSelected(True)

        selected       = self.selectedItems()
        instance_items = [it for it in selected if not self._is_group_node(it)]
        items_in_group = [it for it in instance_items if it.parent() is not None]
        hidden_items   = [it for it in instance_items if it.data(0, _VISIBLE_ROLE) is False]
        has_instance   = bool(instance_items)
        has_hidden     = bool(hidden_items)

        menu = QMenu(self)
        menu.setStyleSheet(_MENU_QSS)

        act_rename = QAction("Rename", self)
        act_rename.setEnabled(len(selected) == 1)
        act_rename.triggered.connect(lambda: self._do_rename(selected[0]))
        menu.addAction(act_rename)

        menu.addSeparator()

        act_create_group = QAction("Create Group", self)
        act_create_group.setEnabled(
            len(selected) >= 2 and len(instance_items) == len(selected))
        act_create_group.triggered.connect(lambda: self._do_create_group(instance_items[:]))
        menu.addAction(act_create_group)

        act_leave_group = QAction("Leave Group", self)
        act_leave_group.setEnabled(bool(items_in_group))
        act_leave_group.triggered.connect(lambda: self._do_leave_group(items_in_group[:]))
        menu.addAction(act_leave_group)

        menu.addSeparator()

        act_show = QAction("Show", self)
        act_show.setEnabled(has_instance and has_hidden)
        act_show.triggered.connect(lambda: self._do_set_visibility(instance_items[:], True))
        menu.addAction(act_show)

        act_hide = QAction("Hide", self)
        act_hide.setEnabled(has_instance and not has_hidden)
        act_hide.triggered.connect(lambda: self._do_set_visibility(instance_items[:], False))
        menu.addAction(act_hide)

        menu.addSeparator()

        act_delete = QAction("Delete", self)
        act_delete.triggered.connect(lambda: self._do_delete(selected[:]))
        menu.addAction(act_delete)

        menu.exec(event.globalPos())

    # ── Rename ────────────────────────────────────────────────────

    def _do_rename(self, item: QTreeWidgetItem) -> None:
        self._renaming_item     = item
        self._renaming_old_name = item.text(0)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.editItem(item, 0)

    def closeEditor(self, editor, hint) -> None:
        super().closeEditor(editor, hint)
        if self._renaming_item is not None:
            self._renaming_item.setFlags(
                self._renaming_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._renaming_item = None

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or self._renaming_item is not item:
            return
        new_name = item.text(0).strip()
        old_name = self._renaming_old_name
        if not new_name or new_name == old_name:
            if not new_name:
                item.setText(0, old_name)
            return
        if self._explorer is None:
            return
        manager = self._explorer._manager
        iid     = item.data(0, _INSTANCE_ID_ROLE)
        if iid is not None:
            inst = manager._instances.get(iid)
            if inst is None:
                return
            self._explorer._used_names.discard(old_name)
            unique = self._explorer._unique_name(new_name)
            self._explorer._used_names.add(unique)
            inst["values"]["Name"] = unique
            item.setText(0, unique)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            if manager._current_instance_id == iid:
                manager._attr_panel.update_field("Name", unique)
            manager.undo_stack.push(_RenameCommand(manager, item, old_name, unique))
        else:
            manager.undo_stack.push(_RenameCommand(manager, item, old_name, new_name))

    # ── Delete ────────────────────────────────────────────────────

    def _do_delete(self, selected: list) -> None:
        if not self._explorer:
            return
        manager = self._explorer._manager

        group_nodes:  list[QTreeWidgetItem]  = []
        instance_map: dict[int, QTreeWidgetItem] = {}
        for item in selected:
            if self._is_group_node(item):
                group_nodes.append(item)
                for i in range(item.childCount()):
                    child = item.child(i)
                    iid   = child.data(0, _INSTANCE_ID_ROLE)
                    if iid is not None:
                        instance_map[iid] = child
            else:
                iid = item.data(0, _INSTANCE_ID_ROLE)
                if iid is not None:
                    instance_map[iid] = item

        if not instance_map and not group_nodes:
            return

        # 捕捉刪除前位置（建立命令），再執行實際刪除
        instance_cmds   = [_DeleteCommand(manager, iid) for iid in instance_map]
        group_node_cmds = [_DeleteGroupNodeCommand(self, gn) for gn in group_nodes]

        scene    = manager._edit_view._canvas._scene
        explorer = self._explorer
        explorer._block_tree_signal = True
        for iid, tree_item in instance_map.items():
            inst = manager._instances.pop(iid, None)
            if inst is None:
                continue
            parent = tree_item.parent()
            if parent is None:
                i = self.indexOfTopLevelItem(tree_item)
                if i >= 0:
                    self.takeTopLevelItem(i)
            else:
                i = parent.indexOfChild(tree_item)
                if i >= 0:
                    parent.takeChild(i)
            ci = inst.get("canvas_item")
            if ci:
                scene.removeItem(ci)
            explorer._used_names.discard(inst["values"].get("Name", ""))
            if manager._current_instance_id == iid:
                manager._attr_panel._on_deselected()

        for gn in group_nodes:
            i = self.indexOfTopLevelItem(gn)
            if i >= 0:
                self.takeTopLevelItem(i)
        explorer._block_tree_signal = False

        # instance_cmds 先推、group_node_cmds 後推
        # → undo 順序相反：group 節點先恢復，再恢復其子 items
        use_macro = len(instance_cmds) + len(group_node_cmds) > 1
        if use_macro:
            manager.begin_macro("Delete")
        for cmd in instance_cmds:
            manager.undo_stack.push(cmd)
        for cmd in group_node_cmds:
            manager.undo_stack.push(cmd)
        if use_macro:
            manager.end_macro()

    # ── Create Group ──────────────────────────────────────────────

    def _do_create_group(self, instance_items: list) -> None:
        if not self._explorer or len(instance_items) < 2:
            return
        manager = self._explorer._manager

        items_data: list = []
        min_top_idx = self.topLevelItemCount()
        for item in instance_items:
            parent = item.parent()
            if parent is None:
                idx         = self.indexOfTopLevelItem(item)
                min_top_idx = min(min_top_idx, idx)
            else:
                idx = parent.indexOfChild(item)
            items_data.append((item, parent, idx))

        group_item = QTreeWidgetItem()
        group_item.setText(0, "Group")
        group_item.setData(0, _INSTANCE_ID_ROLE, None)
        group_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

        for item, parent, _ in reversed(items_data):
            if parent is None:
                i = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(i)
            else:
                i = parent.indexOfChild(item)
                parent.takeChild(i)

        for item, _, _ in items_data:
            group_item.addChild(item)

        self.insertTopLevelItem(min_top_idx, group_item)
        self.expandItem(group_item)

        manager.undo_stack.push(_CreateGroupCommand(manager, group_item, items_data))
        self._do_rename(group_item)

    # ── Leave Group ───────────────────────────────────────────────

    def _do_leave_group(self, items_in_group: list) -> None:
        if not self._explorer:
            return
        manager    = self._explorer._manager
        items_data: list = []
        for item in items_in_group:
            parent = item.parent()
            if parent is not None:
                items_data.append((item, parent, parent.indexOfChild(item)))

        if not items_data:
            return

        for item, parent, _ in items_data:
            i = parent.indexOfChild(item)
            if i >= 0:
                parent.takeChild(i)
            self.addTopLevelItem(item)

        manager.undo_stack.push(_LeaveGroupCommand(manager, items_data))

    # ── Show / Hide ───────────────────────────────────────────────

    def _do_set_visibility(self, instance_items: list, visible: bool) -> None:
        if not self._explorer:
            return
        manager = self._explorer._manager
        for item in instance_items:
            if item.data(0, _VISIBLE_ROLE) is None:
                continue
            item.setData(0, _VISIBLE_ROLE, visible)
            iid = item.data(0, _INSTANCE_ID_ROLE)
            if iid is not None:
                inst = manager._instances.get(iid)
                if inst:
                    ci = inst.get("canvas_item")
                    if ci:
                        ci.setVisible(visible)
        self.viewport().update()


# ── 共用樣式 ─────────────────────────────────────────────────────────────────
_SCROLL_QSS = """
    QScrollArea { background: #121212; border: none; }
    QScrollBar:vertical {
        background: transparent; width: 5px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #1FFFFFFF; border-radius: 2px; min-height: 24px;
    }
    QScrollBar::handle:vertical:hover { background: #3AFFFFFF; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

_SPLITTER_QSS = (
    "QSplitter::handle { background: #1FFFFFFF; }"
    "QSplitter::handle:hover { background: #2AFFFFFF; }"
    "QSplitter::handle:horizontal { width: 1px; }"
    "QSplitter::handle:vertical   { height: 1px; }"
)

_MENU_QSS = """
    QMenu {
        background-color: #272727;
        border: 1px solid #1FFFFFFF;
        border-radius: 6px;
        padding: 4px;
        color: #DEFFFFFF;
        font-size: 13px;
    }
    QMenu::item {
        padding: 5px 24px 5px 12px;
        border-radius: 4px;
        min-width: 140px;
    }
    QMenu::item:selected { background-color: #1C90CAF9; }
    QMenu::item:disabled { color: #61FFFFFF; }
    QMenu::separator {
        height: 1px;
        background: #1FFFFFFF;
        margin: 3px 6px;
    }
"""


# ── PanelWidgetManager ────────────────────────────────────────────────────────
@accept_drop("drop_mime")
class PanelWidgetManager(WidgetManager):
    """
    錶盤編輯面板管理器。
    初始四面板：ObjectExplorerPanel（左）、EditViewPanel（中）、
    LayerPickerPanel（右上）、AttributePanel（右下）。
    分割時產生空白佔位 PanelWidget。

    面板間通訊 signal：
      object_selected(object_type)  — ObjectExplorer 點選項目時發出
      attr_changed(field, value)    — AttributePanel 任一欄位值變動時發出
    """

    object_selected          = pyqtSignal(str)
    instance_selected        = pyqtSignal(str, dict, int)   # object_type, values, instance_id
    instance_deselected      = pyqtSignal()
    multi_selection_changed  = pyqtSignal(list)             # list[int] 全部選取 ids
    attr_changed             = pyqtSignal(str, object)
    dark_mode_changed        = pyqtSignal(bool)
    lua_requested     = pyqtSignal(int, str, str, str, bool, bool)  # inst_id(-1=template), obj_name, field, value, numeric, expression_mode
    lua_committed     = pyqtSignal()                   # Lua Apply 後通知 preview 刷新

    def __init__(self, parent=None):
        self.drop_mime = QMimeData()
        self.drop_mime.setData("panel", b"")
        self._creating_initial = True
        super().__init__(parent)          # 建立 _obj_explorer 並加入 _root_splitter
        self._creating_initial = False
        self.is_dark_mode: bool        = True
        self.undo_stack            = QUndoStack(self)
        self._instance_id_counter: int            = 0
        self._instances:           dict[int, dict] = {}
        self._current_instance_id: int | None     = None
        self._current_object_type: str | None     = None
        self._type_defaults:       dict[str, dict] = {}  # 各型別的自訂預設值
        self._selected_ids:        set[int]        = set()
        self._watch_settings: dict = {
            k: v
            for d in _attrs.watchSetting[1:]
            for k, v in d.items()
            if k != "description"
        }

        self._editing_instance_ids: set[int] = set()
        self._edit_view    = EditViewPanel(manager=self)
        self._layer_picker = LayerPickerPanel(manager=self)
        self._attr_panel   = AttributePanel(manager=self)
        self._widgets += [self._edit_view, self._layer_picker, self._attr_panel]

        right_col = QSplitter(Qt.Orientation.Vertical)
        right_col.setHandleWidth(1)
        right_col.setChildrenCollapsible(False)
        right_col.setStyleSheet(_SPLITTER_QSS)
        right_col.addWidget(self._layer_picker)
        right_col.addWidget(self._attr_panel)
        right_col.setSizes([300, 300])
        self._right_col = right_col

        self._root_splitter.setHandleWidth(1)
        self._root_splitter.setStyleSheet(_SPLITTER_QSS)
        self._root_splitter.addWidget(self._edit_view)
        self._root_splitter.addWidget(right_col)
        # setSizes 需等 widget 取得實際寬度後才有效
        QTimer.singleShot(0, lambda: self._root_splitter.setSizes([220, 560, 280]))

        # Ctrl+S 使用者手動存檔
        sc = QShortcut(QKeySequence.StandardKey.Save, self)
        sc.activated.connect(self.save)

        # 未處理例外時自動存檔
        _prev_hook = sys.excepthook
        def _crash_hook(exc_type, exc_val, exc_tb):
            self.save()
            _prev_hook(exc_type, exc_val, exc_tb)
        sys.excepthook = _crash_hook

        self.attr_changed.connect(self._on_watch_setting_changed)
        QTimer.singleShot(0, self._sync_initial_watch_name)

        # 每秒以最新時間 tag 值重算所有 canvas item（有來源 tag 自動刷新）
        self._time_refresh_timer = QTimer(self)
        self._time_refresh_timer.setInterval(1000)
        self._time_refresh_timer.timeout.connect(self.refresh_all_instances)
        self._time_refresh_timer.start()

    def _sync_initial_watch_name(self) -> None:
        title = self.windowTitle()
        if title:
            self._watch_settings["Watch name"] = title
            self._attr_panel.update_field("Watch name", title)

    def _on_watch_setting_changed(self, field: str, value) -> None:
        if self._current_instance_id is not None or self._current_object_type is not None:
            return
        self._watch_settings[field] = value
        if field == "Watch name":
            self.setWindowTitle(str(value))

    def place_object(self, object_name: str, pos: QPointF | None = None) -> None:
        """讀取屬性後放入場景並加入物件總管。
        若屬性面板目前正以 template 模式（無 instance 選取）顯示同型別物件，
        則沿用使用者已編輯的值；否則重置為預設值。
        """
        if (self._current_instance_id is None
                and self._current_object_type == object_name):
            values = self._attr_panel.get_current_values()
            self._type_defaults[object_name] = values.copy()
        else:
            self.object_selected.emit(object_name)
            values = self._attr_panel.get_current_values()
        if pos is not None:
            values["X"] = int(pos.x())
            values["Y"] = int(pos.y())
        base = values.get("Name", object_name)
        name = self._obj_explorer._unique_name(base)
        values["Name"] = name

        instance_id = self._instance_id_counter
        self._instance_id_counter += 1

        canvas_item = self._edit_view._canvas._place_from_values(object_name, values)
        tree_item   = self._obj_explorer.add_instance(name, object_name, values, instance_id)

        self._instances[instance_id] = {
            "tree_item":   tree_item,
            "canvas_item": canvas_item,
            "object_type": object_name,
            "values":      values.copy(),
        }

        # 自動選取新放置的 instance
        self._current_instance_id = instance_id
        self._selected_ids = {instance_id}
        self.instance_selected.emit(object_name, values, instance_id)
        self.multi_selection_changed.emit([instance_id])

        self.undo_stack.push(_PlaceCommand(self, instance_id))

    def save(self) -> None:
        """存檔：使用者按 Ctrl+S 或程式崩潰時呼叫。"""
        # TODO: 實作錶盤資料序列化（等資料模型完成後填充）
        pass

    def _create_managed_widget(self) -> PanelWidget:
        if getattr(self, "_creating_initial", False):
            self._obj_explorer = ObjectExplorerPanel(manager=self)
            self._widgets.append(self._obj_explorer)
            return self._obj_explorer
        pw = PanelWidget(manager=self)
        self._widgets.append(pw)
        return pw

    def _make_split_widget(self, source_item, source_widget) -> QWidget:
        """Panel 自身就是要移入新位置的 widget；外部拖曳才建立空白佔位。"""
        if source_widget is not None:
            return source_item
        return self._create_managed_widget()

    def _already_at_outer(self, source_widget: QWidget, direction: str) -> bool:
        sp = self._root_splitter
        H, V = Qt.Orientation.Horizontal, Qt.Orientation.Vertical
        if direction == 'left':
            return sp.orientation() == H and sp.widget(0) is source_widget
        if direction == 'right':
            return sp.orientation() == H and sp.widget(sp.count() - 1) is source_widget
        if direction == 'top':
            return sp.orientation() == V and sp.widget(0) is source_widget
        if direction == 'bottom':
            return sp.orientation() == V and sp.widget(sp.count() - 1) is source_widget
        return False

    def _move_item(self, item, source_widget: PanelWidget | None,
                   target_widget: PanelWidget | None):
        if source_widget is not None and target_widget is None:
            # 從 splitter 物理移除，待 _split_widget 重新定位；不標 empty
            parent = source_widget.parentWidget()
            if isinstance(parent, QSplitter):
                source_widget.setParent(None)

    def _widget_of(self, item) -> PanelWidget | None:
        return item if item in self._widgets else None

    def _widget_is_empty(self, widget: QWidget) -> bool:
        return isinstance(widget, PanelWidget) and widget._empty

    # ── Lua panel drop 處理 ───────────────────────────────────────

    def dropEvent(self, event):
        zone        = self._overlay.get_hovered_zone()
        source_item = DragManager.get_data()
        target      = self._active_widget
        self._overlay.reset()
        self._active_widget = None

        if zone is None or source_item is None or target is None:
            event.acceptProposedAction()
            return
        self._execute_drop(zone, source_item, target)
        event.acceptProposedAction()

    def lua_field_committed(self, inst_id: int, field: str, new_value: str) -> None:
        """LuaScriptPanel Apply 後回寫屬性值並推 undo command。"""
        if inst_id >= 0:
            inst = self._instances.get(inst_id)
            if inst is None:
                return
            old_val = inst["values"].get(field, "")
            inst["values"][field] = new_value
            ci = inst.get("canvas_item")
            if ci is not None:
                ci.apply_attr(field, new_value)
            ti = inst.get("tree_item")
            if ti is not None:
                ti.setData(0, Qt.ItemDataRole.UserRole + 1, inst["values"].copy())
            self._attr_panel.update_field(field, new_value)
            self.undo_stack.push(
                _AttrChangeCommand(self, inst_id, field, old_val, new_value))
        else:
            obj_type = self._current_object_type
            if not obj_type:
                return
            old_val = self._type_defaults.get(obj_type, {}).get(field, "")
            self._type_defaults.setdefault(obj_type, {})[field] = new_value
            self._attr_panel.update_field(field, new_value)
            self.undo_stack.push(
                _TemplateAttrChangeCommand(self, obj_type, field, old_val, new_value))
        self.lua_committed.emit()

    def refresh_all_instances(self) -> None:
        """Tag 值變更後，重新對所有 canvas item 呼叫 apply_attr 使 eval_lua_expr 以新值重算。"""
        skip_ids = set(self._editing_instance_ids)

        for inst_id, inst in self._instances.items():
            if inst_id in skip_ids:
                continue
            ci = inst.get("canvas_item")
            if ci is None:
                continue
            for field, value in inst["values"].items():
                ci.apply_attr(field, value)

        canvas = getattr(getattr(self, "_edit_view", None), "_canvas", None)
        if canvas is None:
            return

        scene = getattr(canvas, "_scene", None)
        if scene is not None:
            ov = getattr(scene, "_overlay", None)
            if ov is not None and ov.isVisible():
                ov._update_geometry()
            mov = getattr(scene, "_multi_overlay", None)
            if mov is not None and mov.isVisible():
                mov.prepareGeometryChange()
                mov._compute_union()
                mov.update()

        canvas.viewport().update()

    # ── Undo API ──────────────────────────────────────────────────

    def push_command(self, cmd: QUndoCommand):
        self.undo_stack.push(cmd)

    def begin_macro(self, text: str):
        self.undo_stack.beginMacro(text)

    def end_macro(self):
        self.undo_stack.endMacro()
