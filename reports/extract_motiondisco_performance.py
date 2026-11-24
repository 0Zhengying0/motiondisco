#!/usr/bin/env python3
"""Read saved MotionDisCo artifacts and Slurm accounting, without launching evaluations."""

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import getpass
import hashlib
import json
import math
from pathlib import Path
import pickle
import re
import sqlite3
from statistics import median
import subprocess
import sys

if __package__:
    from . import performance_records as telemetry
else:
    import performance_records as telemetry


ROOT = Path(__file__).resolve().parents[1]
SACCT_FIELDS = (
    "JobID,JobIDRaw,JobName%100,State%40,ExitCode,DerivedExitCode,Start,End,"
    "ElapsedRaw,Timelimit,Partition,AllocCPUS,CPUTimeRAW,TotalCPU,UserCPU,SystemCPU,"
    "ReqMem,MaxRSS,AveRSS,MaxVMSize,ReqTRES%200,AllocTRES%200,TRESUsageInAve%400,"
    "TRESUsageInMax%400,TRESUsageInTot%400,NodeList%120,WorkDir%500,StdOut%500,StdErr%500"
)
LOG_KINDS = {
    "campaign": "campaign", "search": "standalone_search", "box-smoke": "standalone_search",
    "instrumented": "standalone_search",
    "qwen-generate": "generated_scene",
    "kso-retest": "kso_retest", "render": "render", "llm-test": "model_probe",
    **dict.fromkeys(("env", "acados", "moto", "faro", "install", "ollama-install", "models", "tera"), "setup"),
}
JOB_KINDS = {
    "md-qwen-campaign": "campaign", "motiondisco-first-search": "search",
    "motiondisco-box-smoke": "box-smoke", "motiondisco-render-best": "render",
    "md-qwen-generate": "qwen-generate",
}
BOX_HALF_EXTENTS = {
    "green_box": (0.1025, 0.095, 0.115), "white_box": (0.1325, 0.1275, 0.135),
    "yellow_box": (0.175, 0.175, 0.185),
}
CANDIDATE_COUNTS = """
program_files_written candidate_generated initial_programs candidate_proposed evaluations_started
metrics_records provisional_metrics evaluations_completed db_programs contact_checked
contact_legal contact_gate_pass schedule_rejected discrete_goal_match kso_pass to_attempted to_returned
to_converged to_valid physical_checks_pass nonzero_score terminal_goal_checked
terminal_goal_met valid_with_terminal_goal_met semantic_checked task_completed task_failed
proposal_failures proposal_not_novel program_errors contact_invalid kso_failures to_failures
candidate_system_errors contact_conversion_errors evaluation_interrupted evaluation_timeout_confirmed evaluation_timeout_near_limit
""".split()
RUN_TIMES = """
llm_chat_request_s embedding_request_s kso_s kso_diagnosis_s to_s to_segment_build_s
to_segment_solve_s to_polish_s planner_function_s proposal_sampling_s evaluation_pipeline_s
render_s render_job_wall_s scene_generate_request_s
""".split() + list(telemetry.SCENE_PHASE_COLUMNS)


@dataclass
class Run:
    job_id: str
    log_kind: str
    scene: str = ""
    directory: Path = None
    workflow_directory: Path = None

    @property
    def group(self):
        return LOG_KINDS[self.log_kind]

    def logs(self, root):
        return root / ("results" if self.group == "generated_scene" else "logs")


def read_text(path):
    return path.read_text(errors="replace") if path and path.is_file() else ""


def read_json(path):
    if not path.is_file():
        return None
    try:
        value = json.loads(read_text(path))
        if isinstance(value, dict):
            return value
        raise ValueError("expected a JSON object")
    except ValueError as error:
        print(f"{path}: {error}", file=sys.stderr)
        return None


def scalar(source, key):
    match = re.search(r"(?m)^ *" + re.escape(key) + r": *([^\r\n]+)", source)
    return match[1].strip().strip("'\"") if match else None


def first(source, pattern):
    match = re.search(pattern, source, re.M)
    return match[1] if match else None


def compact(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def recorded_sum(values):
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return round(sum(values), 3) if values else None


def seconds(value):
    if not value or value in ("Unknown", "N/A", "UNLIMITED"):
        return None
    days, sep, clock = value.partition("-")
    fields = (clock if sep else days).split(":")
    return round((86400 * int(days) if sep else 0) +
                 sum(float(v) * 60 ** i for i, v in enumerate(reversed(fields))), 3)


def gib(value):
    match = re.fullmatch(r"([\d.]+)([KMGTP])(?:[cn])?", value or "")
    return round(float(match[1]) * 1024 ** ("KMGTP".index(match[2]) - 2), 6) if match else None


def accounting_source(args, root):
    snapshot = args.sacct or args.output_dir / "karolina_sacct.psv"
    if args.refresh_sacct:
        command = ["sacct", "-S", args.since, "-u", getpass.getuser(), "-P", "-o", SACCT_FIELDS]
        if args.job_id:
            command += ["-j", args.job_id]
        result = subprocess.run(command,
                                check=True, stdout=subprocess.PIPE, universal_newlines=True)
        lines = result.stdout.splitlines()
        reader = csv.DictReader(lines, delimiter="|")
        data = list(reader)
        instrumented_ids = {meta.get("job_id") for _, meta in instrumented_runs(root)}
        ids = {row["JobID"] for row in data if relevant_job(row, root) or row["JobID"] in instrumented_ids}
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, reader.fieldnames, delimiter="|")
            writer.writeheader()
            writer.writerows(row for row in data if row["JobID"].split(".")[0] in ids)
    if not snapshot.is_file():
        print(f"Slurm snapshot unavailable: {snapshot}", file=sys.stderr)
        return {}
    with snapshot.open(newline="") as stream:
        return {row["JobID"]: row for row in csv.DictReader(stream, delimiter="|")}


def relevant_job(row, root):
    name, jid = row["JobName"], row["JobID"]
    return "." not in jid and (name in JOB_KINDS or name.startswith("motiondisco-")
                               or (row.get("WorkDir") == str(root) and "/logs/md-" in row.get("StdOut", "")))


def instrumented_runs(root):
    for path in sorted((root / "results").rglob("run_performance.jsonl")):
        meta = telemetry.last_event(telemetry.events(path), "run_config")
        if meta:
            yield path.parent, meta


def discover(root, jobs, campaign):
    runs = {}
    for jid, data in jobs.items():
        if "." in jid:
            continue
        name = data["JobName"]
        kind = JOB_KINDS.get(name, name.replace("motiondisco-", "", 1))
        if kind in LOG_KINDS:
            runs[jid] = Run(jid, kind)
    for log in sorted((root / "logs").glob("md-*")):
        match = re.fullmatch(r"md-(.+)-(\d+(?:_\d+)?)\.(out|err|performance\.jsonl)", log.name)
        if match and match[1] in LOG_KINDS:
            runs.setdefault(match[2], Run(match[2], match[1]))
    for log in sorted((root / "results").glob("md-qwen-generate-*")):
        match = re.fullmatch(r"md-qwen-generate-(\d+)\.(out|err|performance\.jsonl)", log.name)
        if match:
            runs.setdefault(match[1], Run(match[1], "qwen-generate"))

    for run in runs.values():
        out = read_text(run.logs(root) / f"md-{run.log_kind}-{run.job_id}.out")
        if run.group == "campaign" and "_" in run.job_id:
            index = int(run.job_id.split("_")[1])
            entry = campaign[index] if index < len(campaign) else {}
            run.scene = first(out, r"^Scene: (\S+)") or entry.get("scene", "")
        elif run.log_kind in {"search", "kso-retest"}:
            run.scene = "example_scene"
        elif run.log_kind in {"box-smoke", "render"}:
            run.scene = "motiondisco.box_stacking"

        output = scalar(out, "output_dir")
        if output and "${" not in output:
            run.directory = root / output
        if run.group == "generated_scene":
            artifact = first(out, r"^Run artifacts: (.+)$")
            if artifact:
                run.workflow_directory = root / artifact.strip()
                record = read_json(run.workflow_directory / "result.json") or {}
                run.scene = record.get("scene") or ""
                solver_dir = run.workflow_directory / "motiondisco"
                if solver_dir.is_dir():
                    run.directory = solver_dir
        if run.log_kind == "kso-retest":
            run.directory = root / "results/diagnostics" / f"kso_retest_{run.job_id}"
        if run.log_kind == "search" and run.directory is None:
            # Hydra created a timestamped config before failing to resolve the launcher config.
            start, end = (jobs.get(run.job_id, {}).get(k, "") for k in ("Start", "End"))
            low, high = (re.sub(r"[-:T]", "", s) for s in (start, end))
            matches = [p for p in (root / "results/shinka_loco_manipulation").glob("*")
                       if low <= p.name.split("_")[0].replace(".", "") <= high]
            if len(matches) == 1:
                run.directory = matches[0]

    for path in sorted((root / "results/md_qwen_campaign").glob("*/*")):
        match = re.fullmatch(r"job_(\d+_\d+)_ollama", path.name)
        if match:
            run = runs.setdefault(match[1], Run(match[1], "campaign"))
            run.directory = path
            run.scene = run.scene or "motiondisco." + path.parent.name
    # Include output directories without a matched Slurm record, with an explicit artifact ID.
    linked = {run.directory for run in runs.values()}
    for path in sorted((root / "results/shinka_loco_manipulation").glob("*/.hydra/config.yaml")):
        directory = path.parent.parent
        if directory not in linked:
            scene = scalar(read_text(path), "scene") or ""
            kind = "box-smoke" if scene.endswith(".box_stacking") else "search"
            runs[directory.name] = Run("", kind, scene, directory)
    linked = {run.directory for run in runs.values()}
    for directory, meta in instrumented_runs(root):
        if directory not in linked:
            job_id = meta.get("job_id") or ""
            run = runs.get(job_id)
            if run is not None and run.group == "generated_scene" and run.directory is None:
                run.directory, run.scene = directory, meta.get("scene") or ""
                run.workflow_directory = directory.parent
            else:
                runs[str(directory)] = Run(job_id, "instrumented", meta.get("scene") or "", directory)
    return sorted(runs.values(), key=lambda r: (not r.job_id, tuple(int(i) for i in r.job_id.split("_")) if r.job_id else (), str(r.directory)))


def read_program_db(directory):
    if not directory or not (directory / "programs.sqlite").is_file():
        return {}
    path = directory / "programs.sqlite"
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as con:
            rows = con.execute("SELECT generation, metadata FROM programs").fetchall()
        records = {}
        for generation, data in rows:
            metadata = json.loads(data or "{}")
            if not metadata.get("_is_island_copy"):
                records[generation] = metadata
        return records
    except (sqlite3.Error, ValueError) as error:
        print(f"{path}: {error}", file=sys.stderr)
        return {}


def request_times(log, *, separate_scene_generation=False):
    values = defaultdict(list)
    urls = {
        "/v1/chat/completions": "llm_chat", "/api/chat": "llm_chat", "/api/generate": "llm_chat",
        "/v1/embeddings": "embedding", "/api/embed": "embedding", "/api/embeddings": "embedding",
    }
    groups = ("llm_chat", "embedding")
    if separate_scene_generation:
        urls["/api/generate"] = "scene_generate"
        groups += ("scene_generate",)
    units = {"s": 1, "ms": 1e-3, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ns": 1e-9, "m": 60, "h": 3600}
    for status, latency, url in re.findall(
        r'^\[GIN\][^|]*\|\s*(\d+)\s*\|\s*([^ |]+)\s*\|[^|]*\|\s*POST\s+"([^"]+)"', log, re.M
    ):
        key = urls.get(url)
        if key:
            values[key].append(sum(float(n) * units[u] for n, u in
                                   re.findall(r"([0-9.]+)(ms|µs|μs|us|ns|s|m|h)", latency)))
            if int(status) >= 400:
                values[key + "_error"].append(status)
    return {field: value for key in groups for field, value in (
        (key + "_request_s", recorded_sum(values[key])),
        (key + "_requests", len(values[key]) if log else None),
        (key + "_http_errors", len(values[key + "_error"]) if log else None),
    )}


def assess_contact(plan, scored):
    """Return a verdict on the original schedule using recorded structure checks."""
    if not isinstance(plan, dict) or not plan or not scored:
        return None
    if scored.get("num_modes", 0) < 2:
        return False
    checks = [scored.get(k) for k in ("well_formed_fraction", "equal_length_bool", "at_least_one_sole_fraction")]
    if any(v is None for v in checks):
        return None
    return all(v == 1 for v in checks) and all(
        isinstance(seq, list) and all(isinstance(mode, (list, tuple)) for mode in seq) and
        not any(a and b and tuple(a[:-1]) != tuple(b[:-1]) for a, b in zip(seq, seq[1:]))
        for seq in plan.values()
    )


class TrajectoryReader(pickle.Unpickler):
    """Only deserialize the numeric NumPy arrays used by the saved trajectories."""

    def find_class(self, module, name):
        import numpy as np
        if (module, name) in {("numpy", "ndarray"), ("numpy", "dtype")}:
            return getattr(np, name)
        if module in ("numpy.core.multiarray", "numpy._core.multiarray") and name in ("_reconstruct", "scalar"):
            return super().find_class(module, name)
        if module in ("numpy.core.numeric", "numpy._core.numeric") and name == "_frombuffer":
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"unsupported trajectory global {module}.{name}")


def inspect_reach_trajectory(record, path, inspect_saved):
    completion = record.get("completion") or {}
    if not path.is_file():
        return None, "trajectory_missing", {}
    if not inspect_saved:
        if isinstance(completion.get("met"), bool):
            return completion["met"], "scene_spec_completion", completion
        return None, None, {}

    try:
        import numpy as np

        target = np.asarray(record.get("validated_target_xyz") or completion["target_xyz_m"], dtype=float)
        tolerance = float(record["completion_tolerance_m"] if record.get("completion_tolerance_m") is not None
                          else completion["maximum_error_m"])
        with path.open("rb") as stream:
            trajectory = np.asarray(TrajectoryReader(stream).load()["results"]["robot_xs"]["robot"], dtype=float)
        if (target.shape != (3,) or not np.isfinite(target).all() or not math.isfinite(tolerance) or tolerance <= 0
                or trajectory.ndim != 2 or trajectory.shape[0] < 2 or trajectory.shape[1] < 3
                or not np.isfinite(trajectory).all()):
            raise ValueError("non-finite or malformed saved robot states or target")
        final = trajectory[-1, :3]
        error = math.dist(final, target)
        met = error <= tolerance
        return met, "saved_reach_trajectory", {
            "target_xyz_m": target.tolist(), "final_xyz_m": final.tolist(), "error_m": error,
            "maximum_error_m": tolerance, "agrees_with_evaluator": (
                met == completion["met"] if isinstance(completion.get("met"), bool) else None
            ),
        }
    except (ImportError, OSError, EOFError, TypeError, ValueError, AttributeError, KeyError, pickle.UnpicklingError) as error:
        return None, "trajectory_audit_failed", {"audit_error": str(error)}


def inspect_task(scene, record, path, inspect_saved):
    if record.get("generated_scene") or record.get("completion"):
        return inspect_reach_trajectory(record, path, inspect_saved)
    goal = record["goal"]
    if goal.get("met") is not None and goal.get("targets"):
        # Scene terminal targets, independent of the numerical TO status.
        return (goal["met"] is True, "terminal_goal", {})
    if not inspect_saved or not path.is_file():
        return (None, None, {})
    if scene not in {"motiondisco.box_stacking", "motiondisco.climb_table_up_down_with_box"}:
        return (None, None, {})
    try:
        import numpy as np
        with path.open("rb") as stream:
            objects = TrajectoryReader(stream).load()["results"]["obj_xs"]
        if scene.endswith(".box_stacking"):
            if objects.keys() != BOX_HALF_EXTENTS.keys():
                return (None, None, {})
            heights = {}
            displacement = []
            for name, states in objects.items():
                dx, dy, dz = BOX_HALF_EXTENTS[name]
                for label, pose in (("initial", states[0]), ("final", states[-1])):
                    x, y, z, w = pose[3:7] / np.linalg.norm(pose[3:7])
                    height = pose[2] + 2 * (x*z-y*w) * dx + 2 * (y*z+x*w) * dy + (1-2*(x*x+y*y)) * dz
                    heights[label] = max(heights.get(label, -math.inf), height)
                displacement.append(float(np.linalg.norm(states[-1, :3] - states[0, :3])))
            delta = heights["final"] - heights["initial"]
            unchanged = max(displacement) <= 0.01 and abs(delta) <= 0.01
            return (False if unchanged else None, "box_stack_height_and_displacement",
                    {"box_stack_initial": heights["initial"], "box_stack_final": heights["final"],
                     "box_stack_gain": delta, "object_final_displacement": max(displacement)})
        box = objects["white_box"]
        displacement = float(np.linalg.norm(box[-1, :3] - box[0, :3]))
        # The default scene starts on the near side. An effectively unchanged
        # final position establishes that the box was not placed on the far side.
        return (False if displacement <= 0.01 else None, "white_box_final_displacement",
                {"object_final_displacement": displacement, "white_box_final_x": float(box[-1, 0])})
    except (ImportError, OSError, ValueError, AttributeError, KeyError, pickle.UnpicklingError, IndexError) as error:
        print(f"{path}: saved trajectory could not be audited: {error}", file=sys.stderr)
        return (None, None, {})


def candidate_records(run, out, db, inspect_saved):
    records = []
    if not run.directory or not run.directory.is_dir():
        return records
    generations = {int(p.name[4:]): p for p in run.directory.glob("gen_*") if p.name[4:].isdigit()}
    if run.group == "kso_retest" and (run.directory / "metrics.json").is_file():
        generations[4] = run.directory
    target = tolerance = None
    if run.group == "generated_scene" and run.workflow_directory:
        validation = read_json(run.workflow_directory / "validation.json") or {}
        task_catalog = read_json(run.workflow_directory / "task_catalog.json") or {}
        if validation.get("pass") is True:
            target = validation.get("target_xyz_m")
        tolerance = (task_catalog.get("tasks", {}).get("reach_position", {})
                     .get("completion_check", {}).get("maximum_error_m"))
    proposed_failures = {int(n) for n in re.findall(r"Failed to generate proposal for generation (\d+)", out)}
    for generation in sorted(generations.keys() | db.keys() | proposed_failures):
        folder = generations.get(generation, run.directory / f"gen_{generation}")
        result = folder / "results" if folder != run.directory else folder
        metrics = read_json(result / "metrics.json")
        x = read_json(result / "extra.json") or {}
        correction = read_json(result / "correct.json") or {}
        failure = read_json(folder / "failure.json")
        metadata = db.get(generation, {})
        public = (metrics or {}).get("public") or {}
        private = (metrics or {}).get("private") or {}
        diagnosis = x.get("ik_diagnosis") or private.get("ik_diagnosis") or {}
        verdict = {k: public.get(k, x.get(k)) for k in ("goal_match", "ik_feasible", "to_valid", "to_converged", "to_cost")}
        found = metrics is not None
        provisional = public.get("to_status") in ("pending", "skipped")
        proposal_failed = failure is not None or generation in proposed_failures
        source = (folder / "main.py").is_file()
        performance = telemetry.candidate_record(folder, result)
        started = (found or generation in db or (result / "job_log.out").is_file()
                   or bool(performance.get("evaluation_trace_status")))
        plan = x.get("contact_mode_seq")
        original_plan = x.get("original_contact_mode_seq")
        scored = x.get("scored") or private
        schedule_rejected = diagnosis.get("kind") == "schedule_error"
        repeated = public.get("is_duplicate") is True
        score = (metrics or {}).get("combined_score")
        error = correction.get("error") or (metrics or {}).get("error")
        violation = (public.get("violations") or [None])[0]
        solver_error = x.get("ik_import_error") or diagnosis.get("solver_error")
        if not solver_error and (x.get("to_import_error") or private.get("to_import_error")):
            solver_error = x.get("to_import_error") or private["to_import_error"]
        child_log = read_text(result / "job_log.out") + read_text(result / "job_log.err")
        program_error = correction.get("correct") is False or bool(error)
        if solver_error and "EOF when reading a line" in str(solver_error) and "t_renderer" in child_log:
            solver_error = f"t_renderer build failed: {solver_error}"
        returned = verdict["to_converged"] is not None or verdict["to_cost"] is not None
        to_attempted = returned or (result / "to_solver.log").is_file() or public.get("to_status") == "pending"
        contact_legal = (None if not found or repeated or program_error
                         else assess_contact(original_plan or plan, scored if not original_plan else private))
        contact_conversion_error = bool(solver_error and re.search(
            r"invalid contact schedule|expected \(\) or \(env_id,type\)", str(solver_error)
        ))
        if schedule_rejected or contact_conversion_error:
            contact_legal = False
        physics = x.get("to_physical") or {}
        goal = x.get("to_goal") or {}
        valid = verdict["to_valid"] is True
        segment_data = [s for s in x.get("to_segments") or [] if s.get("status") is not None]
        record = dict(verdict, generation=generation, found=found, provisional=provisional,
                      proposal_failed=proposal_failed, not_novel="NOT_NOVEL" in str((failure or {}).get("failure_reason", "")),
                      source=source, started=started, score=score, plan=plan, goal=goal, physics=physics,
                      completion=x.get("task_completion") or public.get("task_completion"),
                      generated_scene=run.group == "generated_scene",
                      validated_target_xyz=target, completion_tolerance_m=tolerance,
                      contact_legal=contact_legal, schedule_rejected=schedule_rejected,
                      contact_conversion_error=contact_conversion_error, contact_gate=verdict["goal_match"] is True and
                      (verdict["ik_feasible"] is not None or to_attempted) and not schedule_rejected,
                      program_error=program_error, solver_error=solver_error, to_attempted=to_attempted, returned=returned,
                      violation=violation, diagnosis=diagnosis, error=error,
                      to_fail_reason=x.get("to_fail_reason"), to_status=x.get("to_status"), segments=segment_data,
                      polish=(x.get("to_polish") or {}).get("time_s"), metadata=metadata,
                      program_time=(metrics or {}).get("execution_time_mean"), saved=(result / "to_run.pkl").is_file())
        record["semantic"], record["semantic_basis"], record["task_values"] = (
            inspect_task(run.scene, record, result / "to_run.pkl", inspect_saved) if valid else (None, None, {})
        )
        if proposal_failed:
            category = "proposal_not_novel" if record["not_novel"] else "proposal_failed"
        elif provisional or (started and not found):
            category = "evaluation_interrupted"
        elif contact_conversion_error:
            category = "contact_invalid"
        elif solver_error:
            dependency_error = re.search(r"make|t_renderer|ModuleNotFound|shared object",
                                         str(solver_error), re.I)
            category = "solver_environment_error" if dependency_error else "solver_exception"
        elif program_error:
            category = "program_error"
        elif not found:
            category = "unsubmitted_artifact"
        elif repeated:
            category = "duplicate_plan"
        elif "too many contact modes" in (violation or "").lower():
            category = "plan_over_mode_cap"
        elif public.get("num_modes", 2) < 2:
            category = "plan_too_short"
        elif contact_legal is False:
            category = "contact_invalid"
        elif verdict["goal_match"] is False:
            category = "discrete_goal_miss"
        elif verdict["ik_feasible"] is False:
            category = "kso_infeasible"
        elif returned and not valid:
            category = "to_invalid"
        elif not valid:
            category = "unclassified_no_trajectory"
        else:
            category = "usable_trajectory"
        record["category"] = category
        record["performance"] = performance
        records.append(record)
    return records


def aggregate_candidates(records, db, eval_limit):
    counts = Counter()
    failures, detail, physical_fails = Counter(), Counter(), Counter()
    for r in records:
        cat = r["category"]
        if cat != "usable_trajectory":
            failures[cat] += 1
        detail_value = r["error"] or r["solver_error"] or r["to_fail_reason"]
        # Goal and schedule feedback includes exact per-candidate indices.
        # Category totals stay comparable while raw reasons remain auditable.
        if not detail_value and cat in {"contact_invalid", "kso_infeasible", "to_invalid", "discrete_goal_miss"}:
            detail_value = r["violation"]
        if detail_value and cat != "usable_trajectory":
            detail[str(detail_value)] += 1
        if r["to_valid"] is not True:
            physical_fails.update(r["physics"].get("fails") or [])
        duration = r["metadata"].get("evaluation_seconds")
        counts.update({key: int(bool(flag)) for key, flag in {
            "program_files_written": r["source"],
            "candidate_generated": r["started"] and not r["proposal_failed"],
            "initial_programs": r["started"] and r["generation"] == 0,
            "candidate_proposed": r["started"] and r["generation"] > 0,
            "evaluations_started": r["started"],
            "metrics_records": r["found"],
            "provisional_metrics": r["provisional"],
            "evaluations_completed": r["found"] and not r["provisional"],
            "contact_checked": r["contact_legal"] is not None,
            "contact_legal": r["contact_legal"] is True,
            "contact_gate_pass": r["contact_gate"],
            "schedule_rejected": r["schedule_rejected"],
            "discrete_goal_match": r["goal_match"] is True,
            "kso_pass": r["ik_feasible"] is True,
            "to_attempted": r["to_attempted"],
            "to_returned": r["returned"],
            "to_converged": r["to_converged"] is True,
            "to_valid": r["to_valid"] is True,
            "physical_checks_pass": r["physics"].get("pass") is True,
            "nonzero_score": isinstance(r["score"], (int, float)) and r["score"] != 0,
            "terminal_goal_checked": r["goal"].get("met") is not None,
            "terminal_goal_met": r["goal"].get("met") is True,
            "valid_with_terminal_goal_met": r["to_valid"] is True and r["goal"].get("met") is True,
            "semantic_checked": r["semantic"] is not None,
            "task_completed": r["semantic"] is True,
            "task_failed": r["semantic"] is False,
            "proposal_failures": r["proposal_failed"],
            "proposal_not_novel": r["not_novel"],
            "program_errors": r["program_error"],
            "contact_invalid": r["contact_legal"] is False,
            "kso_failures": r["ik_feasible"] is False and r["contact_gate"] and not r["solver_error"],
            "to_failures": r["returned"] and r["to_valid"] is False,
            "candidate_system_errors": cat == "solver_environment_error",
            "contact_conversion_errors": r["contact_conversion_error"],
            "evaluation_interrupted": cat == "evaluation_interrupted",
            "evaluation_timeout_near_limit": cat == "evaluation_interrupted" and duration and
            eval_limit and 0.98 * eval_limit <= duration <= 1.02 * eval_limit,
            "evaluation_timeout_confirmed": cat == "evaluation_interrupted" and
            re.search(r"(?:timed out|exceeded timeout)", str(r["error"] or ""), re.I),
        }.items()})
    counts["db_programs"] = len(db)
    summary = {key: counts[key] for key in CANDIDATE_COUNTS}
    summary.update(failure_categories=compact(failures), failure_details=compact(detail),
                   to_physical_failure_checks=compact(physical_fails))
    summary.update(
        kso_diagnosis_s=recorded_sum(r["diagnosis"].get("diagnosis_seconds") for r in records),
        to_segment_build_s=recorded_sum(s.get("build_time_s") for r in records for s in r["segments"]),
        to_segment_solve_s=recorded_sum(s.get("solve_time_s") for r in records for s in r["segments"]),
        to_polish_s=recorded_sum(r["polish"] for r in records),
        planner_function_s=recorded_sum(r["program_time"] for r in records),
        proposal_sampling_s=recorded_sum(m.get("sampling_seconds") for m in db.values()),
        evaluation_pipeline_s=recorded_sum(m.get("evaluation_seconds") for m in db.values()),
        kso_diagnosis_records=sum(r["diagnosis"].get("diagnosis_seconds") is not None for r in records),
        to_segment_records=sum(len(r["segments"]) for r in records),
        db_evaluation_timing_records=sum(m.get("evaluation_seconds") is not None for m in db.values()),
        metrics_missing_generations=compact([r["generation"] for r in records if r["started"] and not r["found"]]),
        provisional_generations=compact([r["generation"] for r in records if r["provisional"]]),
        proposal_failed_generations=compact([r["generation"] for r in records if r["proposal_failed"]]),
    )
    valid = [r for r in records if r["to_valid"] is True]
    summary["usable_trajectory_files"] = sum(r["saved"] for r in valid)
    summary["distinct_usable_contact_plans"] = len({plan_hash(r["plan"]) for r in valid if r["plan"]})
    summary["distinct_completed_contact_plans"] = len({
        plan_hash(r["plan"]) for r in valid if r["semantic"] is True and r["plan"]
    })
    if counts["task_completed"]:
        summary["task_outcome"] = "confirmed_completed"
    elif valid and counts["task_failed"] == len(valid):
        summary["task_outcome"] = "all_usable_trajectories_failed_task_check"
    elif valid:
        summary["task_outcome"] = "undetermined"
    else:
        summary["task_outcome"] = "no_usable_trajectory"
    for prefix, pool in (
        ("best_valid", valid),
        ("best_to_scored", [r for r in records if r["returned"]]),
    ):
        scored = [r for r in pool if isinstance(r["score"], (int, float)) and math.isfinite(r["score"])]
        if scored:
            best = max(scored, key=lambda r: (r["score"], -r["generation"]))
            summary.update({f"{prefix}_{key}": best[key] for key in ("generation", "score", "to_cost", "to_valid", "to_converged")})
            summary[f"{prefix}_task_check"] = best["semantic"]
    semantic_rows = {r["generation"]: dict(r["task_values"], basis=r["semantic_basis"], met=r["semantic"])
                     for r in valid if r["semantic_basis"]}
    summary["usable_task_evidence"] = compact(semantic_rows)
    return summary


def slurm_fields(row, batch):
    allocation = dict(item.split("=", 1) for item in (row.get("AllocTRES") or "").split(",") if "=" in item)
    usage = dict(item.split("=", 1) for item in (batch.get("TRESUsageInMax") or "").split(",") if "=" in item)
    gpu_count = allocation.get("gres/gpu")
    elapsed = int(row["ElapsedRaw"]) if row.get("ElapsedRaw", "").isdigit() else None
    total_cpu = seconds(row.get("TotalCPU"))
    cpu_capacity = int(row["CPUTimeRAW"]) if row.get("CPUTimeRAW", "").isdigit() else None
    return dict(slurm_job_id_raw=row.get("JobIDRaw"), slurm_state=row.get("State"),
                job_exit_code=row.get("ExitCode"), derived_exit_code=row.get("DerivedExitCode"),
                batch_state=batch.get("State"), batch_exit_code=batch.get("ExitCode"),
                start_local=row.get("Start"), end_local=row.get("End"), wall_s=elapsed,
                slurm_time_limit_s=seconds(row.get("Timelimit")), partition=row.get("Partition"),
                node=row.get("NodeList"), alloc_cpus=row.get("AllocCPUS"),
                alloc_cpu_s=cpu_capacity, total_cpu_s=total_cpu, user_cpu_s=seconds(row.get("UserCPU")),
                system_cpu_s=seconds(row.get("SystemCPU")),
                average_cpu_cores=round(total_cpu / elapsed, 5) if elapsed and total_cpu is not None else None,
                alloc_cpu_fraction=round(total_cpu / cpu_capacity, 6) if cpu_capacity and total_cpu is not None else None,
                req_mem=row.get("ReqMem"), req_mem_gib=gib(row.get("ReqMem")),
                batch_max_rss=batch.get("MaxRSS"), batch_max_rss_gib=gib(batch.get("MaxRSS")),
                batch_ave_rss=batch.get("AveRSS"), batch_max_vm_size=batch.get("MaxVMSize"),
                alloc_gpus=gpu_count, alloc_gpu_h=round(elapsed * int(gpu_count) / 3600, 6) if elapsed is not None and gpu_count and gpu_count.isdigit() else None,
                batch_gpu_util_tres=usage.get("gres/gpuutil"), batch_gpu_mem_tres=usage.get("gres/gpumem"),
                req_tres=row.get("ReqTRES"), alloc_tres=row.get("AllocTRES"),
                batch_tres_usage_in_ave=batch.get("TRESUsageInAve"),
                batch_tres_usage_in_max=batch.get("TRESUsageInMax"),
                batch_tres_usage_in_tot=batch.get("TRESUsageInTot"))


def terminal_status(run, state, out, err, budget, complete, records):
    reason = None
    if state == "OUT_OF_MEMORY" or "oom_kill" in err:
        return "out_of_memory", "system", "Slurm/cgroup host-memory OOM"
    if state and state.startswith(("TIMEOUT", "CANCELLED", "PREEMPTED", "NODE_FAIL", "BOOT_FAIL")):
        return state.lower(), "system", state
    for pattern, label in (
        ("Could not override 'evo_config.max_novelty_attempts'", "Hydra strict override syntax"),
        ("No module named 'examples'", "Python import path: examples"),
        ("cd: boxes: No such file or directory", "shell quoting of scene description"),
        ("No module named '_run_common'", "Python import path: _run_common"),
        ("cmake: command not found", "missing cmake"),
        ("CMAKE_MAKE_PROGRAM is not set", "CMake build tool/compiler unavailable"),
        ("unrecognized option '--zstd'", "tar lacks --zstd"),
        ("GLIBC_2.3", "t_renderer GLIBC mismatch"),
    ):
        if pattern in err:
            reason = label
            break
    if state in {"FAILED", "DEADLINE"} or reason:
        return "failed", "system", reason or state
    if run.group == "kso_retest" and any(r["category"] == "solver_environment_error" for r in records):
        return "completed_solver_environment_error", "system", "missing solver build dependency"
    if state in {"PENDING", "RUNNING", "COMPLETING"}:
        return state.lower(), None, None
    if run.group in {"campaign", "standalone_search", "generated_scene"} and budget and complete < budget:
        if "API cost budget reached:" in out:
            return "cost_budget_early_stop", "configuration", "API cost budget reached before the node budget"
        if "budget exhausted" in out.lower():
            return "budget_underfilled", "algorithm" if all(r["category"] != "evaluation_interrupted" for r in records) else "mixed", "generation slots exhausted"
        if state == "COMPLETED" or "completed successfully" in out:
            return "evaluation_incomplete", "unknown", "fewer final metrics than budget"
    if state == "COMPLETED" or "Campaign scene completed:" in out or "completed successfully" in out or "KSO retest completed;" in out:
        if any(r["category"] == "evaluation_interrupted" for r in records):
            return "evaluation_incomplete", "unknown", "one or more evaluations interrupted"
        return "completed", None, None
    return "unknown", None, None


def run_record(root, jobs, campaign, run, inspect_saved):
    cfg_path = run.directory / ".hydra/config.yaml" if run.directory else None
    cfg = read_text(cfg_path)
    stem = run.logs(root) / f"md-{run.log_kind}-{run.job_id}"
    out_path, err_path = stem.with_suffix(".out"), stem.with_suffix(".err")
    out, err = read_text(out_path), read_text(err_path)
    job = jobs.get(run.job_id, {})
    batch = jobs.get(run.job_id + ".batch", {})
    if not batch and job.get("JobIDRaw"):
        batch = jobs.get(job["JobIDRaw"] + ".batch", {})
    job_events = stem.with_suffix(".performance.jsonl")
    job_rows = telemetry.events(job_events)
    job_start = telemetry.last_event(job_rows, "job_start")
    raw_id = job.get("JobIDRaw") or job_start.get("raw_job_id") or run.job_id
    server_path = run.logs(root) / f"md-{run.log_kind}-server-{raw_id}.log"
    server = read_text(server_path)
    workflow = (read_json(run.workflow_directory / "result.json") or {}) if run.workflow_directory else {}
    generation_rows = telemetry.events(run.workflow_directory / "scene_generation_performance.jsonl") if run.workflow_directory else []
    generation_config = telemetry.last_event(generation_rows, "scene_generation_config")
    budget = scalar(cfg, "num_generations") or first(out, r"^Scene: .*\| nodes: (\d+)")
    if not budget and job_start.get("budget") is not None:
        budget = str(job_start["budget"])
    if not budget and generation_config.get("node_budget") is not None:
        budget = str(generation_config["node_budget"])
    entry = next((item for item in campaign if item["scene"] == run.scene), {})
    if not budget and run.group == "campaign":
        budget = entry.get("nodes")
    if not budget and run.log_kind == "box-smoke":
        budget = "10"
    budget = int(budget) if budget and budget.isdigit() else None
    scene = scalar(cfg, "scene") or run.scene
    run.scene = scene
    evaluation_limit = seconds(scalar(cfg, "time"))
    search = run.group in {"campaign", "standalone_search"} or (
        run.group == "generated_scene" and run.directory is not None
    )
    stats = {}
    db = read_program_db(run.directory) if search else {}
    candidates = candidate_records(run, out, db, inspect_saved)
    if search or run.group == "kso_retest":
        stats = aggregate_candidates(candidates, db, evaluation_limit)
        if run.group == "kso_retest":
            for key in ("candidate_generated", "initial_programs", "candidate_proposed", "program_files_written", "db_programs"):
                stats[key] = None
    if search or run.group in {"generated_scene", "model_probe"}:
        stats.update(request_times(server, separate_scene_generation=run.group == "generated_scene"))
    slurm = slurm_fields(job, batch)
    job_end = telemetry.last_event(job_rows, "job_end")
    run_end = telemetry.last_event(
        telemetry.events(run.directory / "run_performance.jsonl") if run.directory else [], "phase_end"
    )
    reported_state = slurm["slurm_state"]
    if not reported_state and job_end.get("exit_code") is not None:
        reported_state = "COMPLETED" if job_end["exit_code"] == 0 else (
            "FAILED" if job_end["exit_code"] not in (130, 143) else None
        )
    if not reported_state and run_end.get("stage") == "search":
        reported_state = "FAILED" if run_end.get("exception") else "COMPLETED"
    status, failure_class, reason = terminal_status(
        run, reported_state, out, err, budget, stats.get("evaluations_completed", 0), candidates
    )
    if run.group == "generated_scene" and reported_state in (None, "COMPLETED", "FAILED"):
        if workflow.get("status") in ("validation_exhausted", "no_valid_trajectory"):
            status = workflow["status"]
            failure_class, reason = "algorithm", status
    search_status = None
    if run.group == "generated_scene" and search:
        launcher_code = workflow.get("launcher_exit_code")
        search_state = reported_state
        if launcher_code is not None:
            search_state = "COMPLETED" if launcher_code == 0 else "FAILED"
        search_status, _, _ = terminal_status(
            run, search_state, out, err, budget, stats.get("evaluations_completed", 0), candidates
        )
    stamps = re.findall(r"(?m)^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+)", out)
    settings = {}
    if cfg:
        for key in ("num_islands", "archive_size", "max_patch_attempts", "max_api_costs",
                    "max_evaluation_jobs", "max_proposal_jobs", "evolve_prompts", "meta_rec_interval",
                    "score_mode", "diversity", "initial_condition"):
            settings[key] = scalar(cfg, key)
        settings["max_novelty_attempts"] = scalar(cfg, "max_novelty_attempts") or "3 (code default)"
    model_manifest = dict(re.findall(r"(?m)^(qwen\S+|embeddinggemma:\S+)\s+([0-9a-f]{12})\s", out))
    if not model_manifest and run.group == "generated_scene":
        digests = telemetry.last_event(job_rows, "ollama_models").get("model_digests", {})
        model_manifest = {name: digest.removeprefix("sha256:")[:12]
                          for name, digest in digests.items()}
    planner_model = first(cfg, r"llm_models:\s+- local/([^@\s]+)")
    helper_model = first(cfg, r"novelty_llm_models:\s+- local/([^@\s]+)")
    embedding_model = first(cfg, r"embedding_model: local/([^@\s]+)")
    if run.group == "campaign" and model_manifest and not cfg:
        planner_model, helper_model, embedding_model = "qwen2.5-coder:14b", "qwen2.5-coder:7b", "embeddinggemma"
    identified_dir = run.workflow_directory or run.directory
    fields = dict(run_group=run.group, scene=scene, job_id=run.job_id,
                  run_id=identified_dir.name if identified_dir else run.job_id,
                  status=status, job_failure_class=failure_class, job_failure_reason=reason,
                  node_budget=budget, eval_limit_s=evaluation_limit,
                  motiondisco_commit=first(out, r"^MotionDisco commit: (\w+)"),
                  faro_commit=first(out, r"^FARO commit: (\w+)"), random_seed=scalar(cfg, "seed"),
                  seed_evidence="recorded config" if scalar(cfg, "seed") else "unrecorded" if search else None,
                  planner_model=planner_model, helper_model=helper_model, embedding_model=embedding_model,
                  model_evidence="hydra_config" if cfg and planner_model else "campaign_manifest_and_launcher" if planner_model else None,
                  model_manifest_ids=compact(model_manifest) if model_manifest else None,
                  ollama_version=first(server, r"Listening on [^\n]+\(version ([^)]+)\)"),
                  ollama_max_loaded_models=first(server, r"OLLAMA_MAX_LOADED_MODELS:(\d+)"),
                  cpu_model=first(server, r"- CPU\s+: ([^\r\n(]+?)\s*\("),
                  gpu_model=first(server, r' msg="inference compute"[^\n]+description="([^"]+)"'),
                  database=first(read_text(run.directory / ".hydra/overrides.yaml") if run.directory else "", r"database(?:@_global_)?=(\S+)"),
                  evolution=first(read_text(run.directory / ".hydra/overrides.yaml") if run.directory else "", r"evolution(?:@_global_)?=(\S+)"),
                  search_settings=compact(settings) if settings else None,
                  search_config_path=str(cfg_path.relative_to(root)) if cfg_path and cfg_path.is_file() else None,
                  description=scalar(cfg, "description") or entry.get("description"),
                  results_path=str(run.directory.relative_to(root)) if run.directory and run.directory.is_relative_to(root) else run.directory,
                  job_stdout=str(out_path.relative_to(root)) if out_path.is_file() else None,
                  job_stderr=str(err_path.relative_to(root)) if err_path.is_file() else None,
                  ollama_log=str(server_path.relative_to(root)) if server_path.is_file() else None,
                  launcher_first_log=stamps[0] if stamps else None, launcher_last_log=stamps[-1] if stamps else None,
                  **slurm)
    if run.group == "render":
        fields.update(render_job_wall_s=slurm["wall_s"], render_encoded_frames=first(out, r"\((\d+) frames from"),
                      render_source_qpos=first(out, r"frames from (\d+) qpos samples"),
                      render_resolution=first(out, r"fps=\d+, (\d+x\d+)"))
    fields.update(stats)
    fields.update(telemetry.run_record(run.directory, job_events, stem.with_suffix(".gpu.jsonl"),
                                       slurm, candidates, generation_config))
    if run.group == "generated_scene":
        fields.update(scene_workflow_status=workflow.get("status"), scene_search_status=search_status,
                      scene_workflow_error=workflow.get("error"), search_launcher_exit_code=workflow.get("launcher_exit_code"),
                      scene_artifacts_path=str(run.workflow_directory) if run.workflow_directory else None,
                      **telemetry.scene_generation_record(generation_rows))
    return fields, candidates


def plan_hash(plan):
    return hashlib.sha256(compact(plan).encode()).hexdigest()


def summarize(rows, candidates_by_run):
    groups = defaultdict(list)
    for row in rows:
        if row["scene"]:
            groups[row["run_group"], row["scene"]].append(row)
    summaries = []
    for (group, scene), members in sorted(groups.items()):
        candidate_lists = [candidates_by_run[row["results_path"] or row["job_id"]] for row in members]
        valid = [c for records in candidate_lists for c in records if c["to_valid"] is True]
        wall = [row["wall_s"] for row in members if row["wall_s"] is not None]
        evaluated_wall = [row["wall_s"] for row in members if row.get("evaluations_started") and row["wall_s"] is not None]
        rss = [row["batch_max_rss_gib"] for row in members if row["batch_max_rss_gib"] is not None]
        cpu = recorded_sum(row["total_cpu_s"] for row in members)
        failure = Counter()
        for row in members:
            failure.update(json.loads(row.get("failure_categories") or "{}"))
        best_rows = [row for row in members if row.get("best_valid_score") is not None]
        best = max(best_rows, key=lambda row: row["best_valid_score"]) if best_rows else {}
        best_task_rows = [(c["score"], row["job_id"], c["generation"], c["to_cost"]) for row, cs in zip(members, candidate_lists)
                          for c in cs if c["semantic"] is True and isinstance(c["score"], (int, float))]
        top_task = max(best_task_rows, default=(None, None, None, None))
        result = dict(run_group=group, scene=scene, runs=len(members),
                      job_ids=compact([row["job_id"] or row["run_id"] for row in members]),
                      run_status_counts=compact(Counter(row["status"] for row in members)),
                      slurm_state_counts=compact(Counter(row["slurm_state"] for row in members if row["slurm_state"])),
                      jobs_started_search_eval=sum(bool(row.get("evaluations_started")) for row in members),
                      runs_with_usable_trajectory=sum(bool(row.get("to_valid")) for row in members),
                      runs_with_task_completed=sum(bool(row.get("task_completed")) for row in members),
                      distinct_usable_contact_plans=len({plan_hash(c["plan"]) for c in valid if c["plan"]}) if valid else 0,
                      distinct_completed_contact_plans=len({plan_hash(c["plan"]) for c in valid
                                                            if c["plan"] and c["semantic"] is True}),
                      usable_plan_hash_coverage=sum(bool(c["plan"]) for c in valid),
                      wall_s_total=recorded_sum(wall), wall_s_min=min(wall, default=None),
                      wall_s_median=median(wall) if wall else None, wall_s_max=max(wall, default=None),
                      evaluated_run_wall_s_min=min(evaluated_wall, default=None),
                      evaluated_run_wall_s_median=median(evaluated_wall) if evaluated_wall else None,
                      evaluated_run_wall_s_max=max(evaluated_wall, default=None),
                      wall_records=len(wall), evaluated_run_wall_records=len(evaluated_wall),
                      total_cpu_h=round(cpu / 3600, 6) if cpu is not None else None,
                      alloc_cpu_h=recorded_sum(row["alloc_cpu_s"] / 3600 for row in members if row["alloc_cpu_s"] is not None),
                      alloc_gpu_h=recorded_sum(row["alloc_gpu_h"] for row in members),
                      max_rss_gib_min=min(rss, default=None), max_rss_gib_max=max(rss, default=None),
                      rss_records=len(rss), failure_categories=compact(failure),
                      best_valid_job_id=best.get("job_id"), best_valid_generation=best.get("best_valid_generation"),
                      best_valid_score=best.get("best_valid_score"), best_valid_to_cost=best.get("best_valid_to_cost"),
                      best_task_score=top_task[0], best_task_job_id=top_task[1],
                      best_task_generation=top_task[2], best_task_to_cost=top_task[3])
        for key in (["node_budget", "usable_trajectory_files", "gpu_sample_count", "scene_llm_attempts",
                     "scene_llm_responses", "scene_validation_failures"] + CANDIDATE_COUNTS + list(telemetry.COUNTS)):
            values = [row[key] for row in members if row.get(key) is not None]
            result[key + "_total"] = sum(values) if values else None
        for key in dict.fromkeys(RUN_TIMES + list(telemetry.TIMES)):
            result[key + "_total"] = recorded_sum(row.get(key) for row in members)
        for key in ("scene_object_count", "scene_movable_object_count", "carry_goal_distance_m", "robot_goal_distance_m",
                    "max_returned_object_displacement_m", "max_returned_object_path_length_m",
                    "gpu_sampled_util_peak_pct", "gpu_sampled_vram_peak_mib"):
            result[key + "_max"] = max((row[key] for row in members if row.get(key) is not None), default=None)
        result["gpu_sampled_runs"] = (sum(bool(row.get("gpu_sample_count")) for row in members)
                                      if any(row.get("gpu_sample_count") is not None for row in members) else None)
        summary_observed = result["metrics_records_total"]
        result["usable_per_metrics_record"] = round(len(valid) / summary_observed, 6) if summary_observed else None
        result["alloc_gpu_h_per_usable"] = round(result["alloc_gpu_h"] / len(valid), 6) if valid and result["alloc_gpu_h"] is not None else None
        completed = result["task_completed_total"]
        result["alloc_gpu_h_per_completed"] = (
            round(result["alloc_gpu_h"] / completed, 6) if completed and result["alloc_gpu_h"] is not None else None
        )
        summaries.append(result)
    return summaries


def write_csv(path, rows, expected_columns=()):
    fields = list(dict.fromkeys(list(rows[0]) + list(expected_columns) + [key for row in rows for key in row])) if rows else list(expected_columns)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--sacct", type=Path, help="read an existing pipe-delimited Slurm snapshot")
    parser.add_argument("--refresh-sacct", action="store_true", help="query Slurm and save a new snapshot")
    parser.add_argument("--since", default="2026-11-01", help="accounting query start date")
    parser.add_argument("--job-id", help="report on one Slurm job or array task")
    parser.add_argument("--skip-trajectory-audit", action="store_true", help="skip offline NumPy trajectory diagnostics")
    args = parser.parse_args()
    root = args.root.resolve()
    with (root / "scripts/qwen_campaign.tsv").open(newline="") as stream:
        campaign = list(csv.DictReader(stream, delimiter="\t"))
    jobs = accounting_source(args, root)
    rows, records, candidate_rows = [], {}, []
    for run in discover(root, jobs, campaign):
        if args.job_id and run.job_id != args.job_id:
            continue
        row, candidates = run_record(root, jobs, campaign, run, not args.skip_trajectory_audit)
        rows.append(row)
        records[row["results_path"] or row["job_id"]] = candidates
        for candidate in candidates:
            if candidate.get("performance") or run.group == "generated_scene":
                candidate_rows.append(dict(
                    run_id=row["run_id"], job_id=row["job_id"], scene=row["scene"],
                    generation=candidate["generation"], failure_category=candidate["category"],
                    to_valid=candidate["to_valid"], to_converged=candidate["to_converged"],
                    failure_detail=(candidate["error"] or candidate["solver_error"] or
                                    candidate["to_fail_reason"] or candidate["violation"]),
                    candidate_started=candidate["started"], metrics_present=candidate["found"],
                    provisional=candidate["provisional"], contact_legal=candidate["contact_legal"],
                    discrete_goal_match=candidate["goal_match"], kso_pass=candidate["ik_feasible"],
                    to_attempted=candidate["to_attempted"], to_returned=candidate["returned"], to_status=candidate["to_status"],
                    combined_score=candidate["score"], to_cost=candidate["to_cost"],
                    to_physical_pass=candidate["physics"].get("pass"),
                    to_physical_fails=compact(candidate["physics"]["fails"]) if "fails" in candidate["physics"] else None,
                    to_terminal_goal_met=candidate["goal"].get("met"),
                    trajectory_saved=candidate["saved"], task_audit_met=candidate["semantic"],
                    task_audit_basis=candidate["semantic_basis"], task_audit_error_m=candidate["task_values"].get("error_m"),
                    task_audit_details=compact(candidate["task_values"]) if candidate["task_values"] else None,
                    task_completion_met=(candidate.get("completion") or {}).get("met"),
                    task_completion_error_m=(candidate.get("completion") or {}).get("error_m"),
                    **candidate["performance"],
                ))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_columns = CANDIDATE_COUNTS + RUN_TIMES + list(telemetry.TIMES + telemetry.COUNTS + telemetry.RUN_FIELDS)
    write_csv(args.output_dir / "motiondisco_runs.csv", rows, run_columns)
    if candidate_rows:
        write_csv(args.output_dir / "motiondisco_candidate_performance.csv", candidate_rows, telemetry.TIMES)
    write_csv(args.output_dir / "motiondisco_scene_summary.csv", summarize(rows, records))
    groups = Counter(row["run_group"] for row in rows)
    print(f"Wrote {len(rows)} job/run rows: {dict(groups)}")


if __name__ == "__main__":
    main()
