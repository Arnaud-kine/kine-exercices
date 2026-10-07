import importlib.util, os, shutil, json
s = importlib.util.spec_from_file_location('specs', '/tmp/b3d/specs.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
SRC, DST = '/tmp/b3d/out3d', '/home/claude/repo/media/3d'; os.makedirs(DST, exist_ok=True)
rendered = {x['slug'] for x in m.SPECS if os.path.exists(f"{SRC}/{x['slug']}.mp4")}
pub = {}
for sl in rendered: pub[sl] = sl
for var, base in m.REUSE.items():
    if base in rendered: pub[var] = base
n = 0
for sl, base in pub.items():
    for ext in ('mp4', 'jpg'):
        shutil.copyfile(f'{SRC}/{base}.{ext}', f'{DST}/{sl}.{ext}'); n += 1
json.dump(pub, open('/tmp/b3d/published.json', 'w'))
import subprocess; subprocess.run(['python3', '/tmp/b3d/make_thumbs.py'])
print(len(rendered), 'exercices calculés +', len(pub) - len(rendered), 'variantes =', len(pub), 'publiables |', n, 'fichiers')
