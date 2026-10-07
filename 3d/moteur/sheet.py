import sys, os, json
from PIL import Image, ImageDraw, ImageFont
root = sys.argv[1]; out = sys.argv[2]; slugs = sys.argv[3:] or sorted(d for d in os.listdir(root) if os.path.exists(f'{root}/{d}/OK'))
def comp(p, w=300):
    im = Image.open(p).convert('RGBA'); bgc = Image.new('RGBA', im.size, (240, 243, 244, 255)); im = Image.alpha_composite(bgc, im).convert('RGB')
    h = int(im.height * w / im.width); return im.resize((w, h))
rows = []
for s in slugs:
    m = json.load(open(f'{root}/{s}/meta.json')); a, b = comp(f'{root}/{s}/A.png'), comp(f'{root}/{s}/B.png')
    h = max(a.height, b.height); r = Image.new('RGB', (600, h + 16), 'white'); r.paste(a, (0, 16)); r.paste(b, (300, 16))
    ImageDraw.Draw(r).text((4, 2), m['name'][:70], fill=(20, 38, 43)); rows.append(r)
sheet = Image.new('RGB', (600, sum(r.height for r in rows)), 'white'); y = 0
for r in rows: sheet.paste(r, (0, y)); y += r.height
sheet.save(out); print(sheet.size)
