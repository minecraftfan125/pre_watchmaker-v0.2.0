"""
批次修改圖示顏色，保留原圖。

用法：
    python img/recolor.py --dir img/edit --color "#FFFFFF" --suffix white
    python img/recolor.py --dir img/edit --color "#AABBCC"           # suffix 預設為 recolored
"""
import argparse
import re
import sys
from pathlib import Path

from PIL import Image


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", hex_str):
        print(f"錯誤：顏色格式無效「{hex_str}」，請使用 #RRGGBB", file=sys.stderr)
        sys.exit(1)
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return r, g, b


def recolor_image(src: Path, dst: Path, rgb: tuple[int, int, int]) -> None:
    img = Image.open(src).convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            _, _, _, a = pixels[x, y]
            pixels[x, y] = (*rgb, a)
    img.save(dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="批次修改 PNG 圖示顏色（保留原圖）")
    parser.add_argument("--dir", required=True, help="圖示資料夾路徑")
    parser.add_argument("--color", required=True, help="目標顏色，格式 #RRGGBB")
    parser.add_argument("--suffix", default="recolored", help="輸出檔名後綴（預設 recolored）")
    args = parser.parse_args()

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"錯誤：資料夾不存在「{folder}」", file=sys.stderr)
        sys.exit(1)

    rgb = parse_hex_color(args.color)
    pngs = sorted(folder.glob("*.png"))

    if not pngs:
        print(f"在 {folder} 找不到任何 PNG 檔案")
        return

    skipped = []
    for src in pngs:
        if f"-{args.suffix}" in src.stem:
            skipped.append(src.name)
            continue
        dst = src.with_stem(f"{src.stem}-{args.suffix}")
        recolor_image(src, dst, rgb)
        print(f"  {src.name}  →  {dst.name}")

    if skipped:
        print(f"\n略過（已含後綴）：{', '.join(skipped)}")

    print(f"\n完成，共處理 {len(pngs) - len(skipped)} 張。")


if __name__ == "__main__":
    main()
