import sys; sys.path.insert(0, '/tmp/b3d')
import bpy, bmesh, math
from mathutils import Vector, Matrix
from rig_lib import *
from pose_lib import *

ARGS = sys.argv[sys.argv.index('--') + 1:]
OBJ, OUTDIR, SAMPLES, WIDTH, HEIGHT, USTR, GEN, AGE, TOPCOL, VIEW = ARGS[0], ARGS[1], int(ARGS[2]), int(ARGS[3]), int(ARGS[4]), ARGS[5], ARGS[6], ARGS[7], ARGS[8], (ARGS[9] if len(ARGS) > 9 else 'profil')
bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
body, eyes, V, W = build_character(OBJ); arm, sk, jpos = build_armature(body, W)
zmax = max(w.z for w in W[:NBODY]); k = zmax / 1.666

# ---------- vêtements colorés par zone (position de repos) ----------
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
sub = body.modifiers.new('Sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
# l'armature doit déformer avant la subdivision
bpy.context.view_layer.objects.active = body
while body.modifiers[0].name != 'Armature': bpy.ops.object.modifier_move_up(modifier='Armature')

def follow_head(obj):
    vg = obj.vertex_groups.new(name='head'); vg.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
    md = obj.modifiers.new('Armature', 'ARMATURE'); md.object = arm; obj.parent = arm
    bpy.context.view_layer.objects.active = obj
    while obj.modifiers[0].name != 'Armature': bpy.ops.object.modifier_move_up(modifier='Armature')

# ---------- cheveux, sourcils, yeux ----------
HAIRC = {'F': {'adulte': '#4B3425', 'senior': '#C7C7C4'}, 'M': {'adulte': '#3B2B22', 'senior': '#CDCDCA'}}[GEN][AGE]
bmh = bmesh.new(); bmh.from_mesh(body.data); bmh.faces.ensure_lookup_table()
headv = [v for v in bmh.verts if v.co.z > 0.88 * zmax]; yc = (min(v.co.y for v in headv) + max(v.co.y for v in headv)) / 2
keep = set()
for f in bmh.faces:
    c = f.calc_center_median(); zw = c.z
    top = zw > 0.962 * zmax and not (GEN == 'M' and AGE == 'senior' and abs(c.x) < 0.07 * k)
    back = zw > 0.905 * zmax and c.y > yc + 0.005
    side = zw > 0.935 * zmax and abs(c.x) > 0.075 * k and c.y > yc - 0.04
    long_ = GEN == 'F' and 0.83 * zmax < zw <= 0.905 * zmax and c.y > yc + 0.012 and abs(c.x) < 0.11 * k
    if top or back or side or long_: keep.add(f.index)
bmesh.ops.delete(bmh, geom=[f for f in bmh.faces if f.index not in keep], context='FACES')
hm = bpy.data.meshes.new('cheveux'); bmh.to_mesh(hm); bmh.free()
hair = bpy.data.objects.new('Cheveux', hm); scene.collection.objects.link(hair)
for p in hair.data.polygons: p.use_smooth = True
hair.data.materials.append(mat('Cheveux', HAIRC, 0.62)); follow_head(hair)
so = hair.modifiers.new('Epaisseur', 'SOLIDIFY'); so.thickness = 0.011; so.offset = 1.0
hs = hair.modifiers.new('Lisse', 'SUBSURF'); hs.levels = 1; hs.render_levels = 1

def eye_material(center, iris_hex):
    m = bpy.data.materials.new('Oeil'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.12
    tc = N.new('ShaderNodeTexCoord'); sb = N.new('ShaderNodeVectorMath'); sb.operation = 'SUBTRACT'; sb.inputs[1].default_value = center; Lk.new(tc.outputs['Object'], sb.inputs[0])
    nm = N.new('ShaderNodeVectorMath'); nm.operation = 'NORMALIZE'; Lk.new(sb.outputs[0], nm.inputs[0])
    dt = N.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'; dt.inputs[1].default_value = (0, -1, 0); Lk.new(nm.outputs[0], dt.inputs[0])
    rp = N.new('ShaderNodeValToRGB'); rp.color_ramp.interpolation = 'CONSTANT'
    rp.color_ramp.elements[0].position = 0.0; rp.color_ramp.elements[0].color = lin('#EDEDEA')
    e1 = rp.color_ramp.elements.new(0.90); e1.color = lin(iris_hex); e2 = rp.color_ramp.elements.new(0.975); e2.color = lin('#101010')
    Lk.new(dt.outputs['Value'], rp.inputs['Fac']); Lk.new(rp.outputs['Color'], bsdf.inputs['Base Color'])
    return m
irisc = '#5A3E2B' if AGE == 'adulte' else '#5F7F8E'
for e in eyes:
    cen = sum((v.co for v in e.data.vertices), Vector()) / len(e.data.vertices)
    e.data.materials.append(eye_material(cen, irisc)); follow_head(e)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(cen.x, cen.y - 0.012, cen.z + 0.030 * k))
    br = bpy.context.active_object; br.scale = (0.026 * k, 0.0065 * k, 0.0058 * k); br.rotation_euler = (0, math.radians(-8 if cen.x > 0 else 8), 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for p in br.data.polygons: p.use_smooth = True
    br.data.materials.append(mat('Sourcil', HAIRC if AGE == 'senior' else '#34261E', 0.8)); follow_head(br)

# ---------- décor ----------
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(mat('Sol', '#C9CFD2', 0.95))
w = bpy.data.worlds.new('M'); scene.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.80, 0.84, 0.87, 1); bg.inputs[1].default_value = 0.55
def area(loc, energy, size, tgt=(0, 0, 0.5)):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.active_object; l.data.energy = energy; l.data.size = size
    l.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area((-2.2, -1.6, 2.8), 230, 2.6); area((-1.2, -3.0, 1.2), 90, 3.0); area((1.2, 2.4, 2.4), 120, 2.0)
CAMS = {'profil': ((-3.3, 0.02, 0.62), (0, 0.02, 0.50)), 'tq': ((-2.6, -2.4, 0.95), (0, 0.02, 0.45))}
cl, ct = CAMS[VIEW]
bpy.ops.object.camera_add(location=cl); cam = bpy.context.active_object; cam.data.lens = 50
cam.rotation_euler = (Vector(ct) - cam.location).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = os.environ.get('DENOISE') == '1'
scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT

# ---------- mesures du personnage (au repos) ----------
bpy.context.view_layer.update()
J = lambda n: Vector(jpos[n])
SIDES = {s: dict(sh=J(f'upperarm01.{s}____head'), el=J(f'lowerarm01.{s}____head'), wr=J(f'wrist.{s}____head'), hip=J(f'upperleg01.{s}____head'), kn=J(f'lowerleg01.{s}____head'), an=J(f'foot.{s}____head')) for s in ('L', 'R')}
NEAR = 'R' if SIDES['R']['sh'].x < SIDES['L']['sh'].x else 'L'; FAR = 'L' if NEAR == 'R' else 'R'
La1 = (SIDES[NEAR]['el'] - SIDES[NEAR]['sh']).length; La2 = (SIDES[NEAR]['wr'] - SIDES[NEAR]['el']).length
Ll1 = (SIDES[NEAR]['kn'] - SIDES[NEAR]['hip']).length; Ll2 = (SIDES[NEAR]['an'] - SIDES[NEAR]['kn']).length
hips_c = (SIDES['L']['hip'] + SIDES['R']['hip']) / 2; sh_c = (SIDES['L']['sh'] + SIDES['R']['sh']) / 2
Lt = (sh_c - hips_c).length
HS = (La1 + La2) * 0.985 + 0.045; HH = Ll1 * 0.97 + 0.055
sina = max(-0.35, min(0.35, (HS - HH) / Lt)); alpha = math.asin(sina)
YH = 0.30; tdir = Vector((0, -math.cos(alpha), math.sin(alpha)))
rest_dir = (sh_c - hips_c).normalized()
rootpb = arm.pose.bones['root']; M_rest = rootpb.bone.matrix_local.copy()
ease = lambda t: 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
def lerpv(a, b, t): return a + (b - a) * t
def pose(u):
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    R = rest_dir.rotation_difference(tdir).to_matrix().to_4x4()
    P = Vector((0, YH, HH))
    rootpb.matrix = Matrix.Translation(P) @ R @ Matrix.Translation(-hips_c) @ M_rest
    bpy.context.view_layer.update()
    # tête : regard vers l'avant et vers le sol
    up = Vector((0, 0, 1))
    for nm, a in (('neck01', 0.12), ('neck02', 0.12), ('neck03', 0.12), ('head', 0.10)):
        d = (tdir * (1 - a) + up * a); aim(arm, nm, d)
    e = ease(u)
    for s in ('L', 'R'):
        # bras
        shp = head_pos(arm, f'upperarm01.{s}')
        sup = Vector((shp.x, shp.y - 0.0, 0.045))
        ext = shp + Vector((0, -(La1 + La2) * 0.995, 0.015))
        tgt = lerpv(sup, ext, e) if s == NEAR else sup
        outx = 1 if shp.x > 0 else -1
        el = ik2(shp, tgt, La1, La2, Vector((0.35 * outx, 1.0, 0.15)))
        aim(arm, f'upperarm01.{s}', el - shp); aim(arm, f'lowerarm01.{s}', tgt - el)
        hd = Vector((0, -1, -0.05)) if s != NEAR else lerpv(Vector((0, -1, -0.05)), (tgt - el).normalized(), e)
        aim(arm, f'wrist.{s}', hd)
        # jambes
        hp = head_pos(arm, f'upperleg01.{s}')
        kneel = Vector((hp.x, hp.y + Ll2 * 0.97, 0.06)); extl = hp + Vector((0, (Ll1 + Ll2) * 0.997, 0.0))
        tgt = lerpv(kneel, extl, e) if s == FAR else kneel
        kn = ik2(hp, tgt, Ll1, Ll2, Vector((0, -1, -0.9 if s != FAR else -0.9 + 1.9 * e)))
        aim(arm, f'upperleg01.{s}', kn - hp); aim(arm, f'lowerleg01.{s}', tgt - kn)
        fd = Vector((0, 1, -0.10)) if s != FAR else lerpv(Vector((0, 1, -0.10)), (tgt - kn).normalized(), e)
        aim(arm, f'foot.{s}', fd)
    bpy.context.view_layer.update()

if __name__ == '__main__' or True:
    os.makedirs(OUTDIR, exist_ok=True)
    for i, us in enumerate(USTR.split(',')):
        u = float(us); pose(u)
        scene.render.filepath = f'{OUTDIR}/f_{int(os.environ.get("START", "0")) + i:03d}.png'; bpy.ops.render.render(write_still=True)
        print('IMAGE', i, 'u =', u)
    print('RENDU TERMINE', 'proche =', NEAR, 'alpha =', round(math.degrees(alpha), 1), 'deg')
