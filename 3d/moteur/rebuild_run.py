
import json, os, subprocess, time, shutil, sys
T0 = time.time(); BUDGET = float(sys.argv[1])
M = json.load(open('/tmp/b3d/rebuild_map2.json'))['mapping']; OUT = '/tmp/b3d/out3d_new'; os.makedirs(OUT, exist_ok=True)
NAMES = {'d-etirement-du-mollet-a-l-espalier': 'Étirement du mollet à l’espalier', 'd-extension-de-poignet-excentriquex': 'Extension de poignet excentrique', 'd-mobilisation-active-du-poignet': 'Mobilisation active du poignet',
 'd-montee-sur-pointes-avec-appui-espalier': 'Montée sur pointes avec appui espalier', 'd-pont-avec-ballon-entre-les-genoux': 'Pont avec ballon entre les genoux', 'd-pont-fessier-avec-activation-du-plancher': 'Pont fessier avec activation du plancher pelvien',
 'd-renforcement-du-poignet-en-flexion-exten': 'Renforcement du poignet en flexion/extension'}
done = 0
for slug, fr in M.items():
    if os.path.exists(f'{OUT}/{slug}.mp4'): continue
    if time.time() - T0 > BUDGET: break
    parent, base = os.path.dirname(fr), os.path.basename(fr); tmp = f'/tmp/b3d/_tmp_{slug}'; os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ); 
    if slug in NAMES: env['POST_NAME'] = NAMES[slug]
    r = subprocess.run(['python3', '/tmp/b3d/post3d.py', parent, tmp, base], env=env, capture_output=True, text=True)
    if os.path.exists(f'{tmp}/{base}.mp4'):
        shutil.copyfile(f'{tmp}/{base}.mp4', f'{OUT}/{slug}.mp4'); shutil.copyfile(f'{tmp}/{base}.jpg', f'{OUT}/{slug}.jpg'); done += 1
    else: print('ERREUR', slug, r.stderr[-200:])
    shutil.rmtree(tmp, ignore_errors=True)
n = len([f for f in os.listdir(OUT) if f.endswith('.mp4')])
print(done, 'reconstruites dans cette étape |', n, 'au total sur', len(M), '|', round(time.time() - T0), 's')
