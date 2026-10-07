import bpy, bmesh, sys, math, json, os, time, importlib.util
from mathutils import Vector, Matrix

ARGS = sys.argv[sys.argv.index('--') + 1:]
CHAR, SPECS, OUTROOT, BUDGET, NF, SAMP, MODE = ARGS[0], ARGS[1], ARGS[2], float(ARGS[3]), int(ARGS[4]), int(ARGS[5]), ARGS[6]   # MODE : full | test
ONLY = ARGS[7].split(',') if len(ARGS) > 7 and ARGS[7] else None
T0 = time.time()
CH = {'FA': ('perso_femme_adulte.obj', '#0E8B85', 'F', 'adulte'), 'MA': ('perso_homme_adulte.obj', '#2F6DA4', 'M', 'adulte'),
      'FS': ('perso_femme_senior.obj', '#0E8B85', 'F', 'senior'), 'MS': ('perso_homme_senior.obj', '#2F6DA4', 'M', 'senior')}
OBJ, TOPCOL, GEN, AGE = CH[CHAR]; OBJ = '/tmp/b3d/' + OBJ
RIG = '/tmp/b3d/mhrepo/makehuman/data/rigs/'

def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1)
def mat(name, col, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(col); b.inputs['Roughness'].default_value = rough; return m

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
V = []; groups = {}; cur = None
for l in open(OBJ):
    if l.startswith('v '): V.append([float(x) for x in l.split()[1:4]])
    elif l.startswith('g '): cur = l.split()[1]; groups.setdefault(cur, [])
    elif l.startswith('f ') and cur: groups[cur].append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
NB = 13380
P = [Vector((p[0] * 0.1, -p[2] * 0.1, p[1] * 0.1)) for p in V]
zmin = min(p.z for p in P[:NB]); P = [Vector((p.x, p.y, p.z - zmin)) for p in P]
height = max(p.z for p in P[:NB]); k = height / 1.666
me = bpy.data.meshes.new('corps'); body = bpy.data.objects.new('Corps', me); scene.collection.objects.link(body)
me.from_pydata([tuple(p) for p in P[:NB]], [], groups['body']); me.update()
ra = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT'); ra.data.foreach_set('vector', [c for p in P[:NB] for c in p])
for p in me.polygons: p.use_smooth = True
sk = json.load(open(RIG + 'default.mhskel')); wts = json.load(open(RIG + 'default_weights.mhw'))['weights']
def jpos(name): idx = sk['joints'][name]; return sum((P[i] for i in idx), Vector()) / len(idx)
arm_d = bpy.data.armatures.new('Squelette'); arm = bpy.data.objects.new('Squelette', arm_d); scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
for n, b in sk['bones'].items():
    e = arm_d.edit_bones.new(n); e.head = jpos(b['head']); e.tail = jpos(b['tail'])
    if (e.tail - e.head).length < 1e-4: e.tail = e.head + Vector((0, 0, 0.01))
for n, b in sk['bones'].items():
    if b['parent']: arm_d.edit_bones[n].parent = arm_d.edit_bones[b['parent']]
bpy.ops.object.mode_set(mode='OBJECT')
body.parent = arm; names = list(sk['bones'].keys())
for n in names: body.vertex_groups.new(name=n)
for n, lst in wts.items():
    if n in body.vertex_groups:
        vg = body.vertex_groups[n]
        for vi, w in lst:
            if vi < NB: vg.add([vi], w, 'REPLACE')
body.modifiers.new('Armature', 'ARMATURE').object = arm
sub = body.modifiers.new('Sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1

def corps_materiau():
    m = bpy.data.materials.new('Corps'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.55; bsdf.inputs['Subsurface Weight'].default_value = 0.10; bsdf.inputs['Subsurface Radius'].default_value = (0.9, 0.35, 0.25)
    att = N.new('ShaderNodeAttribute'); att.attribute_name = 'rest'; att.attribute_type = 'GEOMETRY'; sep = N.new('ShaderNodeSeparateXYZ'); Lk.new(att.outputs['Vector'], sep.inputs[0])
    def M(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: Lk.new(v, n.inputs[i])
        return n.outputs[0]
    X, Y, Z = sep.outputs[0], sep.outputs[1], sep.outputs[2]; AX = M('ABSOLUTE', X)
    between = lambda v, lo, hi: M('MULTIPLY', M('GREATER_THAN', v, lo), M('LESS_THAN', v, hi)); zl = lambda zw: zw * k
    shorts = M('MULTIPLY', between(Z, zl(0.60), zl(1.00)), M('LESS_THAN', AX, 0.30 * k))
    torso = M('MULTIPLY', between(Z, zl(1.00), zl(1.44)), M('LESS_THAN', AX, 0.215 * k))
    neck = M('MULTIPLY', M('LESS_THAN', AX, 0.085 * k), M('GREATER_THAN', Z, zl(1.385)))
    def sq(v): return M('MULTIPLY', v, v)
    def d2(sx): return M('ADD', M('ADD', sq(M('SUBTRACT', X, sx)), sq(Y)), sq(M('SUBTRACT', Z, zl(1.38))))
    near = M('LESS_THAN', M('MINIMUM', d2(0.185 * k), d2(-0.185 * k)), (0.118 * k) ** 2)
    sleeve = M('MULTIPLY', M('MULTIPLY', near, M('GREATER_THAN', AX, 0.17 * k)), M('GREATER_THAN', Z, zl(1.20)))
    shirt = M('MAXIMUM', M('MULTIPLY', torso, M('SUBTRACT', 1.0, neck)), sleeve)
    def col(h): n = N.new('ShaderNodeRGB'); n.outputs[0].default_value = lin(h); return n.outputs[0]
    def mix(f, c1, c2): n = N.new('ShaderNodeMixRGB'); Lk.new(f, n.inputs[0]); Lk.new(c1, n.inputs[1]); Lk.new(c2, n.inputs[2]); return n.outputs[0]
    c = mix(shirt, col('#D8B193'), col(TOPCOL)); c = mix(shorts, c, col('#33454D')); Lk.new(c, bsdf.inputs['Base Color']); return m
body.data.materials.append(corps_materiau())

HAIRC = {'F': {'adulte': '#4B3425', 'senior': '#C7C7C4'}, 'M': {'adulte': '#3B2B22', 'senior': '#CDCDCA'}}[GEN][AGE]
bmh = bmesh.new(); bmh.from_mesh(body.data); bmh.faces.ensure_lookup_table()
headv = [v for v in bmh.verts if v.co.z > 0.88 * height]; yc = (min(v.co.y for v in headv) + max(v.co.y for v in headv)) / 2; keep = set()
for f in bmh.faces:
    c = f.calc_center_median(); zw = c.z
    top = zw > 0.962 * height and not (GEN == 'M' and AGE == 'senior' and abs(c.x) < 0.07 * k)
    back = zw > 0.905 * height and c.y > yc + 0.005; side = zw > 0.935 * height and abs(c.x) > 0.075 * k and c.y > yc - 0.04
    long_ = GEN == 'F' and 0.83 * height < zw <= 0.905 * height and c.y > yc + 0.012 and abs(c.x) < 0.11 * k
    if top or back or side or long_: keep.add(f.index)
bmesh.ops.delete(bmh, geom=[f for f in bmh.faces if f.index not in keep], context='FACES')
hm = bpy.data.meshes.new('cheveux'); bmh.to_mesh(hm); bmh.free()
hair = bpy.data.objects.new('Cheveux', hm); scene.collection.objects.link(hair); hair.parent = arm
for n in names: hair.vertex_groups.new(name=n)
bvert = {tuple(round(c, 6) for c in v.co): v.index for v in body.data.vertices}
for v in hair.data.vertices:
    bi = bvert.get(tuple(round(c, 6) for c in v.co))
    if bi is not None:
        for g in body.data.vertices[bi].groups: hair.vertex_groups[g.group].add([v.index], g.weight, 'REPLACE')
hair.data.materials.append(mat('Cheveux', HAIRC, 0.62)); hair.modifiers.new('Armature', 'ARMATURE').object = arm
so = hair.modifiers.new('Epaisseur', 'SOLIDIFY'); so.thickness = 0.011; so.offset = 1.0
for p in hair.data.polygons: p.use_smooth = True
hs = hair.modifiers.new('Lisse', 'SUBSURF'); hs.levels = 1; hs.render_levels = 1
def mesh_from_group(name, objname):
    fs = groups[name]; used = sorted({i for f in fs for i in f}); remap = {o: n for n, o in enumerate(used)}
    m = bpy.data.meshes.new(objname); m.from_pydata([tuple(P[i]) for i in used], [], [[remap[i] for i in f] for f in fs]); m.update()
    o = bpy.data.objects.new(objname, m); scene.collection.objects.link(o); return o
def eye_material(center, iris_hex):
    m = bpy.data.materials.new('Oeil'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.12
    tc = N.new('ShaderNodeTexCoord'); sb = N.new('ShaderNodeVectorMath'); sb.operation = 'SUBTRACT'; sb.inputs[1].default_value = center; Lk.new(tc.outputs['Object'], sb.inputs[0])
    nm = N.new('ShaderNodeVectorMath'); nm.operation = 'NORMALIZE'; Lk.new(sb.outputs[0], nm.inputs[0])
    dt = N.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'; dt.inputs[1].default_value = (0, -1, 0); Lk.new(nm.outputs[0], dt.inputs[0])
    rp = N.new('ShaderNodeValToRGB'); rp.color_ramp.interpolation = 'CONSTANT'; rp.color_ramp.elements[0].position = 0.0; rp.color_ramp.elements[0].color = lin('#EDEDEA')
    e1 = rp.color_ramp.elements.new(0.90); e1.color = lin(iris_hex); e2 = rp.color_ramp.elements.new(0.975); e2.color = lin('#101010')
    Lk.new(dt.outputs['Value'], rp.inputs['Fac']); Lk.new(rp.outputs['Color'], bsdf.inputs['Base Color']); return m
def rigid_head(o):
    o.parent = arm; vg = o.vertex_groups.new(name='head'); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE'); o.modifiers.new('Armature', 'ARMATURE').object = arm
irisc = '#5A3E2B' if AGE == 'adulte' else '#5F7F8E'
for gname, oname in (('helper-l-eye', 'OeilG'), ('helper-r-eye', 'OeilD')):
    e = mesh_from_group(gname, oname); cen = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)
    e.data.materials.append(eye_material(cen, irisc)); rigid_head(e)
    for p in e.data.polygons: p.use_smooth = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(cen.x, cen.y - 0.012, cen.z + 0.030 * k))
    br = bpy.context.active_object; br.name = 'Sourcil'; br.scale = (0.026 * k, 0.0065 * k, 0.0058 * k); br.rotation_euler = (0, math.radians(-8 if cen.x > 0 else 8), 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True); br.data.materials.append(mat('Sourcil', HAIRC if AGE == 'senior' else '#34261E', 0.8)); rigid_head(br)
    for p in br.data.polygons: p.use_smooth = True

# ---------- moteur de poses : directions en repère monde (f = devant du personnage debout = -Y, b = +Y, u/d = haut/bas, l = +X gauche du personnage, r = -X) ----------
pb = arm.pose.bones
TOK = {'f': (0, -1, 0), 'b': (0, 1, 0), 'u': (0, 0, 1), 'd': (0, 0, -1), 'l': (1, 0, 0), 'r': (-1, 0, 0)}
def V3(s):
    if isinstance(s, (tuple, list, Vector)): return Vector(s).normalized()
    v = Vector((0, 0, 0))
    for ch in s: v += Vector(TOK[ch.lower()])
    return v.normalized()
def refresh(): bpy.context.view_layer.update()
def aim(name, d):
    p = pb[name]; m = p.matrix.copy(); cur = (m.to_3x3() @ Vector((0, 1, 0))).normalized(); q = cur.rotation_difference(Vector(d).normalized()); h = m.translation.copy()
    p.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ m; refresh()
def reset_pose():
    for p in pb: p.location = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0)
    refresh()
POST = {'stand': (0, 0, 0), 'quad': (76, 0, 0), 'prone': (90, 0, 0), 'supine': (-90, 0, 180), 'side': (-90, 90, 180)}   # tangage, roulis (autour de Y monde, après), lacet
def root_rot(post):
    pitch, roll, yaw = POST[post]
    return Matrix.Rotation(math.radians(roll), 3, 'Y') @ Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'X')
def set_root(post):
    R = root_rot(post).to_4x4(); hips = (arm.data.bones['pelvis.L'].head_local + arm.data.bones['pelvis.R'].head_local) / 2
    p = pb['root']; m = p.matrix.copy(); p.matrix = Matrix.Translation(hips) @ R @ Matrix.Translation(-hips) @ m; refresh()
    return root_rot(post)
def lerp_num(a, b, t): return a + (b - a) * t
def twist(name, deg):
    p = pb[name]; m = p.matrix.copy(); ax = (m.to_3x3() @ Vector((0, 1, 0))).normalized(); h = m.translation.copy()
    p.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ m; refresh()
def lerpv(a, b, t): return (V3(a) * (1 - t) + V3(b) * t).normalized()
def pose_apply(post, A, B, t):
    reset_pose(); R = set_root(post); up0 = R @ Vector((0, 0, 1)); left = R @ Vector((1, 0, 0))
    g = lambda key, dflt: (A.get(key, dflt), B.get(key, A.get(key, dflt)))
    # tronc
    ta, tb = g('trunk', 'U'); T = lerpv(ta if ta != 'U' else tuple(up0), tb if tb != 'U' else tuple(up0), t)
    s0 = lerp_num(*g('trunk_s', 0.0), t)
    for i, b in enumerate(('spine05', 'spine04', 'spine03', 'spine02', 'spine01')):
        f = max(0.0, ((i + 1) / 5.0 - s0) / (1 - s0)); aim(b, (up0 * (1 - f) + T * f).normalized())
    ha, hb = g('head', None); H = lerpv(ha, hb, t) if ha is not None else T
    aim('neck01', (T * 0.5 + H * 0.5).normalized()); aim('neck02', H); aim('head', H)
    tw = lerp_num(*g('headtw', 0.0), t)
    if tw: twist('neck02', tw * 0.4); twist('head', tw * 0.6)
    for s in ('L', 'R'):
        aa, ab = g('arm' + s, ('d', 'd')); aa = aa if isinstance(aa, (tuple, list)) else (aa, aa); ab = ab if isinstance(ab, (tuple, list)) else (ab, ab)
        U_ = lerpv(aa[0], ab[0], t); F_ = lerpv(aa[1], ab[1], t); aim(f'upperarm01.{s}', U_); aim(f'lowerarm01.{s}', F_); aim(f'wrist.{s}', g('hand' + s, None)[0] and lerpv(*g('hand' + s, None), t) or F_)
        la, lb = g('leg' + s, ('d', 'd')); la = la if isinstance(la, (tuple, list)) else (la, la); lb = lb if isinstance(lb, (tuple, list)) else (lb, lb)
        Th = lerpv(la[0], lb[0], t); Sh = lerpv(la[1], lb[1], t); aim(f'upperleg01.{s}', Th); aim(f'lowerleg01.{s}', Sh)
        fa, fb = g('foot' + s, None)
        dflt = Sh.cross(left); dflt = dflt.normalized() if dflt.length > 1e-3 else Vector((0, -1, 0))
        if fa is None and fb is None: Fo = dflt
        else:
            a_ = V3(fa) if fa is not None else dflt; b_ = V3(fb) if fb is not None else dflt; Fo = (a_ * (1 - t) + b_ * t).normalized()
        aim(f'foot.{s}', Fo)
def mesh_bounds():
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); mm = ev.to_mesh()
    co = [v.co.copy() for v in mm.vertices]; ev.to_mesh_clear(); return co
def place(anchor_xy=None, anchor_bone=None, floor=0.0):
    co = mesh_bounds(); z = min(c.z for c in co); p = pb['root']; m = p.matrix.copy(); m.translation.z -= (z - floor)
    if anchor_xy is not None:
        cur = (arm.matrix_world @ pb[anchor_bone].head); m.translation.x += anchor_xy[0] - cur.x; m.translation.y += anchor_xy[1] - cur.y
    p.matrix = m; refresh()

# ---------- décor ----------
PROPS = []
def box(name, cen, size, col='#9FB0B8', rough=0.8):
    bpy.ops.mesh.primitive_cube_add(size=1, location=cen); o = bpy.context.active_object; o.name = name; o.scale = size; o.data.materials.append(mat(name, col, rough)); PROPS.append(o); return o
def ball(name, cen, r, col='#C9833B'):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=cen); o = bpy.context.active_object; o.name = name; o.data.materials.append(mat(name, col, 0.5))
    for p in o.data.polygons: p.use_smooth = True
    PROPS.append(o); return o
def cyl(name, a, b, r, col='#D9A53A'):
    a, b = Vector(a), Vector(b); d = b - a; bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=r, depth=1, location=(a + b) / 2); o = bpy.context.active_object; o.name = name
    o.scale = (1, 1, max(d.length, 1e-3)); o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(mat(name, col, 0.6)); PROPS.append(o); return o
def clear_props():
    for o in PROPS: bpy.data.objects.remove(o, do_unlink=True)
    PROPS.clear()
BANDS = []
def add_props(specp, ref):
    """specp : liste de dictionnaires {t: type, ...}. ref : positions de référence (pelvis, pied, main...) du personnage en pose A."""
    for pr in specp:
        t = pr['t']; ox, oy, oz = pr.get('o', (0, 0, 0))
        if t == 'chair':
            hz = ref['pelvis'].z - 0.085; cy = ref['pelvis'].y - 0.10 + oy; cx = ref['pelvis'].x
            box('assise', (cx, cy, hz - 0.02), (0.44, 0.44, 0.04)); box('dossier', (cx, cy + 0.22, hz + 0.24), (0.44, 0.04, 0.50))
            for dx in (-0.19, 0.19):
                for dy in (-0.19, 0.19): box('pied', (cx + dx, cy + dy, (hz - 0.04) / 2), (0.035, 0.035, hz - 0.04))
        elif t == 'wall':   # plan vertical : 'y' absolu relatif à pelvis
            y = ref['pelvis'].y + pr['y'] + oy; box('mur', (0, y + 0.03, 1.0), (3.0, 0.06, 2.2), '#E4E9EC', 0.95)
        elif t == 'espalier':
            y = ref['pelvis'].y + pr['y'] + oy; box('espalier_fond', (0, y + 0.03, 1.0), (1.0, 0.04, 2.2), '#E4E9EC', 0.95)
            for dx in (-0.45, 0.45): box('montant', (dx, y - 0.02, 1.0), (0.05, 0.05, 2.2), '#B58A5B', 0.7)
            for zz in [0.2 + 0.2 * i for i in range(10)]: cyl('barreau', (-0.45, y - 0.02, zz), (0.45, y - 0.02, zz), 0.014, '#B58A5B')
        elif t == 'table':
            z = pr['z']; y = ref['pelvis'].y + pr['y'] + oy; box('plateau', (ref['pelvis'].x, y, z - 0.02), (0.9, 0.55, 0.04), '#C9B79C', 0.7)
            for dx in (-0.4, 0.4):
                for dy in (-0.23, 0.23): box('pied_table', (ref['pelvis'].x + dx, y + dy, (z - 0.04) / 2), (0.04, 0.04, z - 0.04), '#C9B79C', 0.7)
        elif t == 'step':
            y = ref['foot'].y + pr.get('y', -0.30) + oy; box('marche', (ref['foot'].x, y, pr.get('z', 0.18) / 2), (0.7, 0.32, pr.get('z', 0.18)), '#9FB0B8', 0.8)
        elif t == 'cushion':
            fp = ref['foot']; box('coussin', (fp.x + ox, fp.y + oy, 0.04), (0.42, 0.42, 0.08), '#E08E5A', 0.7)
        elif t == 'ball':
            c = Vector(pr['c']) + Vector((ref['pelvis'].x, ref['pelvis'].y, 0)) ; ball('ballon', c, pr.get('r', 0.12))
        elif t == 'roller':
            c = Vector(pr['c']) + Vector((ref['pelvis'].x, ref['pelvis'].y, 0)); cyl('rouleau', c - Vector((0.22, 0, 0)), c + Vector((0.22, 0, 0)), pr.get('r', 0.07), '#7E9C8A')
        elif t == 'bench':
            z = pr['z']; y = ref['pelvis'].y + pr['y'] + oy; box('banc', (ref['pelvis'].x, y, z / 2), (0.45, pr.get('d', 0.9), z), '#9FB0B8', 0.8)
        elif t == 'band':   # élastique : ancre fixe (relative au bassin) ou os -> os
            a = pr['a']; a = a if isinstance(a, str) else Vector((ref['pelvis'].x, ref['pelvis'].y, 0)) + Vector(a)
            BANDS.append((a, pr['bone'], cyl('elastique', (0, 0, 0), (0, 0, 1), 0.007, '#D9A53A')))
        elif t == 'stick':
            BANDS.append((pr['a'], pr['bone'], cyl('canne', (0, 0, 0), (0, 0, 1), 0.012, '#B58A5B')))
        elif t == 'dome':
            fp = ref['foot']; ball('dome', (fp.x + ox, fp.y + oy, -0.08), 0.22, '#D9553A')
def update_bands():
    for a, bone, o in BANDS:
        a = (arm.matrix_world @ pb[a].tail) if isinstance(a, str) else a
        b = arm.matrix_world @ pb[bone].tail; d = b - a; o.location = (a + b) / 2; o.scale = (1, 1, max(d.length, 1e-3)); o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()

# ---------- caméra, lumière, rendu ----------
fl = None
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.use_denoising = False; scene.render.film_transparent = True
scene.render.image_settings.color_mode = 'RGBA'
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.active_object
fm = mat('Sol', '#D3D9DC', 1.0); fm.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = 0.0; fl.data.materials.append(fm); fl.is_shadow_catcher = True
w = bpy.data.worlds.new('Monde'); scene.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.90, 0.92, 0.93, 1); bg.inputs[1].default_value = 0.65
LIGHTS = []
def set_lights(az):
    for l in LIGHTS: bpy.data.objects.remove(l, do_unlink=True)
    LIGHTS.clear()
    def area(loc, energy, size):
        bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.active_object; l.data.energy = energy; l.data.size = size
        l.rotation_euler = (Vector((0, 0, 0.5)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); LIGHTS.append(l)
    pol = lambda a, r, z: (r * math.cos(math.radians(a)), -r * math.sin(math.radians(a)), z)
    area(pol(az + 40, 4.0, 3.2), 230, 2.6); area(pol(az - 55, 3.6, 1.8), 90, 3.0); area(pol(az + 180, 3.0, 2.6), 120, 2.0)
cam = None
def set_camera(az, tgt, scale, aspect):
    global cam
    if cam is not None: bpy.data.objects.remove(cam, do_unlink=True)
    el = math.radians(11); loc = tgt + Vector((6 * math.cos(el) * math.cos(math.radians(az)), -6 * math.cos(el) * math.sin(math.radians(az)), 6 * math.sin(el)))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
    cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
def render(path, w, h, samples):
    scene.render.resolution_x = w; scene.render.resolution_y = h; scene.cycles.samples = samples; scene.render.filepath = path; bpy.ops.render.render(write_still=True)

def ease(u): return 0.5 - 0.5 * math.cos(math.pi * u)
def run_exercise(sp):
    slug = sp['slug']; out = f'{OUTROOT}/{slug}'; os.makedirs(out, exist_ok=True)
    clear_props(); BANDS.clear()
    post = sp['post']; A = sp['A']; B = sp['B']
    fl0 = lambda t: lerp_num(A.get('floor', 0.0), B.get('floor', 0.0), t)
    pose_apply(post, A, B, 0.0); anchor_bone = sp.get('anchor', 'pelvis.L' if post in ('supine', 'prone', 'side', 'quad') else 'foot.L'); place(None, None, fl0(0.0))
    anchor_xy = (arm.matrix_world @ pb[anchor_bone].head).xy.copy()
    ref = {'pelvis': arm.matrix_world @ pb['pelvis.L'].head, 'foot': arm.matrix_world @ pb['foot.L'].head}
    ref['pelvis'] = Vector((0, ref['pelvis'].y, ref['pelvis'].z))
    add_props(sp.get('props', []), ref)
    # cadrage commun : on mesure les poses extrêmes
    pts = []
    for t in (0.0, 0.5, 1.0):
        pose_apply(post, A, B, t); place(anchor_xy, anchor_bone, fl0(t)); pts += [(c.x, c.y, c.z) for c in mesh_bounds()[::7]]
    az = {'side': 0, 'front': 90, '3q': 32, 'back': -90}[sp.get('view', 'side')]; azr = math.radians(az)
    # coordonnées écran : droite caméra = (−sin az ?) ; on projette
    rx, ry = -math.sin(azr) * 0 + (math.cos(azr) * 0), 0
    right = Vector((math.sin(azr), math.cos(azr), 0)); right = Vector((math.sin(azr + math.pi), math.cos(azr + math.pi), 0)) if False else Vector((-math.sin(azr) * 0, 0, 0))
    # base écran : pour une caméra à l'azimut az (position (cos az, -sin az)), vers l'origine, la droite écran vaut (sin az, cos az, 0)
    right = Vector((math.sin(azr), math.cos(azr), 0))
    us = [p[0] * right.x + p[1] * right.y for p in pts]; zs = [p[2] for p in pts]
    umin, umax, zmin_, zmax_ = min(us), max(us), min(zs), max(zs)
    aspect = 3 / 4 if sp.get('orient', 'port' if post == 'stand' else 'land') == 'port' else 4 / 3
    wid = (umax - umin) * 1.18 + 0.2; hei = (zmax_ - zmin_) * 1.2 + 0.25
    scale = max(wid, hei * aspect) * sp.get('zoom', 1.0); ucen = (umin + umax) / 2; zcen = (zmin_ + zmax_) / 2 + 0.02
    tgt = Vector((ucen * right.x, ucen * right.y, zcen)); set_camera(az, tgt, scale, aspect); set_lights(az)
    W = 270 if aspect < 1 else 360; H = 360 if aspect < 1 else 270
    json.dump({'aspect': aspect, 'w': W, 'h': H, 'hold': sp.get('hold', False), 'name': sp.get('name', slug)}, open(f'{out}/meta.json', 'w'))
    if MODE != 'full' or aspect < 1:   # test, photos, ou personnage debout : photos de départ et d'arrivée en meilleure qualité
        for nm, tt in (('A', 0.0), ('B', 1.0)):
            pose_apply(post, A, B, tt); place(anchor_xy, anchor_bone, fl0(tt)); update_bands(); render(f'{out}/{nm}.png', int(W * 1.5), int(H * 1.5), SAMP * 2)
    if MODE == 'full' and not os.path.exists(f'{out}/f000.png'):
        for i in range(NF):
            t = ease(i / (NF - 1)); pose_apply(post, A, B, t); place(anchor_xy, anchor_bone, fl0(t)); update_bands(); render(f'{out}/f{i:03d}.png', W, H, SAMP)
    open(f'{out}/OK', 'w').write('ok')

# ---------- exécution ----------
spec = importlib.util.spec_from_file_location('specs', SPECS); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
todo = [s for s in mod.SPECS if s['char'] == CHAR and (ONLY is None or s['slug'] in ONLY) and (MODE == 'photo' or not os.path.exists(f"{OUTROOT}/{s['slug']}/OK"))]
print('A TRAITER', len(todo), flush=True)
for sp in todo:
    if time.time() - T0 > BUDGET: break
    t1 = time.time()
    try: run_exercise(sp); print('FAIT', sp['slug'], round(time.time() - t1), 's', flush=True)
    except Exception as e: print('ERREUR', sp['slug'], repr(e), flush=True)
print('FIN', round(time.time() - T0), 's', flush=True)
