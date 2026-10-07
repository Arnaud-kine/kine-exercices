import sys
from PIL import Image, ImageDraw
out = sys.argv[1]; items = [a.split('=', 1) for a in sys.argv[2:]]   # slug=Libellé
cells = []
for i, (sl, lab) in enumerate(items, 1):
    im = Image.open(f'/tmp/b3d/st_out/{sl}-images.png').convert('RGB'); w = 400; im = im.resize((w, int(im.height * w / im.width)))
    c = Image.new('RGB', (w, im.height + 22), 'white'); c.paste(im, (0, 22)); d = ImageDraw.Draw(c); d.rectangle((0, 0, 24, 18), fill=(200, 30, 30)); d.text((8, 3), str(i), fill='white'); d.text((30, 4), lab, fill=(20, 38, 43)); cells.append(c)
cols = 2; rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
H = sum(max(c.height for c in r) for r in rows) + 8 * len(rows); s = Image.new('RGB', (408 * cols, H), 'white'); y = 0
for r in rows:
    for k, c in enumerate(r): s.paste(c, (k * 408, y))
    y += max(c.height for c in r) + 8
s.save(out); print(s.size)
