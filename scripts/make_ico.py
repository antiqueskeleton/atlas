"""Generate installer/atlas.ico from images/atlas_icon.png.

Run from the project root:  python scripts/make_ico.py
Requires Pillow (pip install Pillow).
"""
from pathlib import Path
from PIL import Image

src = Path("images/atlas_icon.png")
dst = Path("installer/atlas.ico")

if not src.exists():
    raise FileNotFoundError(f"Source image not found: {src}")

img = Image.open(src).convert("RGBA")
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
icons = [img.resize(sz, Image.LANCZOS) for sz in sizes]
icons[0].save(dst, format="ICO", sizes=sizes, append_images=icons[1:])
print(f"Created {dst}  ({len(sizes)} sizes)")
