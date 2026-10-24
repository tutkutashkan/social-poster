#!/usr/bin/env python3
"""Render image cards for posts in queue.toml that have a `card` field.

Each card is a 1200x675 PNG at the post's `image` path. Run this on a Mac
(it uses macOS system fonts) after adding or editing cards:

  python3 make_cards.py            render cards that don't exist yet
  python3 make_cards.py --all      re-render every card

Needs Pillow (pip install pillow). The poster itself doesn't.
"""

import argparse
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1200, 675
PAD = 96
BG, INK, MUTED, ACCENT = "#101322", "#F5F6FA", "#9AA0BC", "#8B6CFF"
HANDLE = "@tashkann"
FONT = "/System/Library/Fonts/SFNS.ttf"


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def wrap(draw, text, fnt, width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=fnt) <= width:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def render(card, footer_right, out):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # largest size whose wrapped text fits the text box
    for size in range(84, 39, -2):
        fnt = font(size, "Bold")
        lines = wrap(draw, card, fnt, W - 2 * PAD)
        line_h = int(size * 1.18)
        if line_h * len(lines) <= H - 2 * PAD - 70:
            break
    block_h = line_h * len(lines)
    y = (H - 70 - block_h) // 2 + 10
    draw.rounded_rectangle([PAD, y - 46, PAD + 72, y - 36], radius=5, fill=ACCENT)
    for line in lines:
        draw.text((PAD, y), line, font=fnt, fill=INK)
        y += line_h
    small = font(30, "Semibold")
    base = H - PAD + 10
    draw.text((PAD, base), HANDLE, font=small, fill=MUTED, anchor="ls")
    if footer_right:
        draw.text((W - PAD, base), footer_right, font=small, fill=ACCENT, anchor="rs")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="re-render existing cards too")
    args = parser.parse_args()
    posts = tomllib.load((ROOT / "queue.toml").open("rb")).get("post", [])
    count = 0
    for post in posts:
        if not post.get("card"):
            continue
        out = ROOT / post["image"]
        if out.exists() and not args.all:
            continue
        render(post["card"], post.get("card_footer", ""), out)
        count += 1
        print(f"{post['image']}  ({out.stat().st_size // 1024} KB)")
    print(f"rendered {count} card(s)")


if __name__ == "__main__":
    main()
