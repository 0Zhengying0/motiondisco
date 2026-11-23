"""Install validated SceneSpecs as standard FARO registry presets."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from .catalogs import load_assets, write_json
from .spec import ASSETS
from .validate import validate

_LOADER = """from pathlib import Path

from examples.loco_manipulation.scene_generation.convert import registered_spec

SPEC = registered_spec(Path(__file__).with_name("scene_spec.json"))
"""

_MODULES = {
    "scene.py": _LOADER + """
from examples.loco_manipulation.scene_generation.catalogs import read_json
from examples.loco_manipulation.scene_generation.convert import make_scene as build_scene

PRESERVE_SCENE_PHYSICS = True


def make_scene():
    return build_scene(SPEC, read_json(Path(__file__).with_name("asset_catalog.json")))
""",
    "initial_conditions.py": _LOADER + """
from examples.loco_manipulation.scene_generation.convert import initial_state


def default(scene):
    return initial_state(SPEC)


INITIAL_CONDITIONS = {"default": default}
""",
    "goals.py": _LOADER + """
from functools import partial

from examples.loco_manipulation.scene_generation.convert import TASK_HANDLERS

discrete, terminal, complete = (partial(handler, SPEC) for handler in TASK_HANDLERS[SPEC.task.type])


def score(scene, resolved_state):
    return terminal(scene, resolved_state).score


DISCRETE_GOALS = {"task": discrete}
TERMINAL_GOALS = {"task": terminal}
OUTCOME_SCORERS = {"task": score}
TASK_COMPLETION = complete
""",
}


def register_spec(raw, dest_root, *, dry_run=False):
    spec, report = validate(raw)
    if not report["pass"]:
        return None, report
    root = Path(dest_root)
    destination = root / spec.scene_id
    if destination.exists():
        report["pass"] = False
        report["errors"].append({
            "code": "SCENE_ID_EXISTS", "subject": spec.scene_id,
            "message": "Use a new scene_id for this registry", "details": {},
        })
        return None, report
    name = f"generated.{spec.scene_id}"
    if dry_run:
        return name, report
    x, y = spec.task.parameters.target_xy
    description = (f"Walk the G1 on the floor to world XY ({x:g}, {y:g}) metres and finish "
                   "with both soles on the floor. Keep the objects on their initial supports.")
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".register-", dir=root) as temporary:
        staging = Path(temporary) / spec.scene_id
        staging.mkdir()
        for filename, source in _MODULES.items():
            (staging / filename).write_text(source, encoding="utf-8")
        write_json(staging / "scene_spec.json", spec.model_dump(mode="json"))
        write_json(staging / "asset_catalog.json", load_assets())
        write_json(staging / "spec.json", {
            "id": spec.scene_id,
            "family": "qwen_scene_spec",
            "description": description,
            "boxes": [obj.instance_id for obj in spec.objects if ASSETS[obj.asset_id]["movable"]],
        })
        # A complete registry directory is published in one rename. An
        # existing, non-empty registry cannot be replaced by another run.
        try:
            os.rename(staging, destination)
        except OSError:
            if not destination.exists():
                raise
            report["pass"] = False
            report["errors"].append({
                "code": "SCENE_ID_EXISTS", "subject": spec.scene_id,
                "message": "Use a new scene_id for this registry", "details": {},
            })
            return None, report
    return name, report
