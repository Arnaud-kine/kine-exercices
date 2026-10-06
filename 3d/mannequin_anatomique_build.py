import bpy, bmesh, sys, math
from mathutils import Vector

def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1)
def mat(name, col, rough=0.5, sss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(col); b.inputs['Roughness'].default_value = rough
    if sss: b.inputs['Subsurface Weight'].default_value = sss; b.inputs['Subsurface Radius'].default_value = (0.9, 0.35, 0.25)
    return m

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OBJ = ARGS[4] if len(ARGS) > 4 else '/tmp/b3d/base.obj'; TOPCOL = ARGS[5] if len(ARGS) > 5 else '#0E8B85'
bpy.ops.wm.obj_import(filepath=OBJ, forward_axis='NEGATIVE_Z', up_axis='Y', global_scale=0.1, use_split_groups=True)
keep = []
for o in list(bpy.context.scene.objects):
    n = o.name.lower()
    if o.type == 'MESH' and (n.startswith('body') or n in ('helper-l-eye', 'helper-r-eye')): keep.append(o)
    else: bpy.data.objects.remove(o, do_unlink=True)
body = [o for o in keep if o.name.lower().startswith('body')][0]
eyes = [o for o in keep if 'eye' in o.name.lower()]
bpy.ops.object.select_all(action='DESELECT')
for o in keep: o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
print('ROTATION', [round(v, 3) for v in body.rotation_euler], 'ECHELLE', [round(v, 3) for v in body.scale])
bpy.context.view_layer.update()
zmin = min((o.matrix_world @ Vector(c)).z for o in keep for c in o.bound_box)
for o in keep: o.location.z -= zmin
bpy.context.view_layer.update()
zmax = max((o.matrix_world @ Vector(c)).z for o in keep for c in o.bound_box)
print('HAUTEUR', round(zmax, 3), 'm')
k = zmax / 1.666

eyeM = mat('Oeil', '#EDEDED', 0.2)
zoff = body.location.z
vs = [v.co for v in body.data.vertices]
mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
ra = body.data.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
ra.data.foreach_set('vector', [c for v in body.data.vertices for c in v.co])
def corps_materiau():
    m = bpy.data.materials.new('Corps'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bsdf = N['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.55; bsdf.inputs['Subsurface Weight'].default_value = 0.10; bsdf.inputs['Subsurface Radius'].default_value = (0.9, 0.35, 0.25)
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
    zl = lambda zw: zw * k - zoff
    shorts = M('MULTIPLY', between(Z, zl(0.60), zl(1.00)), M('LESS_THAN', AX, 0.30 * k))
    torso = M('MULTIPLY', between(Z, zl(1.00), zl(1.44)), M('LESS_THAN', AX, 0.215 * k))
    neck = M('MULTIPLY', M('LESS_THAN', AX, 0.085 * k), M('GREATER_THAN', Z, zl(1.385)))
    def sq(v): return M('MULTIPLY', v, v)
    def d2(sx): return M('ADD', M('ADD', sq(M('SUBTRACT', X, sx)), sq(Y)), sq(M('SUBTRACT', Z, zl(1.38))))
    near = M('LESS_THAN', M('MINIMUM', d2(0.185 * k), d2(-0.185 * k)), (0.118 * k) ** 2)
    sleeve = M('MULTIPLY', M('MULTIPLY', near, M('GREATER_THAN', AX, 0.17 * k)), M('GREATER_THAN', Z, zl(1.20)))
    shirt = M('MAXIMUM', M('MULTIPLY', torso, M('SUBTRACT', 1.0, neck)), sleeve)
    def col(name, hexc): n = N.new('ShaderNodeRGB'); n.outputs[0].default_value = lin(hexc); return n.outputs[0]
    def mix(fac, c1, c2): n = N.new('ShaderNodeMixRGB'); Lk.new(fac, n.inputs[0]); Lk.new(c1, n.inputs[1]); Lk.new(c2, n.inputs[2]); return n.outputs[0]
    c = mix(shirt, col('p', '#D8B193'), col('h', TOPCOL)); c = mix(shorts, c, col('s', '#33454D'))
    Lk.new(c, bsdf.inputs['Base Color'])
    return m
bpy.context.view_layer.objects.active = body; body.select_set(True)
body.data.materials.clear(); body.data.materials.append(corps_materiau())
bpy.ops.object.shade_smooth()
sub = body.modifiers.new('Sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
GEN = ARGS[6] if len(ARGS) > 6 else 'F'; AGE = ARGS[7] if len(ARGS) > 7 else 'adulte'
HAIRC = {'F': {'adulte': '#4B3425', 'senior': '#C7C7C4'}, 'M': {'adulte': '#3B2B22', 'senior': '#CDCDCA'}}[GEN][AGE]
bmh = bmesh.new(); bmh.from_mesh(body.data); bmh.faces.ensure_lookup_table()
headv = [v for v in bmh.verts if v.co.z + zoff > 0.88 * zmax]
yc = (min(v.co.y for v in headv) + max(v.co.y for v in headv)) / 2
keep = set()
for f in bmh.faces:
    c = f.calc_center_median(); zw = c.z + zoff
    top = zw > 0.962 * zmax and not (GEN == 'M' and AGE == 'senior' and abs(c.x) < 0.07 * k)
    back = zw > 0.905 * zmax and c.y > yc + 0.005
    side = zw > 0.935 * zmax and abs(c.x) > 0.075 * k and c.y > yc - 0.04
    long_ = GEN == 'F' and 0.83 * zmax < zw <= 0.905 * zmax and c.y > yc + 0.012 and abs(c.x) < 0.11 * k
    if top or back or side or long_: keep.add(f.index)
bmesh.ops.delete(bmh, geom=[f for f in bmh.faces if f.index not in keep], context='FACES')
hm = bpy.data.meshes.new('cheveux_maillage'); bmh.to_mesh(hm); bmh.free()
hair = bpy.data.objects.new('Cheveux', hm); scene.collection.objects.link(hair); hair.location = body.location
hairM = mat('Cheveux', HAIRC, 0.62)
hair.data.materials.append(hairM)
bpy.context.view_layer.objects.active = hair; hair.select_set(True)
so = hair.modifiers.new('Epaisseur', 'SOLIDIFY'); so.thickness = 0.011; so.offset = 1.0
hs = hair.modifiers.new('Lisse', 'SUBSURF'); hs.levels = 1; hs.render_levels = 1
bpy.ops.object.shade_smooth()
# yeux : iris et pupille ; sourcils
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
    e.data.materials.clear(); e.data.materials.append(eye_material(cen, irisc))
    bpy.context.view_layer.objects.active = e; bpy.ops.object.shade_smooth()
    wc = cen + e.location
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(wc.x, wc.y - 0.012, wc.z + 0.030 * k))
    br = bpy.context.active_object; br.name = 'Sourcil'; br.scale = (0.026 * k, 0.0065 * k, 0.0058 * k); br.rotation_euler = (0, math.radians(-8 if wc.x > 0 else 8), 0)
    br.data.materials.append(mat('Sourcil', HAIRC if AGE == 'senior' else '#34261E', 0.8))
    bpy.ops.object.shade_smooth()

floor_m = mat('Sol', '#C9CFD2', 0.95)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(floor_m)
w = bpy.data.worlds.new('Monde'); scene.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.80, 0.84, 0.87, 1); bg.inputs[1].default_value = 0.55
def area(name, loc, energy, size, target=(0, 0, 0.9)):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.active_object; l.name = name; l.data.energy = energy; l.data.size = size
    l.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return l
area('Cle', (-2.0, -2.4, 3.0), 210, 2.6); area('Remplissage', (2.6, -1.8, 1.6), 85, 3.0); area('Contre', (0.8, 2.8, 2.6), 120, 2.0)
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
samples = int(args[0]) if args else 24; width = int(args[1]) if len(args) > 1 else 360; out = args[2] if len(args) > 2 else '/tmp/b3d/mh.png'
view = args[3] if len(args) > 3 else 'tq'
cams = {'tq': ((-1.75, -2.6, 1.05), (0, 0, 0.84)), 'face': ((0, -3.6, 1.0), (0, 0, 0.86)), 'profil': ((-3.6, 0, 1.0), (0, 0, 0.86))}
loc, tgt = cams[view]
bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; cam.data.lens = 55
cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.use_denoising = False; scene.cycles.samples = samples
scene.render.resolution_x = width; scene.render.resolution_y = int(width * 1.45); scene.render.filepath = out
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/tmp/b3d/mannequin_mh.blend')
print('RENDU TERMINE', out)
