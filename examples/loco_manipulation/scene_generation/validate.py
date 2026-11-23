"""Geometry and static MuJoCo checks for generated scenes."""

from dataclasses import asdict
from itertools import combinations, product
from math import ceil

import mujoco as mj
import numpy as np

from faro.configs.mujoco import build_mujoco, robot_prefix
from faro.configs.scene import OnFace
from faro.utils.contact_type import CONTACT_TYPE_UNILATERAL
from shinka.performance import phase, timed

from .convert import FLOOR, ROBOT, initial_state, make_scene, standing_xy_yaw, TASK_HANDLERS
from .spec import Issue, check_references, parse_spec

THRESHOLDS = {
    "bounds_m": 1e-6,
    "support_gap_m": 1e-5,
    "box_penetration_m": 0.001,
    "sole_penetration_m": 0.002,
    "sole_contact_gap_m": 0.001,
    "simulation_s": 2.0,
    "settle_s": 0.25,
    "position_drift_m": 0.005,
    "angle_drift_rad": 0.03,
    "linear_speed_m_s": 0.01,
    "angular_speed_rad_s": 0.05,
}


def box_corners(center, rotation, half):
    return center + (np.asarray(list(product((-1, 1), repeat=3))) * half) @ rotation.T


def geometry(model, scene):
    geoms = {}
    robot = {}
    feet = {}
    prefix = robot_prefix(ROBOT)
    for idx in range(model.ngeom):
        geom = model.geom(idx)
        body = model.body(int(model.geom_bodyid[idx])).name
        if body.startswith(prefix):
            robot[idx] = body.removeprefix(prefix)
            if geom.type[0] == mj.mjtGeom.mjGEOM_SPHERE and body.endswith("_ankle_roll_link"):
                feet[idx] = robot[idx]
        else:
            geoms[geom.name.split("-")[0]] = idx
    if set(geoms) != set(scene.objects) or len(set(feet.values())) != 2:
        raise ValueError("MuJoCo geometry names do not match the FARO objects and two G1 soles")
    return geoms, robot, feet


def fresh_data(model, qpos):
    data = mj.MjData(model)
    data.qpos[:] = qpos
    mj.mj_forward(model, data)
    return data


def footprint_feedback(vertices, support_half):
    footprint = vertices[:, :2]
    lower, upper = footprint.min(axis=0), footprint.max(axis=0)
    box_half = (upper - lower) / 2
    return {
        "center_xy_m": np.round((upper + lower) / 2, 6).tolist(),
        "footprint_half_extents_m": np.round(box_half, 6).tolist(),
        "center_abs_limits_xy_m": np.round(support_half - box_half, 6).tolist(),
        "overflow_xy_m": np.round(np.maximum(np.maximum(-lower, upper) - support_half, 0), 6).tolist(),
    }


def shared_support_separation(first_vertices, second_vertices, support_half):
    """Suggest nonoverlapping center intervals along either support axis."""
    clearance = 0.02
    first_min, first_max = first_vertices.min(axis=0), first_vertices.max(axis=0)
    second_half = (second_vertices.max(axis=0) - second_vertices.min(axis=0)) / 2
    limits = support_half - second_half[:2]
    details = {"center_abs_limits_xy_m": np.round(limits, 6).tolist(), "suggested_clearance_m": clearance}
    if np.any(limits < 0):
        return {**details, "center_ranges_m": {"x": [], "y": []}}
    ranges = {}
    for i, axis in enumerate(("x", "y")):
        left = (-limits[i], min(limits[i], first_min[i] - second_half[i] - clearance))
        right = (max(-limits[i], first_max[i] + second_half[i] + clearance), limits[i])
        ranges[axis] = [np.round(interval, 6).tolist() for interval in (left, right) if interval[0] <= interval[1]]
    return {**details, "center_ranges_m": ranges}


@timed("mujoco_scene_geometry")
def check_geometry(scene, state, model, data, geoms):
    errors = []
    epsilon = THRESHOLDS["bounds_m"]
    bounds = np.asarray(scene.objects[FLOOR].half_extents)
    corners = {name: box_corners(data.geom_xpos[idx], data.geom_xmat[idx].reshape(3, 3),
                                 model.geom_size[idx]) for name, idx in geoms.items() if name != FLOOR}
    support_corners = {}
    for name, vertices in corners.items():
        if np.any(np.abs(vertices[:, :2]) > bounds + epsilon):
            errors.append(Issue("OUT_OF_BOUNDS", name, "Box footprint exceeds the finite floor",
                                {"frame": "world_xy", "floor_half_extents_m": bounds.tolist(),
                                 **footprint_feedback(vertices, bounds)}))
        if vertices[:, 2].min() < -THRESHOLDS["box_penetration_m"]:
            errors.append(Issue("PENETRATION", name, "Box penetrates the floor",
                                {"depth_m": float(-vertices[:, 2].min()), "other": FLOOR}))
        placement = state.objects[name]
        if not isinstance(placement, OnFace):
            errors.append(Issue("UNSUPPORTED_OBJECT", name, "An explicit support is required"))
            continue
        support, _ = placement.on
        if support == FLOOR:
            support_corners[name] = vertices
            gap = float(vertices[:, 2].min())
            if abs(gap) > THRESHOLDS["support_gap_m"]:
                errors.append(Issue("UNSUPPORTED_OBJECT", name, "Bottom face does not meet the floor",
                                    {"support": FLOOR, "gap_m": gap}))
            continue
        idx = geoms[support]
        support_rotation = data.geom_xmat[idx].reshape(3, 3)
        local = (vertices - data.geom_xpos[idx]) @ support_rotation
        support_corners[name] = local
        half = model.geom_size[idx]
        if np.any(np.abs(local[:, :2]) > half[:2] + epsilon):
            errors.append(Issue("OUT_OF_BOUNDS", name, "Box footprint exceeds the declared support",
                                {"frame": "support_local_xy", "support": support,
                                 "support_half_extents_m": half[:2].tolist(),
                                 **footprint_feedback(local, half[:2])}))
        gap = float(local[:, 2].min() - half[2])
        if abs(gap) > THRESHOLDS["support_gap_m"]:
            errors.append(Issue("UNSUPPORTED_OBJECT", name, "Bottom face does not meet the declared support",
                                {"support": support, "gap_m": gap}))

    # FARO adds fixed geoms to the world body. MuJoCo omits world–world
    # pairs, so test upright-box separating axes directly for every pair.
    for first, second in combinations(corners, 2):
        a, b = corners[first], corners[second]
        da, db = geoms[first], geoms[second]
        axes = np.column_stack((np.eye(3)[:, 2], data.geom_xmat[da].reshape(3, 3)[:, :2],
                                data.geom_xmat[db].reshape(3, 3)[:, :2]))
        aa, bb = a @ axes, b @ axes
        depth = np.minimum(aa.max(axis=0) - bb.min(axis=0), bb.max(axis=0) - aa.min(axis=0)).min()
        if depth > THRESHOLDS["box_penetration_m"]:
            details = {"other": second, "depth_m": float(depth)}
            if first in support_corners and second in support_corners and state.objects[first].on == state.objects[second].on:
                support, _ = state.objects[first].on
                support_half = np.asarray(scene.objects[support].half_extents[:2])
                details["separation_hint"] = {
                    "move_instance": second, "support": support, "frame": "support_local_xy",
                    **shared_support_separation(support_corners[first], support_corners[second], support_half),
                }
            errors.append(Issue("PENETRATION", first, "Box volumes overlap", details))
    return errors


@timed("mujoco_standing")
def check_standing(scene, model, data, geoms, robot, feet, at_goal=False):
    errors = []
    subject = "task.parameters.target_xy" if at_goal else "robot"
    codes = ("INVALID_TARGET", "INVALID_TARGET") if at_goal else ("ROBOT_COLLISION", "OUT_OF_BOUNDS")
    floor = geoms[FLOOR]
    owners = {idx: name for name, idx in geoms.items()}
    floor_contacts = set()
    collision_depths = {}
    for contact in data.contact:
        a, b = contact.geom
        if b in robot:
            a, b = b, a
        if a not in robot or b not in owners:
            continue
        distance = float(contact.dist)
        if b == floor and a in feet:
            if distance <= THRESHOLDS["sole_contact_gap_m"]:
                floor_contacts.add(feet[a])
            collision = distance < -THRESHOLDS["sole_penetration_m"]
        else:
            collision = distance <= 0
        if collision:
            pair = (robot[a], owners[b])
            collision_depths[pair] = min(distance, collision_depths.get(pair, 0.0))
    for (body, other), distance in sorted(collision_depths.items()):
        errors.append(Issue(codes[0], subject, "G1 standing pose collides with the environment",
                            {"robot_body": body, "other": other, "contact_distance_m": distance}))

    half = scene.objects[FLOOR].half_extents
    outside = {body for idx, body in feet.items()
               if np.any(np.abs(data.geom_xpos[idx, :2]) + model.geom_size[idx, 0] >
                         np.asarray(half) + THRESHOLDS["bounds_m"])}
    if outside:
        errors.append(Issue(codes[1], subject, "G1 soles exceed the finite floor", {"feet": sorted(outside)}))
    floor_contacts.update(body for idx, body in feet.items() if mj.mj_geomDistance(
        model, data, floor, idx, 2 * THRESHOLDS["sole_contact_gap_m"], None
    ) <= THRESHOLDS["sole_contact_gap_m"])
    if missing := set(feet.values()) - floor_contacts:
        errors.append(Issue("INVALID_TARGET" if at_goal else "UNSUPPORTED_ROBOT", subject,
                            "Both G1 soles must contact the floor", {"feet": sorted(missing)}))
    return errors


def _on_support(data, geoms, name, support):
    child, parent = geoms[name], geoms[support]
    for contact in data.contact:
        a, b = contact.geom
        if {a, b} == {child, parent}:
            up = contact.frame[2] if a == parent else -contact.frame[2]
            if up > 0.9 and contact.dist <= THRESHOLDS["support_gap_m"]:
                return True
    return False


@timed("mujoco_static")
def check_stability(scene, state, model, data, geoms, robot):
    if not scene.env_objects:
        return [], {}
    initial = data.qpos.copy()
    joints = {}
    missing = []
    for name in scene.env_objects:
        joint = model.joint(f"{name}-floating_base_joint")
        q, v = int(joint.qposadr[0]), int(joint.dofadr[0])
        joints[name] = q, v
        support = state.objects[name].on[0]
        if _on_support(data, geoms, name, support):
            continue
        # MuJoCo may omit coincident box contacts at floating-point
        # precision. Probe at a 10 micrometre displacement and restore
        # the exact authored starting pose before the simulation.
        data.qpos[q + 2] -= THRESHOLDS["support_gap_m"]
        mj.mj_forward(model, data)
        if not _on_support(data, geoms, name, support):
            missing.append(Issue("UNSUPPORTED_OBJECT", name,
                                 "MuJoCo found no upward contact with the declared support",
                                 {"support": support}))
        data.qpos[q + 2] = initial[q + 2]
        mj.mj_forward(model, data)
    if missing:
        return missing, {}

    # Keep the compiled geometry and dynamics for the boxes. Isolate the
    # uncontrolled robot from collisions and hold its initial state at each step.
    ids = list(robot)
    contype, affinity = model.geom_contype[ids].copy(), model.geom_conaffinity[ids].copy()
    model.geom_contype[ids] = model.geom_conaffinity[ids] = 0
    q_robot = np.ones(model.nq, dtype=bool)
    v_robot = np.ones(model.nv, dtype=bool)
    for q, v in joints.values():
        q_robot[q:q + 7] = False
        v_robot[v:v + 6] = False

    limits = {key: value for key, value in THRESHOLDS.items()
              if key in ("position_drift_m", "angle_drift_rad", "linear_speed_m_s", "angular_speed_rad_s")}
    metrics = {name: dict.fromkeys(limits, 0.0) for name in joints}
    errors = []
    try:
        duration = THRESHOLDS["simulation_s"]
        for _ in range(ceil(duration / model.opt.timestep)):
            data.qpos[q_robot], data.qvel[v_robot] = initial[q_robot], 0
            mj.mj_step(model, data)
            if not np.all(np.isfinite(data.qpos)) or not np.all(np.isfinite(data.qvel)) or any(
                    warning.number for warning in data.warning):
                return [Issue("UNSTABLE_OBJECT", "scene", "MuJoCo reported a numerical instability")], metrics
            for name, (q, v) in joints.items():
                angle = 2 * np.arccos(np.clip(abs(initial[q + 3:q + 7] @ data.qpos[q + 3:q + 7]), 0, 1))
                values = {"position_drift_m": np.linalg.norm(data.qpos[q:q + 3] - initial[q:q + 3]),
                          "angle_drift_rad": angle}
                if data.time >= duration - THRESHOLDS["settle_s"]:
                    values["linear_speed_m_s"] = np.linalg.norm(data.qvel[v:v + 3])
                    values["angular_speed_rad_s"] = np.linalg.norm(data.qvel[v + 3:v + 6])
                for key, value in values.items():
                    metrics[name][key] = max(metrics[name][key], float(value))
        mj.mj_forward(model, data)
        for name, values in metrics.items():
            exceeds = {key: limits[key] for key, value in values.items() if value > limits[key]}
            support = state.objects[name].on[0]
            if exceeds or not _on_support(data, geoms, name, support):
                errors.append(Issue("UNSTABLE_OBJECT", name, "Object drifted, kept moving or lost its support",
                                    {"support": support, "measured": values, "exceeded_limits": exceeds}))
    finally:
        model.geom_contype[ids], model.geom_conaffinity[ids] = contype, affinity
    return errors, metrics


def validate(raw, *, require_novelty=True):
    """Return the parsed SceneSpec and a JSON-compatible validation report."""
    spec, errors = parse_spec(raw)
    report = {"pass": False, "errors": [], "mujoco_version": mj.__version__,
              "thresholds": THRESHOLDS, "stability": {}}
    if spec is not None:
        from faro.configs.robot import make_g1_robot

        robot = make_g1_robot()
        errors = check_references(spec, {"floor", ROBOT, *robot.patch_ees})
    if not errors and require_novelty:
        from .novelty import check_novelty
        errors = check_novelty(spec)
    if not errors:
        try:
            with phase("mujoco_scene_build"):
                scene = make_scene(spec)
                state = initial_state(spec)
                resolved = scene.resolve(state)
                model, qpos = build_mujoco(scene, resolved)
            data = fresh_data(model, qpos)
            geoms, robot, feet = geometry(model, scene)
            for name, placement in state.objects.items():
                if isinstance(placement, OnFace) and any(
                    CONTACT_TYPE_UNILATERAL not in scene.faces.admitted[scene.face_id(*face)]
                    for face in (placement.on, (name, placement.self_face))
                ):
                    errors.append(Issue("INVALID_CONTACT_PERMISSION", name, "Support requires unilateral contact"))

            errors.extend(check_geometry(scene, state, model, data, geoms))
            errors.extend(check_standing(scene, model, data, geoms, robot, feet))
            _, terminal, _ = TASK_HANDLERS[spec.task.type]
            target_xyz = terminal(spec, scene, resolved).robots[ROBOT].xyz
            target_state = type(state)(
                robots={ROBOT: standing_xy_yaw((*target_xyz[:2], spec.robot.initial_xy_yaw[2]))},
                objects=state.objects,
            )
            # Change only the robot root translation in the compiled scene.
            target = scene.resolve(target_state)
            root = model.joint(robot_prefix(ROBOT) + scene.robots[ROBOT].pin_model.names[1])
            qa = int(root.qposadr[0])
            goal_qpos = qpos.copy()
            goal_qpos[qa:qa + 3] = target.robots[ROBOT].q[:3]
            goal_data = fresh_data(model, goal_qpos)
            errors.extend(check_standing(scene, model, goal_data, geoms, robot, feet, at_goal=True))
            if not errors:
                errors, report["stability"] = check_stability(scene, state, model, data, geoms, robot)
            report["face_ids"] = {f"{name}.{face}": idx for (name, face), idx in scene.faces.by_name.items()}
            report["target_xyz_m"] = target_xyz.tolist()
        except (ValueError, RuntimeError, KeyError) as exc:
            errors.append(Issue("BUILD_FAILED", "scene", f"{type(exc).__name__}: {exc}"))
    report["errors"] = [asdict(error) for error in errors]
    report["pass"] = not errors
    return spec, report
