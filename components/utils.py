from PyQt5.QtWidgets import QWidget

def summon_components(attribute: dict, parent=None):
    """
    動態建立一個具有指定屬性的 QWidget 元件。

    Args:
        attribute: 屬性字典，鍵為屬性名稱，值為預設值
        parent: 父元件

    Returns:
        Component: 具有指定屬性的 QWidget 實例
    """
    slots = tuple(attribute.keys())

    class Component(QWidget):
        __slots__ = slots

        def __init__(self, parent=None):
            super().__init__(parent)
            for k, v in attribute.items():
                setattr(self, k, v)

    return Component(parent)


__all__ = ['summon_components']
