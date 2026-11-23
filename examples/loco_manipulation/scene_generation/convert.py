"""Construct the FARO scene, initial state and task goals from SceneSpec."""

from functools import lru_cache
from math import dist

import numpy as np

from faro.configs.objects import FixedBox, MovableBox, Plane
from faro.configs.robot import make_g1_robot
from faro.configs.scene import OnFace, Pose, Scene, Standing, StateSpec
from faro.search.goal import DiscreteGoal, GoalTolerances, PositionTarget, TerminalGoal
from faro.utils.contact_type import CONTACT_TYPE_UNILATERAL

from .catalogs import load_assets, load_tasks
from .spec import ASSETS, parse_spec

ROBOT = "robot"
FLOOR = "floor"
FLOOR_FACE = (FLOOR, "surface")
TASKS = load_tasks()["tasks"]


def physics_kwargs(entry):
    return {
        "color": entry["color_rgba"],
        "contact_types": entry["contact_types"],
        "face_contact_types": entry["face_contact_types"],
    }


def standing_xy_yaw(xy_yaw):
    return Standing(on=FLOOR_FACE, xy_yaw=xy_yaw)


def make_scene(spec, asset_catalog=None):
    catalog = load_assets() if asset_catalog is None else asset_catalog
    objects = {FLOOR: Plane(half_extents=spec.floor.half_extents, **physics_kwargs(catalog["floor_defaults"]))}
    for obj in spec.objects:
        asset = catalog["assets"][obj.asset_id]
        common = {"half_extents": asset["half_extents"], **physics_kwargs(asset)}
        cls = {"FixedBox": FixedBox, "MovableBox": MovableBox}[asset["faro_type"]]
        objects[obj.instance_id] = cls(**common, **({"mass": asset["mass"]} if cls is MovableBox else {}))
    return Scene(name=f"generated.{spec.scene_id}", robots={ROBOT: make_g1_robot()}, objects=objects)


def initial_state(spec):
    return StateSpec(
        robots={ROBOT: standing_xy_yaw(spec.robot.initial_xy_yaw)},
        objects={FLOOR: Pose(), **{
            obj.instance_id: OnFace(on=(obj.support_object, obj.support_surface), xy_yaw=obj.relative_xy_yaw)
            for obj in spec.objects
        }},
    )


def reach_xyz(spec, state):
    return np.array([*spec.task.parameters.target_xy, state.robots[ROBOT].q[2]])


def reach_discrete(spec, scene):
    floor_id = scene.face_id(*FLOOR_FACE)
    return DiscreteGoal({
        ("ee", ROBOT, patch): (floor_id, CONTACT_TYPE_UNILATERAL)
        for patch in scene.robots[ROBOT].standing_contacts
    })


def reach_terminal(spec, scene, state):
    goal = TASKS[spec.task.type]["faro_goal"]
    # FARO constrains each coordinate separately. Leave room for the TO
    # feasibility residual inside the independent 3D completion radius.
    return TerminalGoal(kso="hard", to="hard", robots={
        ROBOT: PositionTarget(
            reach_xyz(spec, state),
            kso_tolerance=GoalTolerances(position=goal["kso_position_tolerance_per_axis_m"]),
            to_tolerance=GoalTolerances(position=goal["to_position_tolerance_per_axis_m"]),
        )
    })


def reach_completion(spec, scene, state, results):
    target = reach_xyz(spec, state)
    tolerance = TASKS[spec.task.type]["completion_check"]["maximum_error_m"]
    report = {"met": False, "target_xyz_m": target.tolist(), "maximum_error_m": tolerance}
    try:
        trajectory = np.asarray(results["robot_xs"][ROBOT], dtype=float)
    except (KeyError, TypeError, ValueError):
        return {**report, "reason": "Missing robot trajectory"}
    if trajectory.ndim != 2 or trajectory.shape[0] < 2 or trajectory.shape[1] < scene.robots[ROBOT].nq:
        return {**report, "reason": "Invalid robot trajectory shape"}
    if not np.isfinite(trajectory).all():
        return {**report, "reason": "Non-finite robot trajectory"}
    final = trajectory[-1, :3]
    error = dist(final, target)
    return {**report, "met": error <= tolerance, "final_xyz_m": final.tolist(), "error_m": error}


TASK_HANDLERS = {"reach_position": (reach_discrete, reach_terminal, reach_completion)}


@lru_cache
def registered_spec(path):
    spec, errors = parse_spec(path.read_bytes())
    if errors:
        raise ValueError(f"Invalid registered SceneSpec in {path}: {errors}")
    return spec
