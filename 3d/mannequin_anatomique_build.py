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
bpy.ops.wm.obj_import(filepath='/tmp/b3d/base.obj', forward_axis='NEGATIVE_Z', up_axis='Y', global_scale=0.1, use_split_groups=True)
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

skinM = mat('Peau', '#D8B193', 0.5, 0.15); shirtM = mat('Haut', '#0E8B85', 0.65); shortM = mat('Short', '#33454D', 0.7); eyeM = mat('Oeil', '#EDEDED', 0.2)
bpy.context.view_layer.objects.active = body; body.select_set(True)
body.data.materials.clear()
for m in (skinM, shirtM, shortM): body.data.materials.append(m)
# coupes nettes : plans horizontaux (taille, cuisse, buste), puis matières par région
zoff = body.location.z
bm = bmesh.new(); bm.from_mesh(body.data)
for z in (1.00, 0.60, 1.38):
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z - zoff), plane_no=(0, 0, 1))
S = [Vector((0.19, 0, 1.36 - zoff)), Vector((-0.19, 0, 1.36 - zoff))]
for f in bm.faces:
    c = f.calc_center_median(); ax, z = abs(c.x), c.z + zoff
    if 0.60 - 1e-4 <= z <= 1.00 + 1e-4 and ax < 0.27 and True: f.material_index = 2
    elif 1.00 <= z <= 1.38 and ax < 0.215: f.material_index = 1
    elif z > 1.20 and min((c - p).length for p in S) < 0.115: f.material_index = 1
    else: f.material_index = 0
bm.to_mesh(body.data); bm.free()
bpy.ops.object.shade_smooth()
sub = body.modifiers.new('Sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
for e in eyes:
    e.data.materials.clear(); e.data.materials.append(eyeM)
    bpy.context.view_layer.objects.active = e; bpy.ops.object.shade_smooth()

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
