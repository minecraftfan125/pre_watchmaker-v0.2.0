"""
all_test/conftest.py — 測試共用 fixture
"""
import pytest

from edit_watch import PanelWidgetManager


@pytest.fixture(autouse=True)
def _stop_time_refresh_timer(monkeypatch):
    """停用 PanelWidgetManager 建構時啟動的 1 秒週期 timer。

    該 timer 會呼叫 refresh_all_instances()，依 _instances[...]["values"] 的值
    覆寫所有 canvas item 屬性。測試中常直接呼叫 layer.apply_attr() 修改屬性但不同步
    更新 values 字典，若單一測試耗時超過 1 秒（例如平行測試下 CPU 競爭），timer 觸發
    會把剛設定的值蓋回舊值，造成間歇性失敗。測試不需要即時刷新，一律停用。
    """
    original_init = PanelWidgetManager.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._time_refresh_timer.stop()

    monkeypatch.setattr(PanelWidgetManager, "__init__", patched_init)
    yield
