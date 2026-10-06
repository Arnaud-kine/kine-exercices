import os, subprocess, shutil, sys
from PIL import Image, ImageDraw, ImageFont
SRC, OUT, NAME = sys.argv[1], sys.argv[2], sys.argv[3]
files = sorted(f for f in os.listdir(SRC) if f.startswith('f_') and f.endswith('.png')); n = len(files)
imgs = [Image.open(f'{SRC}/{f}').convert('RGB') for f in files]; W, H = imgs[0].size
fb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26); fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
PH = [('Départ', 'À quatre pattes, dos plat', [0] * 14), ('Tendre', 'Bras et jambe opposés, sans cambrer', list(range(n))),
      ('Tenir 5 secondes', 'Bassin stable, regard vers le sol', [n - 1] * 36), ('Revenir', 'Lentement, en contrôlant', list(range(n - 1, -1, -1)))]
shutil.rmtree('/tmp/b3d/seq', ignore_errors=True); os.makedirs('/tmp/b3d/seq'); k = 0
for lab, sub, idx in PH:
    for i in idx:
        c = Image.new('RGB', (W, H + 84), 'white'); c.paste(imgs[i], (0, 0)); d = ImageDraw.Draw(c)
        d.text((W // 2, H + 8), lab, font=fb, fill=(20, 38, 43), anchor='ma'); d.text((W // 2, H + 46), sub, font=fs, fill=(91, 107, 112), anchor='ma')
        c.save(f'/tmp/b3d/seq/{k:04d}.png'); k += 1
print('images de la séquence :', k, '| durée à 12 images/s :', round(k / 12, 1), 's')
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '12', '-i', '/tmp/b3d/seq/%04d.png', '-vf', 'minterpolate=fps=24:mi_mode=blend', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '/tmp/b3d/cycle_3d.mp4'], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-stream_loop', '2', '-i', '/tmp/b3d/cycle_3d.mp4', '-c', 'copy', '-movflags', '+faststart', f'{OUT}/{NAME}.mp4'], check=True)
print('vidéo :', round(os.path.getsize(f'{OUT}/{NAME}.mp4') / 1e3), 'Ko')
