#!/usr/bin/env python3
"""
Aggregate individual run results into benchmark summary statistics.

Reads grading.json files from run directories and produces:
- run_summary with mean, stddev, min, max for each metric
- delta between with_skill and without_skill configurations
- step_summary (only for step-level runs from run_step_eval.py): pass rate,
  output consistency and own vs inherited failures per step x model

Usage:
    python aggregate_benchmark.py <benchmark_dir>

Example:
    python aggregate_benchmark.py benchmarks/2026-01-15T10-30-00/

The script supports two directory layouts:

    Workspace layout (from skill-creator iterations):
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── without_skill/
            ├── run-1/grading.json
            └── run-2/grading.json

    Legacy layout (with runs/ subdirectory):
    <benchmark_dir>/
    └── runs/
        └── eval-N/
            ├── with_skill/
            │   └── run-1/grading.json
            └── without_skill/
                └── run-1/grading.json
"""

import argparse
import difflib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    # Support both layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif list(benchmark_dir.glob("eval-*")):
        search_dir = benchmark_dir
    else:
        print(f"No eval directories found in {benchmark_dir} or {benchmark_dir / 'runs'}")
        return {}

    results: dict[str, list] = {}

    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        metadata_path = eval_dir / "eval_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path) as mf:
                    eval_id = json.load(mf).get("eval_id", eval_idx)
            except (json.JSONDecodeError, OSError):
                eval_id = eval_idx
        else:
            try:
                eval_id = int(eval_dir.name.split("-")[1])
            except ValueError:
                eval_id = eval_idx

        # Discover config directories dynamically rather than hardcoding names
        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            # Skip non-config directories (inputs, outputs, etc.)
            if not list(config_dir.glob("run-*")):
                continue
            config = config_dir.name
            if config not in results:
                results[config] = []

            for run_dir in sorted(config_dir.glob("run-*")):
                run_number = int(run_dir.name.split("-")[1])
                grading_file = run_dir / "grading.json"

                if not grading_file.exists():
                    print(f"Warning: grading.json not found in {run_dir}")
                    continue

                try:
                    with open(grading_file) as f:
                        grading = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON in {grading_file}: {e}")
                    continue

                # Extract metrics
                result = {
                    "eval_id": eval_id,
                    "run_number": run_number,
                    "pass_rate": grading.get("summary", {}).get("pass_rate", 0.0),
                    "passed": grading.get("summary", {}).get("passed", 0),
                    "failed": grading.get("summary", {}).get("failed", 0),
                    "total": grading.get("summary", {}).get("total", 0),
                }

                # Extract timing — check grading.json first, then sibling timing.json
                timing = grading.get("timing", {})
                result["time_seconds"] = timing.get("total_duration_seconds", 0.0)
                timing_file = run_dir / "timing.json"
                if result["time_seconds"] == 0.0 and timing_file.exists():
                    try:
                        with open(timing_file) as tf:
                            timing_data = json.load(tf)
                        result["time_seconds"] = timing_data.get("total_duration_seconds", 0.0)
                        result["tokens"] = timing_data.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass

                # Extract metrics if available
                metrics = grading.get("execution_metrics", {})
                result["tool_calls"] = metrics.get("total_tool_calls", 0)
                if not result.get("tokens"):
                    result["tokens"] = metrics.get("output_chars", 0)
                result["errors"] = metrics.get("errors_encountered", 0)

                # Extract expectations — viewer requires fields: text, passed, evidence
                raw_expectations = grading.get("expectations", [])
                for exp in raw_expectations:
                    if "text" not in exp or "passed" not in exp:
                        print(f"Warning: expectation in {grading_file} missing required fields (text, passed, evidence): {exp}")
                result["expectations"] = raw_expectations

                # Extract notes from user_notes_summary
                notes_summary = grading.get("user_notes_summary", {})
                notes = []
                notes.extend(notes_summary.get("uncertainties", []))
                notes.extend(notes_summary.get("needs_review", []))
                notes.extend(notes_summary.get("workarounds", []))
                result["notes"] = notes

                results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta.
    """
    run_summary = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": {"mean": 0, "stddev": 0, "min": 0, "max": 0}
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        tokens = [r.get("tokens", 0) for r in runs]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens)
        }

    # Calculate delta between the first two configs (if two exist)
    if len(configs) >= 2:
        primary = run_summary.get(configs[0], {})
        baseline = run_summary.get(configs[1], {})
    else:
        primary = run_summary.get(configs[0], {}) if configs else {}
        baseline = {}

    delta_pass_rate = primary.get("pass_rate", {}).get("mean", 0) - baseline.get("pass_rate", {}).get("mean", 0)
    delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get("time_seconds", {}).get("mean", 0)
    delta_tokens = primary.get("tokens", {}).get("mean", 0) - baseline.get("tokens", {}).get("mean", 0)

    run_summary["delta"] = {
        "pass_rate": f"{delta_pass_rate:+.2f}",
        "time_seconds": f"{delta_time:+.1f}",
        "tokens": f"{delta_tokens:+.0f}"
    }

    return run_summary


# ---------------------------------------------------------------------------
# Step-level aggregation (runs produced by run_step_eval.py)
# ---------------------------------------------------------------------------

# Thresholds for flags surfaced to the analyzer's ambiguity pass.
UNSTABLE_JSON_MATCH = 0.6    # share of runs matching the most common JSON artifact
UNSTABLE_TEXT_DIVERGENCE = 0.35  # 1 - mean pairwise similarity of text artifacts
MODEL_GAP = 0.25             # spread of step success rate between configurations


def _eval_dirs(benchmark_dir: Path) -> list[tuple[int, Path]]:
    runs_dir = benchmark_dir / "runs"
    search_dir = runs_dir if runs_dir.exists() else benchmark_dir
    found = []
    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        eval_id = eval_idx
        metadata_path = eval_dir / "eval_metadata.json"
        try:
            if metadata_path.exists():
                eval_id = json.loads(metadata_path.read_text()).get("eval_id", eval_idx)
            else:
                eval_id = int(eval_dir.name.split("-")[1])
        except (ValueError, IndexError, json.JSONDecodeError, OSError):
            pass
        found.append((eval_id, eval_dir))
    return found


def _load_step_grading(run_dir: Path) -> dict | None:
    grading_file = run_dir / "grading.json"
    if not grading_file.exists():
        return None
    try:
        grading = json.loads(grading_file.read_text())
    except json.JSONDecodeError:
        return None
    return grading if isinstance(grading.get("steps"), dict) else None


def load_step_results(benchmark_dir: Path) -> dict:
    """Collect step-level gradings: {"chain": [...], "isolated": [...]}.

    Chain runs live at eval-*/<config>/run-*/, isolated runs at
    eval-*/<config>/isolated/<step>/run-*/. Only grading.json files with a
    `steps` field (written by grade_steps.py) are included.
    """
    records: dict[str, list] = {"chain": [], "isolated": []}
    for eval_id, eval_dir in _eval_dirs(benchmark_dir):
        for config_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            for run_dir in sorted(config_dir.glob("run-*")):
                grading = _load_step_grading(run_dir)
                if grading:
                    records["chain"].append({"eval_id": eval_id, "config": config_dir.name,
                                             "run_dir": run_dir, "grading": grading})
            isolated_root = config_dir / "isolated"
            if isolated_root.is_dir():
                for step_dir in sorted(p for p in isolated_root.iterdir() if p.is_dir()):
                    for run_dir in sorted(step_dir.glob("run-*")):
                        grading = _load_step_grading(run_dir)
                        if grading:
                            records["isolated"].append({"eval_id": eval_id, "config": config_dir.name,
                                                        "step": step_dir.name, "run_dir": run_dir,
                                                        "grading": grading})
    return records


def _step_failed(step_grading: dict) -> bool:
    return step_grading.get("failed", 0) > 0 or not step_grading.get("exists", True)


def _read_artifact(run_dir: Path, step_grading: dict) -> str | None:
    path = run_dir / "outputs" / step_grading.get("artifact", "")
    if not path.is_file():
        return None
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def _consistency(artifacts_by_eval: dict, is_json: bool) -> dict | None:
    """How similar a step's artifacts are across repeated runs of the same eval."""
    exact_rates: list[float] = []
    divergences: list[float] = []
    field_shares: dict[str, list[float]] = {}
    for texts in artifacts_by_eval.values():
        texts = [t for t in texts if t is not None]
        if len(texts) < 2:
            continue
        parsed = []
        if is_json:
            for t in texts:
                try:
                    parsed.append(json.loads(t))
                except json.JSONDecodeError:
                    parsed.append(None)
            keys = [json.dumps(p, sort_keys=True) if p is not None else t.strip() for p, t in zip(parsed, texts)]
        else:
            keys = ["\n".join(line.rstrip() for line in t.strip().splitlines()) for t in texts]
        exact_rates.append(Counter(keys).most_common(1)[0][1] / len(keys))

        ratios = [difflib.SequenceMatcher(None, a, b).ratio() for a, b in combinations(keys, 2)]
        divergences.append(1 - sum(ratios) / len(ratios))

        if is_json and all(isinstance(p, dict) for p in parsed):
            for field in sorted({k for p in parsed for k in p}):
                values = [json.dumps(p.get(field), sort_keys=True) for p in parsed]
                field_shares.setdefault(field, []).append(Counter(values).most_common(1)[0][1] / len(values))

    if not exact_rates:
        return None
    return {
        "kind": "json" if is_json else "text",
        "exact_match_rate": round(sum(exact_rates) / len(exact_rates), 4),
        "mean_divergence": round(sum(divergences) / len(divergences), 4),
        "field_agreement": {f: round(sum(v) / len(v), 4) for f, v in field_shares.items()},
    }


def aggregate_step_results(records: dict) -> dict | None:
    """Summarize step-level results per step x configuration.

    Returns None when there are no step-level gradings, so benchmarks that
    don't use step manifests are unchanged.
    """
    chain = records.get("chain", [])
    isolated = records.get("isolated", [])
    if not chain and not isolated:
        return None

    # Step order and edges from the gradings themselves (artifact names are NN-prefixed).
    step_info: dict[str, dict] = {}
    for rec in chain + isolated:
        for sid, sg in rec["grading"]["steps"].items():
            if sid not in step_info:
                step_info[sid] = {"id": sid, "type": sg.get("type"), "inputs": sg.get("inputs", []),
                                  "artifact": sg.get("artifact", "")}
    steps = sorted(step_info.values(), key=lambda s: (Path(s["artifact"]).name, s["id"]))
    configs = sorted({rec["config"] for rec in chain + isolated})

    cells: dict[str, dict] = {}
    flags: list[dict] = []
    propagation: list[dict] = []

    for step in steps:
        sid = step["id"]
        cells[sid] = {}
        for config in configs:
            runs = [r for r in chain if r["config"] == config and sid in r["grading"]["steps"]]
            iso_runs = [r for r in isolated if r["config"] == config and r["step"] == sid
                        and sid in r["grading"]["steps"]]
            if not runs and not iso_runs:
                continue
            cell: dict = {"runs": len(runs)}
            if runs:
                sgs = [r["grading"]["steps"][sid] for r in runs]
                n = len(sgs)
                failed = [_step_failed(sg) for sg in sgs]
                contaminated = [bool(sg.get("contaminated")) for sg in sgs]
                cell["pass_rate"] = calculate_stats([sg.get("pass_rate", 0.0) for sg in sgs])
                # Share of runs where every check on the step passed
                cell["success_rate"] = round(1 - sum(failed) / n, 4)
                cell["critical_failure_rate"] = round(sum(bool(sg.get("critical_failed")) for sg in sgs) / n, 4)
                cell["contaminated_rate"] = round(sum(contaminated) / n, 4)
                chain_fail = sum(failed) / n
                own = sum(f and not c for f, c in zip(failed, contaminated)) / n
                inherited = sum(f and c for f, c in zip(failed, contaminated)) / n
                cell["failure_attribution"] = {
                    "chain_failure_rate": round(chain_fail, 4),
                    "own_failure_rate": round(own, 4),
                    "inherited_failure_rate": round(inherited, 4),
                    "source": "contamination",
                }
                by_eval: dict = {}
                for r, sg in zip(runs, sgs):
                    by_eval.setdefault(r["eval_id"], []).append(_read_artifact(r["run_dir"], sg))
                cell["consistency"] = _consistency(by_eval, Path(step["artifact"]).suffix.lower() == ".json")
                cell["nondeterministic"] = any(
                    a.get("id") == "auto-reproducible" and a.get("passed") is False
                    for sg in sgs for a in sg.get("assertions", [])
                )
            else:
                cell["pass_rate"] = None
                cell["success_rate"] = None
                cell["failure_attribution"] = None
                cell["consistency"] = None

            if iso_runs:
                iso_sgs = [r["grading"]["steps"][sid] for r in iso_runs]
                iso_fail = sum(_step_failed(sg) for sg in iso_sgs) / len(iso_sgs)
                cell["isolated"] = {
                    "runs": len(iso_sgs),
                    "pass_rate": calculate_stats([sg.get("pass_rate", 0.0) for sg in iso_sgs]),
                    "failure_rate": round(iso_fail, 4),
                }
                if cell["failure_attribution"]:
                    # Isolated runs get golden inputs, so their failures are the step's own.
                    chain_fail = cell["failure_attribution"]["chain_failure_rate"]
                    cell["failure_attribution"].update({
                        "own_failure_rate": round(iso_fail, 4),
                        "inherited_failure_rate": round(max(0.0, chain_fail - iso_fail), 4),
                        "source": "isolated",
                    })
            else:
                cell["isolated"] = None

            cell_flags = []
            success = cell.get("success_rate")
            if success is not None and cell["runs"] >= 2 and 0 < success < 1:
                cell_flags.append({"reason": "inconsistent",
                                   "detail": f"passes in {success*100:.0f}% of {cell['runs']} runs"})
            elif success == 0:
                cell_flags.append({"reason": "always_fails", "detail": f"fails in all {cell['runs']} runs"})
            cons = cell.get("consistency")
            if cons and step["type"] == "probabilistic":
                if cons["kind"] == "json" and cons["exact_match_rate"] < UNSTABLE_JSON_MATCH:
                    unstable = [f for f, v in cons["field_agreement"].items() if v < UNSTABLE_JSON_MATCH]
                    detail = f"only {cons['exact_match_rate']*100:.0f}% of runs agree"
                    if unstable:
                        detail += f"; unstable fields: {', '.join(unstable)}"
                    cell_flags.append({"reason": "unstable_output", "detail": detail})
                elif cons["kind"] == "text" and cons["mean_divergence"] > UNSTABLE_TEXT_DIVERGENCE:
                    cell_flags.append({"reason": "unstable_output",
                                       "detail": f"mean divergence {cons['mean_divergence']:.2f} across runs"})
            if cell.get("nondeterministic"):
                cell_flags.append({"reason": "nondeterministic", "detail": "deterministic step gave different outputs for the same input"})
            fa = cell.get("failure_attribution")
            if fa and fa["inherited_failure_rate"] > 0 and fa["inherited_failure_rate"] >= fa["own_failure_rate"]:
                cell_flags.append({"reason": "inherited_failures",
                                   "detail": f"{fa['inherited_failure_rate']*100:.0f}% of runs fail because of upstream steps"})
            cell["flags"] = cell_flags
            for f in cell_flags:
                flags.append({"step": sid, "config": config, **f})
            cells[sid][config] = cell

        means = {c: v["success_rate"] for c, v in cells[sid].items() if v.get("success_rate") is not None}
        if len(means) >= 2:
            best, worst = max(means, key=means.get), min(means, key=means.get)
            gap = means[best] - means[worst]
            if gap >= MODEL_GAP:
                flags.append({"step": sid, "config": None, "reason": "model_gap",
                              "detail": f"{best} {means[best]*100:.0f}% vs {worst} {means[worst]*100:.0f}%"})

    # Propagation: how often a critical failure upstream comes with a failure downstream.
    for step in steps:
        for upstream_id in step["inputs"]:
            for config in configs:
                runs = [r for r in chain if r["config"] == config
                        and upstream_id in r["grading"]["steps"] and step["id"] in r["grading"]["steps"]]
                upstream_bad = [r for r in runs if r["grading"]["steps"][upstream_id].get("critical_failed")]
                if not upstream_bad:
                    continue
                downstream_bad = sum(_step_failed(r["grading"]["steps"][step["id"]]) for r in upstream_bad)
                propagation.append({
                    "from": upstream_id, "to": step["id"], "config": config,
                    "upstream_critical_failures": len(upstream_bad),
                    "downstream_failures": downstream_bad,
                    "rate": round(downstream_bad / len(upstream_bad), 4),
                })

    return {
        "steps": [{"id": s["id"], "type": s["type"], "inputs": s["inputs"], "artifact": s["artifact"]} for s in steps],
        "configs": configs,
        "cells": cells,
        "propagation": propagation,
        "flags": flags,
        "thresholds": {
            "unstable_json_match": UNSTABLE_JSON_MATCH,
            "unstable_text_divergence": UNSTABLE_TEXT_DIVERGENCE,
            "model_gap": MODEL_GAP,
        },
    }


def generate_step_markdown(step_summary: dict) -> list[str]:
    configs = step_summary["configs"]
    lines = ["", "## Step Breakdown", "",
             "| Step | Type | " + " | ".join(configs) + " |",
             "|------|------|" + "|".join("---" for _ in configs) + "|"]
    for step in step_summary["steps"]:
        row = [step["id"], step["type"] or "?"]
        for config in configs:
            cell = step_summary["cells"].get(step["id"], {}).get(config)
            if not cell or not cell.get("pass_rate"):
                row.append("—")
                continue
            pr = cell["pass_rate"]
            text = f"{cell['success_rate']*100:.0f}% runs pass; checks {pr['mean']*100:.0f}% ± {pr['stddev']*100:.0f}%"
            fa = cell.get("failure_attribution") or {}
            if fa.get("chain_failure_rate"):
                text += f" (own {fa['own_failure_rate']*100:.0f}% / inherited {fa['inherited_failure_rate']*100:.0f}%)"
            row.append(text)
        lines.append("| " + " | ".join(row) + " |")

    if step_summary["propagation"]:
        lines += ["", "### Failure propagation", ""]
        for p in step_summary["propagation"]:
            lines.append(f"- {p['config']}: {p['from']} → {p['to']}: {p['downstream_failures']}/{p['upstream_critical_failures']} "
                         f"critical upstream failures were followed by a downstream failure")
    if step_summary["flags"]:
        lines += ["", "### Flags (candidates for the ambiguity pass)", ""]
        for f in step_summary["flags"]:
            where = f"{f['step']}" + (f" @ {f['config']}" if f.get("config") else "")
            lines.append(f"- **{f['reason']}** — {where}: {f['detail']}")
    return lines


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array for benchmark.json
    runs = []
    for config in results:
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens", 0),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0)
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))

    # Runs per configuration, taken from the data (max over evals)
    run_counts: dict[tuple, int] = {}
    for config, config_runs in results.items():
        for r in config_runs:
            run_counts[(config, r["eval_id"])] = run_counts.get((config, r["eval_id"]), 0) + 1

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": max(run_counts.values()) if run_counts else 0
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    step_summary = aggregate_step_results(load_step_results(benchmark_dir))
    if step_summary:
        benchmark["step_summary"] = step_summary

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]
    config_a = configs[0] if len(configs) >= 1 else "config_a"
    config_b = configs[1] if len(configs) >= 2 else "config_b"
    label_a = config_a.replace("_", " ").title()
    label_b = config_b.replace("_", " ").title()

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({metadata['runs_per_configuration']} runs each per configuration)",
        "",
        "## Summary",
        "",
        f"| Metric | {label_a} | {label_b} | Delta |",
        "|--------|------------|---------------|-------|",
    ]

    a_summary = run_summary.get(config_a, {})
    b_summary = run_summary.get(config_b, {})
    delta = run_summary.get("delta", {})

    # Format pass rate
    a_pr = a_summary.get("pass_rate", {})
    b_pr = b_summary.get("pass_rate", {})
    lines.append(f"| Pass Rate | {a_pr.get('mean', 0)*100:.0f}% ± {a_pr.get('stddev', 0)*100:.0f}% | {b_pr.get('mean', 0)*100:.0f}% ± {b_pr.get('stddev', 0)*100:.0f}% | {delta.get('pass_rate', '—')} |")

    # Format time
    a_time = a_summary.get("time_seconds", {})
    b_time = b_summary.get("time_seconds", {})
    lines.append(f"| Time | {a_time.get('mean', 0):.1f}s ± {a_time.get('stddev', 0):.1f}s | {b_time.get('mean', 0):.1f}s ± {b_time.get('stddev', 0):.1f}s | {delta.get('time_seconds', '—')}s |")

    # Format tokens
    a_tokens = a_summary.get("tokens", {})
    b_tokens = b_summary.get("tokens", {})
    lines.append(f"| Tokens | {a_tokens.get('mean', 0):.0f} ± {a_tokens.get('stddev', 0):.0f} | {b_tokens.get('mean', 0):.0f} ± {b_tokens.get('stddev', 0):.0f} | {delta.get('tokens', '—')} |")

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    if benchmark.get("step_summary"):
        lines.extend(generate_step_markdown(benchmark["step_summary"]))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark run results into summary statistics"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="Path to the benchmark directory"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="Name of the skill being benchmarked"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="Path to the skill being benchmarked"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"Directory not found: {args.benchmark_dir}")
        sys.exit(1)

    # Generate benchmark
    benchmark = generate_benchmark(args.benchmark_dir, args.skill_name, args.skill_path)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    with open(output_json, "w") as f:
        json.dump(benchmark, f, indent=2)
    print(f"Generated: {output_json}")

    # Write benchmark.md
    markdown = generate_markdown(benchmark)
    with open(output_md, "w") as f:
        f.write(markdown)
    print(f"Generated: {output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print(f"\nSummary:")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = config.replace("_", " ").title()
        print(f"  {label}: {pr*100:.1f}% pass rate")
    print(f"  Delta:         {delta.get('pass_rate', '—')}")


if __name__ == "__main__":
    main()
