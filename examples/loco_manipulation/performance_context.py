"""Scene and trajectory descriptors for performance traces."""

import numpy as np

from shinka.performance import event, observation


@observation
def record_task(task, *, score_mode=None):
    scene, state, goal = task.scene, task.resolved_state, task.terminal_goal
    object_distances = {
        name: float(np.linalg.norm(target.value[:3] - state.env_objects[name].q[:3]))
        for name, target in (goal.objects.items() if goal else ())
        if name in state.env_objects
    }
    robot_target = goal.robots.get(task.robot_id) if goal else None
    robot_distance = (float(np.linalg.norm(robot_target.value[:3] - state.robots[task.robot_id].q[:3]))
                      if robot_target is not None else None)
    event(
        "scene_config",
        resolved_scene=task.scene_name,
        initial_condition=task.ic_name,
        object_count=len(scene.objects),
        movable_object_count=len(scene.env_objects),
        fixed_object_count=len(scene.fixed_env_objects),
        object_goal_distances_m=object_distances,
        carry_goal_distance_m=max(object_distances.values(), default=None),
        robot_goal_distance_m=robot_distance,
        to_goal_mode=goal.to if goal else None,
        kso_goal_mode=goal.kso if goal else None,
        score_mode=score_mode,
    )


@observation
def record_trajectory(solve):
    displacements, lengths = {}, {}
    for name, state in (solve.results.get("obj_xs") or {}).items():
        xyz = np.asarray(state)[:, :3]
        if len(xyz) and np.isfinite(xyz).all():
            displacements[name] = float(np.linalg.norm(xyz[-1] - xyz[0]))
            lengths[name] = float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())
    event("trajectory_distances", object_end_displacement_m=displacements,
          object_path_length_m=lengths)
