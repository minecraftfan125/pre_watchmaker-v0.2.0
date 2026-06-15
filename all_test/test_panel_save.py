"""
PanelWidgetManager.save() 相關測試：
  - save() 不拋例外
  - Ctrl+S QShortcut 安裝並連到 save()
  - sys.excepthook 觸發時呼叫 save()
  - excepthook chain 保留先前的 hook
"""
import sys
import pytest
from PyQt6.QtGui import QKeySequence, QShortcut

from edit_watch import PanelWidgetManager


class _CountingSave(PanelWidgetManager):
    """測試用子類：覆寫 save() 以記錄呼叫次數，避開 PyQt6 signal bound-method 快取問題。"""

    def __init__(self, *args, **kwargs):
        self._save_count = 0
        super().__init__(*args, **kwargs)

    def save(self):
        self._save_count += 1


@pytest.fixture(autouse=True)
def restore_excepthook():
    """每個測試前後還原 sys.excepthook，避免測試互相污染。"""
    original = sys.excepthook
    yield
    sys.excepthook = original


@pytest.fixture
def manager(qtbot):
    m = _CountingSave()
    qtbot.addWidget(m)
    m.show()
    return m


# ── save() 基本可呼叫性 ─────────────────────────────────────────────────────────

class TestSaveCallable:
    def test_save_does_not_raise(self, manager):
        """save() 現為 stub，直接呼叫不應拋例外。"""
        manager.save()


# ── Ctrl+S shortcut ─────────────────────────────────────────────────────────────

class TestCtrlSShortcut:
    def test_ctrl_s_shortcut_installed(self, manager):
        """manager 內應安裝 Ctrl+S QShortcut。"""
        shortcuts = manager.findChildren(QShortcut)
        save_key = QKeySequence(QKeySequence.StandardKey.Save)
        assert any(sc.key() == save_key for sc in shortcuts), \
            "Ctrl+S QShortcut 未安裝於 PanelWidgetManager"

    def test_ctrl_s_triggers_save(self, manager):
        """觸發 Ctrl+S shortcut activated signal 應呼叫 save()。"""
        shortcuts = manager.findChildren(QShortcut)
        save_key = QKeySequence(QKeySequence.StandardKey.Save)
        sc = next(s for s in shortcuts if s.key() == save_key)

        before = manager._save_count
        sc.activated.emit()
        assert manager._save_count == before + 1


# ── sys.excepthook ──────────────────────────────────────────────────────────────

class TestExcepthook:
    def test_excepthook_calls_save(self, qtbot):
        """sys.excepthook 被觸發時應呼叫 manager.save()。

        注意：chain base 設為 no-op，防止 pytest-qt 自己的 hook 視 ValueError 為測試失敗。
        """
        sys.excepthook = lambda *_: None   # no-op base，隔離 pytest-qt hook
        m = _CountingSave()
        qtbot.addWidget(m)

        sys.excepthook(ValueError, ValueError("crash"), None)

        assert m._save_count == 1

    def test_excepthook_chains_original_hook(self, qtbot):
        """manager 安裝的 crash hook 不應遺失先前的 excepthook。"""
        original_called = []
        sys.excepthook = lambda *_: original_called.append(True)

        m = _CountingSave()
        qtbot.addWidget(m)

        sys.excepthook(ValueError, ValueError("crash"), None)

        assert original_called, "先前的 excepthook 未被呼叫（chain 斷裂）"
