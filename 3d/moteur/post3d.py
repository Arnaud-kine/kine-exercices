import os, sys, json, shutil, subprocess, math
import numpy as np, cv2
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
ROOT, OUT = sys.argv[1], sys.argv[2]; slugs = sys.argv[3:]
BG = (244, 246, 247)
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; FR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def comp(p):
    im = np.asarray(Image.open(p).convert('RGBA')).astype(np.float32) / 255.0; a = im[:, :, 3]; rgb = im[:, :, :3]
    fig = ((a > 0.80) & (rgb.max(axis=2) > 0.045)).astype(np.uint8); edge = cv2.dilate(fig, np.ones((3, 3), np.uint8)).astype(bool)
    shadow = cv2.GaussianBlur(np.where(edge, 0, a), (0, 0), 3.0); shadow = np.clip((shadow - 0.14) / 0.86, 0, 1) * 0.85   # ombre lissée, bruit de fond supprimé, ombre de contact conservée
    base = np.ones_like(rgb) * (np.array(BG, np.float32) / 255.0); base = base * (1 - shadow[:, :, None])
    ae = np.where(edge, a, 0)[:, :, None]; out = base * (1 - ae) + rgb * ae
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)), (a * 255).astype(np.uint8)
def clean(im, h=2.5):
    a = cv2.fastNlMeansDenoisingColored(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR), None, h, h, 5, 15); im = Image.fromarray(cv2.cvtColor(a, cv2.COLOR_BGR2RGB))
    im = ImageEnhance.Contrast(im).enhance(1.25); im = ImageEnhance.Color(im).enhance(1.20); return ImageEnhance.Brightness(im).enhance(0.97)
BAND = 0.075   # bandeau fin et identique sur toutes les vidéos : 7,5 % de la hauteur, placé SOUS l'image
def caption(im, name, lab, W, H):
    bh = int(H * BAND); bh += bh % 2; H2 = H + bh; H2 += H2 % 2; bh = H2 - H
    out = Image.new('RGB', (W, H2), (255, 255, 255)); out.paste(im, (0, 0)); d = ImageDraw.Draw(out)
    fb = ImageFont.truetype(FB, max(11, int(H * 0.038))); ft = ImageFont.truetype(FR, max(9, int(H * 0.034)))
    w = d.textlength(lab, font=fb); d.text(((W - w) / 2, H + (bh - int(H * 0.038)) / 2 - 2), lab, font=fb, fill=(20, 38, 43))
    d.text((6, 4), name[:48], font=ft, fill=(95, 110, 115)); return out
for slug in slugs:
    src = f'{ROOT}/{slug}'; m = json.load(open(f'{src}/meta.json')); W, H = m['w'], m['h']
    if os.environ.get('POST_NAME'): m['name'] = os.environ['POST_NAME']   # nom affiché, pour les variantes qui réutilisent les images d'un autre exercice; os.makedirs(OUT, exist_ok=True)
    frames = sorted(f for f in os.listdir(src) if f.startswith('f') and f.endswith('.png')); n = len(frames)
    tmp = f'{src}/_c'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for i, f in enumerate(frames): clean(comp(f'{src}/{f}')[0]).save(f'{tmp}/{i:03d}.png')
    sub = H - int(H * 0.13)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(n / float(m.get('dur', 2.0))), '-i', f'{tmp}/%03d.png', '-vf', 'minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:vsbmc=1', f'{tmp}/i%03d.png'], check=True)
    out_frames = sorted(f for f in os.listdir(tmp) if f.startswith('i')); L = [Image.open(f'{tmp}/{f}').convert('RGB') for f in out_frames]
    A, B = L[0], L[-1]; hold_s = 1.2 if m.get('hold') else 0.4
    PU, PS = os.environ.get('PAUSE_U'), float(os.environ.get('PAUSE_S', '0') or 0)
    def at(pos):                                           # image à une position fractionnaire de la descente (fondu entre deux images voisines)
        pos = max(0.0, min(len(L) - 1.0, pos)); a = int(pos); b = min(a + 1, len(L) - 1); return Image.blend(L[a], L[b], pos - a) if b != a else L[a]
    if PU:
        ks = float(PU) * (len(L) - 1); top = len(L) - 1.0; n1, n3 = 36, 46; n2 = int(24 * PS); RETOUR = []
        for q in range(n1):                               # la descente ralentit jusqu'à l'arrêt (vitesse nulle à l'arrivée)
            s = (q + 1) / n1; RETOUR.append((at(top - (top - ks) * (1 - (1 - s) ** 3)), 'Retour lent'))
        for q in range(n2):                               # position tenue : très léger balancement, jamais une image figée
            RETOUR.append((at(ks + 0.9 * math.sin(2 * math.pi * q / n2) * math.sin(math.pi * q / n2)), 'Pause'))
        for q in range(n3):                               # la reprise est douce (vitesse nulle au départ et à l'arrivée sur la chaise)
            s = (q + 1) / n3; RETOUR.append((at(ks - ks * (s ** 3 * (s * (6 * s - 15) + 10))), 'Retour lent'))
    else: RETOUR = [(x, 'Retour lent') for x in reversed(L)]
    seq = [(A, 'Départ')] * 19 + [(x, 'Mouvement lent') for x in L] + [(B, 'Position finale')] * int(24 * hold_s) + RETOUR + [(A, 'Départ')] * 10
    if m.get('noreturn'): seq = [(A, 'Départ')] * 19 + [(x, 'Mouvement lent') for x in L] + [(B, 'Position finale')] * int(24 * 1.2)   # marche : on s'arrête à la fin, sans revenir en arrière
    sq = f'{tmp}/s'; os.makedirs(sq)
    if os.environ.get('CAPTION_ALL'): seq = [(im, os.environ['CAPTION_ALL']) for im, lab in seq]   # exercice tenu : le même texte pendant toute la vidéo
    for i, (im, lab) in enumerate(seq): caption(im, m['name'], lab, W, H).save(f'{sq}/{i:04d}.png')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '24', '-i', f'{sq}/%04d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '23', '-movflags', '+faststart', f'{OUT}/{slug}.mp4'], check=True)
    # photo : départ | arrivée, recadrés sur le personnage
    fa, fb_ = (f'{src}/A.png', f'{src}/B.png') if os.path.exists(f'{src}/A.png') else (f'{src}/{frames[0]}', f'{src}/{frames[-1]}')
    pa, aa = comp(fa); pb_, ab = comp(fb_); pa, pb_ = clean(pa, 4.0 if pa.width < 500 else 2.0), clean(pb_, 4.0 if pb_.width < 500 else 2.0)
    if pa.width < 500: pa, pb_ = pa.resize((pa.width * 2, pa.height * 2), Image.LANCZOS), pb_.resize((pb_.width * 2, pb_.height * 2), Image.LANCZOS); aa = np.asarray(Image.fromarray(aa).resize((aa.shape[1] * 2, aa.shape[0] * 2))); ab = np.asarray(Image.fromarray(ab).resize((ab.shape[1] * 2, ab.shape[0] * 2)))
    mask = (np.maximum(aa, ab) > 140); ys, xs = np.where(mask); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); mx, my = int((x1 - x0) * 0.06) + 8, int((y1 - y0) * 0.08) + 8
    box = (max(0, x0 - mx), max(0, y0 - my), min(pa.width, x1 + mx), min(pa.height, y1 + my)); ca, cb = pa.crop(box), pb_.crop(box)
    ph = Image.new('RGB', (ca.width * 2 + 6, ca.height), (255, 255, 255)); ph.paste(ca, (0, 0)); ph.paste(cb, (ca.width + 6, 0))
    if ph.height > 420: ph = ph.resize((int(ph.width * 420 / ph.height), 420), Image.LANCZOS)
    ph.save(f'{OUT}/{slug}.jpg', quality=88); shutil.rmtree(tmp, ignore_errors=True)
    print('PRET', slug, f'{os.path.getsize(OUT + "/" + slug + ".mp4") // 1000} Ko', ph.size, flush=True)
