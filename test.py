"""
測試執行器：呼叫 pytest 執行 all_test/ 目錄內的所有測試。

使用方式：
    python test.py              # 執行所有測試
    python test.py -v           # 詳細輸出
    python test.py -k keyword   # 只執行名稱含 keyword 的測試
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
    args = [str(TEST_DIR)] + sys.argv[1:]
    sys.exit(pytest.main(args))


if __name__ == "__main__":
    main()
