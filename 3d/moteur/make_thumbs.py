import json, os, sys, numpy as np
from PIL import Image
BG = np.array([244, 246, 247]); DST = '/home/claude/repo/media/3d'
pub = json.load(open('/tmp/b3d/published.json')); n = 0
for slug in sorted(pub):
    p = f'{DST}/{slug}.jpg'
    if not os.path.exists(p): continue
    im = Image.open(p).convert('RGB'); w, h = im.size; b = im.crop((w // 2 + 3, 0, w, h))        # moitié droite = image d'arrivée
    a = np.asarray(b).astype(int); diff = np.abs(a - BG).max(axis=2) > 38; ys, xs = np.where(diff)
    if len(xs) < 50: b2 = b
    else:
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); mx, my = int((x1 - x0) * 0.10) + 6, int((y1 - y0) * 0.10) + 6
        x0, x1, y0, y1 = max(0, x0 - mx), min(b.width, x1 + mx), max(0, y0 - my), min(b.height, y1 + my); b2 = b.crop((x0, y0, x1, y1))
    W, H = b2.size; tw = max(W, int(H * 4 / 3)); th = max(H, int(W * 3 / 4))                      # complète en 4/3 avec le fond
    canvas = Image.new('RGB', (tw, th), tuple(BG)); canvas.paste(b2, ((tw - W) // 2, (th - H) // 2))
    canvas.resize((288, 216), Image.LANCZOS).save(f'{DST}/{slug}-v.jpg', quality=88); n += 1
print(n, 'vignettes créées')
