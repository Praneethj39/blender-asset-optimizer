"""Level-of-detail generation with Blender's Decimate (collapse) modifier.

Output objects are named <name>_LOD0, <name>_LOD1 ... and parented to an
empty called <name>. Unity's model importer turns that naming pattern into
a LODGroup automatically; Unreal can import the same file with
'Import Mesh LODs' enabled."""
import bpy


def _tri_count(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def decimated_copy(obj, ratio, name):
    if ratio >= 0.999:
        me = obj.data.copy()
    else:
        mod = obj.modifiers.new("lod_decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        obj.modifiers.remove(mod)
    me.name = name
    new = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(new)
    return new


def build_lods(obj, ratios, tri_budget):
    """Replace obj with a parent empty + LOD children. Returns list of (name, tris)."""
    base = obj.name
    tris0 = _tri_count(obj.data)
    # LOD0 itself is capped to the triangle budget
    scale = min(1.0, tri_budget / max(tris0, 1))
    parent = bpy.data.objects.new(base + "_grp", None)
    bpy.context.scene.collection.objects.link(parent)
    parent.location = obj.location
    out = []
    for i, r in enumerate(ratios):
        lod = decimated_copy(obj, r * scale, f"{base}_LOD{i}")
        lod.parent = parent
        lod.location = (0, 0, 0)
        out.append((lod.name, _tri_count(lod.data)))
    old_mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    parent.name = base
    return out
