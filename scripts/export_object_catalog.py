#!/usr/bin/env python3
"""Export reusable object definitions from the FARO MotionDisco scenes."""

import argparse
import hashlib
import json
from importlib import import_module
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[1]
FARO_ROOT = ROOT / "submodules" / "faro"
FARO_SRC = FARO_ROOT / "src"
SCENE_ROOT = FARO_SRC / "scenes" / "motiondisco"
DEFAULT_OUTPUT = ROOT / "results" / "motiondisco_object_catalog.json"


def faro_version():
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(FARO_ROOT), *args], text=True
        ).strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != FARO_ROOT.resolve():
        raise RuntimeError(f"Expected a FARO Git checkout at {FARO_ROOT}")
    return {
        "commit": git("rev-parse", "HEAD"),
        "source_tree_dirty": bool(
            git("status", "--porcelain", "--untracked-files=normal", "--", "src")
        ),
    }


def object_definition(cfg, faces, name):
    face_ids = {
        face: face_id for (owner, face), face_id in faces.by_name.items() if owner == name
    }
    return {
        "faro_type": type(cfg).__name__,
        "half_extents": list(cfg.half_extents),
        "full_size": [2 * length for length in cfg.half_extents],
        "mass": float(cfg.mass) if hasattr(cfg, "mass") else None,
        "color_rgba": list(cfg.color),
        "contact_types": sorted(set(cfg.contact_types)),
        "face_contact_types": {
            face: sorted(set(types)) for face, types in cfg.face_contact_types.items()
        },
        "surfaces": list(face_ids),
        "surface_allowed_contact_types": {
            face: sorted(set(faces.admitted[face_id])) for face, face_id in face_ids.items()
        },
    }


def build_catalog():
    scene_files = sorted(SCENE_ROOT.glob("*/scene.py"))
    if not scene_files:
        raise RuntimeError(f"No scene.py files found in {SCENE_ROOT}")
    version = faro_version()
    sys.path.insert(0, str(FARO_SRC))
    from faro.utils import contact_type

    objects = {}
    sources = []
    for path in scene_files:
        module = import_module(f"scenes.motiondisco.{path.parent.name}.scene")
        if Path(module.__file__).resolve() != path.resolve():
            raise RuntimeError(f"Expected {path}, loaded {module.__file__}")
        scene = module.make_scene()
        source_file = path.relative_to(ROOT).as_posix()
        sources.append({
            "scene": scene.name,
            "source_file": source_file,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "object_instance_count": len(scene.objects),
        })
        for name, cfg in scene.objects.items():
            definition = object_definition(cfg, scene.faces, name)
            signature = json.dumps(definition, sort_keys=True, allow_nan=False)
            if signature not in objects:
                digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
                objects[signature] = {
                    "id": f"{definition['faro_type'].lower()}-{digest[:16]}",
                    **definition,
                    "occurrences": [],
                }
            objects[signature]["occurrences"].append({
                "name": name,
                "scene": scene.name,
                "source_file": source_file,
            })

    for entry in objects.values():
        entry["names"] = sorted({occ["name"] for occ in entry["occurrences"]})

    labels = {
        contact_type.CONTACT_TYPE_UNILATERAL: "unilateral_sticking",
        contact_type.CONTACT_TYPE_SLIDING: "sliding",
        contact_type.CONTACT_TYPE_BILATERAL: "bilateral",
    }
    return {
        "schema_version": 1,
        "faro": version,
        "units": {"half_extents": "m", "full_size": "m", "mass": "kg"},
        "dimension_axes": {
            "Plane": ["x", "y"],
            "FixedBox": ["x", "y", "z"],
            "MovableBox": ["x", "y", "z"],
        },
        "plane_dimensions": "Bounded XY contact surface. Collision shape is an infinite half-space.",
        "contact_type_codes": {
            code: {"name": label, "solver_supported": code in contact_type.SUPPORTED_TYPES}
            for code, label in labels.items()
        },
        "contact_permissions": (
            "contact_types apply to every surface. face_contact_types add permissions "
            "to named surfaces. surface_allowed_contact_types is the effective union from FARO."
        ),
        "scene_count": len(sources),
        "object_instance_count": sum(source["object_instance_count"] for source in sources),
        "unique_object_count": len(objects),
        "scenes": sources,
        "objects": list(objects.values()),
    }


def write_catalog(output, catalog):
    output.parent.mkdir(parents=True, exist_ok=True)
    stream = NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, delete=False
    )
    temporary_path = Path(stream.name)
    try:
        with stream:
            json.dump(catalog, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    catalog = build_catalog()
    write_catalog(args.output, catalog)
    print(
        f"Exported {catalog['unique_object_count']} unique objects from "
        f"{catalog['object_instance_count']} instances in {catalog['scene_count']} scenes."
    )
    print(f"FARO commit: {catalog['faro']['commit']}")
    print(f"Catalog: {args.output.resolve()}")


if __name__ == "__main__":
    main()
