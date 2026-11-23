#!/usr/bin/env python3
"""Host-side Slurm lifecycle and allocated-GPU sampling (Python 3.6+)."""

import argparse
import csv
import json
import logging
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time


def append(path, event, **fields):
    payload = {"event": event, "version": 1, "unix_s": time.time(), **fields}
    with open(path, "a") as stream:
        stream.write(json.dumps(payload, allow_nan=False) + "\n")


def selectors():
    """Read the Slurm allocation without assuming its local GPU numbering."""
    for name in ("SLURM_STEP_GPUS", "SLURM_JOB_GPUS"):
        value = os.environ.get(name, "")
        if value and all(re.fullmatch(r"\d+|GPU-[\w-]+", item) for item in value.split(",")):
            return value.split(","), name
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")
    if all(item.startswith("GPU-") for item in visible):
        return visible, "CUDA_VISIBLE_DEVICES_UUID"
    return [None], "single_visible_device"


def number(value):
    try:
        return int(value)
    except ValueError:
        return None


def gpu_command(device):
    command = [
        "nvidia-smi",
        "--query-gpu=uuid,name,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    if device is not None:
        command.append("--id=" + device)
    return command


def query_gpus(device=None):
    result = subprocess.run(gpu_command(device), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=5, check=True)
    rows = list(csv.reader(result.stdout.splitlines(), skipinitialspace=True))
    if not rows or any(len(row) != 5 for row in rows):
        raise ValueError("unexpected nvidia-smi GPU query output")
    return [{"uuid": uuid, "gpu_model": name, "gpu_util_pct": number(util),
             "vram_used_mib": number(used), "vram_total_mib": number(total)}
            for uuid, name, util, used, total in rows]


def diagnostic_output(value):
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return (value or "")[:1024]


def sample(path, interval, job_id):
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    devices, source = selectors()
    parent = os.getppid()
    errors = set()

    def record_error(device, exc):
        reason = type(exc).__name__
        exit_code = getattr(exc, "returncode", None)
        key = (device, reason, exit_code)
        if key not in errors:
            append(path, "sampler_error", job_id=job_id, error=reason,
                   command=gpu_command(device), exit_code=exit_code, message=str(exc),
                   stdout=diagnostic_output(getattr(exc, "stdout", None)),
                   stderr=diagnostic_output(getattr(exc, "stderr", None)))
            errors.add(key)

    append(path, "sampler_start", job_id=job_id, interval_s=interval, selector_source=source)
    try:
        if all(device is not None and device.isdigit() for device in devices):
            # On Karolina the job cgroup exposes only the allocated GPUs and
            # NVML renumbers them. Use UUIDs once visibility matches the allocation.
            try:
                visible = {gpu["uuid"] for gpu in query_gpus()}
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                record_error(None, exc)
            else:
                if len(visible) == len(devices) and all(uuid.startswith("GPU-") for uuid in visible):
                    devices = sorted(visible)
                    append(path, "sampler_selection", job_id=job_id, method="visible_uuids", devices=devices)
        while not stop.is_set() and os.getppid() == parent:
            started = time.monotonic()
            for device in devices:
                if stop.is_set():
                    break
                try:
                    samples = query_gpus(device)
                    if len(samples) != 1:
                        raise ValueError("cannot identify a single allocated GPU")
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    record_error(device, exc)
                else:
                    append(path, "gpu_sample", job_id=job_id, **samples[0])
            stop.wait(max(0, interval - (time.monotonic() - started)))
    finally:
        append(path, "sampler_end", job_id=job_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation")
    launch = sub.add_parser("start")
    launch.add_argument("path")
    launch.add_argument("job_id")
    launch.add_argument("scene")
    launch.add_argument("budget", type=int)
    launch.add_argument("seed", type=int)
    launch.add_argument("seed_source")
    launch.add_argument("motiondisco_commit")
    launch.add_argument("faro_commit")
    end = sub.add_parser("end")
    end.add_argument("path")
    end.add_argument("job_id")
    end.add_argument("exit_code", type=int)
    models = sub.add_parser("models")
    models.add_argument("path")
    models.add_argument("job_id")
    gpu = sub.add_parser("sample")
    gpu.add_argument("path")
    gpu.add_argument("job_id")
    gpu.add_argument("--interval", type=float, default=15)
    sub.add_parser("seed")
    args = parser.parse_args()
    try:
        if args.operation == "seed":
            print(secrets.randbelow(2**31))
        elif args.operation == "start":
            append(args.path, "job_start", job_id=args.job_id, raw_job_id=os.getenv("SLURM_JOB_ID"),
                   scene=args.scene, budget=args.budget, configured_seed=args.seed,
                   seed_source=args.seed_source, motiondisco_commit=args.motiondisco_commit,
                   faro_commit=args.faro_commit)
        elif args.operation == "end":
            append(args.path, "job_end", job_id=args.job_id, exit_code=args.exit_code)
        elif args.operation == "models":
            digests = {model["name"]: model["digest"] for model in json.load(sys.stdin)["models"]}
            append(args.path, "ollama_models", job_id=args.job_id, model_digests=digests)
        elif args.operation == "sample":
            sample(args.path, max(5, args.interval), args.job_id)
        else:
            parser.error("select an operation")
    except (OSError, ValueError, KeyError) as exc:
        logging.warning("Karolina performance recorder: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
