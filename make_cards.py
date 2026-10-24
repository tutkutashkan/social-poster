#!/usr/bin/env python3
"""Render image cards for posts in queue.toml that have a `card` field.

Each card is a 1200x675 PNG at the post's `image` path. Run this on a Mac
(it uses macOS system fonts) after adding or editing cards:

  python3 make_cards.py            render cards that don't exist yet
  python3 make_cards.py --all      re-render every card

Needs Pillow (pip install pillow). Cards with card_style = "tryseo" use the
tryseo.org look and are rendered with Google Chrome; wrap words in *asterisks*
to highlight them in green. The poster itself needs neither.
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


# ---------------------------------------------------------------- TrySEO style
# Mirrors tryseo.org's own share image (src/app/opengraph-image.tsx in the site repo):
# forest background, black-to-moss orb, tilted bone card, sprout leaf, the mascot logo,
# an Outfit 700 headline with *highlighted* words in sprout, and the site's tagline.
# Rendered with headless Chrome so the site's fonts and CSS carry over exactly.

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LOGO_FACE = """
<path d="M16.3 9.4C17.4 5.3 20.8 2.7 25.8 2.5C24.5 6.7 21.1 9.5 16.3 9.4Z" fill="#68ef3f"/>
<circle cx="4.4" cy="19.6" r="2.7" fill="#b7bda5"/><circle cx="4.4" cy="19.6" r="1.35" fill="#26a200"/>
<circle cx="27.6" cy="19.6" r="2.7" fill="#b7bda5"/><circle cx="27.6" cy="19.6" r="1.35" fill="#26a200"/>
<path d="M16 8.8C21.4 9 27.4 12.4 27.4 19.2C27.4 25 22.8 28.4 16 28.4C9.2 28.4 4.6 25 4.6 19.2C4.6 12.4 10.6 9 16 8.8Z" fill="#ffffff"/>
<rect x="6.6" y="12.9" width="18.8" height="12.6" rx="6.3" fill="#d2f8c4"/>
<rect x="7.8" y="14" width="16.4" height="10.4" rx="5.2" fill="#122314"/>
<path d="M10 15.9Q11.2 15.2 12.8 15.2" fill="none" stroke="#ffffff" stroke-opacity="0.3" stroke-width="0.8" stroke-linecap="round"/>
<rect x="10.6" y="16.7" width="2.9" height="4.6" rx="1.45" fill="#68ef3f"/>
<rect x="18.5" y="16.7" width="2.9" height="4.6" rx="1.45" fill="#68ef3f"/>
"""
TRYSEO_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Outfit; src: url("{fonts}/Outfit-latin.woff2") format("woff2"); font-weight: 100 900; }}
@font-face {{ font-family: Geist; src: url("{fonts}/Geist-latin.woff2") format("woff2"); font-weight: 100 900; }}
* {{ margin: 0; box-sizing: border-box; }}
body {{ width: 1200px; height: 675px; overflow: hidden; background: #122314; color: #fff; font-family: Geist, sans-serif; position: relative; }}
.orb {{ position: absolute; top: -70px; right: 170px; width: 320px; height: 320px; border-radius: 9999px;
        background: linear-gradient(160deg, #000 0%, #273f2b 100%); }}
.card {{ position: absolute; top: 160px; right: 72px; width: 300px; height: 220px; padding: 32px; border-radius: 24px;
         background: #f2f5eb; transform: rotate(-6deg); display: flex; flex-direction: column; justify-content: space-between; }}
.row {{ display: flex; align-items: center; gap: 14px; }}
.dot {{ width: 40px; height: 40px; border-radius: 9999px; background: #30322a; }}
.bar {{ height: 14px; border-radius: 9999px; background: #d9deca; }}
.lines {{ display: flex; flex-direction: column; gap: 12px; }}
.leaf {{ position: absolute; top: 350px; right: 300px; transform: rotate(12deg); }}
.wrap {{ position: absolute; inset: 72px; display: flex; flex-direction: column; justify-content: space-between; }}
.brand {{ display: flex; align-items: center; gap: 16px; font-family: Outfit; font-weight: 700; font-size: 40px; letter-spacing: -1px; }}
.brand b {{ color: #68ef3f; font-weight: 700; }}
h1 {{ font-family: Outfit; font-weight: 700; line-height: 0.98; letter-spacing: -0.03em; max-width: 690px; }}
h1 em {{ font-style: normal; color: #68ef3f; }}
.tag {{ margin-top: 28px; font-size: 28px; color: #b7bda5; letter-spacing: -0.5px; }}
</style></head><body>
<div class="orb"></div>
<div class="card"><div class="row"><div class="dot"></div><div class="bar" style="width:120px"></div></div>
  <div class="lines"><div class="bar" style="width:236px"></div><div class="bar" style="width:200px"></div><div class="bar" style="width:150px"></div></div></div>
<svg class="leaf" width="128" height="128" viewBox="0 0 24 24"><path d="M4.5 19.5C4.5 10.6 10.6 4.5 19.5 4.5c0 8.9-6.1 15-15 15Z" fill="#68ef3f"/>
  <path d="M4.5 19.5 14.5 9.5" stroke="#fff" stroke-opacity="0.5" stroke-width="1.4" stroke-linecap="round"/></svg>
<div class="wrap">
  <div class="brand"><svg width="60" height="60" viewBox="0 0 32 32">{logo}</svg><span>TrySEO<b>.org</b></span></div>
  <div><h1 id="h">{headline}</h1><div class="tag">Articles · Backlinks · AI search visibility</div></div>
</div>
<script>
// Largest size (up to 92px) that keeps the headline within 3 lines and above the tagline.
const h = document.getElementById("h");
document.fonts.ready.then(() => {{
  for (let s = 92; s >= 52; s -= 2) {{ h.style.fontSize = s + "px"; if (h.offsetHeight <= s * 0.98 * 3 + 4) break; }}
}});
</script></body></html>"""


def render_tryseo(card, out):
    import html, re, subprocess, tempfile
    headline = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html.escape(card))
    page = TRYSEO_HTML.format(fonts=(ROOT / "fonts").as_uri(), logo=LOGO_FACE, headline=headline)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "card.html"
        src.write_text(page)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                        "--force-device-scale-factor=1", "--window-size=1200,675", "--virtual-time-budget=3000",
                        f"--screenshot={out}", src.as_uri()], check=True, capture_output=True, timeout=60)
    Image.open(out).convert("RGB").save(out, optimize=True)


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
        if post.get("card_style") == "tryseo":
            render_tryseo(post["card"], out)
        else:
            render(post["card"], post.get("card_footer", ""), out)
        count += 1
        print(f"{post['image']}  ({out.stat().st_size // 1024} KB)")
    print(f"rendered {count} card(s)")


if __name__ == "__main__":
    main()
