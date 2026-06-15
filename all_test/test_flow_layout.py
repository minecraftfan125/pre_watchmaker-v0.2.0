"""FlowLayout 排版邏輯驗證測試。

測試矩陣：
  A. 左對齊 + 單行：物件間距 = left_margin，靠左堆疊
  B. 右對齊 + 單行：物件間距 = right_margin，靠右堆疊
  C. 左對齊 + 多行：space-evenly（邊緣間距 = 物件間距）
  D. 中對齊 + 單行：space-evenly
  E. 單欄（n_items=1，各對齊）：靠左 / 靠右 / 置中
  F. heightForWidth / minimumSize
  G. n_cols 邊界：固定間距剛好放 2 欄 / 差一像素放不下
  H. 上邊距偏移 / v_spacing
  I. 空 layout

重要：qtbot.addWidget 使用 weakref，container (c) 必須由呼叫端用強引用保持存活，
否則 C++ QWidget 被立即刪除，子件也隨之消失。_make 因此回傳 (c, items, layout)。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from special_ui import FlowLayout

_AF = Qt.AlignmentFlag


# ── 輔助 ─────────────────────────────────────────────────────────────────────

def _make(qtbot, *, cw, ch, n, iw, ih,
          lm=0, rm=0, vs=0, align=_AF.AlignLeft, tm=0, bm=0):
    """建立已顯示的 FlowLayout 容器，回傳 (container, items, layout)。

    呼叫端必須用局部變數持有 container，否則 C++ 端會在函式返回後立即析構。
    """
    c = QWidget()
    qtbot.addWidget(c)   # 僅弱引用，強引用由呼叫端的 'c' 持有
    fl = FlowLayout(c, left_margin=lm, right_margin=rm, v_spacing=vs, alignment=align)
    fl.setContentsMargins(0, tm, 0, bm)
    items = []
    for _ in range(n):
        child = QWidget(c)
        child.setFixedSize(iw, ih)
        fl.addWidget(child)
        items.append(child)
    c.resize(cw, ch)
    c.show()
    qtbot.waitExposed(c)
    return c, items, fl


# ── A. 左對齊 + 單行 ──────────────────────────────────────────────────────────

class TestLeftAlignSingleRow:
    """
    cw=500, lm=20, rm=20  →  available_w = 460
    iw=100, n=3
    n_cols = min(3, (460+20)//(100+20)) = min(3, 4) = 3  →  n_rows=1 單行

    col x：20, 140, 260（間距 = lm = 20）
    """

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c, self.items, self.fl = _make(
            qtbot, cw=500, ch=300, n=3, iw=100, ih=80,
            lm=20, rm=20, align=_AF.AlignLeft,
        )

    def test_col0_x(self):
        assert self.items[0].x() == 20

    def test_col1_x(self):
        assert self.items[1].x() == 140

    def test_col2_x(self):
        assert self.items[2].x() == 260

    def test_all_on_same_row(self):
        assert self.items[0].y() == self.items[1].y() == self.items[2].y()

    def test_gap_equals_left_margin(self):
        gap01 = self.items[1].x() - (self.items[0].x() + 100)
        gap12 = self.items[2].x() - (self.items[1].x() + 100)
        assert gap01 == 20
        assert gap12 == 20


# ── B. 右對齊 + 單行 ──────────────────────────────────────────────────────────

class TestRightAlignSingleRow:
    """
    cw=500, lm=20, rm=20  →  available_w = 460
    iw=100, n=3
    n_cols = 3，n_rows=1 → 單行，靠右堆疊

    col x：140, 260, 380（最後物件右邊緣 = 480 = x0 + available_w）
    """

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c, self.items, self.fl = _make(
            qtbot, cw=500, ch=300, n=3, iw=100, ih=80,
            lm=20, rm=20, align=_AF.AlignRight,
        )

    def test_col0_x(self):
        # x0+available_w-sw - (n_cols-1-0)*(sw+rm) = 480-100-2*120 = 140
        assert self.items[0].x() == 140

    def test_col1_x(self):
        assert self.items[1].x() == 260

    def test_col2_x(self):
        assert self.items[2].x() == 380

    def test_last_item_packed_to_right_edge(self):
        # 最後物件右邊緣 = x0 + available_w = 20 + 460 = 480
        assert self.items[2].x() + 100 == 20 + 460

    def test_gap_equals_right_margin(self):
        gap01 = self.items[1].x() - (self.items[0].x() + 100)
        gap12 = self.items[2].x() - (self.items[1].x() + 100)
        assert gap01 == 20
        assert gap12 == 20


# ── C. 左對齊 + 多行 → space-evenly ──────────────────────────────────────────

class TestLeftAlignMultiRow:
    """
    cw=500, lm=20, rm=20  →  available_w = 460
    iw=100, ih=80, vs=10, n=5
    n_cols = min(5, (460+20)//(100+20)) = min(5, 4) = 4  →  n_rows=2  多行

    space-evenly gap = (460 - 4*100) / (4+1) = 60/5 = 12（整數，無捨入誤差）
    Row 0 x：32, 144, 256, 368
    Row 1 (item 4)：x=32，y = ih+vs = 80+10 = 90
    """

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c, self.items, self.fl = _make(
            qtbot, cw=500, ch=500, n=5, iw=100, ih=80,
            lm=20, rm=20, vs=10, align=_AF.AlignLeft,
        )
        self.x0   = 20
        self.avail = 460
        self.gap  = (self.avail - 4 * 100) / (4 + 1)   # 12.0 精確整數

    def test_row0_col0_x(self):
        assert self.items[0].x() == round(self.x0 + 1 * self.gap)

    def test_row0_col1_x(self):
        assert self.items[1].x() == round(self.x0 + 2 * self.gap + 100)

    def test_row0_col2_x(self):
        assert self.items[2].x() == round(self.x0 + 3 * self.gap + 200)

    def test_row0_col3_x(self):
        assert self.items[3].x() == round(self.x0 + 4 * self.gap + 300)

    def test_row1_x_same_as_row0_col0(self):
        assert self.items[4].x() == self.items[0].x()

    def test_row0_y_is_zero(self):
        for i in range(4):
            assert self.items[i].y() == 0

    def test_row1_y(self):
        assert self.items[4].y() == 80 + 10

    def test_space_evenly_edge_gaps_equal(self):
        left_gap  = self.items[0].x() - self.x0
        inter_gap = self.items[1].x() - (self.items[0].x() + 100)
        right_gap = (self.x0 + self.avail) - (self.items[3].x() + 100)
        assert left_gap == inter_gap == right_gap


# ── D. 中對齊 + 單行 → space-evenly ─────────────────────────────────────────

class TestCenterAlignSingleRow:
    """
    cw=500, lm=20, rm=20  →  available_w = 460
    iw=100, n=3, align=AlignHCenter
    n_cols = min(3, 460//100) = 3  →  n_rows=1

    space-evenly gap = (460 - 3*100) / (3+1) = 160/4 = 40（整數，無誤差）
    col x：60, 200, 340
    """

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c, self.items, self.fl = _make(
            qtbot, cw=500, ch=300, n=3, iw=100, ih=80,
            lm=20, rm=20, align=_AF.AlignHCenter,
        )
        self.x0   = 20
        self.avail = 460
        self.gap  = (self.avail - 3 * 100) / (3 + 1)   # 40.0

    def test_col0_x(self):
        assert self.items[0].x() == round(self.x0 + self.gap)

    def test_col1_x(self):
        assert self.items[1].x() == round(self.x0 + 2 * self.gap + 100)

    def test_col2_x(self):
        assert self.items[2].x() == round(self.x0 + 3 * self.gap + 200)

    def test_left_inter_right_gaps_equal(self):
        left_gap  = self.items[0].x() - self.x0
        inter_gap = self.items[1].x() - (self.items[0].x() + 100)
        right_gap = (self.x0 + self.avail) - (self.items[2].x() + 100)
        assert left_gap == inter_gap == right_gap


# ── E. 單欄（n_items=1，各對齊）──────────────────────────────────────────────

class TestSingleColumnAlignment:
    """
    n=1  →  n_cols=1 必然成立
    cw=300, lm=20, rm=20, iw=50  →  available_w = 260

    left   : x = x0 = 20
    right  : x = x0 + avail - sw = 20 + 260 - 50 = 230
    center : x = x0 + (260-50)//2 = 20 + 105 = 125
    """

    def test_left_x(self, qtbot):
        c, items, _ = _make(qtbot, cw=300, ch=200, n=1, iw=50, ih=50,
                            lm=20, rm=20, align=_AF.AlignLeft)
        assert items[0].x() == 20

    def test_right_x(self, qtbot):
        c, items, _ = _make(qtbot, cw=300, ch=200, n=1, iw=50, ih=50,
                            lm=20, rm=20, align=_AF.AlignRight)
        assert items[0].x() == 230

    def test_center_x(self, qtbot):
        c, items, _ = _make(qtbot, cw=300, ch=200, n=1, iw=50, ih=50,
                            lm=20, rm=20, align=_AF.AlignHCenter)
        assert items[0].x() == 125   # 20 + (260-50)//2


# ── F. heightForWidth / minimumSize ──────────────────────────────────────────

class TestHeightCalculation:
    """
    iw=100, ih=80, lm=20, rm=20, vs=10, tm=5, bm=5, n=5, align=AlignLeft

    width=500: available=460, n_cols=4, n_rows=2
      height = tm(5) + 2*80 + 1*10 + bm(5) = 180

    width=260: available=220
      n_cols = (220+20)//(100+20) = 2, n_rows=3
      height = 5 + 3*80 + 2*10 + 5 = 270

    minimumSize: min_w = lm+sw+rm = 140
      available=100, n_cols=(100+20)//120=1, n_rows=5
      min_h = 5 + 5*80 + 4*10 + 5 = 450
    """

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c = QWidget()       # 強引用：必須持有才能防止 C++ 端析構
        qtbot.addWidget(self.c)
        self.fl = FlowLayout(self.c, left_margin=20, right_margin=20,
                             v_spacing=10, alignment=_AF.AlignLeft)
        self.fl.setContentsMargins(0, 5, 0, 5)
        self.children = []
        for _ in range(5):
            child = QWidget(self.c)
            child.setFixedSize(100, 80)
            self.fl.addWidget(child)
            self.children.append(child)   # 持有子件強引用

    def test_height_wide(self):
        assert self.fl.heightForWidth(500) == 180

    def test_height_narrow(self):
        assert self.fl.heightForWidth(260) == 270

    def test_minimum_size(self):
        ms = self.fl.minimumSize()
        assert ms.width()  == 140
        assert ms.height() == 450


# ── G. n_cols 邊界：固定間距剛好 / 差一像素 ──────────────────────────────────

class TestNColsBoundary:
    """
    lm=20, rm=20, sw=100：2 物件需 2*100 + 1*20 = 220px
    available_w=220  →  n_cols=(220+20)//(100+20)=2  剛好放下
    available_w=219  →  n_cols=(219+20)//(100+20)=1  放不下，換行
    """

    def test_exactly_fits_two_cols(self, qtbot):
        # cw = 220 + 20 + 20 = 260
        c, items, _ = _make(qtbot, cw=260, ch=300, n=2, iw=100, ih=80,
                            lm=20, rm=20, align=_AF.AlignLeft)
        assert items[0].y() == items[1].y()

    def test_one_pixel_too_narrow_wraps(self, qtbot):
        # cw = 219 + 20 + 20 = 259
        c, items, _ = _make(qtbot, cw=259, ch=300, n=2, iw=100, ih=80,
                            lm=20, rm=20, align=_AF.AlignLeft)
        assert items[0].y() != items[1].y()

    def test_boundary_x_positions_when_two_cols(self, qtbot):
        c, items, _ = _make(qtbot, cw=260, ch=300, n=2, iw=100, ih=80,
                            lm=20, rm=20, align=_AF.AlignLeft)
        # col0: x0=20; col1: 20 + (100+20) = 140
        assert items[0].x() == 20
        assert items[1].x() == 140


# ── H. 上邊距偏移 / v_spacing ─────────────────────────────────────────────────

class TestMarginAndSpacing:
    def test_top_margin_offsets_y(self, qtbot):
        tm = 24
        c, items, _ = _make(qtbot, cw=300, ch=200, n=1, iw=100, ih=80,
                            lm=0, rm=0, align=_AF.AlignLeft, tm=tm)
        assert items[0].y() == tm

    def test_v_spacing_between_rows(self, qtbot):
        # cw=120, lm=10, rm=10 → available_w=100; sw=100 → n_cols=1（單欄）
        # ih=50, vs=15 → 第 2 列 y = 50+15 = 65
        c, items, _ = _make(qtbot, cw=120, ch=300, n=2, iw=100, ih=50,
                            lm=10, rm=10, vs=15, align=_AF.AlignLeft)
        assert items[1].y() - items[0].y() == 50 + 15


# ── I. 空 layout ──────────────────────────────────────────────────────────────

class TestEmptyLayout:

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        self.c = QWidget()
        qtbot.addWidget(self.c)
        self.fl = FlowLayout(self.c, left_margin=20, right_margin=20, v_spacing=10)

    def test_height_for_width_is_zero(self):
        assert self.fl.heightForWidth(500) == 0

    def test_height_for_any_width_is_zero(self):
        for w in (0, 100, 999):
            assert self.fl.heightForWidth(w) == 0
