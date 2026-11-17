"""Mesh statistics and engine-readiness checks."""
import bpy  # noqa: F401
import bmesh


def mesh_stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    s = dict(verts=len(bm.verts), tris=tris, non_manifold_edges=non_manifold,
             loose_verts=loose, ngons=ngons, has_uvs=bool(obj.data.uv_layers),
             scale_applied=tuple(round(x, 4) for x in obj.scale) == (1.0, 1.0, 1.0))
    bm.free()
    return s


def check(stats, tri_budget):
    """Return a list of problems that would need manual fixing in Unity/Unreal."""
    issues = []
    if stats["tris"] > tri_budget:
        issues.append(f"over triangle budget ({stats['tris']} > {tri_budget})")
    if stats["loose_verts"]:
        issues.append("loose vertices")
    if not stats["has_uvs"]:
        issues.append("no UVs")
    if not stats["scale_applied"]:
        issues.append("unapplied scale")
    return issues
