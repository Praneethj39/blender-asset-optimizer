"""Generate deliberately 'dirty' car-like test assets.

Real CAD/scan exports usually arrive with the same problems we inject here:
split (duplicate) vertices, flipped normals, loose geometry, unapplied
transforms, meaningless object names, empty helper objects and far too
many polygons for real-time use. The optimizer is tested against these.

Usage:
    python tools/make_test_assets.py --out samples --count 3 --seed 7
"""
import argparse
import math
import os
import random

import bpy  # must be imported before bmesh/mathutils
import bmesh
from mathutils import Matrix


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def new_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def make_body(rng):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= rng.uniform(3.8, 4.6)
        v.co.y *= rng.uniform(1.6, 1.9)
        v.co.z *= rng.uniform(0.9, 1.2)
        v.co.z += 0.7
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=rng.randint(22, 30), use_grid_fill=True)
    return bm


def make_wheel(rng, radius):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=rng.choice([192, 256]),
        radius1=radius, radius2=radius, depth=rng.uniform(0.22, 0.3),
    )
    # stand the cylinder up so its axis points along Y like a real wheel
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3)
    return bm


def make_glass(rng):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=rng.randint(60, 90), y_segments=rng.randint(30, 50),
                          size=rng.uniform(0.6, 0.8))
    return bm


def make_mirror(rng):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=0.12)
    for v in bm.verts:
        v.co.x *= 0.6
        v.co.y *= 1.3
    return bm


def dirty(obj, rng):
    """Inject the defects a cleanup pipeline must fix."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # 1) split every edge -> duplicate vertices everywhere (typical of CAD/STEP exports)
    bmesh.ops.split_edges(bm, edges=bm.edges[:])
    # 2) flip a random subset of faces
    flip = [f for f in bm.faces if rng.random() < 0.15]
    bmesh.ops.reverse_faces(bm, faces=flip)
    # 3) loose vertices and loose edges
    for _ in range(rng.randint(5, 20)):
        a = bm.verts.new((rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(0, 2)))
        if rng.random() < 0.5:
            b = bm.verts.new((a.co.x + 0.01, a.co.y, a.co.z))
            bm.edges.new((a, b))
    bm.to_mesh(obj.data)
    bm.free()
    # 4) unapplied transforms
    obj.scale = (rng.uniform(0.9, 1.1),) * 3
    obj.rotation_euler.z += rng.uniform(-0.05, 0.05)


def build_car(rng, idx):
    reset_scene()
    junk = iter(f"Mesh.{i:03d}" for i in range(rng.randint(1, 50), 999))
    body = new_object(next(junk), make_body(rng))
    r = rng.uniform(0.32, 0.4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w = new_object(next(junk), make_wheel(rng, r))
            w.location = (sx * 1.4, sy * 0.95, r)
    g = new_object(next(junk), make_glass(rng))
    g.location = (0.6, 0, 1.6)
    g.rotation_euler = (0, math.radians(-35), 0)
    for sy in (-1, 1):
        m = new_object(next(junk), make_mirror(rng))
        m.location = (0.9, sy * 1.0, 1.25)
    # helper empties that CAD exports love to include
    for i in range(3):
        e = bpy.data.objects.new(f"Empty.{i:03d}", None)
        bpy.context.scene.collection.objects.link(e)
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH":
            dirty(o, rng)
    return f"car_{idx:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="samples")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    for i in range(a.count):
        name = build_car(rng, i)
        path = os.path.join(a.out, name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=os.path.abspath(path), use_selection=False)
        print("wrote", path)


if __name__ == "__main__":
    main()
