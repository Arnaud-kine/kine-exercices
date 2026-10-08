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
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.55; bsdf.inputs['Subsurface Weight'].default_value = 0.0
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
    shorts = M('MULTIPLY', between(Z, zl(0.085), zl(1.00)), M('LESS_THAN', AX, 0.30 * k))   # pantalon long jusqu'aux chevilles : les mains et les avant-bras ressortent sur les jambes
    torso = M('MULTIPLY', between(Z, zl(1.00), zl(1.44)), M('LESS_THAN', AX, 0.215 * k))
    neck = M('MULTIPLY', M('LESS_THAN', AX, 0.085 * k), M('GREATER_THAN', Z, zl(1.385)))
    def sq(v): return M('MULTIPLY', v, v)
    def d2(sx): return M('ADD', M('ADD', sq(M('SUBTRACT', X, sx)), sq(Y)), sq(M('SUBTRACT', Z, zl(1.38))))
    near = M('LESS_THAN', M('MINIMUM', d2(0.185 * k), d2(-0.185 * k)), (0.118 * k) ** 2)
    sleeve = M('MULTIPLY', M('MULTIPLY', near, M('GREATER_THAN', AX, 0.17 * k)), M('GREATER_THAN', Z, zl(1.20)))
    shirt = M('MAXIMUM', M('MULTIPLY', torso, M('SUBTRACT', 1.0, neck)), sleeve)
    def col(h): n = N.new('ShaderNodeRGB'); n.outputs[0].default_value = lin(h); return n.outputs[0]
    def mix(f, c1, c2): n = N.new('ShaderNodeMixRGB'); Lk.new(f, n.inputs[0]); Lk.new(c1, n.inputs[1]); Lk.new(c2, n.inputs[2]); return n.outputs[0]
    c = mix(shirt, col('#D8B193'), col(TOPCOL)); c = mix(shorts, c, col('#5E7A94')); Lk.new(c, bsdf.inputs['Base Color']); return m
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
    e1 = rp.color_ramp.elements.new(0.80); e1.color = lin(iris_hex); e2 = rp.color_ramp.elements.new(0.955); e2.color = lin('#101010')
    Lk.new(dt.outputs['Value'], rp.inputs['Fac']); Lk.new(rp.outputs['Color'], bsdf.inputs['Base Color']); return m
def rigid_head(o):
    o.parent = arm; vg = o.vertex_groups.new(name='head'); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE'); o.modifiers.new('Armature', 'ARMATURE').object = arm
irisc = '#5A3E2B' if AGE == 'adulte' else '#5F7F8E'
for gname, oname in (('helper-l-eye', 'OeilG'), ('helper-r-eye', 'OeilD')):
    e = mesh_from_group(gname, oname)
    for v in e.data.vertices: v.co.y -= 0.003 * k   # on avance un peu le globe pour que l'iris dépasse des paupières
    cen = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)
    e.data.materials.append(eye_material(cen, irisc)); rigid_head(e)
    for p in e.data.polygons: p.use_smooth = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(cen.x, cen.y - 0.010, cen.z + 0.021 * k))
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
    for p in pb: p.location = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0); p.scale = (1, 1, 1); p.rotation_mode = 'QUATERNION'
    refresh()
POST = {'stand': (0, 0, 0), 'quad': (76, 0, 0), 'prone': (90, 0, 0), 'supine': (-90, 0, 180), 'side': (-90, 90, 180)}   # tangage, roulis (autour de Y monde, après), lacet
OVR = dict(tilt=0.0, htilt=0.0, dp=0.0, beta=0.0)
PTILT = [0.0]
SAG = [0.0]
def root_rot(post):
    pitch, roll, yaw = POST[post]; pitch += OVR['dp'] + PTILT[0]
    return Matrix.Rotation(math.radians(roll), 3, 'Y') @ Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'X')
def set_root(post):
    R = root_rot(post).to_4x4(); hips = (arm.data.bones['pelvis.L'].head_local + arm.data.bones['pelvis.R'].head_local) / 2
    p = pb['root']; m = p.matrix.copy(); p.matrix = Matrix.Translation(hips) @ R @ Matrix.Translation(-hips) @ m; refresh()
    return root_rot(post)
_fv = arm.data.bones['foot.L'].tail_local - arm.data.bones['foot.L'].head_local
FOOT_SLOPE = math.asin(max(-1.0, min(1.0, -_fv.z / _fv.length)))   # pente de l'os du pied, plante à plat (~26°)
print('PENTE du pied', round(math.degrees(FOOT_SLOPE), 1), 'degrés', flush=True)
def lerp_num(a, b, t): return a + (b - a) * t
def twist(name, deg):
    p = pb[name]; m = p.matrix.copy(); ax = (m.to_3x3() @ Vector((0, 1, 0))).normalized(); h = m.translation.copy()
    p.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ m; refresh()
def lerpv(a, b, t): return (V3(a) * (1 - t) + V3(b) * t).normalized()
SKINNED = [o for o in bpy.data.objects if o.type == 'MESH' and any(md.type == 'ARMATURE' for md in o.modifiers)]
def mods(on):
    for o in SKINNED:
        for md in o.modifiers: md.show_viewport = on
CAL = {'h': 0.0, 'hL': 0.0, 'hR': 0.0, 'a': 0.03, 'hd': 0.0, 'm': 1.0, 'arm': 0.0, 'hdB': 0.0, 'armB': 0.0, 'au': 0.0, 'af': 0.0, 'ah': 0.0, 'auB': 0.0, 'afB': 0.0, 'ahB': 0.0, 'ft': 0.0, 'ftB': 0.0, 'cl': 0.0, 'clB': 0.0}
_hip0 = [None]
def hip0():
    """Hauteur de l'articulation de la hanche quand le personnage est allongé sur le dos, mesurée sur le corps."""
    if _hip0[0] is None:
        A0 = dict(armL='b', armR='b', legL=('b', 'b'), legR=('b', 'b'))
        mods(False); _pose_apply('supine', A0, A0, 0.0); mods(True); refresh(); place(None, None, 0.0)
        z = zregions(); _hip0[0] = (arm.matrix_world @ pb['upperleg01.L'].head).z - z['pelv']; print('HANCHE au-dessus du bas du dos', round(_hip0[0] * 100, 1), 'cm', flush=True)
    return _hip0[0]
def ik_leg(ik, sd='L'):
    """Cuisse et tibia pour que le pied soit à plat au sol, à la distance D du bassin, le bassin étant levé de 'lift' m (sur le dos)."""
    Lt = (arm.data.bones['lowerleg01.L'].head_local - arm.data.bones['upperleg01.L'].head_local).length
    Ls = (arm.data.bones['foot.L'].head_local - arm.data.bones['lowerleg01.L'].head_local).length
    H = hip0() + ik['lift'] * k - CAL['h' + sd]; dz = H - arm.data.bones['foot.L'].head_local.z; D = ik['D'] * k
    dist = min(math.hypot(D, dz), (Lt + Ls) * 0.999); a = math.acos(max(-1.0, min(1.0, (Lt * Lt + dist * dist - Ls * Ls) / (2 * Lt * dist))))
    th = -math.atan2(dz, D) + a; thd = Vector((0, math.cos(th), math.sin(th))); knee = thd * Lt; shd = (Vector((0, D, -dz)) - knee).normalized()
    return thd, shd
ARM_CUR = {}
REFP = [Vector((0, 0, 0))]
LASTPOSE = [None]
def pose_apply(post, A, B, t):
    LASTPOSE[0] = (A, t); mods(False); _pose_apply(post, A, B, t); mods(True); refresh()
def _pose_apply(post, A, B, t):
    if 'pelvtilt' in A or 'pelvtilt' in B: PTILT[0] = lerp_num(A.get('pelvtilt', 0.0), B.get('pelvtilt', 0.0), t)   # bascule du bassin
    reset_pose(); R = set_root(post); up0 = R @ Vector((0, 0, 1)); left = R @ Vector((1, 0, 0))
    g = lambda key, dflt: (A.get(key, dflt), B.get(key, A.get(key, dflt)))
    # tronc
    UPD = Vector((0, 0.07, 1)).normalized() if post == 'stand' else up0   # debout : tronc redressé de 4° par rapport à la pose d'origine, qui penche vers l'avant
    ta, tb = g('trunk', 'U'); T = lerpv(ta if ta != 'U' else tuple(UPD), tb if tb != 'U' else tuple(UPD), t)
    IKA = A.get('ik'); IKB = B.get('ik', IKA)
    if IKA and 'trunk' not in B:   # le bassin est levé de 'lift' m ; l'épaule repose sur le sol par l'omoplate (+3 cm de l'articulation)
        al = lerp_num(IKA['alpha'], IKB.get('alpha', IKA['alpha']), t) if 'alpha' in IKA else math.asin(max(-0.6, min(0.95, (lerp_num(IKA['lift'], IKB['lift'], t) * CAL['m'] + CAL['a']) / 0.52))); T = Vector((0, -math.cos(al), -math.sin(al)))
    if OVR['tilt']: T = Matrix.Rotation(OVR['tilt'], 3, 'X') @ T
    lb_ = A.get('lean_bump', B.get('lean_bump', 0.0))
    if lb_: T = (Matrix.Rotation(math.radians(lb_) * math.sin(math.pi * max(0.0, min(1.0, t / 0.8))), 3, 'X') @ T).normalized()   # vraie rotation du tronc vers l'avant   # le tronc se penche vers l'avant au milieu du mouvement, puis se redresse
    s0 = lerp_num(*g('trunk_s', 0.0), t)
    for i, b in enumerate(('spine05', 'spine04', 'spine03', 'spine02', 'spine01')):
        f = 1.0 if IKA else max(0.0, ((i + 1) / 5.0 - s0) / (1 - s0)); dv_ = (up0 * (1 - f) + T * f)
        if IKA and (A.get('upperlift') or B.get('upperlift')): dv_ = dv_ + Vector((0, 0, (0.0, 0.0, 0.15, 0.55, 1.0)[i] * math.sin(lerp_num(A.get('upperlift', 0.0), B.get('upperlift', 0.0), t))))   # haut du corps qui se soulève, bas du dos posé
        if IKA and (A.get('curl') or B.get('curl')): ang_ = al * (1.0, 0.8, 0.55, 0.3, 0.1)[i] * lerp_num(A.get('curl', 1.0), B.get('curl', 1.0), t) * 1.7; dv_ = Vector((0, -math.cos(ang_), -math.sin(ang_)))   # dos arrondi : le bas de la colonne se courbe vers le haut
        if SAG[0] and post == 'supine': dv_ = dv_ + Vector((0, 0, (-1.0, -0.6, -0.2, 0.6, 1.0)[i] * math.sin(SAG[0])))   # dos plat : le milieu de la colonne s'affaisse vers le sol
        aim(b, dv_.normalized())
    ha, hb = g('head', None); H = lerpv(ha, hb, t) if ha is not None else T
    if IKA:   # pont : l'épaule est abaissée pour reposer sur le sol
        c_ = lerp_num(CAL['cl'], CAL['clB'], t)
        for sd in ('L', 'R'):
            cb = pb['clavicle.' + sd]; v = ((arm.matrix_world @ cb.tail) - (arm.matrix_world @ cb.head)).normalized(); aim('clavicle.' + sd, (v + Vector((0, 0, -math.sin(c_)))).normalized())
    if IKA and ha is None: H = (lambda hh: Vector((0, -math.cos(hh), math.sin(hh))))(lerp_num(CAL['hd'], CAL['hdB'], t))   # nuque neutre, tête à plat : l'appui est sur les épaules et les omoplates
    if post == 'side' and ha is None: H = (T + Vector((0, 0, 0.30))).normalized()   # sur le côté : la tête est relevée, le visage se voit
    if OVR['htilt']: H = Matrix.Rotation(OVR['htilt'], 3, 'X') @ H
    aim('neck01', (T * 0.5 + H * 0.5).normalized()); aim('neck02', H); aim('head', H)
    tw = lerp_num(*g('headtw', 0.0), t)
    if tw: twist('neck02', tw * 0.4); twist('head', tw * 0.6)
    for s in ('L', 'R'):
        aa, ab = g('arm' + s, ('d', 'd')); aa = aa if isinstance(aa, (tuple, list)) else (aa, aa); ab = ab if isinstance(ab, (tuple, list)) else (ab, ab)
        U_ = lerpv(aa[0], ab[0], t); F_ = lerpv(aa[1], ab[1], t)
        if IKA:   # sur le dos : bras posés sur le sol sur toute leur longueur, sauf pose décrite à la main (au départ ou à l'arrivée)
            def _ov(a_, f_): return Vector((0, math.cos(a_), -math.sin(a_))), Vector((0, math.cos(f_), -math.sin(f_)))
            def _xp(v): v = v if isinstance(v, (tuple, list)) else (v, v); return V3(v[0]), V3(v[1])
            ea, eb = A.get('arm' + s), B.get('arm' + s)
            ua, fa_v = _xp(ea) if ea is not None else _ov(CAL['au'], CAL['af'])
            ub, fb_v = _xp(eb) if eb is not None else _ov(CAL['auB'], CAL['afB'])
            U_ = (ua * (1 - t) + ub * t).normalized(); F_ = (fa_v * (1 - t) + fb_v * t).normalized()
        ARM_CUR[s] = (U_, F_)   # bras de départ réel (posé à plat si c'est un exercice couché), pour le mélange avec la prise des jambes
        aim(f'upperarm01.{s}', U_); aim(f'lowerarm01.{s}', F_)
        Fw = Vector((0, -1, -0.05)).normalized() if (post in ('quad', 'prone') and F_.z < -0.8) else F_   # main à plat, doigts vers l'avant
        if IKA and ('arm' + s) not in A and ('arm' + s) not in B: ph_ = lerp_num(CAL['ah'], CAL['ahB'], t); Fw = Vector((0, math.cos(ph_), -math.sin(ph_)))   # pont : main à plat, doigts vers les pieds
        aim(f'wrist.{s}', g('hand' + s, None)[0] and lerpv(*g('hand' + s, None), t) or Fw)
        if IKA and ROLL[s]: twist(f'wrist.{s}', ROLL[s])   # paume vers le sol
        if IKA:   # sur le dos : jambes calculées pour que le talon / la plante reposent sur le sol
            ikas, ikbs = A.get('ik' + s, IKA), B.get('ik' + s, IKB)
            def _ex(v): v = v if isinstance(v, (tuple, list)) else (v, v); return V3(v[0]), V3(v[1])
            ea, eb = A.get('leg' + s), B.get('leg' + s, A.get('leg' + s))
            ta_, sa_ = _ex(ea) if ea is not None else ik_leg(ikas, s)
            tb_, sb_ = (lambda d: (d, d))(ik_leg(B.get('ik' + ('R' if s == 'L' else 'L'), IKB), 'R' if s == 'L' else 'L')[0]) if eb == 'straight' else (_ex(eb) if eb is not None else ik_leg(ikbs, s))   # 'straight' : jambe tendue dans l'axe cuisse du côté porteur
            Th = (ta_ * (1 - t) + tb_ * t).normalized(); Sh = (sa_ * (1 - t) + sb_ * t).normalized()
        else:
            la, lb = g('leg' + s, ('d', 'd')); la = la if isinstance(la, (tuple, list)) else (la, la); lb = lb if isinstance(lb, (tuple, list)) else (lb, lb)
            tl_ = max(0.0, min(1.0, (t - A.get('leg_delay', 0.0)) / (1.0 - A.get('leg_delay', 0.0))))   # on se penche d'abord, puis les jambes s'étendent
            Th = lerpv(la[0], lb[0], tl_); Sh = lerpv(la[1], lb[1], tl_)
        if OVR['beta'] and Th.z > 0.3 and Sh.z < -0.4: Sh = (Matrix.Rotation(OVR['beta'], 3, 'X') @ Sh).normalized()   # tibia plus ou moins incliné pour que le pied soit à plat quand le bassin repose sur le sol
        aim(f'upperleg01.{s}', Th); aim(f'lowerleg01.{s}', Sh)
        fa, fb = g('foot' + s, None)
        dflt = Sh.cross(left); dflt = dflt.normalized() if dflt.length > 1e-3 else Vector((0, -1, 0))
        dflt = (dflt * math.cos(FOOT_SLOPE) + Sh * math.sin(FOOT_SLOPE)).normalized()   # plante à plat : l'os du pied penche vers le bas
        if IKA and ('leg' + s) not in B and ('leg' + s) not in A and lerp_num(A.get('ik' + s, IKA)['D'], B.get('ik' + s, IKB)['D'], t) < 0.6: sf_ = FOOT_SLOPE + lerp_num(CAL['ft'], CAL['ftB'], t); dflt = Vector((0, math.cos(sf_), -math.sin(sf_)))   # pont : la plante du pied repose à plat sur le sol
        dd_ = lerp_num(A.get('dorsi' + s, 0.0), B.get('dorsi' + s, A.get('dorsi' + s, 0.0)), t)
        if dd_: dflt = (dflt * math.cos(math.radians(dd_)) - Sh * math.sin(math.radians(dd_))).normalized()   # flexion dorsale : le pied se rapproche du tibia, au lieu de pointer vers le bas
        if post == 'stand' and not IKA and Sh.z < -0.85: dflt = Vector((0, -math.cos(FOOT_SLOPE), -math.sin(FOOT_SLOPE)))   # debout, jambe d'appui : le pied reste à plat, quelle que soit l'inclinaison du tibia
        if post in ('prone', 'quad') or (post == 'stand' and abs(Sh.z) < 0.12 and Sh.y > 0.8): dflt = Sh.copy()   # à genoux, à quatre pattes, sur le ventre : pied à plat, dessus du pied au sol (flexion plantaire)
        if fa is None and fb is None: Fo = dflt
        else:
            a_ = V3(fa) if fa is not None else dflt; b_ = V3(fb) if fb is not None else dflt; Fo = (a_ * (1 - t) + b_ * t).normalized()
        fs_ = A.get('foot_soft' + s, B.get('foot_soft' + s, None))
        if fs_ is not None and fa is None and fb is None: Fo = (Vector((0, -math.cos(FOOT_SLOPE), -math.sin(FOOT_SLOPE))) * (1 - fs_) + Fo * fs_).normalized()   # pied de la jambe levée : il suit la jambe, mais l'amplitude de son mouvement est réduite
        bmp_ = A.get('dorsi_bump' + s, B.get('dorsi_bump' + s, 0.0))
        if bmp_: r_ = math.radians(bmp_) * math.sin(math.pi * t); Fo = (Fo * math.cos(r_) - Sh * math.sin(r_)).normalized()   # légère flexion du pied au milieu du mouvement, qui s'annule à l'arrivée
        aim(f'foot.{s}', Fo)
    if A.get('reach_pt') is not None or A.get('reach_lat') is not None: reach_hands(A, 1.0 if A.get('reach_full') else t)
    elif A.get('reach') and t > 0.0: reach_hands(A, t)
_dom = None
def zones():
    global _dom
    if _dom is None:
        nm = {i: g.name for i, g in enumerate(body.vertex_groups)}; hand, leg = [], []
        for v in body.data.vertices:
            if not v.groups: continue
            n = nm[max(v.groups, key=lambda g: g.weight).group]
            if n.startswith(('wrist', 'metacarpal', 'finger')): hand.append(v.index)
            elif n.startswith(('upperleg', 'lowerleg')): leg.append(v.index)
        _dom = (hand, leg)
    return _dom
def settle_quad(A, B):
    POST['quad'] = (76.0, 0, 0)
    for _ in range(3):
        pose_apply('quad', A, B, 0.0); place(); co = mesh_bounds()[:NB]; hand, leg = zones()
        gap = min(co[i].z for i in leg) - min(co[i].z for i in hand)
        print('QUAD gap', round(gap * 100, 2), 'cm, tangage', round(POST['quad'][0], 2), flush=True)
        if abs(gap) < 0.002: break
        POST['quad'] = (POST['quad'][0] - math.degrees(math.asin(max(-0.5, min(0.5, gap / (0.55 * k))))), 0, 0)
GRIP_SIGN = float(os.environ.get('GRIP_SIGN', '-1'))
def apply_grip(A, t):
    """Ferme la main (doigts autour d'un barreau). 'grip' = {côté: degré de fermeture 0..1}; le degré suit la pose (progressif)."""
    import math as _m
    for sd_, amt in A.get('grip', {}).items():
        k = amt * (1.0 if A.get('grip_full') else t)
        for fi, base in ((2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0), (1, 0.45)):
            for seg, ang in ((1, 55), (2, 80), (3, 55)):
                b = pb.get(f'finger{fi}-{seg}.{sd_}')
                if b is None: continue
                b.rotation_mode = 'XYZ'; b.rotation_euler = (GRIP_SIGN * _m.radians(ang * base * k), 0, 0)
    refresh()
def reach_hands(A, t):
    """Les mains vont saisir les jambes (point à une fraction 'reach' du tibia) : calcul des deux segments du bras."""
    import numpy as _np
    for s in ('L', 'R'):
        if A.get('reach_only') and s != A['reach_only']: continue   # une seule main tient le barreau
        S_ = arm.matrix_world @ pb[f'upperarm01.{s}'].head; K = arm.matrix_world @ pb[f'lowerleg01.{s}'].head; An = arm.matrix_world @ pb[f'foot.{s}'].head
        sd = (An - K).normalized(); nrm = (Vector((0, 0, 1)) - sd * sd.z).normalized()          # face supérieure du tibia
        if A.get('reach_lat') is not None:   # barreau sur le côté : la main reste à côté du bassin, à la hauteur voulue
            pel = arm.matrix_world @ pb['pelvis.L'].head; lx, ly, lz = A['reach_lat']; Tg = Vector((pel.x + lx, pel.y + ly, lz)); sd = Vector((0, -1, 0))
        elif A.get('reach_pt') is not None:   # point fixe dans l'espace, comme une barre d'espalier : (avance par rapport au bassin de départ, hauteur)
            sg = 1.0 if S_.x > 0 else -1.0; Tg = Vector((REFP[0].x + sg * A.get('reach_dx', 0.10), REFP[0].y + A['reach_pt'][0], A['reach_pt'][1])); sd = Vector(A.get('reach_wrist', (0, -1, 0))).normalized()   # orientation de la main : par défaut vers l'avant, ou accrochée à un barreau
        else: Tg = K + (An - K) * A['reach'] + nrm * A.get('reach_r', 0.065)                      # la main se pose sur le tibia, pas dans le tibia
        if A.get('reach_pt') is not None or A.get('reach_lat') is not None: pass
        elif A.get('reach_front') is not None:   # les deux mains se rejoignent devant les genoux (côté poitrine), au milieu du corps
            Hh = arm.matrix_world @ pb[f'upperleg01.{s}'].head; dt = (K - Hh).normalized(); nf = -(Vector((0, 0, 1)) - dt * dt.z).normalized()
            Tg = K + nf * A['reach_front']; Tg.x = ((arm.matrix_world @ pb['pelvis.L'].head).x + (arm.matrix_world @ pb['pelvis.R'].head).x) / 2
        elif A.get('reach_side') is not None: Tg.x += (1.0 if S_.x > 0 else -1.0) * A['reach_side']   # la main est à l'extérieur du tibia, du côté visible
        else: mid_x = ((arm.matrix_world @ pb['pelvis.L'].head).x + (arm.matrix_world @ pb['pelvis.R'].head).x) / 2; Tg.x = mid_x   # les deux mains se rejoignent au milieu du corps
        L1 = (arm.data.bones[f'lowerarm01.{s}'].head_local - arm.data.bones[f'upperarm01.{s}'].head_local).length
        L2 = (arm.data.bones[f'wrist.{s}'].head_local - arm.data.bones[f'lowerarm01.{s}'].head_local).length
        v = Tg - S_; d = max(0.12, min(v.length, (L1 + L2) * 0.995)); u = v.normalized()
        if A.get('reach_pt') is not None and s == 'L': print('MAINS t=%.2f' % t, 'épaule y=%.2f z=%.2f' % (S_.y, S_.z), '| cible y=%.2f z=%.2f' % (Tg.y, Tg.z), '| distance %.2f m (bras %.2f m)' % (v.length, L1 + L2), flush=True)
        a = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
        out = Vector((1, 0, 0)) if S_.x > 0 else Vector((-1, 0, 0)); p = (out - u * out.dot(u)).normalized()
        if A.get('reach_elbow'): a = math.radians(A['reach_elbow'])   # coude écarté vers l'extérieur : le bras contourne le genou
        E = S_ + (u * math.cos(a) + p * math.sin(a)) * L1
        Ur, Fr = (E - S_).normalized(), (Tg - E).normalized(); Uc, Fc = ARM_CUR[s]
        Ub, Fb = (Uc * (1 - t) + Ur * t).normalized(), (Fc * (1 - t) + Fr * t).normalized()
        aim(f'upperarm01.{s}', Ub); aim(f'lowerarm01.{s}', Fb); aim(f'wrist.{s}', (Fb * (1 - t) + sd * t).normalized())   # les doigts épousent le tibia
def mesh_bounds():
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); mm = ev.to_mesh()
    co = [v.co.copy() for v in mm.vertices]; ev.to_mesh_clear(); return co
FLOORREF = ['all']
def place(anchor_xy=None, anchor_bone=None, floor=0.0):
    z = zregions()[FLOORREF[0]] if FLOORREF[0] in ('lowbody', 'pelv') else min(c.z for c in mesh_bounds()); p = pb['root']; m = p.matrix.copy(); m.translation.z -= (z - floor)
    if anchor_xy is not None:
        cur = (arm.matrix_world @ pb[anchor_bone].head); m.translation.x += anchor_xy[0] - cur.x; m.translation.y += anchor_xy[1] - cur.y
    p.matrix = m; refresh()
    if LASTPOSE[0] and LASTPOSE[0][0].get('grip'): apply_grip(LASTPOSE[0][0], LASTPOSE[0][1])
    if LASTPOSE[0] and (LASTPOSE[0][0].get('reach_pt') is not None or LASTPOSE[0][0].get('reach_lat') is not None):   # le corps est maintenant à sa place définitive : les mains rejoignent le point fixe (barre)
        mods(False); reach_hands(LASTPOSE[0][0], 1.0 if LASTPOSE[0][0].get('reach_full') else LASTPOSE[0][1]); mods(True); refresh()

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
            dp_ = pr.get('depth', 0.44)   # profondeur de l'assise : réduite quand les pieds sont reculés, pour que les jambes debout ne traversent pas la chaise
            box('assise', (cx, cy, hz - 0.02), (0.44, dp_, 0.04)); box('dossier', (cx, cy + dp_ / 2, hz + 0.24), (0.44, 0.04, 0.50))
            for dx in (-0.19, 0.19):
                for dy in (-(dp_ / 2 - 0.03), dp_ / 2 - 0.03): box('pied', (cx + dx, cy + dy, (hz - 0.04) / 2), (0.035, 0.035, hz - 0.04))
        elif t == 'wall':   # plan vertical : 'y' absolu relatif à pelvis
            y = ref['pelvis'].y + pr['y'] + oy; box('mur', (-0.95, y + 0.03, 1.0), (1.4, 0.06, 2.2), '#E4E9EC', 0.95)   # mur seulement derrière le personnage : sa tranche ne masque plus le corps
        elif t == 'espalier':
            y = ref['pelvis'].y + pr['y'] + oy; pass   # pas de panneau de fond : vu de profil, sa tranche passerait devant le visage et le buste
            box('montant', (-0.45, y - 0.02, 1.0), (0.05, 0.05, 2.2), '#B58A5B', 0.7)   # un seul montant, du côté opposé à la caméra : celui du côté de la caméra masquerait le visage et le buste
            for zz in [0.2 + 0.2 * i for i in range(10)]: cyl('barreau', (-0.45, y - 0.02, zz), (0.45, y - 0.02, zz), 0.014, '#B58A5B')
        elif t == 'espalier_lat':   # espalier placé sur le côté du personnage (côté opposé à la caméra), parallèle à sa marche
            wx = ref['pelvis'].x + pr.get('x', -0.42); box('mur_espalier', (wx - 0.03, ref['pelvis'].y - 0.2, 1.1), (0.04, 3.0, 2.3), '#EDEFF0', 0.95)
            for zz in [0.2 + 0.2 * i for i in range(10)]: cyl('barreau', (wx + 0.02, ref['pelvis'].y - 1.6, zz), (wx + 0.02, ref['pelvis'].y + 1.2, zz), 0.014, '#B58A5B')
        elif t == 'table':
            z = pr['z']; y = ref['pelvis'].y + pr['y'] + oy; box('plateau', (ref['pelvis'].x, y, z - 0.02), (0.9, 0.55, 0.04), '#C9B79C', 0.7)
            for dx in (-0.4, 0.4):
                for dy in (-0.23, 0.23): box('pied_table', (ref['pelvis'].x + dx, y + dy, (z - 0.04) / 2), (0.04, 0.04, z - 0.04), '#C9B79C', 0.7)
        elif t == 'step':
            y = ref['foot'].y + pr.get('y', -0.30) + oy; box('marche', (ref['foot'].x, y, pr.get('z', 0.18) / 2), (0.7, 0.32, pr.get('z', 0.18)), '#9FB0B8', 0.8)
        elif t == 'cushion':
            fp = ref['foot']; box('mousse', (fp.x + ox, fp.y + oy, 0.03), (0.40, 0.50, 0.06), '#2F78C4', 0.75)   # carré de mousse bleu, 40 x 50 x 6 cm
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
scene.cycles.max_bounces = 3; scene.cycles.diffuse_bounces = 2; scene.cycles.glossy_bounces = 1; scene.cycles.transmission_bounces = 0; scene.cycles.volume_bounces = 0; scene.cycles.transparent_max_bounces = 2
scene.cycles.sample_clamp_indirect = 3.0; scene.render.use_persistent_data = True
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
    area(pol(az + 25, 1.7, 3.8), 260, 1.4); area(pol(az - 55, 3.4, 1.9), 80, 3.0); area(pol(az + 180, 3.0, 2.6), 110, 2.0)
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5)); sl = bpy.context.active_object; sl.data.energy = 1.4; sl.data.angle = math.radians(1.5); sl.rotation_euler = (0, 0, 0); LIGHTS.append(sl)   # ombre de contact nette sous le corps
cam = None
def set_camera(az, tgt, scale, aspect, elev=11):
    global cam
    if cam is not None: bpy.data.objects.remove(cam, do_unlink=True)
    el = math.radians(elev); loc = tgt + Vector((6 * math.cos(el) * math.cos(math.radians(az)), -6 * math.cos(el) * math.sin(math.radians(az)), 6 * math.sin(el)))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
    cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
def render(path, w, h, samples):
    scene.render.resolution_x = w; scene.render.resolution_y = h; scene.cycles.samples = samples; scene.render.filepath = path; bpy.ops.render.render(write_still=True)

def ease(u): return 0.5 - 0.5 * math.cos(math.pi * u)

def region(bones, thr=0.35):
    idx = set()
    for n in bones:
        for vi, w in wts.get(n, []):
            if vi < NB and w >= thr: idx.add(vi)
    return sorted(idx)
REG = {'uarm': region(['upperarm01.L', 'upperarm02.L', 'upperarm01.R', 'upperarm02.R'], 0.4), 'farm': region(['lowerarm01.L', 'lowerarm02.L', 'lowerarm01.R', 'lowerarm02.R'], 0.4), 'pelv': region(['spine05', 'pelvis.L', 'pelvis.R']), 'feet': region([b for b in names if b.startswith(('foot', 'toe'))], 0.3), 'lowbody': region(['spine05', 'pelvis.L', 'pelvis.R'] + [b for b in names if b.startswith(('upperleg', 'lowerleg', 'foot', 'toe'))], 0.3), 'upper': region(['spine02', 'spine01', 'clavicle.L', 'clavicle.R']), 'head': region(['head', 'neck02']),
       'hands': region([b for b in names if b.startswith(('wrist', 'metacarpal', 'finger'))], 0.3), 'knees': region([b for b in names if b.startswith(('lowerleg', 'foot', 'toe'))], 0.3)}
REG['lumbar'] = region(['spine04', 'spine03'], 0.5)
REG['shoulder'] = region(['clavicle.L', 'clavicle.R', 'shoulder01.L', 'shoulder01.R'], 0.15)
REG['heel'] = region(['foot.L', 'foot.R'], 0.5)
for _s in ('L', 'R'):
    REG['heel' + _s] = region(['foot.' + _s], 0.5); REG['toes' + _s] = region([b for b in names if b.startswith('toe') and b.endswith('.' + _s)], 0.4)
REG['toes'] = region([b for b in names if b.startswith('toe')], 0.4)
REG['palm'] = region(['wrist.L', 'wrist.R'] + [b for b in names if b.startswith('metacarpal')], 0.5)
REGX = {}
for _s in ('L', 'R'):
    REGX['thumb' + _s] = region([b for b in names if b.startswith('finger1') and b.endswith('.' + _s)], 0.5)
    REGX['hand' + _s] = region(['wrist.' + _s] + [b for b in names if b.startswith(('metacarpal', 'finger')) and b.endswith('.' + _s)], 0.4)
ROLL = {'L': 0.0, 'R': 0.0}
def hand_pts(side):
    co = mesh_bounds()[:NB]; h = [co[i] for i in REGX['hand' + side]]; th = [co[i] for i in REGX['thumb' + side]]
    return sum(h, Vector()) / len(h), sum(th, Vector()) / len(th)
def choose_roll(post, A, B):
    """Choisit, pour chaque main, la rotation de l'avant-bras qui pose la main à plat (plan de la main horizontal),
    la paume vers le sol (le pouce vers le milieu du corps)."""
    import numpy as np
    best = {'L': (-9.0, 0.0), 'R': (-9.0, 0.0)}
    for deg in [d for d in range(0, 360, 20)]:
        ROLL['L'] = ROLL['R'] = float(deg); pose_apply(post, A, B, 0.0); place(None, None, 0.0); co = mesh_bounds()[:NB]
        for sd in ('L', 'R'):
            pts = np.array([[co[i].x, co[i].y, co[i].z] for i in REGX['hand' + sd]]); c = pts.mean(axis=0)
            w, v = np.linalg.eigh(np.cov((pts - c).T)); nz = abs(v[2, 0])                    # normale du plan de la main : 1 = main parfaitement à plat
            th = np.array([[co[i].x, co[i].y, co[i].z] for i in REGX['thumb' + sd]]).mean(axis=0); med = -1.0 if c[0] > 0 else 1.0
            sc = 3.0 * nz + (th[0] - c[0]) * med * 10.0                                         # pouce du côté du milieu du corps => paume vers le sol
            if sc > best[sd][0]: best[sd] = (sc, float(deg), nz)
    ROLL['L'], ROLL['R'] = best['L'][1], best['R'][1]
    print('ROTATION des mains :', ROLL, '| main à plat (1 = parfait) :', round(best['L'][2], 2), round(best['R'][2], 2), flush=True)
def choose_pelvic_tilt(post, A, B):
    """Dos plat : on teste plusieurs affaissements de la colonne et on garde celui qui pose le bas du dos au plus près du sol,
    sans décoller le bassin ni le haut du dos."""
    best = (9.0, 0.0, 0.0); PTILT[0] = 0.0
    for d in (0.0, 0.08, 0.16, 0.24, 0.32, 0.40):
        SAG[0] = d; FLOORREF[0] = 'all'; pose_apply(post, A, B, 0.0); place(None, None, 0.0); z = zregions()
        base = min(z['pelv'], z['upper']); gap = z['lumbar'] - base; sc = abs(gap) + 2.0 * abs(z['upper'] - z['pelv'])
        if sc < best[0]: best = (sc, d, gap)
    SAG[0] = best[1]; print('DOS PLAT : affaissement', best[1], 'rad, bas du dos à', round(best[2] * 100, 1), 'cm du sol', flush=True)
def zregions():
    sub.show_viewport = False; refresh()
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); mm = ev.to_mesh(); co = [v.co.z for v in mm.vertices]; ev.to_mesh_clear(); sub.show_viewport = True; refresh()
    return {k: min(co[i] for i in idx) for k, idx in REG.items() if idx}
def set_ovr(sol, t):
    if sol is None: OVR.update(tilt=0.0, htilt=0.0, dp=0.0); return
    for k in OVR: OVR[k] = sol[0][k] * (1 - t) + sol[1][k] * t
def solve_contacts(sp):
    """Amène au sol les zones qui doivent le toucher : dos et tête (couché) ; bassin et pieds (jambes pliées) ; mains et genoux (quatre pattes)."""
    post, A, B = sp['post'], sp['A'], sp['B']
    if sp.get('nosolve') or post not in ('supine', 'side', 'quad'): return None
    hook = sp.get('hook', (None, None)); sol = []
    for tt in (0.0, 1.0):
        hm = hook[int(tt)] if post == 'supine' else None
        o = dict(tilt=0.0, htilt=0.0, dp=0.0, beta=0.0); fl = lerp_num(A.get('floor', 0.0), B.get('floor', 0.0), tt); info = ''
        FLOORREF[0] = 'pelv' if hm == 'pelvis' else 'lowbody'
        for it in range(12):
            OVR.update(o); pose_apply(post, A, B, tt); place(None, None, fl); z = zregions()
            if post == 'quad':
                g_ = z['hands'] - z['knees']; info = f"mains-genoux {g_*100:+.1f} cm"
                if abs(g_) < 0.006: break
                o['dp'] = max(-18.0, min(14.0, o['dp'] + 0.8 * g_ / 0.0096)); continue
            du, dh = z['upper'] - fl, z['head'] - fl; info = f"dos {du*100:+.1f} cm, tête {dh*100:+.1f} cm"
            if hm == 'pelvis':
                gf = z['feet'] - fl; info += f", pieds {gf*100:+.1f} cm"          # le bassin est au sol ; les pieds doivent y être aussi
                if abs(gf) < 0.006 and abs(du) < 0.006 and abs(dh) < 0.006: break
                if abs(gf) >= 0.006: o['beta'] = max(-0.6, min(1.1, o['beta'] - 0.8 * gf / 0.45)); continue
            elif hm == 'upper':
                if abs(du) < 0.006 and abs(dh) < 0.006: break
                if abs(du) >= 0.006: o['beta'] = max(-0.6, min(1.1, o['beta'] + 0.8 * du / 0.55)); continue
                o['htilt'] = max(-0.6, min(0.6, o['htilt'] + 0.8 * dh / 0.20)); continue
            if abs(du) < 0.005 and abs(dh) < 0.005: break
            dt = 0.8 * du / 0.40; o['tilt'] = max(-0.5, min(0.5, o['tilt'] + dt)); o['htilt'] = max(-0.6, min(0.6, o['htilt'] + 0.8 * (dh - 0.62 * dt) / 0.20))
            if post == 'side': o['htilt'] = 0.0   # sur le côté : la tête reste dans l'axe, comme sur la photo d'origine
        print('CONTACT', sp['slug'], 'départ' if tt == 0 else 'arrivée', hm or '', info, f"beta {o['beta']:.2f} tilt {o['tilt']:.2f}", flush=True); sol.append(dict(o))
    OVR.update(tilt=0.0, htilt=0.0, dp=0.0, beta=0.0); return sol
def run_exercise(sp):
    slug = sp['slug']; out = f'{OUTROOT}/{slug}'; os.makedirs(out, exist_ok=True)
    clear_props(); BANDS.clear()
    post = sp['post']; A = sp['A']; B = sp['B']
    if post == 'quad': settle_quad(A, B)
    fl0 = lambda t: lerp_num(A.get('floor', 0.0), B.get('floor', 0.0), t)
    PTILT[0] = 0.0; SAG[0] = 0.0
    if sp.get('flatback'): choose_pelvic_tilt(post, A, B)
    SOL = solve_contacts(sp)
    hk = sp.get('hook', (None, None))
    def fref(t): return 'pelv' if (SOL is not None and post == 'supine' and hk[1 if t > 0.5 else 0] == 'pelvis') else ('lowbody' if (SOL is not None and post in ('supine', 'side')) else 'all')
    FLOORREF[0] = fref(0.0); set_ovr(SOL, 0.0)
    if A.get('ik'):   # pont : étalonnage automatique (pied au sol, dos au sol), puis contrôle chiffré
        CAL.update(h=0.0, hL=0.0, hR=0.0, a=0.03, hd=0.0, m=1.0, arm=0.0, hdB=0.0, armB=0.0, au=0.0, af=0.0, ah=0.0, auB=0.0, afB=0.0, ahB=0.0, ft=0.0, ftB=0.0, cl=0.0, clB=0.0)
        cl = lambda v, lo, hi: max(lo, min(hi, v))
        FLOORREF[0] = 'all'; choose_roll(post, A, B)
        for it in range(0 if sp.get('free_upper') else 16):   # dos sur un banc : pas de réglage automatique, la géométrie est décrite directement
            FLOORREF[0] = 'all'; pose_apply(post, A, B, 0.0); place(None, None, 0.0); za = zregions()
            pose_apply(post, A, B, 1.0); place(None, None, 0.0); zb = zregions()
            fa_, fb_ = min(za['pelv'], za['upper'], za['feet'], za['head']), min(zb['pelv'], zb['upper'], zb['feet'], zb['head'])
            gh, ga, gd = za['pelv'] - za['feet'], za['upper'] - za['pelv'], za['upper'] - za['head']; dv = zb['pelv'] - zb['upper']; gb = zb['upper'] - zb['feet']
            if sp.get('liftB'): gb = 0.0; dv = 0.0   # le haut du corps se soulève à l'arrivée : on ne le plaque pas au sol
            ga_ = (za['uarm'] - fa_, za['farm'] - fa_, za['hands'] - fa_); gb_ = (zb['uarm'] - fb_, zb['farm'] - fb_, zb['hands'] - fb_)   # paume et doigts au niveau du corps
            flat = [sd for sd in ('L', 'R') if ('leg' + sd) not in A and ('leg' + sd) not in B and A.get('ik' + sd, A['ik'])['D'] < 0.6]
            gt = (sum((za['toes' + sd] - za['heel' + sd]) + (zb['toes' + sd] - zb['heel' + sd]) for sd in flat) / (2 * len(flat))) if flat else 0.0
            if max(abs(ga), abs(gd), *map(abs, ga_)) < 0.004 and max([abs(za['heel' + sd] - za['pelv']) for sd in ('L', 'R') if ('leg' + sd) not in A] + [0.0]) < 0.004 and abs(gb) < 0.006 and (max(map(abs, gb_)) < 0.006 or ('armL' in B)) and (abs(zb['upper'] - zb['head']) < 0.006 or 'trunk' in B) and abs(gt) < 0.004 and abs(za['shoulder'] - fa_) < 0.005 and abs(zb['shoulder'] - fb_) < 0.005: break
            for sd in ('L', 'R'):
                gl = []
                if ('leg' + sd) not in A: gl.append(za['heel' + sd] - za['pelv'])
                if ('leg' + sd) not in B and ('leg' + sd) not in A: gl.append(zb['heel' + sd] - min(zb['pelv'], zb['upper'], zb['head'], zb['shoulder']))
                if gl: CAL['h' + sd] -= 0.8 * sum(gl) / len(gl)
            CAL['a'] += 0.0 if sp.get('fixm') else ga; CAL['hd'] += gd / 0.2; CAL['hdB'] += 0.0 if sp.get('liftB') else (zb['upper'] - zb['head']) / 0.2
            CAL['cl'] = cl(CAL['cl'] + 0.8 * (za['shoulder'] - fa_) / 0.15, 0.0, 0.7); CAL['clB'] = CAL['clB'] if sp.get('liftB') else cl(CAL['clB'] + 0.8 * (zb['shoulder'] - fb_) / 0.15, 0.0, 0.7)
            CAL['ft'] = CAL['ftB'] = cl(CAL['ft'] + 0.6 * gt / 0.14, -0.35, 0.35)       # talon et orteils au même niveau (plante à plat)
            CAL['au'] = cl(CAL['au'] + 0.8 * ga_[1] / 0.30, -0.1, 0.6); CAL['af'] = 0.0; CAL['ah'] = cl(CAL['ah'] + 0.8 * ga_[2] / 0.10, -0.3, 0.3)   # avant-bras horizontal, posé ; le bras descend jusqu'à lui
            if all(('arm' + sd) not in B for sd in ('L', 'R')): CAL['auB'] = cl(CAL['auB'] + 0.8 * gb_[1] / 0.30, -0.1, 0.7)
            CAL['afB'] = 0.0; CAL['ahB'] = cl(CAL['ahB'] + 0.8 * gb_[2] / 0.10, -0.3, 0.3)
            if abs(gb) >= 0.006 and dv > 0.03 and not sp.get('fixm'): CAL['m'] = max(0.5, min(3.0, CAL['m'] * (zb['pelv'] - zb['feet']) / dv))
        if A.get('reach'): CAL['auB'] = CAL['au']; CAL['afB'] = CAL['af']; CAL['ahB'] = CAL['ah']   # mains aux jambes : pas de bras posé au sol à l'arrivée
        if sp.get('free_upper'): CAL.update(hd=0.0, hdB=0.0, cl=0.0, clB=0.0, au=0.0, auB=0.0, af=0.0, afB=0.0, ah=0.0, ahB=0.0)   # haut du dos sur un banc : pas de contact au sol à calibrer
        for tt in (0.0, 1.0):
            FLOORREF[0] = 'all'; pose_apply(post, A, B, tt); place(None, None, 0.0); zz = zregions()
            print('CONTROLE', slug, 'départ' if tt == 0 else 'arrivée', {k: round(v * 100, 1) for k, v in zz.items() if k in ('pelv', 'upper', 'shoulder', 'head', 'heel', 'toes', 'uarm', 'farm', 'palm', 'hands', 'knees', 'lowbody', 'heelL', 'heelR')}, 'cm au-dessus du point le plus bas ; étalonnage', {a: round(b * 100, 1) for a, b in CAL.items()}, flush=True)
        FLOORREF[0] = fref(0.0); set_ovr(SOL, 0.0)
    pose_apply(post, A, B, 0.0); anchor_bone = sp.get('anchor', 'pelvis.L' if post in ('supine', 'prone', 'side', 'quad') else 'foot.L'); place(None, None, fl0(0.0))
    anchor_xy = (arm.matrix_world @ pb[anchor_bone].head).xy.copy()
    ref = {'pelvis': arm.matrix_world @ pb['pelvis.L'].head, 'foot': arm.matrix_world @ pb['foot.L'].head}
    ref['pelvis'] = Vector((0, ref['pelvis'].y, ref['pelvis'].z))
    REFP[0] = ref['pelvis'].copy()
    add_props(sp.get('props', []), ref)
    if sp.get('solve_toe'):
        st_ = sp['solve_toe']; sd2 = st_['side']; other = 'L' if sd2 == 'R' else 'R'; lo, hi = 0.0, 1.5
        tr_, tf_ = ('toe3-3.' + sd2 if ('toe3-3.' + sd2) in pb else 'foot.' + sd2), ('toe3-3.' + other if ('toe3-3.' + other) in pb else 'foot.' + other)
        for _ in range(14):
            mid = (lo + hi) / 2; B['leg' + sd2] = (st_['thigh'], (0, math.cos(mid), -math.sin(mid))); pose_apply(post, A, B, 1.0); place(anchor_xy, anchor_bone, fl0(1.0))
            if (arm.matrix_world @ pb[tr_].tail).z > (arm.matrix_world @ pb[tf_].tail).z + st_.get('marge', 0.01): lo = mid   # orteils arrière trop hauts : le tibia descend
            else: hi = mid
        print('PIED ARRIÈRE : tibia incliné de', round(math.degrees(mid)), 'degrés sous l\'horizontale', flush=True)
    # cadrage commun : on mesure les poses extrêmes
    pts = []
    for t in (0.0, 0.5, 1.0):
        set_ovr(SOL, t); FLOORREF[0] = fref(t); pose_apply(post, A, B, t); place(anchor_xy, anchor_bone, fl0(t)); pts += [(c.x, c.y, c.z) for c in mesh_bounds()[::7]]
    az = {'side': 0, 'front': 90, '3q': 32, 'back': -90}[sp.get('view', 'side')]; azr = math.radians(az)
    # coordonnées écran : droite caméra = (−sin az ?) ; on projette
    rx, ry = -math.sin(azr) * 0 + (math.cos(azr) * 0), 0
    right = Vector((math.sin(azr), math.cos(azr), 0)); right = Vector((math.sin(azr + math.pi), math.cos(azr + math.pi), 0)) if False else Vector((-math.sin(azr) * 0, 0, 0))
    # base écran : pour une caméra à l'azimut az (position (cos az, -sin az)), vers l'origine, la droite écran vaut (sin az, cos az, 0)
    right = Vector((math.sin(azr), math.cos(azr), 0))
    ELEV = sp.get('elev', 11); el_ = math.radians(ELEV); dxy = (math.cos(azr), -math.sin(azr))
    us = [p[0] * right.x + p[1] * right.y for p in pts]; zs = [p[2] * math.cos(el_) - math.sin(el_) * (p[0] * dxy[0] + p[1] * dxy[1]) for p in pts]   # hauteur à l'écran, profondeur comprise
    if sp.get('props'): zs.append(-0.03)   # le cadrage inclut le sol sous les accessoires (mousse, marche)
    umin, umax, zmin_, zmax_ = min(us), max(us), min(zs), max(zs)
    aspect = 3 / 4 if sp.get('orient', 'port' if post == 'stand' else 'land') == 'port' else 4 / 3
    wid = (umax - umin) * 1.1 + 0.16; hei = (zmax_ - zmin_) * 1.08 + 0.16
    hei_eff = hei   # le bandeau de légende est maintenant sous l'image : on ne lui réserve plus de place
    scale = (max(wid, hei_eff * aspect) if aspect >= 1 else max(hei_eff, wid / aspect)) * sp.get('zoom', 1.0)   # en vertical, l'échelle de la caméra mesure la hauteur
    vext = scale / aspect if aspect >= 1 else scale
    ucen = (umin + umax) / 2; zcen = ((zmin_ + zmax_) / 2 + 0.01) / math.cos(el_)   # le personnage est centré dans l'image
    tgt = Vector((ucen * right.x, ucen * right.y, zcen))
    if sp.get('focus') == 'head':
        tgt = arm.matrix_world @ pb['head'].tail; tgt.z -= 0.02; scale = sp.get('focus_scale', 0.5)
    set_camera(az, tgt, scale, aspect, ELEV); set_lights(az)
    W = 270 if aspect < 1 else 360; H = 360 if aspect < 1 else 270
    json.dump({'aspect': aspect, 'w': W, 'h': H, 'hold': sp.get('hold', False), 'name': sp.get('name', slug)}, open(f'{out}/meta.json', 'w'))
    if os.environ.get('HANDDEBUG'):
        names = [b for b in pb.keys() if 'finger' in b and b.endswith('.L')]; print('DOIGTS', sorted(names), flush=True)
        for b in ('finger3-1.L', 'finger3-2.L', 'wrist.L'): print('AXES', b, [tuple(round(v, 2) for v in (arm.matrix_world.to_3x3() @ pb[b].matrix.to_3x3() @ ax)) for ax in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))], flush=True)
    if MODE == 'diag' and sp.get('probe'):   # mesure du nez par rapport aux chaussures et de la hauteur du bassin, tout au long du mouvement
        toe = 'toe3-3.L' if 'toe3-3.L' in pb else 'foot.L'
        for tt in [k / 10 for k in range(11)]:
            pose_apply(post, A, B, tt); place(anchor_xy, anchor_bone, fl0(tt)); nose = (arm.matrix_world @ pb['head'].tail).y - 0.07; tip = (arm.matrix_world @ pb[toe].tail).y
            print('PROBE', slug, 't=%.1f' % tt, 'nez - bout du pied : %+.0f cm (positif = nez derrière les chaussures)' % ((nose - tip) * 100), '| bassin z : %.0f cm' % ((arm.matrix_world @ pb['pelvis.L'].head).z * 100), '| bassin y : %+.0f cm | haut du dos y : %+.0f cm | genou y : %+.0f | cheville y : %+.0f' % ((arm.matrix_world @ pb['pelvis.L'].head).y * 100, (arm.matrix_world @ pb['spine02'].head).y * 100, (arm.matrix_world @ pb['lowerleg01.' + os.environ.get('PROBE_SIDE', 'L')].head).y * 100, (arm.matrix_world @ pb['foot.' + os.environ.get('PROBE_SIDE', 'L')].head).y * 100) + ' | semelle gauche z : %.1f cm, droite z : %.1f cm' % ((arm.matrix_world @ pb['foot.L'].head).z * 100 - 7.1, (arm.matrix_world @ pb['foot.R'].head).z * 100 - 7.1) + ' | hanche y : %+.0f | épaule y : %+.0f | tête y : %+.0f' % ((arm.matrix_world @ pb['upperleg01.' + os.environ.get('PROBE_SIDE', 'L')].head).y * 100, (arm.matrix_world @ pb['upperarm01.L'].head).y * 100, (arm.matrix_world @ pb['head'].head).y * 100), flush=True)
        return
    if MODE == 'diag':
        zonemap = {'head': 'tête', 'neck01': 'cou', 'neck02': 'cou', 'neck03': 'cou', 'spine01': 'haut du dos (omoplates)', 'spine02': 'milieu du dos', 'spine03': 'milieu du dos', 'spine04': 'bas du dos', 'spine05': 'bassin/bas du dos'}
        def zone(n):
            if n in zonemap: return zonemap[n]
            for k, v in (('wrist', 'main'), ('metacarpal', 'main'), ('finger', 'main'), ('lowerarm', 'avant-bras'), ('upperarm', 'bras'), ('clavicle', 'épaule'), ('shoulder', 'épaule'), ('foot', 'pied'), ('toe', 'pied'), ('lowerleg', 'jambe'), ('upperleg', 'cuisse'), ('pelvis', 'bassin')):
                if n.startswith(k): return v
            return n
        names_by_idx = {i: g.name for i, g in enumerate(body.vertex_groups)}
        dom = []
        for v in body.data.vertices:
            gs = sorted(v.groups, key=lambda g: -g.weight); dom.append(zone(names_by_idx[gs[0].group]) if gs else '?')
        for nm, tt in (('A', 0.0), ('B', 1.0)):
            pose_apply(post, A, B, tt); place(anchor_xy, anchor_bone, fl0(tt)); co = mesh_bounds()[:NB]
            zmn = {}
            for i, c in enumerate(co): zmn[dom[i]] = min(zmn.get(dom[i], 9), c.z)
            touching = sorted(k for k, z in zmn.items() if z < 0.012)
            hi = sorted(((round(z * 100, 1), k) for k, z in zmn.items() if 0.012 <= z < 0.40))[:6]
            print('DIAG', slug, nm, '| touche le sol (<1,2 cm) :', ', '.join(touching) or 'rien', '| plus bas des autres zones (cm) :', hi, flush=True)
        return

    if MODE != 'full' or aspect < 1:   # test, photos, ou personnage debout : photos de départ et d'arrivée en meilleure qualité
        for nm, tt in (('A', 0.0), ('B', 1.0)):
            set_ovr(SOL, tt); FLOORREF[0] = fref(tt); pose_apply(post, A, B, tt); place(anchor_xy, anchor_bone, fl0(tt)); update_bands(); render(f'{out}/{nm}.png', int(W * 1.5), int(H * 1.5), SAMP * 2)
    if MODE == 'full' and not os.path.exists(f'{out}/f000.png'):
        for i in range(NF):
            t = ease(i / (NF - 1)); set_ovr(SOL, t); FLOORREF[0] = fref(t); pose_apply(post, A, B, t); place(anchor_xy, anchor_bone, fl0(t)); update_bands(); render(f'{out}/f{i:03d}.png', W, H, SAMP)
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
