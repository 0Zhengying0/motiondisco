"""Read MotionDisCo performance sidecars while retaining partial observations."""

from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import fmean


PHASE_COLUMNS = {
    "proposal_s": ("proposal",),
    "program_generation_s": ("program_generation",),
    "candidate_evaluation_s": ("candidate_evaluation",),
    "contact_check_s": ("contact_check", "contact_validation"),
    "kso_s": ("kso", "kso_window"),
    "kso_attempt_s": ("kso_attempt",),
    "kso_native_wall_s": ("kso_native",),
    "to_s": ("to",),
    "to_segmented_s": ("to_segmented",),
    "to_build_work_s": ("to_build",),
    "to_solve_work_s": ("to_solve",),
    "to_polish_s": ("to_polish",),
    "physical_check_work_s": ("physical_check",),
}
TIMES = tuple(PHASE_COLUMNS) + ("to_exclusive_s", "kso_native_profiled_s", "kso_native_initialization_s")
COUNTS = ("telemetry_candidates", "timed_evaluations", "timed_kso_candidates", "timed_to_candidates",
          "candidate_llm_requests", "open_timing_spans")
RUN_FIELDS = (
    "scene_object_count", "scene_movable_object_count", "scene_fixed_object_count", "carry_goal_distance_m",
    "robot_goal_distance_m", "object_goal_distances_m", "max_returned_object_displacement_m",
    "max_returned_object_path_length_m", "effective_solver_config", "seed_consumers",
    "seed_ollama_enabled", "python_hash_seed", "motiondisco_dirty", "faro_dirty",
    "motiondisco_working_source_changes_sha256", "faro_working_source_changes_sha256", "ollama_model_digests",
    "job_started_unix_s", "job_ended_unix_s", "recorded_job_exit_code", "configured_job_seed",
    "configured_job_seed_source", "gpu_sample_count", "gpu_sample_interval_s", "gpu_sampled_util_mean_pct",
    "gpu_sampled_util_peak_pct", "gpu_sampled_vram_mean_mib", "gpu_sampled_vram_peak_mib",
    "gpu_sampled_vram_total_mib", "gpu_sampled_devices", "gpu_util_source", "gpu_vram_source",
)


def events(path):
    if path is None or not path.is_file():
        return []
    with path.open(errors="replace") as source:
        rows = []
        for line in source:
            # SIGKILL can leave an unfinished trailing record.
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("version") == 1 and "event" in row:
                rows.append(row)
    return rows


def last_event(rows, name):
    return next((row for row in reversed(rows) if row["event"] == name), {})


def union_seconds(intervals):
    start = end = total = 0
    for begin, stop in sorted(intervals):
        if begin >= end:
            total += end - start
            start, end = begin, stop
        else:
            end = max(end, stop)
    return (total + end - start) / 1e9


def exclusive_to(to_spans, nested_spans, unfinished_nested):
    if not to_spans:
        return None
    total = 0.0
    for start, end in to_spans:
        a, b = start["monotonic_ns"], end["monotonic_ns"]
        if any(a <= event["monotonic_ns"] < b for event in unfinished_nested):
            return None
        intervals = []
        for inner_start, inner_end in nested_spans:
            low = max(a, inner_start["monotonic_ns"])
            high = min(b, inner_end["monotonic_ns"])
            if low < high:
                intervals.append((low, high))
        total += (b - a) / 1e9 - union_seconds(intervals)
    return total


def compact(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def candidate_record(folder, results):
    proposal = events(folder / "proposal_performance.jsonl")
    evaluation = events(results / "evaluation_performance.jsonl")
    rows = proposal + evaluation
    if not rows:
        return {}
    starts = {row["span"]: row for row in rows if row["event"] == "phase_start"}
    endings = {row["span"]: row for row in rows if row["event"] == "phase_end" and row["span"] in starts}
    spans = defaultdict(list)
    for span, end in endings.items():
        spans[end["stage"]].append((starts[span], end))
    unfinished = [start for span, start in starts.items() if span not in endings]
    values = {}
    for column, stages in PHASE_COLUMNS.items():
        pairs = [pair for stage in stages for pair in spans[stage]]
        values[column] = round(sum(end["seconds"] for _, end in pairs), 6) if pairs else None
    exclusive = exclusive_to(spans["to"], spans["physical_check"] + spans["kso_window"],
                             [span for span in unfinished if span["stage"] in ("physical_check", "kso_window")])
    values["to_exclusive_s"] = round(exclusive, 6) if exclusive is not None else None
    profiles = [row for row in rows if row["event"] == "kso_native_profile"]
    if profiles:
        values["kso_native_profiled_s"] = round(sum(row["solve_s"] for row in profiles), 6)
        values["kso_native_initialization_s"] = round(sum(row["initialization_s"] for row in profiles), 6)
    chat = [row for row in proposal if row["event"] == "llm_request"]
    values.update(
        candidate_llm_requests=len(chat) if chat or last_event(proposal, "local_chat_call") else None,
        llm_request_seeds=compact([row["seed"] for row in chat]) if chat else None,
        llm_request_models=compact(dict(Counter(row["model"] or "unknown" for row in chat))) if chat else None,
        open_timing_spans=len(unfinished),
        open_timing_stages=compact(dict(Counter(row["stage"] for row in unfinished))) if unfinished else None,
        evaluation_seed=last_event(evaluation, "evaluation_seed").get("seed"),
        evaluation_seed_source=last_event(evaluation, "evaluation_seed").get("source"),
        evaluation_trace_status=("interrupted" if not spans["candidate_evaluation"] else
                                 "exception" if spans["candidate_evaluation"][-1][1]["exception"] else
                                 "evaluated") if evaluation else None,
    )
    scene = last_event(rows, "scene_config")
    if scene:
        for column, source in (("scene_object_count", "object_count"), ("scene_movable_object_count", "movable_object_count"),
                               ("scene_fixed_object_count", "fixed_object_count"), ("carry_goal_distance_m", "carry_goal_distance_m"),
                               ("robot_goal_distance_m", "robot_goal_distance_m")):
            values[column] = scene.get(source)
        values["object_goal_distances_m"] = compact(scene["object_goal_distances_m"]) if scene.get("object_goal_distances_m") else None
    distance = last_event(rows, "trajectory_distances")
    for key in ("object_end_displacement_m", "object_path_length_m"):
        values[key] = compact(distance[key]) if distance.get(key) else None
    values["max_returned_object_displacement_m"] = max((distance.get("object_end_displacement_m") or {}).values(), default=None)
    values["max_returned_object_path_length_m"] = max((distance.get("object_path_length_m") or {}).values(), default=None)
    configs = {}
    for name in ("kso_config", "to_config"):
        config = last_event(rows, name)
        if config:
            configs[name] = {k: v for k, v in config.items() if k not in
                             ("event", "version", "unix_s", "pid", "job_id", "scene", "run_id", "generation", "sample_id")}
    values["effective_solver_config"] = compact(configs) if configs else None
    return values


def run_record(directory, job_path, gpu_path, raw, candidates):
    job = events(job_path)
    start, end = last_event(job, "job_start"), last_event(job, "job_end")
    seed = last_event(events(directory / "run_performance.jsonl") if directory else [], "run_config")
    gpu = events(gpu_path)
    samples = [rec for rec in gpu if rec["event"] == "gpu_sample"]
    utils = [rec["gpu_util_pct"] for rec in samples if rec["gpu_util_pct"] is not None]
    vram = [rec["vram_used_mib"] for rec in samples if rec["vram_used_mib"] is not None]
    totals = [rec["vram_total_mib"] for rec in samples if rec["vram_total_mib"] is not None]
    gpu_models = sorted({rec["gpu_model"] for rec in samples})
    measured = [r["performance"] for r in candidates if r.get("performance")]
    result = {
        "job_started_unix_s": start.get("unix_s"), "job_ended_unix_s": end.get("unix_s"),
        "recorded_job_exit_code": end.get("exit_code"), "configured_job_seed": start.get("configured_seed"),
        "configured_job_seed_source": start.get("seed_source"),
        "ollama_model_digests": (compact(last_event(job, "ollama_models")["model_digests"])
                                 if last_event(job, "ollama_models") else None),
        "gpu_sample_count": len(samples) if gpu else None,
        "gpu_sample_interval_s": last_event(gpu, "sampler_start").get("interval_s"),
        "gpu_sampled_devices": compact(dict(sorted({(rec["uuid"], rec["gpu_model"]) for rec in samples}))) if samples else None,
        "gpu_sampled_util_mean_pct": round(fmean(utils), 6) if utils else None,
        "gpu_sampled_util_peak_pct": max(utils, default=None),
        "gpu_sampled_vram_mean_mib": round(fmean(vram), 6) if vram else None,
        "gpu_sampled_vram_peak_mib": max(vram, default=None),
        "gpu_sampled_vram_total_mib": max(totals, default=None),
        "gpu_util_source": "slurm_tres" if raw.get("batch_gpu_util_tres") else "nvidia-smi" if utils else None,
        "gpu_vram_source": "slurm_tres" if raw.get("batch_gpu_mem_tres") else "nvidia-smi" if vram else None,
    }
    if gpu_models:
        result["gpu_model"] = "; ".join(gpu_models)
    if seed.get("seed") is not None:
        result.update(random_seed=seed["seed"], seed_evidence=seed.get("seed_source"),
                      seed_consumers=compact(seed.get("seed_consumers", [])), seed_ollama_enabled=seed.get("ollama_seed_enabled"),
                      python_hash_seed=seed.get("python_hash_seed"))
    for key in ("motiondisco", "faro"):
        version = seed.get(key) or {}
        if bool(version):
            result[key + "_dirty"] = version.get("dirty")
            result[key + "_working_source_changes_sha256"] = version.get("working_source_changes_sha256")
        commit = version.get("commit") or start.get(key + "_commit")
        if commit:
            result[key + "_commit"] = commit
    for key in ("scene_object_count", "scene_movable_object_count", "scene_fixed_object_count",
                "carry_goal_distance_m", "robot_goal_distance_m", "object_goal_distances_m"):
        result[key] = next((p[key] for p in measured if p.get(key) is not None), None)
    for key in ("max_returned_object_displacement_m", "max_returned_object_path_length_m"):
        result[key] = max((p[key] for p in measured if p.get(key) is not None), default=None)
    solver_config = {}
    for p in measured:
        if p.get("effective_solver_config"):
            solver_config.update(json.loads(p["effective_solver_config"]))
    result["effective_solver_config"] = compact(solver_config) if solver_config else None
    if measured:
        result.update(telemetry_candidates=len(measured), timed_evaluations=0, timed_kso_candidates=0, timed_to_candidates=0)
        for column, seconds_column in (("timed_evaluations", "candidate_evaluation_s"),
                                       ("timed_kso_candidates", "kso_s"), ("timed_to_candidates", "to_s")):
            result[column] = sum(p.get(seconds_column) is not None for p in measured)
        for key in ("open_timing_spans", "candidate_llm_requests"):
            values = [p[key] for p in measured if p.get(key) is not None]
            result[key] = sum(values) if values else None
        for key in TIMES:
            values = [p[key] for p in measured if p.get(key) is not None]
            if values:
                result[key] = round(sum(values), 6)
    return result
