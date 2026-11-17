"""Geometry cleanup steps. Everything works on bmesh so it runs headless
(no viewport / edit-mode context needed) and each step reports what it fixed."""
import bpy  # noqa: F401  (loads bmesh / mathutils)
import bmesh
from mathutils import Matrix, Vector


def _load(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return bm


def _save(obj, bm):
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def remove_empties(scene):
    """Delete helper empties that have no children (CAD export leftovers)."""
    gone = [o for o in scene.objects if o.type == "EMPTY" and not o.children]
    for o in gone:
        bpy.data.objects.remove(o, do_unlink=True)
    return len(gone)


def apply_transforms(obj):
    """Bake rotation+scale into vertex data so the engine sees scale (1,1,1)."""
    loc = obj.matrix_world.to_translation()
    m = obj.matrix_world.copy()
    m.translation = Vector((0, 0, 0))
    changed = not (m == Matrix.Identity(4))
    obj.data.transform(m)
    obj.matrix_world = Matrix.Translation(loc)
    return changed


def delete_loose(obj):
    bm = _load(obj)
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    n = len(loose_v)
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    _save(obj, bm)
    return n


def merge_by_distance(obj, dist=1e-4):
    bm = _load(obj)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    removed = before - len(bm.verts)
    _save(obj, bm)
    return removed


def dissolve_degenerate(obj, dist=1e-6):
    bm = _load(obj)
    before = len(bm.faces)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=dist)
    removed = before - len(bm.faces)
    _save(obj, bm)
    return removed


def dissolve_planar(obj, angle_deg=0.5):
    """Lossless reduction: merge coplanar faces (CAD tessellators split flat
    panels into thousands of triangles), then re-triangulate for the engine."""
    import math
    bm = _load(obj)
    before = sum(len(f.verts) - 2 for f in bm.faces)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle_deg), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    after = len(bm.faces)
    _save(obj, bm)
    return before - after


def fix_normals(obj):
    """Make face winding consistent and pointing outward; return faces flipped."""
    bm = _load(obj)
    bm.faces.ensure_lookup_table()
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    flipped = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0)
    _save(obj, bm)
    return flipped


def center_pivot(obj):
    """Move the origin to the bounding-box centre.

    Matters in XR: a wheel whose pivot sits at the world origin cannot be
    spun in an engine without extra setup."""
    me = obj.data
    if not me.vertices:
        return
    xs, ys, zs = zip(*(v.co for v in me.vertices))
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    me.transform(Matrix.Translation(-c))
    obj.location = obj.location + c


def ensure_uvs(obj):
    """Add simple box-projected UVs when the mesh has none."""
    if obj.data.uv_layers:
        return False
    bm = _load(obj)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co[a], co[b])
    _save(obj, bm)
    return True


def triangulate(obj):
    bm = _load(obj)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    _save(obj, bm)


def purge_orphans():
    for coll in (bpy.data.meshes, bpy.data.materials):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)
