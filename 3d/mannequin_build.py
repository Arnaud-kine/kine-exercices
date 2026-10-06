import bpy, bmesh, math, sys
from mathutils import Vector

def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1)
def mat(name, col, rough=0.55, sheen=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(col); b.inputs['Roughness'].default_value = rough
    return m

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- squelette (pose neutre, légèrement écartée), unités : mètres, le personnage regarde vers -Y ----------
J = {  # nom: (x, y, z, rayon_x, rayon_y)
 'pelvis': (0, 0, 0.98, 0.150, 0.105), 'spine1': (0, 0, 1.12, 0.135, 0.095), 'spine2': (0, 0, 1.27, 0.150, 0.098), 'chest': (0, 0, 1.40, 0.165, 0.105),
 'neck': (0, 0.005, 1.53, 0.050, 0.050), 'head_base': (0, 0.01, 1.58, 0.048, 0.048),
 'clav.L': (0.075, 0, 1.47, 0.050, 0.050), 'shoulder.L': (0.185, 0, 1.465, 0.058, 0.058), 'elbow.L': (0.365, 0, 1.22, 0.043, 0.043), 'wrist.L': (0.47, 0, 0.98, 0.032, 0.026), 'hand.L': (0.505, 0, 0.90, 0.034, 0.014),
 'hip.L': (0.092, 0, 0.93, 0.104, 0.104), 'knee.L': (0.105, 0, 0.51, 0.068, 0.066), 'ankle.L': (0.105, 0.0, 0.095, 0.046, 0.044), 'toe.L': (0.105, -0.15, 0.045, 0.040, 0.034),
}
names = list(J.keys())
for n in [n for n in names if n.endswith('.L')]:
    r = n[:-2] + '.R'; x, y, z, a, b = J[n]; J[r] = (-x, y, z, a, b)
names = list(J.keys()); idx = {n: i for i, n in enumerate(names)}
E = [('pelvis', 'spine1'), ('spine1', 'spine2'), ('spine2', 'chest'), ('chest', 'neck'), ('neck', 'head_base')]
for s in ('L', 'R'):
    E += [('chest', f'clav.{s}'), (f'clav.{s}', f'shoulder.{s}'), (f'shoulder.{s}', f'elbow.{s}'), (f'elbow.{s}', f'wrist.{s}'), (f'wrist.{s}', f'hand.{s}'),
          ('pelvis', f'hip.{s}'), (f'hip.{s}', f'knee.{s}'), (f'knee.{s}', f'ankle.{s}'), (f'ankle.{s}', f'toe.{s}')]
me = bpy.data.meshes.new('corps_maillage'); ob = bpy.data.objects.new('Mannequin_corps', me); scene.collection.objects.link(ob)
me.from_pydata([Vector(J[n][:3]) for n in names], [(idx[a], idx[b]) for a, b in E], [])
ob.modifiers.new('Skin', 'SKIN'); sk = me.skin_vertices[0].data
for n in names: sk[idx[n]].radius = (J[n][3], J[n][4])
sk[idx['pelvis']].use_root = True
ob.modifiers['Skin'].use_smooth_shade = True
sub = ob.modifiers.new('Sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 2
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.modifier_apply(modifier='Skin')
skin, shirt, shorts, shoe = mat('Peau', '#E0B396', 0.5), mat('Haut', '#0E8B85', 0.65), mat('Short', '#33454D', 0.7), mat('Chaussures', '#F4F4F2', 0.45)
for m in (skin, shirt, shorts, shoe): ob.data.materials.append(m)
for p in ob.data.polygons:
    c = p.center; ax, z = abs(c.x), c.z
    if z < 0.09: p.material_index = 3
    elif 0.52 < z < 1.075 and ax < 0.26: p.material_index = 2
    elif z > 1.515 and ax < 0.065: p.material_index = 0
    elif z >= 1.075 and ax < 0.22: p.material_index = 1
    elif 1.22 <= z <= 1.50 and 0.22 <= ax < 0.45: p.material_index = 1
    else: p.material_index = 0
bpy.ops.object.modifier_apply(modifier='Sub')
bpy.ops.object.shade_smooth()

# ---------- tête, cheveux, visage ----------
def sphere(name, loc, sc, m, seg=40):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=1, location=loc); o = bpy.context.active_object; o.name = name; o.scale = sc
    bpy.ops.object.transform_apply(scale=True); bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o
head = sphere('Tete', (0, 0.012, 1.685), (0.088, 0.100, 0.118), skin)
nose = sphere('Nez', (0, -0.092, 1.665), (0.014, 0.022, 0.026), skin, 16)
earL = sphere('OreilleG', (0.087, 0.018, 1.672), (0.010, 0.020, 0.032), skin, 16); earR = sphere('OreilleD', (-0.087, 0.018, 1.672), (0.010, 0.020, 0.032), skin, 16)
eyeM = mat('Oeil', '#1b1b1b', 0.3)
eyes = [sphere('OeilG', (0.034, -0.083, 1.700), (0.009, 0.007, 0.010), eyeM, 12), sphere('OeilD', (-0.034, -0.083, 1.700), (0.009, 0.007, 0.010), eyeM, 12)]
browM = mat('Sourcil', '#3A2A22', 0.8)
hairM = mat('Cheveux', '#3A2A22', 0.75)
hair = sphere('Cheveux', (0, 0.020, 1.700), (0.094, 0.106, 0.118), hairM, 48)
bm = bmesh.new(); bm.from_mesh(hair.data)
kill = [f for f in bm.faces if (f.calc_center_median().y < -0.045 + 0.0 and f.calc_center_median().z < 1.80) or f.calc_center_median().z < 1.66]
bmesh.ops.delete(bm, geom=kill, context='FACES'); bm.to_mesh(hair.data); bm.free()
neckO = None

# ---------- éclairage, caméra, sol ----------
floor_m = mat('Sol', '#C9CFD2', 0.95)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.active_object; fl.data.materials.append(floor_m)
w = bpy.data.worlds.new('Monde'); scene.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.80, 0.84, 0.87, 1); bg.inputs[1].default_value = 0.55
def area(name, loc, energy, size, target=(0, 0, 1.0)):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.active_object; l.name = name; l.data.energy = energy; l.data.size = size
    d = Vector(target) - Vector(loc); l.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return l
area('Cle', (-2.0, -2.4, 3.0), 210, 2.6); area('Remplissage', (2.6, -1.8, 1.6), 85, 3.0); area('Contre', (0.8, 2.8, 2.6), 120, 2.0)
bpy.ops.object.camera_add(location=(-1.75, -2.6, 1.12)); cam = bpy.context.active_object; cam.data.lens = 55
cam.rotation_euler = (Vector((0, 0, 0.86)) - cam.location).to_track_quat('-Z', 'Y').to_euler(); scene.camera = cam
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.use_denoising = False
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
samples = int(args[0]) if args else 24; width = int(args[1]) if len(args) > 1 else 360; out = args[2] if len(args) > 2 else '/tmp/b3d/test.png'
scene.cycles.samples = samples; scene.render.resolution_x = width; scene.render.resolution_y = int(width * 1.45); scene.render.filepath = out
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/tmp/b3d/mannequin.blend')
print('RENDU TERMINE', out)
