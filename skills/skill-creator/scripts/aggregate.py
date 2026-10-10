#!/usr/bin/env python3
"""Aggregate an iteration's graded runs into benchmark.json and benchmark.md.

Reports, per configuration (`<model>` or `<model>__<label>`), the pass rate
and time as mean ± stddev, the delta against each baseline (`<model>__no_skill`,
`<model>__old_skill`, ...), and per step x configuration: success rate,
output consistency across runs, own vs inherited failures, how failures
propagate between steps, and flags for the ambiguity pass.

Usage:
    python -m scripts.aggregate <workspace>/iteration-N [--skill-name NAME]
"""

import argparse
import difflib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path


def calculate_stats(values: list[float]) -> dict:
    """Mean, sample stddev, min and max."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}
    n = len(values)
    mean = sum(values) / n
    stddev = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1)) if n > 1 else 0.0
    return {"mean": round(mean, 4), "stddev": round(stddev, 4), "min": round(min(values), 4), "max": round(max(values), 4)}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

# Thresholds for flags surfaced to the analyzer's ambiguity pass.
UNSTABLE_JSON_MATCH = 0.6    # share of runs matching the most common JSON artifact
UNSTABLE_TEXT_DIVERGENCE = 0.35  # 1 - mean pairwise similarity of text artifacts
MODEL_GAP = 0.25             # spread of step success rate between configurations


def _eval_dirs(benchmark_dir: Path) -> list[tuple[int, Path]]:
    found = []
    for eval_idx, eval_dir in enumerate(sorted(benchmark_dir.glob("eval-*"))):
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


def load_runs(benchmark_dir: Path) -> dict:
    """Collect gradings: {"chain": [...], "isolated": [...]}.

    Chain runs live at eval-*/<config>/run-*/, isolated runs at
    eval-*/<config>/isolated/<step>/run-*/ (both written by run_evals.py).
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


# ---------------------------------------------------------------------------
# Per step x configuration
# ---------------------------------------------------------------------------

def aggregate_step_results(records: dict) -> dict | None:
    """Summarize results per step x configuration. None if there are no runs."""
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


# ---------------------------------------------------------------------------
# Per configuration
# ---------------------------------------------------------------------------

def summarize_runs(chain: list[dict]) -> tuple[list[dict], dict, dict]:
    """Per-run rows, per-config stats, and deltas of each config vs its baselines."""
    rows = []
    for rec in chain:
        summary = rec["grading"].get("summary", {})
        timing = _read_json(rec["run_dir"] / "timing.json")
        rows.append({
            "eval_id": rec["eval_id"],
            "configuration": rec["config"],
            "run_number": rec["grading"].get("run_number"),
            "pass_rate": summary.get("pass_rate", 0.0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "total": summary.get("total", 0),
            "pending": sum(sg.get("pending", 0) for sg in rec["grading"]["steps"].values()),
            "time_seconds": round(timing.get("duration_ms", 0) / 1000, 1),
        })

    run_summary = {}
    for config in sorted({r["configuration"] for r in rows}):
        runs = [r for r in rows if r["configuration"] == config]
        run_summary[config] = {
            "runs": len(runs),
            "pass_rate": calculate_stats([r["pass_rate"] for r in runs]),
            "time_seconds": calculate_stats([r["time_seconds"] for r in runs]),
            "pending_checks": sum(r["pending"] for r in runs),
        }

    deltas = {}
    for config in run_summary:
        base, sep, _label = config.partition("__")
        if sep and base in run_summary:
            deltas[config] = {
                "skill": base,
                "baseline": config,
                "pass_rate": round(run_summary[base]["pass_rate"]["mean"] - run_summary[config]["pass_rate"]["mean"], 4),
                "time_seconds": round(run_summary[base]["time_seconds"]["mean"] - run_summary[config]["time_seconds"]["mean"], 1),
            }
    return rows, run_summary, deltas


def failing_checks(chain: list[dict]) -> list[dict]:
    """Each failing check with how often it failed, per eval x config (for review)."""
    counts: dict[tuple, dict] = {}
    for rec in chain:
        for sid, sg in rec["grading"]["steps"].items():
            for a in sg.get("assertions", []):
                if a.get("passed") is False:
                    key = (rec["eval_id"], rec["config"], sid, a.get("text", ""))
                    entry = counts.setdefault(key, {"eval_id": key[0], "config": key[1], "step": sid,
                                                    "text": key[3], "failures": 0, "example_evidence": a.get("evidence", ""),
                                                    "example_run": str(rec["run_dir"])})
                    entry["failures"] += 1
    return sorted(counts.values(), key=lambda e: (-e["failures"], e["eval_id"], e["config"], e["step"]))


def generate_benchmark(benchmark_dir: Path, skill_name: str = "") -> dict:
    records = load_runs(benchmark_dir)
    rows, run_summary, deltas = summarize_runs(records["chain"])
    counts = Counter((r["configuration"], r["eval_id"]) for r in rows)
    return {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": sorted({r["eval_id"] for r in rows}),
            "runs_per_configuration": max(counts.values()) if counts else 0,
        },
        "runs": rows,
        "run_summary": run_summary,
        "deltas": deltas,
        "failing_checks": failing_checks(records["chain"]),
        "step_summary": aggregate_step_results(records),
        "notes": [],  # filled in by the analysis pass
    }


def generate_markdown(benchmark: dict) -> str:
    meta = benchmark["metadata"]
    lines = [
        f"# Benchmark: {meta['skill_name']}",
        "",
        f"{meta['timestamp']} · evals {', '.join(map(str, meta['evals_run'])) or '—'} · "
        f"up to {meta['runs_per_configuration']} runs per eval per configuration",
        "",
        "| Configuration | Runs | Pass rate | Time |",
        "|---|---|---|---|",
    ]
    for config, s in benchmark["run_summary"].items():
        pr, t = s["pass_rate"], s["time_seconds"]
        lines.append(f"| {config} | {s['runs']} | {pr['mean']*100:.0f}% ± {pr['stddev']*100:.0f}% | "
                     f"{t['mean']:.1f}s ± {t['stddev']:.1f}s |")
    for d in benchmark["deltas"].values():
        lines.append(f"\n{d['skill']} vs {d['baseline']}: pass rate {d['pass_rate']*100:+.0f} points, "
                     f"time {d['time_seconds']:+.1f}s")
    pending = sum(s["pending_checks"] for s in benchmark["run_summary"].values())
    if pending:
        lines += ["", f"**{pending} LLM-graded checks are pending** and excluded from the pass rates above. "
                      "Grade them before trusting these numbers."]
    if benchmark.get("step_summary"):
        lines.extend(generate_step_markdown(benchmark["step_summary"]))
    if benchmark["failing_checks"]:
        lines += ["", "## Failing checks", "", "| Eval | Config | Step | Check | Failures | Example evidence |",
                  "|---|---|---|---|---|---|"]
        for f in benchmark["failing_checks"]:
            evidence = str(f["example_evidence"]).replace("|", "\\|").replace("\n", " ")[:160]
            lines.append(f"| {f['eval_id']} | {f['config']} | {f['step']} | {f['text']} | {f['failures']} | {evidence} |")
    if benchmark.get("notes"):
        lines += ["", "## Notes", ""] + [f"- {n}" for n in benchmark["notes"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate graded runs into benchmark.json and benchmark.md")
    parser.add_argument("benchmark_dir", type=Path, help="Iteration directory written by run_evals.py")
    parser.add_argument("--skill-name", default="", help="Name of the skill being benchmarked")
    args = parser.parse_args()
    if not args.benchmark_dir.is_dir():
        raise SystemExit(f"Directory not found: {args.benchmark_dir}")

    benchmark = generate_benchmark(args.benchmark_dir, args.skill_name)
    out_json = args.benchmark_dir / "benchmark.json"
    out_json.write_text(json.dumps(benchmark, indent=2))
    out_json.with_suffix(".md").write_text(generate_markdown(benchmark))
    print(f"Wrote {out_json} and {out_json.with_suffix('.md')}")
    for config, s in benchmark["run_summary"].items():
        print(f"  {config}: {s['pass_rate']['mean']*100:.0f}% pass rate over {s['runs']} runs")


if __name__ == "__main__":
    main()
