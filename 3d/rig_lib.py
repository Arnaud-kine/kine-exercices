import bpy, bmesh, json, math, sys, os
from mathutils import Vector, Matrix, Quaternion

SK = '/tmp/b3d/mhrepo/makehuman/data/rigs/default.mhskel'
WT = '/tmp/b3d/mhrepo/makehuman/data/rigs/default_weights.mhw'
NBODY = 13380

def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1)
def mat(name, col, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(col); b.inputs['Roughness'].default_value = rough
    return m

def parse_obj(path):
    V, groups, cur = [], {}, None
    for l in open(path):
        if l.startswith('v '): V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith('g '): cur = l.split()[1]; groups.setdefault(cur, [])
        elif l.startswith('f ') and cur in ('body', 'helper-l-eye', 'helper-r-eye'):
            groups[cur].append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    return V, groups

def to_world(p, ymin):  # coordonnées MakeHuman (x, y haut, z devant) -> Blender (x, -z, y), en mètres, pieds au sol
    return Vector((p[0] * 0.1, -p[2] * 0.1, (p[1] - ymin) * 0.1))

def build_character(obj_path):
    V, G = parse_obj(obj_path)
    ymin = min(v[1] for v in V[:NBODY])
    W = [to_world(v, ymin) for v in V]
    faces = G['body']; mx = max(max(f) for f in faces); assert mx < NBODY, mx
    me = bpy.data.meshes.new('corps'); body = bpy.data.objects.new('Corps', me); bpy.context.scene.collection.objects.link(body)
    me.from_pydata([tuple(w) for w in W[:NBODY]], [], faces); me.update()
    for p in me.polygons: p.use_smooth = True
    ra = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT'); ra.data.foreach_set('vector', [c for w in W[:NBODY] for c in w])
    # yeux
    eyes = []
    for gname in ('helper-l-eye', 'helper-r-eye'):
        fs = G[gname]; used = sorted({i for f in fs for i in f}); remap = {o: n for n, o in enumerate(used)}
        em = bpy.data.meshes.new(gname); eo = bpy.data.objects.new(gname, em); bpy.context.scene.collection.objects.link(eo)
        em.from_pydata([tuple(W[i]) for i in used], [], [[remap[i] for i in f] for f in fs]); em.update()
        for p in em.polygons: p.use_smooth = True
        eyes.append(eo)
    return body, eyes, V, W

def build_armature(body, W):
    sk = json.load(open(SK)); wt = json.load(open(WT))['weights']
    jpos = {}
    for name, idx in sk['joints'].items(): jpos[name] = sum((W[i] for i in idx), Vector()) / len(idx)
    arm_d = bpy.data.armatures.new('Squelette'); arm = bpy.data.objects.new('Squelette', arm_d); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for name, b in sk['bones'].items():
        e = arm_d.edit_bones.new(name); h, t = jpos[b['head']], jpos[b['tail']]
        if (t - h).length < 1e-4: t = h + Vector((0, 0, 0.01))
        e.head, e.tail = h, t; eb[name] = e
    for name, b in sk['bones'].items():
        if b['parent']: eb[name].parent = eb[b['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone, lst in wt.items():
        vg = body.vertex_groups.new(name=bone)
        for i, w in lst:
            if i < NBODY: vg.add([i], w, 'REPLACE')
    md = body.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    body.parent = arm
    return arm, sk, jpos
