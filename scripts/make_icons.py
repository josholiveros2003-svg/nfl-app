"""Draws the app icon (a football over stat bars) at the sizes iPhone/browsers need.
Run: pipeline/.venv/bin/python scripts/make_icons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # draw big, then shrink for smooth edges

img = Image.new("RGB", (S, S), "#0B0F17")
d = ImageDraw.Draw(img)

# Stat bars along the bottom
bars = [(0.22, 0.30, "#34C77B"), (0.40, 0.45, "#34C77B"), (0.58, 0.38, "#D9A441"), (0.76, 0.55, "#34C77B")]
for x, h, c in bars:
    x0 = int(x * S) - 60
    d.rounded_rectangle([x0, int(S * (0.88 - h)), x0 + 120, int(S * 0.88)], radius=24, fill=c)

# Football, drawn flat then rotated
ball = Image.new("RGBA", (S, S), (0, 0, 0, 0))
b = ImageDraw.Draw(ball)
b.ellipse([S * 0.18, S * 0.33, S * 0.82, S * 0.67], fill="#8B4A2B", outline="#F2F4F8", width=18)
b.line([S * 0.36, S * 0.5, S * 0.64, S * 0.5], fill="#F2F4F8", width=22)
for i in range(5):
    x = S * (0.40 + i * 0.05)
    b.line([x, S * 0.46, x, S * 0.54], fill="#F2F4F8", width=18)
ball = ball.rotate(30, resample=Image.BICUBIC).transform(
    (S, S), Image.AFFINE, (1, 0, 0, 0, 1, int(S * 0.12)), resample=Image.BICUBIC)
img.paste(ball, (0, 0), ball)

out = ROOT / "public"
out.mkdir(exist_ok=True)
for name, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)]:
    img.resize((size, size), Image.LANCZOS).save(out / name)
img.resize((1024, 1024)).save(ROOT / "assets" / "icon.png")
img.resize((48, 48), Image.LANCZOS).save(ROOT / "assets" / "favicon.png")
print("icons written")
