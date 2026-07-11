"""
測試執行器：呼叫 pytest 執行 all_test/ 目錄內的所有測試。
預設以 pytest-xdist 平行執行（-n auto，依 CPU 核心數自動分配 worker process）。

使用方式：
    python test.py              # 平行執行所有測試
    python test.py -v           # 詳細輸出
    python test.py -k keyword   # 只執行名稱含 keyword 的測試
    python test.py -n 0         # 停用平行化，改為單一 process 循序執行
    python test.py -n 4         # 指定 4 個 worker process
"""

import os
import sys
from pathlib import Path

# headless 模式：不需要實體顯示器，CI/CD 環境也能執行
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent
TEST_DIR = PROJECT_ROOT / "all_test"


def main() -> None:
    import pytest

    if not TEST_DIR.exists():
        print(f"[警告] 找不到測試目錄：{TEST_DIR}")
        sys.exit(0)

    # 將 all_test/ 作為起點，並把使用者傳入的參數原封不動交給 pytest
    user_args = sys.argv[1:]
    has_dist_opt = any(
        a in ("-n", "--numprocesses") or a.startswith("-n=") or a.startswith("--numprocesses=")
        for a in user_args
    )
    args = [str(TEST_DIR)] + user_args
    if not has_dist_opt:
        # 每個 worker process 各自持有獨立的 QApplication，
        # 平行執行對 PyQt6/pytest-qt 測試是安全的
        args += ["-n", "auto"]
    sys.exit(pytest.main(args))


if __name__ == "__main__":
    main()
