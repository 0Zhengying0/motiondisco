#!/usr/bin/env python3
"""Summarize completed and in-progress Qwen campaign runs as CSV."""

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "scripts/qwen_campaign.tsv"
RESULTS = ROOT / "results/md_qwen_campaign"
OUTPUT = ROOT / "results/qwen_campaign_summary.csv"
TIMESTAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\]")
JOB_NAME = re.compile(r"^job_(\d+)_(\d+)_ollama$")


def job_logs(run_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    match = JOB_NAME.match(run_dir.name)
    if not match:
        return None, None
    stem = f"md-campaign-{match.group(1)}_{match.group(2)}"
    return ROOT / "logs" / f"{stem}.out", ROOT / "logs" / f"{stem}.err"


def elapsed_hours(log: Optional[Path]) -> str:
    if log is None or not log.exists():
        return ""
    first = last = None
    with log.open(errors="replace") as stream:
        for line in stream:
            match = TIMESTAMP.match(line)
            if match:
                stamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                first = first or stamp
                last = stamp
    return f"{(last - first).total_seconds() / 3600:.2f}" if first and last else ""


def main() -> None:
    with TABLE.open(newline="") as stream:
        scenes = list(csv.DictReader(stream, delimiter="\t"))

    rows = []
    for item in scenes:
        scene = item["scene"]
        target = int(item["nodes"])
        run_dirs = sorted((RESULTS / scene.rsplit(".", 1)[-1]).glob("job_*_ollama"))
        if not run_dirs:
            rows.append([scene, "", target, 0, 0, 0, 0, "", "", "", "", "pending"])
            continue

        for run_dir in run_dirs:
            out_log, err_log = job_logs(run_dir)
            metrics = []
            for path in run_dir.glob("gen_*/results/metrics.json"):
                try:
                    generation = int(path.parent.parent.name.split("_", 1)[1])
                    data = json.loads(path.read_text())
                    metrics.append((generation, data))
                except (ValueError, json.JSONDecodeError, OSError):
                    continue

            valid = [
                (generation, data)
                for generation, data in metrics
                if data.get("public", {}).get("to_valid") is True
            ]
            converged = sum(
                data.get("public", {}).get("to_converged") is True
                for _, data in metrics
            )
            best = max(valid, key=lambda pair: float(pair[1].get("combined_score", 0))) if valid else None
            failures = Counter(
                str((data.get("public", {}).get("violations") or [""])[0])
                for _, data in metrics
                if data.get("public", {}).get("to_valid") is not True
            )
            finished = bool(out_log and out_log.exists() and "Campaign scene completed:" in out_log.read_text(errors="replace"))
            oom = bool(err_log and err_log.exists() and "oom_kill" in err_log.read_text(errors="replace"))
            status = "out_of_memory" if oom else "complete" if finished and len(metrics) >= target else "incomplete" if finished else "running"
            rows.append([
                scene, run_dir.name, target, len(metrics), int(bool(valid)), len(valid), converged,
                f"{best[1]['combined_score']:.6f}" if best else "",
                best[0] if best else "",
                elapsed_hours(out_log),
                failures.most_common(1)[0][0][:160] if failures else "",
                status,
            ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "scene", "run", "nodes_target", "nodes_observed", "scene_success",
            "valid_plans", "to_converged", "best_valid_score", "best_generation",
            "elapsed_hours", "top_failure", "status",
        ])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
