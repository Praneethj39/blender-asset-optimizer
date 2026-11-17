"""Render README images: original vs optimized asset, and the LOD chain.

Back-face culling is on, so faces with flipped normals show up as holes in
the original - the same way they would vanish in a game engine.

    python tools/render_previews.py --src samples/car_00.fbx --opt build/car_00.fbx --out docs
"""
import argparse
import os

import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

W, H = 900, 600


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "BLENDER_WORKBENCH"
    s.render.resolution_x, s.render.resolution_y = W, H
    s.render.film_transparent = False
    sh = s.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.75, 0.78, 0.82)
    sh.show_backface_culling = True
    sh.show_cavity = True
    s.world = bpy.data.worlds.new("w")
    s.world.color = (1, 1, 1)


def keep_only(pred):
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH" and not pred(o):
            bpy.data.objects.remove(o, do_unlink=True)


def add_wire(thickness):
    mat = bpy.data.materials.new("wire")
    mat.diffuse_color = (0.08, 0.12, 0.2, 1)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        w = o.copy()
        w.data = o.data
        bpy.context.scene.collection.objects.link(w)
        m = w.modifiers.new("wire", "WIREFRAME")
        m.thickness = thickness
        m.use_replace = True
        w.data.materials.clear() if False else None
        w.color = (0.08, 0.12, 0.2, 1)
        w.active_material = mat
    bpy.context.scene.display.shading.color_type = "OBJECT"
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and not o.modifiers:
            o.color = (0.75, 0.78, 0.82, 1)


_CAM = {}


def camera_on_scene(fit=False):
    """Frame the scene once (fit=True) and reuse that exact camera for every
    shot, so before/after and LOD images are directly comparable."""
    if fit or not _CAM:
        pts = [o.matrix_world @ Vector(c) for o in bpy.context.scene.objects if o.type == "MESH"
               for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        c, r = (lo + hi) / 2, (hi - lo).length
        loc = c + Vector((1.0, -1.25, 0.75)).normalized() * r * 1.9
        _CAM.update(loc=loc, rot=(c - loc).to_track_quat("-Z", "Y").to_euler())
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location, cam.rotation_euler = _CAM["loc"], _CAM["rot"]
    bpy.context.scene.camera = cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def tris():
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and not o.modifiers:
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n


def label(img, text, sub=""):
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        g = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        f = g = ImageFont.load_default()
    d.text((24, 18), text, fill=(20, 30, 50), font=f)
    if sub:
        d.text((24, 58), sub, fill=(70, 80, 100), font=g)
    return img


def side_by_side(paths, labels, out):
    ims = [label(Image.open(p).convert("RGB"), *l) for p, l in zip(paths, labels)]
    canvas = Image.new("RGB", (sum(i.width for i in ims) + 10 * (len(ims) - 1), H), "white")
    x = 0
    for i in ims:
        canvas.paste(i, (x, 0))
        x += i.width + 10
    canvas.save(out)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="samples/car_00.fbx")
    ap.add_argument("--opt", default="build/car_00.fbx")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp = "/tmp/_render"
    os.makedirs(tmp, exist_ok=True)

    # frame the camera on the clean asset (loose junk in the original would skew it)
    reset()
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(a.opt))
    keep_only(lambda o: o.name.endswith("_LOD0"))
    camera_on_scene(fit=True)

    # 1) before / after
    reset()
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(a.src))
    t_before = tris()
    add_wire(0.004)
    camera_on_scene()
    render(f"{tmp}/before.png")

    reset()
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(a.opt))
    keep_only(lambda o: o.name.endswith("_LOD0"))
    t_after = tris()
    add_wire(0.004)
    camera_on_scene()
    render(f"{tmp}/after.png")
    side_by_side([f"{tmp}/before.png", f"{tmp}/after.png"],
                 [("Original export", f"{t_before:,} triangles - holes = flipped faces"),
                  ("Optimized (LOD0)", f"{t_after:,} triangles - clean, named, centred pivots")],
                 f"{a.out}/before_after.png")

    # 2) LOD chain
    paths, labels = [], []
    for k in range(3):
        reset()
        bpy.ops.import_scene.fbx(filepath=os.path.abspath(a.opt))
        keep_only(lambda o, k=k: o.name.endswith(f"_LOD{k}"))
        n = tris()
        add_wire(0.004)
        camera_on_scene()
        render(f"{tmp}/lod{k}.png")
        paths.append(f"{tmp}/lod{k}.png")
        labels.append((f"LOD{k}", f"{n:,} triangles"))
    side_by_side(paths, labels, f"{a.out}/lods.png")


if __name__ == "__main__":
    main()
