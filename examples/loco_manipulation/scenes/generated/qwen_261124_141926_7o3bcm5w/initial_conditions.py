from pathlib import Path

from examples.loco_manipulation.scene_generation.convert import registered_spec

SPEC = registered_spec(Path(__file__).with_name("scene_spec.json"))

from examples.loco_manipulation.scene_generation.convert import initial_state


def default(scene):
    return initial_state(SPEC)


INITIAL_CONDITIONS = {"default": default}
