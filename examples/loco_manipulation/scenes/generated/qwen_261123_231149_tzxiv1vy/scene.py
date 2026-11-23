from pathlib import Path

from examples.loco_manipulation.scene_generation.convert import registered_spec

SPEC = registered_spec(Path(__file__).with_name("scene_spec.json"))

from examples.loco_manipulation.scene_generation.catalogs import read_json
from examples.loco_manipulation.scene_generation.convert import make_scene as build_scene

PRESERVE_SCENE_PHYSICS = True


def make_scene():
    return build_scene(SPEC, read_json(Path(__file__).with_name("asset_catalog.json")))
