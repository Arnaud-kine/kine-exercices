import numpy as np, sys
T = '/tmp/b3d/mhrepo/makehuman/data/targets/macrodetails/'
def load_target(path):
    idx, d = [], []
    for l in open(path):
        if l.startswith('#') or not l.strip(): continue
        p = l.split(); idx.append(int(p[0])); d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, dtype=int), np.array(d, dtype=float).reshape(-1, 3)
def build(gender, years, out, muscle='averagemuscle', wval=0.5):
    lines = open('/tmp/b3d/base.obj').read().split('\n')
    vi = [i for i, l in enumerate(lines) if l.startswith('v ')]
    V = np.array([[float(x) for x in lines[i].split()[1:4]] for i in vi])
    old = max(0.0, min(1.0, (years - 25) / 65.0)); young = 1 - old
    G = {'female': 1 - gender, 'male': gender}; A = {'young': young, 'old': old}
    W = []
    for r in ('african', 'asian', 'caucasian'):
        for g, wg in G.items():
            for a, wa in A.items():
                w = (1 / 3) * wg * wa
                if w > 1e-6: W.append((f'{r}-{g}-{a}.target', w))
    WT = {'averageweight': 1 - abs(wval - 0.5) * 2, 'maxweight': max(0.0, (wval - 0.5) * 2), 'minweight': max(0.0, (0.5 - wval) * 2)}
    for g, wg in G.items():
        for a, wa in A.items():
            for wn, wwt in WT.items():
                w = wg * wa * wwt
                if w > 1e-6: W.append((f'universal-{g}-{a}-{muscle}-{wn}.target', w))
    D = np.zeros_like(V)
    for name, w in W:
        idx, d = load_target(T + name); D[idx] += w * d
    V2 = V + D
    for k, i in enumerate(vi): lines[i] = 'v %.6f %.6f %.6f' % tuple(V2[k])
    open(out, 'w').write('\n'.join(lines))
    body = V2[:13380]
    return round((body[:, 1].max() - body[:, 1].min()) / 10, 3)
if __name__ == '__main__':
    for nom, g, a, wv in [('femme_adulte', 0, 40, 0.5), ('homme_adulte', 1, 40, 0.5), ('femme_senior', 0, 80, 0.62), ('homme_senior', 1, 80, 0.62)]:
        h = build(g, a, f'/tmp/b3d/perso_{nom}.obj', wval=wv); print(nom, '-> taille du corps', h, 'm')
