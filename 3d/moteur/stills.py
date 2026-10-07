import sys, os, json, numpy as np, cv2
from PIL import Image
sys.argv = [sys.argv[0]] + sys.argv[1:]
ROOT, OUT = sys.argv[1], sys.argv[2]; slugs = sys.argv[3:]
BG = (244, 246, 247)
def comp(p):
    im = np.asarray(Image.open(p).convert('RGBA')).astype(np.float32) / 255.0; a = im[:, :, 3]; rgb = im[:, :, :3]
    fig = ((a > 0.80) & (rgb.max(axis=2) > 0.045)).astype(np.uint8); edge = cv2.dilate(fig, np.ones((3, 3), np.uint8)).astype(bool)
    shadow = cv2.GaussianBlur(np.where(edge, 0, a), (0, 0), 1.6); shadow = np.clip((shadow - 0.07) / 0.93, 0, 1); base = np.ones_like(rgb) * (np.array(BG, np.float32) / 255.0); base = base * (1 - shadow[:, :, None])
    ae = np.where(edge, a, 0)[:, :, None]; out = base * (1 - ae) + rgb * ae; return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)), (a * 255).astype(np.uint8)
for slug in slugs:
    pa, aa = comp(f'{ROOT}/{slug}/A.png'); pb, ab = comp(f'{ROOT}/{slug}/B.png')
    ys, xs = np.where(np.maximum(aa, ab) > 140); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); mx, my = int((x1 - x0) * 0.06) + 8, int((y1 - y0) * 0.10) + 8
    box = (max(0, x0 - mx), max(0, y0 - my), min(pa.width, x1 + mx), min(pa.height, y1 + my)); ca, cb = pa.crop(box), pb.crop(box)
    s = Image.new('RGB', (ca.width, ca.height * 2 + 6), 'white'); s.paste(ca, (0, 0)); s.paste(cb, (0, ca.height + 6))
    s.save(f'{OUT}/{slug}-images.png'); print('IMAGES', slug, s.size)
