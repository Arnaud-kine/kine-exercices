import bpy, math
from mathutils import Vector, Matrix

def aim(arm, name, new_dir):
    """Oriente l'os 'name' le long de new_dir (repère monde), sans changer la position de sa tête."""
    pb = arm.pose.bones[name]; bpy.context.view_layer.update()
    M = pb.matrix.copy()                      # repère de l'armature
    cur = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    R = cur.rotation_difference(Vector(new_dir).normalized()).to_matrix()
    N = R @ M.to_3x3()
    pb.matrix = Matrix.Translation(M.translation) @ N.to_4x4()
    bpy.context.view_layer.update()

def head_pos(arm, name):
    bpy.context.view_layer.update(); return arm.matrix_world @ arm.pose.bones[name].head
def tail_pos(arm, name):
    bpy.context.view_layer.update(); return arm.matrix_world @ arm.pose.bones[name].tail

def ik2(root, target, L1, L2, pole):
    d = (target - root); dist = max(abs(L1 - L2) + 1e-3, min(L1 + L2 - 1e-3, d.length)); dirn = d.normalized()
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist); h = math.sqrt(max(0.0, L1 * L1 - a * a))
    perp = (Vector(pole) - dirn * Vector(pole).dot(dirn))
    perp = perp.normalized() if perp.length > 1e-6 else Vector((0, 0, 1))
    return root + dirn * a + perp * h
