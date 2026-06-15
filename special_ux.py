from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QWidget as _QWidget

class DragManager:
    _current_drag_data = None

    @classmethod
    def set_data(cls, data):
        cls._current_drag_data = data

    @classmethod
    def get_data(cls):
        return cls._current_drag_data

    @classmethod
    def clear(cls):
        cls._current_drag_data = None

def drag_data(mime, data_provider=None):
    """
    為 widget 加入拖曳功能。

    實例需在 __init__ 中將 self.mime 設為 QMimeData；
    裝飾器在 __init__ 完成後凍結快照，之後 self.mime 不再被讀取。
    drag.setMimeData(_make_mime()) 使用凍結後的副本，避免 Qt 接管所有權問題。

    data_provider : callable(self) -> payload；若 None，payload 為 self 本身。
    """
    def which(item):
        _orig_init    = item.__dict__.get('__init__')
        _orig_press   = item.__dict__.get('mousePressEvent')
        _orig_move    = item.__dict__.get('mouseMoveEvent')
        _orig_release = item.__dict__.get('mouseReleaseEvent')

        def _make_factory(source: QMimeData):
            """凍結 mime 內容，回傳每次呼叫都產生新副本的工廠。"""
            snapshot = [(fmt, bytes(source.data(fmt))) for fmt in source.formats()]
            def factory() -> QMimeData:
                copy = QMimeData()
                for fmt, data in snapshot:
                    copy.setData(fmt, data)
                return copy
            return factory

        def __init__(self, *args, **kwargs):
            if _orig_init:
                _orig_init(self, *args, **kwargs)
            else:
                super(item, self).__init__(*args, **kwargs)
            source = getattr(self, mime, None)
            if isinstance(source, QMimeData):
                self._mime_factory = _make_factory(source)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event.position().toPoint()
            if _orig_press:
                _orig_press(self, event)
            else:
                super(item, self).mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if (
                event.buttons() & Qt.MouseButton.LeftButton
                and getattr(self, '_drag_start_pos', None) is not None
            ):
                delta = event.position().toPoint() - self._drag_start_pos
                if delta.manhattanLength() > 5:
                    _make_mime = getattr(self, '_mime_factory', None)
                    if _make_mime is None:
                        return
                    payload = data_provider(self) if callable(data_provider) else self
                    DragManager.set_data(payload)
                    drag = QDrag(self)
                    drag.setMimeData(_make_mime())
                    self._drag_start_pos = None
                    drag.exec(Qt.DropAction.CopyAction)
                    DragManager.clear()
                    return
            if _orig_move:
                _orig_move(self, event)
            else:
                super(item, self).mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = None
            if _orig_release:
                _orig_release(self, event)
            else:
                super(item, self).mouseReleaseEvent(event)

        item.__init__          = __init__
        item.mousePressEvent   = mousePressEvent
        item.mouseMoveEvent    = mouseMoveEvent
        item.mouseReleaseEvent = mouseReleaseEvent
        return item
    return which

def accept_drop(mime: str):
    """
    為 widget 類別加入 drop 接受能力。

    mime : 實例屬性名稱，值可為 QMimeData、str 或 list[str]。
           與 drag_data 對稱：格式在 __init__ 完成後讀取並快照至 self._accept_formats。
    dragMoveEvent / dropEvent 會沿 MRO 尋找繼承實作並串接呼叫；
    dragEnterEvent 僅做 accept/ignore，不串接父類（避免 QWidget 預設 ignore 覆寫）。
    """
    def which(item):
        def _find_override(name):
            """在 MRO 中尋找第一個繼承的覆寫方法（不含 QWidget 及以上）。"""
            for klass in item.__mro__[1:]:
                if klass is _QWidget or klass is object:
                    return None
                if name in klass.__dict__:
                    return klass.__dict__[name]
            return None

        _orig_init  = item.__init__
        _orig_enter = item.__dict__.get('dragEnterEvent')
        _orig_move  = item.__dict__.get('dragMoveEvent')  or _find_override('dragMoveEvent')
        _orig_drop  = item.__dict__.get('dropEvent')       or _find_override('dropEvent')

        def __init__(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            self.setAcceptDrops(True)
            source = getattr(self, mime, None)
            if isinstance(source, QMimeData):
                self._accept_formats = list(source.formats())
            elif isinstance(source, str):
                self._accept_formats = [source]
            elif isinstance(source, (list, tuple)):
                self._accept_formats = list(source)
            else:
                self._accept_formats = []

        def dragEnterEvent(self, event):
            if any(event.mimeData().hasFormat(f) for f in self._accept_formats):
                event.acceptProposedAction()
                if _orig_enter:
                    _orig_enter(self, event)
            else:
                super(item, self).dragEnterEvent(event)

        def dragMoveEvent(self, event):
            if any(event.mimeData().hasFormat(f) for f in self._accept_formats):
                event.acceptProposedAction()
                if _orig_move:
                    _orig_move(self, event)
            else:
                super(item, self).dragMoveEvent(event)

        def dropEvent(self, event):
            if any(event.mimeData().hasFormat(f) for f in self._accept_formats):
                self.drop_data = DragManager.get_data()
                if _orig_drop:
                    _orig_drop(self, event)
                event.acceptProposedAction()
            else:
                super(item, self).dropEvent(event)

        item.__init__       = __init__
        item.dragEnterEvent = dragEnterEvent
        item.dragMoveEvent  = dragMoveEvent
        item.dropEvent      = dropEvent
        return item
    return which
