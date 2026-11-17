"""End-to-end check: generate one dirty asset, optimise it, re-import the FBX
and assert it is engine-ready.   Run:  python -m pytest -q"""
import json
import subprocess
import sys
from pathlib import Path

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    subprocess.run([sys.executable, "tools/make_test_assets.py", "--out", str(src), "--count", "1"],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "optimizer.run", "--in", str(src), "--out", str(out),
                    "--formats", "fbx"], cwd=ROOT, check=True, capture_output=True)

    report = json.loads((out / "report.json").read_text())[0]
    assert report["fixes"]["empties_removed"] == 3
    assert report["fixes"]["duplicate_verts_merged"] > 0

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(out / "car_00.fbx"))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert meshes and all("_LOD" in o.name for o in meshes)
    for o in meshes:
        assert tuple(round(s, 4) for s in o.scale) == (1.0, 1.0, 1.0)
        assert o.data.uv_layers
        bm = bmesh.new()
        bm.from_mesh(o.data)
        assert not any(not v.link_faces for v in bm.verts), f"loose verts in {o.name}"
        bm.free()
    # every LOD chain gets lighter
    for p in report["parts"]:
        assert p["lod_tris"] == sorted(p["lod_tris"], reverse=True)
