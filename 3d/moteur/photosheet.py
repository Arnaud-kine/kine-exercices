import sys, os
from PIL import Image, ImageDraw
d = '/tmp/b3d/out3d'; names = sys.argv[2:] or sorted(f[:-4] for f in os.listdir(d) if f.endswith('.jpg'))
rows = []
for n in names:
    im = Image.open(f'{d}/{n}.jpg').convert('RGB'); w = 760; im = im.resize((w, int(im.height * w / im.width))); r = Image.new('RGB', (w, im.height + 14), 'white'); r.paste(im, (0, 14)); ImageDraw.Draw(r).text((3, 1), n[:60], fill=(20, 38, 43)); rows.append(r)
s = Image.new('RGB', (760, sum(r.height for r in rows)), 'white'); y = 0
for r in rows: s.paste(r, (0, y)); y += r.height
s.save(sys.argv[1]); print(s.size)
