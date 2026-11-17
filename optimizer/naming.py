"""Rename parts to an engine-friendly convention:  SM_<Asset>_<Part>[_<Side>]_NN

The part label comes from an optional classifier (see mesh-part-classifier);
without one, parts are just called 'Part'. The side tag comes from where the
part sits relative to the asset's centre (X = front/back, Y = left/right)."""
from collections import Counter


def side_tag(loc, center, tol=0.15):
    fx = "F" if loc.x > center.x + tol else "R" if loc.x < center.x - tol else ""
    sy = "L" if loc.y > center.y + tol else "Ri" if loc.y < center.y - tol else ""
    if fx and sy:
        return fx + ("L" if sy == "L" else "R")  # FL / FR / RL / RR
    return {"L": "L", "Ri": "R"}.get(sy, fx)


def rename_parts(objs, asset, labels, center):
    counts = Counter()
    mapping = {}
    for obj in objs:
        part = labels.get(obj.name, "Part").capitalize()
        side = side_tag(obj.location, center)
        key = (part, side)
        counts[key] += 1
        new = "_".join(x for x in ("SM", asset, part, side, f"{counts[key]:02d}") if x)
        mapping[obj.name] = new
        obj.name = new
        obj.data.name = new
    return mapping
