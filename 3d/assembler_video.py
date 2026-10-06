import os, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
SRC, OUT, TITRE = sys.argv[1], sys.argv[2], sys.argv[3]
FPS = 24; N = len([f for f in os.listdir(SRC) if f.startswith('f') and f.endswith('.png')])
frames = [Image.open(f'{SRC}/f{i:03d}.png').convert('RGB') for i in range(N)]
W, H = frames[0].size
try: fb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(H * 0.058)); fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', int(H * 0.04)); ft = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', int(H * 0.036))
except Exception: fb = fs = ft = None
phases = [('Départ', 'À quatre pattes, dos plat', 29, 'rest'), ('Tendre', 'Bras et jambe opposés, sans cambrer', N - 1, 'up'), ('Tenir 5 secondes', 'Bassin stable, regard vers le sol', 72, 'hold'), ('Revenir', 'Lentement, en contrôlant', N - 1, 'down')]
seq = []
for lab, sub, n, kind in phases:
    for j in range(n):
        idx = 0 if kind == 'rest' else (j + 1 if kind == 'up' else (N - 1 if kind == 'hold' else N - 2 - j))
        seq.append((idx, lab, sub))
def draw(im, lab, sub):
    im = im.copy(); d = ImageDraw.Draw(im)
    d.rectangle((0, H - int(H * 0.17), W, H), fill=(255, 255, 255))
    for txt, f, y, col in ((lab, fb, H - int(H * 0.165), (20, 38, 43)), (sub, fs, H - int(H * 0.09), (91, 107, 112))):
        w = d.textlength(txt, font=f); d.text(((W - w) / 2, y), txt, font=f, fill=col)
    d.text((10, 8), TITRE, font=ft, fill=(110, 125, 130)); return im
shutil.rmtree(f'{OUT}/seq', ignore_errors=True); os.makedirs(f'{OUT}/seq')
for i, (idx, lab, sub) in enumerate(seq): draw(frames[idx], lab, sub).save(f'{OUT}/seq/{i:04d}.png')
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(FPS), '-i', f'{OUT}/seq/%04d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', f'{OUT}/cycle.mp4'], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-stream_loop', '2', '-i', f'{OUT}/cycle.mp4', '-c', 'copy', '-movflags', '+faststart', f'{OUT}/video.mp4'], check=True)
print('images dans le cycle :', len(seq), '| durée :', round(len(seq) / FPS, 1), 's')
