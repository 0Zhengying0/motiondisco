from pathlib import Path

from examples.loco_manipulation.scene_generation.convert import registered_spec

SPEC = registered_spec(Path(__file__).with_name("scene_spec.json"))

from functools import partial

from examples.loco_manipulation.scene_generation.convert import TASK_HANDLERS

discrete, terminal, complete = (partial(handler, SPEC) for handler in TASK_HANDLERS[SPEC.task.type])


def score(scene, resolved_state):
    return terminal(scene, resolved_state).score


DISCRETE_GOALS = {"task": discrete}
TERMINAL_GOALS = {"task": terminal}
OUTCOME_SCORERS = {"task": score}
TASK_COMPLETION = complete
