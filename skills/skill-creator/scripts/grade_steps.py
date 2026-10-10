#!/usr/bin/env python3
"""Grade the per-step artifacts of a step-level eval run.

Reads `run_meta.json` and `outputs/steps/*` from a run directory, applies
each step's assertions (programmatic, then reference, then LLM-graded),
marks steps downstream of a failed critical check as "contaminated", and
writes `grading.json`.

The flattened `expectations` / `summary` fields keep grading.json
compatible with aggregate_benchmark.py and the eval viewer; the `steps`
field carries the per-step detail.

Usage:
    python -m scripts.grade_steps <run_dir> [--skill-path PATH] [--grader-model MODEL]

Without --grader-model, LLM-graded checks stay pending (`passed: null`).
Verdicts filled into grading.json by hand or by the grader agent are kept
when regrading, so rerun this script afterwards to update the summaries.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Callable

try:
    from scripts.step_manifest import (
        load_evals, load_manifest, step_format, steps_by_id, topological_order, upstream,
    )
except ImportError:
    from step_manifest import (
        load_evals, load_manifest, step_format, steps_by_id, topological_order, upstream,
    )

# (rubric, artifact_text, context) -> (passed, evidence)
LLMGrader = Callable[[str, str, str], tuple[bool, str]]

STEPS_SUBDIR = Path("outputs") / "steps"


def _get_field(data, path: str):
    """Read a dotted field path ("a.b.0") from parsed JSON. Raises KeyError."""
    cur = data
    if path in ("", "."):
        return cur
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def _field_text(text: str, parsed, check: dict) -> str:
    """The text a string check applies to: a JSON field if given, else the artifact."""
    field = check.get("field")
    if field is None:
        return text
    value = _get_field(parsed, field)
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _in_range(n: int, check: dict) -> bool:
    lo, hi = check.get("min"), check.get("max")
    return (lo is None or n >= lo) and (hi is None or n <= hi)


def _range_desc(check: dict) -> str:
    return f"[{check.get('min', '-')}, {check.get('max', '-')}]"


def run_check(check: dict, text: str, parsed, skill_path: Path) -> tuple[bool, str]:
    """Run one programmatic or reference check. Returns (passed, evidence)."""
    ctype = check["type"]
    needs_json = ctype in {"json_required", "json_field_equals", "json_array_length", "reference_json_fields"} \
        or check.get("field") is not None
    if needs_json and parsed is None:
        return False, "Artifact is not valid JSON"

    try:
        if ctype == "json_valid":
            return (parsed is not None), ("Valid JSON" if parsed is not None else "Artifact is not valid JSON")

        if ctype == "json_required":
            missing = []
            for field in check.get("fields", []):
                try:
                    _get_field(parsed, field)
                except KeyError:
                    missing.append(field)
            return (not missing), ("All required fields present" if not missing else f"Missing fields: {', '.join(missing)}")

        if ctype == "json_field_equals":
            actual = _get_field(parsed, check["field"])
            expected = check.get("value")
            if check.get("case_insensitive") and isinstance(actual, str) and isinstance(expected, str):
                ok = actual.strip().lower() == expected.strip().lower()
            else:
                ok = actual == expected
            return ok, f"{check['field']} = {json.dumps(actual, ensure_ascii=False)} (expected {json.dumps(expected, ensure_ascii=False)})"

        if ctype == "json_array_length":
            value = _get_field(parsed, check["field"])
            if not isinstance(value, list):
                return False, f"{check['field']} is not a list"
            return _in_range(len(value), check), f"{check['field']} has {len(value)} items (allowed {_range_desc(check)})"

        if ctype == "regex":
            target = _field_text(text, parsed, check)
            flags = 0
            for ch in check.get("flags", ""):
                flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}.get(ch, 0)
            match = re.search(check["pattern"], target, flags)
            should_match = check.get("should_match", True)
            if should_match:
                return bool(match), (f"Matched: {match.group(0)[:120]!r}" if match else f"No match for /{check['pattern']}/")
            return (not match), (f"Unexpected match: {match.group(0)[:120]!r}" if match else f"No match for /{check['pattern']}/, as required")

        if ctype in ("contains", "not_contains"):
            target = _field_text(text, parsed, check)
            needle = check["value"]
            hay = target
            if check.get("case_insensitive", True):
                hay, needle = hay.lower(), needle.lower()
            found = needle in hay
            if ctype == "contains":
                return found, (f"Found {check['value']!r}" if found else f"{check['value']!r} not found")
            return (not found), (f"Unexpectedly found {check['value']!r}" if found else f"{check['value']!r} absent, as required")

        if ctype == "line_count":
            target = _field_text(text, parsed, check)
            n = len([line for line in target.splitlines() if line.strip()])
            return _in_range(n, check), f"{n} non-empty lines (allowed {_range_desc(check)})"

        if ctype == "word_count":
            target = _field_text(text, parsed, check)
            n = len(target.split())
            return _in_range(n, check), f"{n} words (allowed {_range_desc(check)})"

        # Reference checks compare against a golden artifact in the skill
        ref_path = skill_path / check["reference"]
        ref_text = ref_path.read_text()

        if ctype == "exact_match":
            if parsed is not None:
                try:
                    same = parsed == json.loads(ref_text)
                except json.JSONDecodeError:
                    same = _normalize(text) == _normalize(ref_text)
            else:
                same = _normalize(text) == _normalize(ref_text)
            return same, ("Matches reference exactly" if same else f"Differs from {check['reference']}")

        if ctype == "reference_similarity":
            ratio = difflib.SequenceMatcher(None, _normalize(text), _normalize(ref_text)).ratio()
            threshold = check.get("min_similarity", 0.5)
            return ratio >= threshold, f"Similarity to {check['reference']}: {ratio:.2f} (min {threshold})"

        if ctype == "reference_json_fields":
            ref = json.loads(ref_text)
            diffs = []
            for field in check.get("fields", []):
                try:
                    a = _get_field(parsed, field)
                except KeyError:
                    diffs.append(f"{field} missing")
                    continue
                b = _get_field(ref, field)
                if a != b:
                    diffs.append(f"{field}: {json.dumps(a, ensure_ascii=False)} != {json.dumps(b, ensure_ascii=False)}")
            return (not diffs), ("Fields match reference" if not diffs else "; ".join(diffs))
    except KeyError as e:
        return False, f"Field not found: {e.args[0]}"
    except (OSError, json.JSONDecodeError, re.error) as e:
        return False, f"Check error: {e}"

    return False, f"Unknown check type: {ctype}"


def _auto_assertions(step: dict, fmt: str) -> list[dict]:
    """Checks every step gets for free, based on its manifest entry."""
    autos = []
    if fmt == "json":
        autos.append({
            "id": "auto-json-valid", "text": "Artifact is valid JSON", "kind": "programmatic",
            "critical": True, "check": {"type": "json_valid"},
        })
        required = (step.get("schema") or {}).get("required") or []
        if required:
            autos.append({
                "id": "auto-schema", "text": f"Artifact has required fields: {', '.join(required)}",
                "kind": "programmatic", "critical": True,
                "check": {"type": "json_required", "fields": required},
            })
    return autos


def grade_step(
    step: dict,
    artifact_path: Path,
    assertions: list[dict],
    skill_path: Path,
    context: str,
    llm_grader: LLMGrader | None,
    step_log: dict | None = None,
    previous_llm: dict | None = None,
) -> dict:
    fmt = step_format(step)
    results: list[dict] = []

    if not artifact_path.exists():
        results.append({
            "id": "auto-artifact-exists", "text": f"Step wrote {step['output']}", "kind": "programmatic",
            "critical": True, "passed": False, "evidence": "Artifact not found",
        })
    else:
        text = artifact_path.read_text(errors="replace")
        parsed = None
        if fmt == "json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None

        if step_log and step_log.get("nondeterministic"):
            results.append({
                "id": "auto-reproducible", "text": "Deterministic step gives the same output for the same input",
                "kind": "programmatic", "critical": True, "passed": False,
                "evidence": "Two executions with identical inputs produced different outputs",
            })

        # Cheapest checks first: programmatic, then reference, then LLM.
        ordered = _auto_assertions(step, fmt) + sorted(
            assertions, key=lambda a: {"programmatic": 0, "reference": 1, "llm": 2}.get(a.get("kind"), 3)
        )
        for idx, a in enumerate(ordered):
            entry = {
                "id": a.get("id") or f"{step['id']}-{idx + 1}",
                "text": a["text"],
                "kind": a.get("kind", "programmatic"),
                "critical": bool(a.get("critical", False)),
            }
            if entry["kind"] == "llm":
                kept = (previous_llm or {}).get(entry["id"])
                if llm_grader is None and kept and kept.get("passed") is not None:
                    # Keep verdicts filled in earlier (e.g. by the grader agent)
                    entry["passed"], entry["evidence"] = bool(kept["passed"]), kept.get("evidence", "")
                elif llm_grader is None:
                    entry["passed"] = None
                    entry["evidence"] = "Pending LLM grading (run with --grader-model or grade with agents/grader.md)"
                else:
                    try:
                        entry["passed"], entry["evidence"] = llm_grader(a["rubric"], text, context)
                    except Exception as e:  # grading failures shouldn't sink the run
                        entry["passed"], entry["evidence"] = None, f"LLM grading failed: {e}"
            else:
                entry["passed"], entry["evidence"] = run_check(a["check"], text, parsed, skill_path)
            results.append(entry)

    graded = [r for r in results if r["passed"] is not None]
    passed = sum(1 for r in graded if r["passed"])
    total = len(graded)
    return {
        "type": step["type"],
        "artifact": str(Path("steps") / step["output"]),
        "exists": artifact_path.exists(),
        "inputs": list(step.get("inputs", [])),
        "assertions": results,
        "passed": passed,
        "failed": total - passed,
        "pending": len(results) - total,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 1.0,
        "critical_failed": any(r["critical"] and r["passed"] is False for r in results),
    }


def grade_run(
    run_dir: Path,
    skill_path: Path | None = None,
    llm_grader: LLMGrader | None = None,
) -> dict:
    """Grade a run directory produced by run_step_eval.py and write grading.json."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text())
    skill_path = Path(skill_path or meta["skill_path"])
    manifest = load_manifest(skill_path)
    if manifest is None:
        raise FileNotFoundError(f"No evals/steps.json in {skill_path}")
    evals = load_evals(skill_path) or {"evals": []}
    eval_item = next((e for e in evals.get("evals", []) if e.get("id") == meta["eval_id"]), {})

    steps = manifest["steps"]
    by_id = steps_by_id(manifest)
    order = topological_order(steps)
    mode = meta.get("mode", "chain")
    isolated_step = meta.get("isolated_step")
    to_grade = [isolated_step] if mode == "isolated" else order

    step_assertions = eval_item.get("step_assertions", {})
    context = f"User request: {eval_item.get('prompt', '')}"

    previous: dict = {}
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        try:
            for psid, pstep in json.loads(grading_path.read_text()).get("steps", {}).items():
                previous[psid] = {a.get("id"): a for a in pstep.get("assertions", []) if a.get("kind") == "llm"}
        except (json.JSONDecodeError, AttributeError):
            previous = {}
    graded: dict[str, dict] = {}
    for sid in to_grade:
        step = by_id[sid]
        log_path = run_dir / "logs" / f"{Path(step['output']).stem}.json"
        step_log = None
        if log_path.exists():
            try:
                step_log = json.loads(log_path.read_text())
            except json.JSONDecodeError:
                step_log = None
        graded[sid] = grade_step(
            step, run_dir / STEPS_SUBDIR / step["output"], step_assertions.get(sid, []),
            skill_path, context, llm_grader, step_log, previous.get(sid),
        )
        if mode == "isolated":
            graded[sid]["inputs_source"] = "golden"

    # Contamination: a failed critical check taints everything downstream.
    for sid in to_grade:
        g = graded[sid]
        tainted_by = sorted(u for u in upstream(steps, sid) if graded.get(u, {}).get("critical_failed"))
        g["contaminated"] = bool(tainted_by)
        g["contaminated_by"] = tainted_by
        if g["failed"] == 0 and g["exists"]:
            g["failure_origin"] = None
        else:
            g["failure_origin"] = "inherited" if tainted_by else "own"

    expectations = []
    for sid in to_grade:
        for a in graded[sid]["assertions"]:
            if a["passed"] is None:
                continue
            expectations.append({"text": f"[{sid}] {a['text']}", "passed": a["passed"], "evidence": a["evidence"]})
    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)

    grading = {
        "mode": mode,
        "isolated_step": isolated_step,
        "model": meta.get("model"),
        "eval_id": meta.get("eval_id"),
        "run_number": meta.get("run_number"),
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        },
        "steps": graded,
    }
    timing_path = run_dir / "timing.json"
    if timing_path.exists():
        try:
            grading["timing"] = json.loads(timing_path.read_text())
        except json.JSONDecodeError:
            pass
    (run_dir / "grading.json").write_text(json.dumps(grading, indent=2))
    return grading


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade per-step artifacts of a step-level eval run")
    parser.add_argument("run_dirs", nargs="+", type=Path, help="Run directories containing run_meta.json")
    parser.add_argument("--skill-path", type=Path, default=None, help="Override the skill path recorded in run_meta.json")
    parser.add_argument("--grader-model", default=None, help="Model for LLM-graded assertions (default: leave them pending)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per LLM grading call in seconds")
    args = parser.parse_args()

    llm_grader = None
    if args.grader_model:
        try:
            from scripts.run_step_eval import make_llm_grader
        except ImportError:
            from run_step_eval import make_llm_grader
        llm_grader = make_llm_grader(args.grader_model, args.timeout)

    for run_dir in args.run_dirs:
        grading = grade_run(run_dir, args.skill_path, llm_grader)
        s = grading["summary"]
        print(f"{run_dir}: {s['passed']}/{s['total']} passed", file=sys.stderr)


if __name__ == "__main__":
    main()
