# blender-asset-optimizer

Headless Blender (Python `bpy`) tool that batch-converts messy CAD/scan-style
3D exports into clean, LOD'd, engine-ready files for Unity and Unreal, with a
report for every asset.

```
dirty .fbx/.obj/.glb  ->  cleanup  ->  part classification + naming  ->  LODs  ->  validate  ->  .fbx + .glb + report
```

## What it fixes

| Step | Why it matters in Unity/Unreal |
|---|---|
| Remove helper empties | CAD exports carry hundreds of empty nodes that bloat the hierarchy |
| Apply rotation/scale | Engine sees scale (1,1,1); physics and lighting behave |
| Delete loose verts/edges, merge duplicate verts | Split vertices break smooth shading and inflate vertex count |
| Recalculate normals outward | Flipped faces render invisible with back-face culling |
| Lossless planar dissolve | CAD tessellators split flat panels into thousands of triangles |
| Pivot to part centre | Wheels, doors etc. can rotate around their own centre in an XR scene |
| Box-projected UVs if missing | Materials and lightmaps need UVs |
| Part labelling + naming (`SM_<Asset>_<Part>_<Side>_NN`) | Uses [mesh-part-classifier](../mesh-part-classifier) (optional) |
| LOD0/1/2 with Decimate (collapse), LOD0 capped to a triangle budget | Unity auto-builds a LODGroup from `_LOD0.._LODn` names |
| FBX (Y-up, metres) + GLB export, JSON/CSV report | One run feeds both engines |

## Results (on generated test assets)

13 synthetic car assets (body, 4 wheels, windscreen, 2 mirrors each), generated
with deliberate defects by `tools/make_test_assets.py`:

* car_00 alone: 63,980 duplicate vertices merged, 2,817 flipped faces fixed, 134 loose vertices and 3 empties removed
* 10-car batch: **528,924 → 214,564 triangles at LOD0 (59.4% fewer)**, LOD1/LOD2 at 50% / 20% of LOD0, about **1 s per asset** on CPU
* With the classifier: **104/104 parts labelled correctly** (e.g. `SM_Car00_Wheel_FL_01`)
* Re-imported output has 0 non-manifold edges, scale (1,1,1), UVs on every part (checked in `tests/`)

These are synthetic assets, not real customer CAD. Real data will need tuning of `--merge-dist`, `--planar-angle` and `--tri-budget`.

## Usage

```bash
pip install bpy==5.3.0 numpy scikit-learn joblib   # bpy = Blender as a Python module (Python 3.13)
python tools/make_test_assets.py --out samples --count 3
python -m optimizer.run --in samples --out build --formats fbx,glb \
       --lods 1.0,0.5,0.2 --tri-budget 8000 \
       --classifier ../mesh-part-classifier/models/part_clf.joblib
python -m pytest -q
```

## Unity

* `unity/Editor/AutoLODImporter.cs`: any model dropped in an `Optimized/` folder is imported with metre scale, lightmap UVs, mesh compression and tuned LOD switch heights.
* `unity/Runtime/WheelSpinner.cs`: spins every `_Wheel_` part around its own pivot. This works without manual setup because the optimizer centred the pivots and the classifier named the wheels.

## Layout

```
optimizer/  cleanup.py  lod.py  naming.py  stats.py  run.py
tools/      make_test_assets.py
unity/      Editor/AutoLODImporter.cs  Runtime/WheelSpinner.cs
tests/      test_pipeline.py
```

## Next steps

* UV unwrapping with seams (xatlas) instead of box projection
* Quad-dominant remeshing for organic scan data
* Texture baking from high-poly to LOD meshes
