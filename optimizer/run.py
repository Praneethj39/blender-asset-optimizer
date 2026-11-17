"""Batch pipeline: import -> clean -> (classify + rename) -> LODs -> validate -> export.

    python -m optimizer.run --in samples --out build --formats fbx,glb \
        --lods 1.0,0.5,0.2 --tri-budget 20000 \
        --classifier ../mesh-part-classifier/models/part_clf.joblib
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import logging

import bpy
from mathutils import Vector

from . import cleanup, lod, naming, stats

IMPORTERS = {
    ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    ".obj": lambda p: bpy.ops.wm.obj_import(filepath=p),
    ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=p),
}


def export(path_base, formats):
    out = []
    for fmt in formats:
        p = f"{path_base}.{fmt}"
        if fmt == "fbx":
            # axis/scale settings that import into Unity at 1 unit = 1 m, Y-up
            bpy.ops.export_scene.fbx(filepath=p, apply_scale_options="FBX_SCALE_UNITS",
                                     axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True,
                                     mesh_smooth_type="FACE", add_leaf_bones=False)
        elif fmt == "glb":
            bpy.ops.export_scene.gltf(filepath=p, export_format="GLB")
        out.append(p)
    return out


def load_classifier(path):
    if not path:
        return None
    sys.path.insert(0, str(Path(path).resolve().parents[1]))
    from partclf.predict import load  # noqa: E402
    return load(path)  # .joblib = feature model, .pt = PointNet


def process(src, out_dir, args, clf):
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    IMPORTERS[src.suffix.lower()](str(src))
    scene = bpy.context.scene
    asset = src.stem.replace("_", "").capitalize()
    log = {"asset": src.name, "fixes": {}, "parts": []}
    fx = log["fixes"]

    fx["empties_removed"] = cleanup.remove_empties(scene)
    meshes = [o for o in scene.objects if o.type == "MESH"]
    before = {o.name: stats.mesh_stats(o) for o in meshes}
    for key in ("loose_verts_removed", "duplicate_verts_merged", "degenerate_faces_removed",
                "faces_flipped", "transforms_applied", "uvs_added",
                "tris_removed_planar"):
        fx[key] = 0
    for o in meshes:
        fx["transforms_applied"] += cleanup.apply_transforms(o)
        fx["loose_verts_removed"] += cleanup.delete_loose(o)
        fx["duplicate_verts_merged"] += cleanup.merge_by_distance(o, args.merge_dist)
        fx["degenerate_faces_removed"] += cleanup.dissolve_degenerate(o)
        fx["faces_flipped"] += cleanup.fix_normals(o)

    # classify on full-resolution cleaned geometry, before any reduction
    labels = clf.predict_objects(meshes) if clf else {}

    for o in meshes:
        if args.planar_angle > 0:
            fx["tris_removed_planar"] += cleanup.dissolve_planar(o, args.planar_angle)
        cleanup.center_pivot(o)
        fx["uvs_added"] += cleanup.ensure_uvs(o)
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    center = (lo + hi) / 2
    old_names = [o.name for o in meshes]
    mapping = naming.rename_parts(meshes, asset, labels, center)

    for old in old_names:
        o = scene.objects[mapping[old]]
        b = before[old]
        lods = lod.build_lods(o, args.lods, args.tri_budget)
        lod0 = scene.objects[lods[0][0]]
        a = stats.mesh_stats(lod0)
        log["parts"].append({
            "source_name": old, "name": mapping[old], "label": labels.get(old, "part"),
            "verts_before": b["verts"], "tris_before": b["tris"],
            "verts_after": a["verts"], "lod_tris": [t for _, t in lods],
            "issues": stats.check(a, args.tri_budget),
        })
    cleanup.purge_orphans()

    files = export(str(out_dir / src.stem), args.formats)
    log["outputs"] = [os.path.basename(f) for f in files]
    log["seconds"] = round(time.time() - t0, 2)
    return log


def main(argv=None):
    logging.getLogger().setLevel(logging.WARNING)  # silence glTF exporter chatter
    ap = argparse.ArgumentParser(description="Batch 3D asset optimizer (Blender, headless)")
    ap.add_argument("--in", dest="inp", required=True, help="folder of .fbx/.obj/.glb files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--formats", default="fbx,glb", type=lambda s: s.split(","))
    ap.add_argument("--lods", default="1.0,0.5,0.2", type=lambda s: [float(x) for x in s.split(",")])
    ap.add_argument("--tri-budget", type=int, default=8000,
                    help="max triangles per part at LOD0 (mobile-XR friendly)")
    ap.add_argument("--planar-angle", type=float, default=0.5,
                    help="degrees; merge coplanar faces losslessly (0 = off)")
    ap.add_argument("--merge-dist", type=float, default=1e-4)
    ap.add_argument("--classifier", help="trained part_clf.joblib or pointnet.pt (optional)")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    clf = load_classifier(args.classifier)
    srcs = sorted(p for p in Path(args.inp).iterdir() if p.suffix.lower() in IMPORTERS)
    logs = []
    for src in srcs:
        print(f"[optimizer] {src.name}")
        logs.append(process(src, out_dir, args, clf))

    (out_dir / "report.json").write_text(json.dumps(logs, indent=2))
    with open(out_dir / "report.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset", "part", "label", "tris_before", "tris_lod0", "tris_lod1",
                    "tris_lod2", "reduction_lod0_%", "issues"])
        for lg in logs:
            for p in lg["parts"]:
                t = p["lod_tris"] + [""] * (3 - len(p["lod_tris"]))
                red = round(100 * (1 - p["lod_tris"][0] / max(p["tris_before"], 1)), 1)
                w.writerow([lg["asset"], p["name"], p["label"], p["tris_before"], *t[:3], red,
                            "; ".join(p["issues"])])
    tb = sum(p["tris_before"] for lg in logs for p in lg["parts"])
    ta = sum(p["lod_tris"][0] for lg in logs for p in lg["parts"])
    print(f"[optimizer] {len(logs)} assets, triangles {tb} -> {ta} at LOD0 "
          f"({100 * (1 - ta / max(tb, 1)):.1f}% less), {sum(lg['seconds'] for lg in logs):.1f}s")


if __name__ == "__main__":
    main()
