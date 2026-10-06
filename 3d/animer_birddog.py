import bpy, bmesh, sys, math, json, os
from mathutils import Vector, Matrix, Quaternion

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OBJ, TOPCOL, GEN, AGE, MODE, OUT = ARGS[0], ARGS[1], ARGS[2], ARGS[3], ARGS[4], ARGS[5]   # MODE : stills | frames
SAMPLES, WIDTH = int(ARGS[6]), int(ARGS[7])
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

# ---------- lecture du corps (indices de points conservés) ----------
V = []; groups = {}; cur = None
for l in open(OBJ):
    if l.startswith('v '): V.append([float(x) for x in l.split()[1:4]])
    elif l.startswith('g '): cur = l.split()[1]; groups.setdefault(cur, [])
    elif l.startswith('f ') and cur: groups[cur].append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
NB = 13380
conv = lambda p: Vector((p[0] * 0.1, -p[2] * 0.1, p[1] * 0.1))
P = [conv(p) for p in V]
zmin = min(p.z for p in P[:NB]); P = [Vector((p.x, p.y, p.z - zmin)) for p in P]
bodyfaces = groups['body']; assert max(max(f) for f in bodyfaces) < NB
height = max(p.z for p in P[:NB]); k = height / 1.666

me = bpy.data.meshes.new('corps'); body = bpy.data.objects.new('Corps', me); scene.collection.objects.link(body)
me.from_pydata([tuple(p) for p in P[:NB]], [], bodyfaces); me.update()
ra = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT'); ra.data.foreach_set('vector', [c for p in P[:NB] for c in p])
for p in me.polygons: p.use_smooth = True

# ---------- squelette ----------
sk = json.load(open(RIG + 'default.mhskel')); wts = json.load(open(RIG + 'default_weights.mhw'))['weights']
def jpos(name):
    idx = sk['joints'][name]; return sum((P[i] for i in idx), Vector()) / len(idx)
arm_d = bpy.data.armatures.new('Squelette'); arm = bpy.data.objects.new('Squelette', arm_d); scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
for n, b in sk['bones'].items():
    e = arm_d.edit_bones.new(n); e.head = jpos(b['head']); e.tail = jpos(b['tail'])
    if (e.tail - e.head).length < 1e-4: e.tail = e.head + Vector((0, 0, 0.01))
for n, b in sk['bones'].items():
    if b['parent']: arm_d.edit_bones[n].parent = arm_d.edit_bones[b['parent']]
bpy.ops.object.mode_set(mode='OBJECT')
body.parent = arm
names = list(sk['bones'].keys())
for n in names: body.vertex_groups.new(name=n)
for n, lst in wts.items():
    if n not in body.vertex_groups: continue
    vg = body.vertex_groups[n]
    for vi, w in lst:
        if vi < NB: vg.add([vi], w, 'REPLACE')
md = body.modifiers.new('Armature', 'ARMATURE'); md.object = arm
sub = body.modifiers.new('Sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2

# ---------- matière du corps (vêtements par zone, position de repos) ----------
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
    X, Y, Z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    AX = M('ABSOLUTE', X)
    between = lambda v, lo, hi: M('MULTIPLY', M('GREATER_THAN', v, lo), M('LESS_THAN', v, hi))
    zl = lambda zw: zw * k
    shorts = M('MULTIPLY', between(Z, zl(0.60), zl(1.00)), M('LESS_THAN', AX, 0.30 * k))
    torso = M('MULTIPLY', between(Z, zl(1.00), zl(1.44)), M('LESS_THAN', AX, 0.215 * k))
    neck = M('MULTIPLY', M('LESS_THAN', AX, 0.085 * k), M('GREATER_THAN', Z, zl(1.385)))
    def sq(v): return M('MULTIPLY', v, v)
    def d2(sx): return M('ADD', M('ADD', sq(M('SUBTRACT', X, sx)), sq(Y)), sq(M('SUBTRACT', Z, zl(1.38))))
    near = M('LESS_THAN', M('MINIMUM', d2(0.185 * k), d2(-0.185 * k)), (0.118 * k) ** 2)
    sleeve = M('MULTIPLY', M('MULTIPLY', near, M('GREATER_THAN', AX, 0.17 * k)), M('GREATER_THAN', Z, zl(1.20)))
    shirt = M('MAXIMUM', M('MULTIPLY', torso, M('SUBTRACT', 1.0, neck)), sleeve)
    def col(hexc): n = N.new('ShaderNodeRGB'); n.outputs[0].default_value = lin(hexc); return n.outputs[0]
    def mix(fac, c1, c2): n = N.new('ShaderNodeMixRGB'); Lk.new(fac, n.inputs[0]); Lk.new(c1, n.inputs[1]); Lk.new(c2, n.inputs[2]); return n.outputs[0]
    c = mix(shirt, col('#D8B193'), col(TOPCOL)); c = mix(shorts, c, col('#33454D')); Lk.new(c, bsdf.inputs['Base Color'])
    return m
body.data.materials.append(corps_materiau())

# ---------- cheveux (coque issue de la surface du crâne, avec les mêmes poids), sourcils, yeux ----------
HAIRC = {'F': {'adulte': '#4B3425', 'senior': '#C7C7C4'}, 'M': {'adulte': '#3B2B22', 'senior': '#CDCDCA'}}[GEN][AGE]
bmh = bmesh.new(); bmh.from_mesh(body.data); bmh.faces.ensure_lookup_table()
headv = [v for v in bmh.verts if v.co.z > 0.88 * height]
yc = (min(v.co.y for v in headv) + max(v.co.y for v in headv)) / 2
keep = set()
for f in bmh.faces:
    c = f.calc_center_median(); zw = c.z
    top = zw > 0.962 * height and not (GEN == 'M' and AGE == 'senior' and abs(c.x) < 0.07 * k)
    back = zw > 0.905 * height and c.y > yc + 0.005
    side = zw > 0.935 * height and abs(c.x) > 0.075 * k and c.y > yc - 0.04
    long_ = GEN == 'F' and 0.83 * height < zw <= 0.905 * height and c.y > yc + 0.012 and abs(c.x) < 0.11 * k
    if top or back or side or long_: keep.add(f.index)
bmesh.ops.delete(bmh, geom=[f for f in bmh.faces if f.index not in keep], context='FACES')
hm = bpy.data.meshes.new('cheveux'); bmh.to_mesh(hm); bmh.free()
hair = bpy.data.objects.new('Cheveux', hm); scene.collection.objects.link(hair); hair.parent = arm
for n in names: hair.vertex_groups.new(name=n)
# poids copiés depuis le corps (même ordre de points conservé par la suppression de faces : on les retrouve par position de repos)
bvert = {tuple(round(c, 6) for c in v.co): v.index for v in body.data.vertices}
for v in hair.data.vertices:
    bi = bvert.get(tuple(round(c, 6) for c in v.co))
    if bi is None: continue
    for g in body.data.vertices[bi].groups: hair.vertex_groups[g.group].add([v.index], g.weight, 'REPLACE')
hair.data.materials.append(mat('Cheveux', HAIRC, 0.62))
hmd = hair.modifiers.new('Armature', 'ARMATURE'); hmd.object = arm
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
    rp = N.new('ShaderNodeValToRGB'); rp.color_ramp.interpolation = 'CONSTANT'
    rp.color_ramp.elements[0].position = 0.0; rp.color_ramp.elements[0].color = lin('#EDEDEA')
    e1 = rp.color_ramp.elements.new(0.90); e1.color = lin(iris_hex); e2 = rp.color_ramp.elements.new(0.975); e2.color = lin('#101010')
    Lk.new(dt.outputs['Value'], rp.inputs['Fac']); Lk.new(rp.outputs['Color'], bsdf.inputs['Base Color']); return m
def rigid_head(o):
    o.parent = arm; vg = o.vertex_groups.new(name='head'); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    md_ = o.modifiers.new('Armature', 'ARMATURE'); md_.object = arm
irisc = '#5A3E2B' if AGE == 'adulte' else '#5F7F8E'
for gname, oname in (('helper-l-eye', 'OeilG'), ('helper-r-eye', 'OeilD')):
    e = mesh_from_group(gname, oname); cen = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)
    e.data.materials.append(eye_material(cen, irisc)); rigid_head(e)
    for p in e.data.polygons: p.use_smooth = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(cen.x, cen.y - 0.012, cen.z + 0.030 * k))
    br = bpy.context.active_object; br.name = 'Sourcil'; br.scale = (0.026 * k, 0.0065 * k, 0.0058 * k); br.rotation_euler = (0, math.radians(-8 if cen.x > 0 else 8), 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    br.data.materials.append(mat('Sourcil', HAIRC if AGE == 'senior' else '#34261E', 0.8)); rigid_head(br)
    for p in br.data.polygons: p.use_smooth = True

# ---------- poses ----------
pb = arm.pose.bones
def refresh(): bpy.context.view_layer.update()
def aim(name, direction):
    p = pb[name]; m = p.matrix.copy(); cur = (m.to_3x3() @ Vector((0, 1, 0))).normalized(); d = Vector(direction).normalized()
    q = cur.rotation_difference(d); h = m.translation.copy()
    p.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ m; refresh()
def pitch_root(deg):
    hips = (arm.data.bones['pelvis.L'].head_local + arm.data.bones['pelvis.R'].head_local) / 2
    p = pb['root']; m = p.matrix.copy(); R = Matrix.Rotation(math.radians(deg), 4, 'X')
    p.matrix = Matrix.Translation(hips) @ R @ Matrix.Translation(-hips) @ m; refresh()
def reset_pose():
    for p in pb: p.location = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0)
    refresh()
F, B_, D, U = (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1)
def quadruped(extend=0.0):
    reset_pose(); pitch_root(76)
    aim('neck01', (0, -1, 0.22)); aim('neck02', (0, -1, 0.14)); aim('head', (0, -1, 0.02))
    for s in ('L', 'R'):
        aim(f'upperarm01.{s}', D); aim(f'lowerarm01.{s}', D)
        aim(f'upperleg01.{s}', D); aim(f'lowerleg01.{s}', (0, 1, -0.02)); aim(f'foot.{s}', (0, 1, -0.35))
    return None
def birddog(t):
    """t = 0 : départ ; t = 1 : bras gauche (côté caméra) et jambe droite tendus."""
    quadruped()
    if t <= 0: return
    lerp = lambda a, b: tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    reset_pose(); pitch_root(76)
    aim('neck01', (0, -1, 0.22)); aim('neck02', (0, -1, 0.14)); aim('head', (0, -1, 0.02 + 0.06 * t))
    aim('upperarm01.R', D); aim('lowerarm01.R', D); aim('upperleg01.L', D); aim('lowerleg01.L', (0, 1, -0.02)); aim('foot.L', (0, 1, -0.35))
    aim('upperarm01.L', lerp(D, (0, -1, 0.04))); aim('lowerarm01.L', lerp(D, (0, -1, 0.04))); aim('wrist.L', lerp(D, (0, -1, 0)))
    aim('upperleg01.R', lerp(D, (0, 1, 0.05))); aim('lowerleg01.R', lerp((0, 1, -0.02), (0, 1, 0.05))); aim('foot.R', lerp((0, 1, -0.35), (0, 1, -0.2)))
    aim('wrist.R', F)
def to_floor():
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); mm = ev.to_mesh()
    z = min(v.co.z for v in mm.vertices); ev.to_mesh_clear()
    p = pb['root']; m = p.matrix.copy(); m.translation.z -= z; p.matrix = m; refresh()

# ---------- sol, lumière, caméra de profil ----------
fl_m = mat('Sol', '#D3D9DC', 0.95); bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(fl_m)
w = bpy.data.worlds.new('Monde'); scene.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.86, 0.89, 0.91, 1); bg.inputs[1].default_value = 0.7
def area(name, loc, energy, size, target=(0, 0, 0.5)):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.active_object; l.name = name; l.data.energy = energy; l.data.size = size
    l.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('Cle', (3.2, -2.2, 3.0), 210, 2.6); area('Remplissage', (3.0, 2.4, 1.6), 85, 3.0); area('Contre', (-2.5, 0.5, 2.6), 120, 2.0)
import math as _m
elev = _m.radians(11); tgt = Vector((0, -0.04, 0.36)); camloc = tgt + Vector((6.0 * _m.cos(elev), 0, 6.0 * _m.sin(elev)))
bpy.ops.object.camera_add(location=camloc); cam = bpy.context.active_object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.25
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = False
scene.render.resolution_x = WIDTH; scene.render.resolution_y = int(WIDTH * 0.75)
os.makedirs(OUT, exist_ok=True)
def render(path): scene.render.filepath = path; bpy.ops.render.render(write_still=True)

if MODE == 'stills':
    for nom, t in (('depart', 0.0), ('milieu', 0.5), ('tendu', 1.0)):
        birddog(t); to_floor(); render(f'{OUT}/{nom}.png'); print('IMAGE', nom)
else:   # frames : t = 0..1 pour l'aller, indices passés en arguments
    ts = json.loads(ARGS[8]); START = int(ARGS[9]) if len(ARGS) > 9 else 0
    for i, t in enumerate(ts):
        birddog(t); to_floor(); render(f'{OUT}/f{START + i:03d}.png'); print('IMAGE', START + i, round(t, 3), flush=True)
bpy.ops.wm.save_as_mainfile(filepath='/tmp/b3d/anim.blend')
print('TERMINE')
