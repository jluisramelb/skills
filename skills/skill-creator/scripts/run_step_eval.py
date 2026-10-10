#!/usr/bin/env python3
"""Run step-level evals for a skill across several models, N times each.

Each probabilistic step is executed as its own `claude -p --model <model>`
call that reads SKILL.md, the user's request and the upstream step
artifacts, and returns exactly one artifact. Human steps replay a recorded
decision (fixture). Deterministic steps are executed by this harness from
the manifest's `command`, cached by input hash, and run twice on a cache
miss to confirm they're reproducible.

Layout written under --workspace (an iteration directory):

    eval-<id>-<name>/
    ├── eval_metadata.json
    └── <model>[__<label>]/
        ├── run-1/
        │   ├── run_meta.json
        │   ├── outputs/steps/<NN>-<step-id>.<ext>
        │   ├── logs/<NN>-<step-id>.json
        │   ├── timing.json
        │   └── grading.json
        └── isolated/<step-id>/run-1/...   (with --isolate)

Isolated mode re-runs a single step from the eval's golden upstream
artifacts. Comparing it with the full chain separates a step's own
failures from failures inherited from earlier steps.

Usage:
    python -m scripts.run_step_eval --skill-path <skill> --workspace <ws>/iteration-1 \\
        --models claude-sonnet-5 claude-opus-5 --runs 5 [--isolate all] [--grader-model M]
    python -m scripts.run_step_eval ... --dry-run   # replay golden artifacts, no model calls
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

try:
    from scripts.grade_steps import STEPS_SUBDIR, grade_run
    from scripts.step_manifest import (
        golden_artifact, load_evals, load_manifest, resolve_fixture, step_format,
        steps_by_id, topological_order, upstream, validate_manifest,
    )
    from scripts.utils import parse_skill_md
except ImportError:
    from grade_steps import STEPS_SUBDIR, grade_run
    from step_manifest import (
        golden_artifact, load_evals, load_manifest, resolve_fixture, step_format,
        steps_by_id, topological_order, upstream, validate_manifest,
    )
    from utils import parse_skill_md

# (prompt, model, cwd, skill_path, timeout) -> {"text", "duration_ms", "tokens", "is_error"}
Executor = Callable[[str, str, Path, Path, int], dict]

ARTIFACT_RE = re.compile(r"<artifact>\s*\n?(.*?)\n?\s*</artifact>", re.DOTALL)
FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```$", re.DOTALL)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "eval"


def config_dir_name(model: str, label: str | None) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    return f"{safe}__{label}" if label else safe


def eval_dir_name(item: dict) -> str:
    name = item.get("name") or slugify(item.get("prompt", ""))
    return f"eval-{item['id']}-{slugify(name)}"


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

def claude_executor(prompt: str, model: str, cwd: Path, skill_path: Path, timeout: int) -> dict:
    """Run one step with `claude -p` and return its text result and usage."""
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--add-dir", str(skill_path),
        "--allowedTools", "Read", "Glob", "Grep",
    ]
    # Allow nesting inside a Claude Code session (see run_eval.py).
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"text": "", "duration_ms": int((time.time() - start) * 1000), "tokens": 0,
                "is_error": True, "error": f"Timed out after {timeout}s"}
    elapsed_ms = int((time.time() - start) * 1000)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"text": proc.stdout, "duration_ms": elapsed_ms, "tokens": 0, "is_error": True,
                "error": (proc.stderr or "Non-JSON output from claude -p").strip()[:2000]}
    usage = data.get("usage") or {}
    tokens = sum(int(usage.get(k) or 0) for k in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
    ))
    return {
        "text": data.get("result", ""),
        "duration_ms": int(data.get("duration_ms") or elapsed_ms),
        "tokens": tokens,
        "is_error": bool(data.get("is_error")) or proc.returncode != 0,
        "error": proc.stderr.strip()[:2000] if proc.returncode != 0 else None,
    }


def make_llm_grader(model: str, timeout: int = 120, executor: Executor | None = None):
    """Build an LLM grader for `kind: llm` assertions using `claude -p`."""
    run = executor or claude_executor

    def grade(rubric: str, artifact_text: str, context: str) -> tuple[bool, str]:
        prompt = (
            "You are grading one artifact from a step-level skill evaluation.\n\n"
            f"{context}\n\n"
            f"<artifact>\n{artifact_text}\n</artifact>\n\n"
            f"Rubric: {rubric}\n\n"
            "Decide whether the artifact satisfies the rubric. Be strict: a pass needs concrete evidence "
            "in the artifact, not just surface compliance. Respond with only a JSON object: "
            '{"passed": true|false, "evidence": "<quote or short explanation>"}'
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = run(prompt, model, Path(tmp), Path(tmp), timeout)
        if result.get("is_error"):
            raise RuntimeError(result.get("error") or "grader call failed")
        text = result.get("text", "")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"grader returned no JSON: {text[:200]!r}")
        verdict = json.loads(match.group(0))
        return bool(verdict.get("passed")), str(verdict.get("evidence", ""))

    return grade


def make_golden_executor(golden_by_output: dict[str, str]) -> Executor:
    """Executor for --dry-run: returns the golden artifact named in the prompt."""
    def run(prompt: str, model: str, cwd: Path, skill_path: Path, timeout: int) -> dict:
        match = re.search(r"OUTPUT_FILE: (\S+)", prompt)
        content = golden_by_output.get(match.group(1)) if match else None
        if content is None:
            return {"text": "", "duration_ms": 0, "tokens": 0, "is_error": True, "error": "no golden artifact"}
        return {"text": f"<artifact>\n{content}\n</artifact>", "duration_ms": 0, "tokens": 0, "is_error": False}
    return run


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

def build_step_prompt(
    skill_name: str, skill_path: Path, step: dict, eval_item: dict, input_paths: dict[str, Path],
) -> str:
    fmt = step_format(step)
    lines = [
        f'You are executing ONE step of the "{skill_name}" skill as part of a step-level evaluation.',
        "",
        f"1. Read the skill instructions at {skill_path / 'SKILL.md'} (and any files it points you to).",
        "2. Read the user's request and the input artifacts below.",
        f"3. Perform ONLY the step \"{step['id']}\" and stop. Don't perform later steps.",
        "",
        "<user_request>",
        eval_item.get("prompt", ""),
        "</user_request>",
    ]
    files = eval_item.get("files") or []
    if files:
        lines += ["", "User-provided input files:"] + [f"- {skill_path / f}" for f in files]
    lines += [
        "",
        f"STEP: {step['id']} ({step['type']})",
        f"SKILL.md SECTION: {step.get('source_section', '(not specified)')}",
    ]
    if step.get("description"):
        lines.append(f"WHAT THIS STEP DOES: {step['description']}")
    if input_paths:
        lines += ["", "Input artifacts from earlier steps (treat these as given; don't redo those steps):"]
        for sid, path in input_paths.items():
            lines += [f'<input step="{sid}" file="{path.name}">', path.read_text(errors="replace"), "</input>"]
    lines += ["", f"OUTPUT_FILE: {step['output']}", f"OUTPUT_FORMAT: {fmt}"]
    required = (step.get("schema") or {}).get("required")
    if required:
        lines.append(f"REQUIRED FIELDS: {', '.join(required)}")
    if step.get("schema", {}).get("example") is not None:
        lines.append("EXAMPLE SHAPE: " + json.dumps(step["schema"]["example"], ensure_ascii=False))
    lines += [
        "",
        "Return the artifact content wrapped exactly in <artifact> and </artifact> tags. "
        "Put nothing else inside the tags" + (" (the content must be valid JSON)." if fmt == "json" else "."),
    ]
    return "\n".join(lines)


def extract_artifact(text: str, fmt: str) -> str | None:
    match = ARTIFACT_RE.search(text or "")
    content = match.group(1) if match else None
    if content is None:
        return None
    content = content.strip()
    fence = FENCE_RE.match(content)
    if fence:
        content = fence.group(1).strip()
    if fmt == "json":
        try:
            content = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass  # keep as-is; grading reports invalid JSON
    return content + "\n"


def _render_command(step: dict, skill_path: Path, input_paths: dict[str, Path], output: Path) -> list[str]:
    cmd = []
    for i, part in enumerate(step["command"]):
        if i == 0 and part in ("python", "python3"):
            cmd.append(sys.executable)
            continue
        part = part.replace("{output}", str(output)).replace("{skill}", str(skill_path))
        part = re.sub(r"\{input:([^}]+)\}", lambda m: str(input_paths[m.group(1)]), part)
        cmd.append(part)
    return cmd


def run_deterministic(
    step: dict, skill_path: Path, input_paths: dict[str, Path], output: Path, cache_dir: Path | None, timeout: int,
) -> dict:
    """Run a deterministic step, using a content-addressed cache.

    On a cache miss the command runs twice into separate files; differing
    outputs mean the step isn't actually deterministic.
    """
    h = hashlib.sha256()
    h.update(json.dumps(step["command"]).encode())
    for sid in sorted(input_paths):
        h.update(sid.encode())
        h.update(input_paths[sid].read_bytes())
    for part in step["command"]:
        candidate = skill_path / part
        if candidate.is_file():
            h.update(candidate.read_bytes())
    key = h.hexdigest()

    if cache_dir:
        cached = cache_dir / key
        if cached.exists():
            shutil.copyfile(cached, output)
            return {"cached": True, "nondeterministic": False, "cache_key": key, "duration_ms": 0}

    start = time.time()
    outputs = []
    first_cmd = _render_command(step, skill_path, input_paths, output)
    for attempt in range(2):
        target = output if attempt == 0 else output.with_name(output.name + ".repeat")
        cmd = _render_command(step, skill_path, input_paths, target)
        proc = subprocess.run(cmd, cwd=skill_path, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            if target.exists() and attempt == 1:
                target.unlink()
            return {"cached": False, "nondeterministic": False, "cache_key": key, "is_error": True,
                    "error": (proc.stderr or proc.stdout).strip()[:2000], "command": first_cmd,
                    "duration_ms": int((time.time() - start) * 1000)}
        outputs.append(target.read_bytes() if target.exists() else None)
    repeat = output.with_name(output.name + ".repeat")
    if repeat.exists():
        repeat.unlink()
    nondeterministic = outputs[0] != outputs[1]
    if cache_dir and not nondeterministic and output.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_dir / f".{key}.{os.getpid()}"
        shutil.copyfile(output, tmp)
        os.replace(tmp, cache_dir / key)
    return {"cached": False, "nondeterministic": nondeterministic, "cache_key": key,
            "command": first_cmd, "duration_ms": int((time.time() - start) * 1000)}


def run_job(job: dict, executor: Executor | None = None, llm_grader=None) -> dict:
    """Execute one chain or isolated run, then grade it. Returns a summary."""
    executor = executor or claude_executor
    skill_path = Path(job["skill_path"])
    run_dir = Path(job["run_dir"])
    manifest = load_manifest(skill_path)
    evals = load_evals(skill_path) or {"evals": []}
    eval_item = next(e for e in evals["evals"] if e["id"] == job["eval_id"])
    skill_name, _, _ = parse_skill_md(skill_path)
    steps = manifest["steps"]
    by_id = steps_by_id(manifest)

    if run_dir.exists():
        shutil.rmtree(run_dir)
    steps_dir = run_dir / STEPS_SUBDIR
    logs_dir = run_dir / "logs"
    steps_dir.mkdir(parents=True)
    logs_dir.mkdir()

    mode = job["mode"]
    target = job.get("isolated_step")
    (run_dir / "run_meta.json").write_text(json.dumps({
        "skill_path": str(skill_path),
        "eval_id": job["eval_id"],
        "model": job["model"],
        "label": job.get("label"),
        "run_number": job["run_number"],
        "mode": mode,
        "isolated_step": target,
    }, indent=2))

    if mode == "isolated":
        # Golden upstream artifacts in, only the target step runs live.
        for sid in sorted(upstream(steps, target)):
            if by_id[sid]["type"] == "human":
                golden = resolve_fixture(skill_path, by_id[sid], eval_item)
            else:
                golden = golden_artifact(skill_path, eval_item, by_id[sid])
            if golden:
                shutil.copyfile(golden, steps_dir / by_id[sid]["output"])
        to_run = [target]
    else:
        to_run = topological_order(steps)

    total_ms = 0
    total_tokens = 0
    for sid in to_run:
        step = by_id[sid]
        output = steps_dir / step["output"]
        input_paths = {dep: steps_dir / by_id[dep]["output"] for dep in step.get("inputs", [])}
        log: dict = {"step": sid, "type": step["type"]}
        missing = [dep for dep, p in input_paths.items() if not p.exists()]
        if missing:
            log.update({"skipped": True, "reason": f"missing input artifacts: {', '.join(missing)}"})
        elif step["type"] == "human":
            fixture = resolve_fixture(skill_path, step, eval_item)
            if fixture:
                shutil.copyfile(fixture, output)
                log["replayed_fixture"] = str(fixture.relative_to(skill_path))
            else:
                log.update({"skipped": True, "reason": "no recorded decision to replay"})
        elif step["type"] == "deterministic":
            cache_dir = Path(job["cache_dir"]) if job.get("cache_dir") else None
            log.update(run_deterministic(step, skill_path, input_paths, output, cache_dir, job["timeout"]))
            total_ms += log.get("duration_ms", 0)
        else:
            prompt = build_step_prompt(skill_name, skill_path, step, eval_item, input_paths)
            result = executor(prompt, job["model"], run_dir, skill_path, job["timeout"])
            artifact = extract_artifact(result.get("text", ""), step_format(step))
            if artifact is not None:
                output.write_text(artifact)
            total_ms += int(result.get("duration_ms") or 0)
            total_tokens += int(result.get("tokens") or 0)
            log.update({
                "prompt": prompt,
                "response": result.get("text", ""),
                "duration_ms": result.get("duration_ms"),
                "tokens": result.get("tokens"),
                "is_error": result.get("is_error", False),
                "error": result.get("error"),
                "artifact_found": artifact is not None,
            })
        (logs_dir / f"{Path(step['output']).stem}.json").write_text(json.dumps(log, indent=2))

    (run_dir / "timing.json").write_text(json.dumps({
        "total_tokens": total_tokens,
        "duration_ms": total_ms,
        "total_duration_seconds": round(total_ms / 1000, 1),
    }, indent=2))

    grading = grade_run(run_dir, skill_path, llm_grader)
    return {"run_dir": str(run_dir), "summary": grading["summary"]}


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

def plan_jobs(
    skill_path: Path, workspace: Path, models: list[str], runs: int, eval_ids: list[int] | None,
    isolate: list[str], label: str | None, timeout: int, use_cache: bool = True,
) -> list[dict]:
    manifest = load_manifest(skill_path)
    evals = load_evals(skill_path) or {"evals": []}
    by_id = steps_by_id(manifest)
    if isolate == ["all"]:
        isolate = [s["id"] for s in manifest["steps"] if s["type"] == "probabilistic"]
    for sid in isolate:
        if sid not in by_id:
            raise ValueError(f"--isolate: unknown step '{sid}'")

    items = [e for e in evals["evals"] if eval_ids is None or e["id"] in eval_ids]
    if not items:
        raise ValueError("No evals selected")
    cache_dir = str(workspace / ".step-cache") if use_cache else None

    jobs = []
    for item in items:
        eval_dir = workspace / eval_dir_name(item)
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "eval_metadata.json").write_text(json.dumps({
            "eval_id": item["id"],
            "eval_name": item.get("name") or eval_dir.name,
            "prompt": item.get("prompt", ""),
            "assertions": item.get("expectations", []),
            "step_assertions": item.get("step_assertions", {}),
        }, indent=2))
        isolatable = []
        for sid in isolate:
            missing = [u for u in upstream(manifest["steps"], sid)
                       if by_id[u]["type"] != "human" and not golden_artifact(skill_path, item, by_id[u])]
            if missing:
                print(f"Warning: eval {item['id']}: can't isolate '{sid}' without golden artifacts for "
                      f"{', '.join(sorted(missing))}; skipping", file=sys.stderr)
            else:
                isolatable.append(sid)
        for model in models:
            config_dir = eval_dir / config_dir_name(model, label)
            base = {"skill_path": str(skill_path), "eval_id": item["id"], "model": model, "label": label,
                    "timeout": timeout, "cache_dir": cache_dir}
            for r in range(1, runs + 1):
                jobs.append({**base, "mode": "chain", "run_number": r, "run_dir": str(config_dir / f"run-{r}")})
                for sid in isolatable:
                    jobs.append({**base, "mode": "isolated", "isolated_step": sid, "run_number": r,
                                 "run_dir": str(config_dir / "isolated" / sid / f"run-{r}")})
    return jobs


def _run_job_worker(job: dict, grader_model: str | None, grader_timeout: int, dry_run: bool) -> dict:
    executor = None
    if dry_run:
        skill_path = Path(job["skill_path"])
        manifest = load_manifest(skill_path)
        item = next(e for e in load_evals(skill_path)["evals"] if e["id"] == job["eval_id"])
        golden = {}
        for step in manifest["steps"]:
            path = golden_artifact(skill_path, item, step)
            if path:
                golden[step["output"]] = path.read_text().strip()
        executor = make_golden_executor(golden)
    llm_grader = make_llm_grader(grader_model, grader_timeout) if grader_model and not dry_run else None
    return run_job(job, executor, llm_grader)


def run_matrix(
    jobs: list[dict], num_workers: int, grader_model: str | None = None, grader_timeout: int = 120,
    dry_run: bool = False,
) -> list[dict]:
    results = []
    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        futures = {pool.submit(_run_job_worker, job, grader_model, grader_timeout, dry_run): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                res = future.result()
                s = res["summary"]
                print(f"  {res['run_dir']}: {s['passed']}/{s['total']}", file=sys.stderr)
                results.append(res)
            except Exception as e:
                print(f"Warning: job failed ({job['run_dir']}): {e}", file=sys.stderr)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run step-level evals across models and repetitions")
    parser.add_argument("--skill-path", required=True, type=Path, help="Path to the skill directory")
    parser.add_argument("--workspace", required=True, type=Path, help="Iteration directory to write results to")
    parser.add_argument("--models", nargs="+", required=True, help="Models to run (e.g. your everyday and your strongest model)")
    parser.add_argument("--runs", type=int, default=5, help="Repetitions per eval per model (default: 5)")
    parser.add_argument("--evals", nargs="+", type=int, default=None, help="Eval ids to run (default: all)")
    parser.add_argument("--isolate", nargs="+", default=[], help="Also run these steps in isolation from golden inputs ('all' = every probabilistic step)")
    parser.add_argument("--label", default=None, help="Config suffix, e.g. 'old_skill' when --skill-path is a snapshot")
    parser.add_argument("--grader-model", default=None, help="Model for LLM-graded assertions (default: leave pending)")
    parser.add_argument("--num-workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per step in seconds")
    parser.add_argument("--no-cache", action="store_true", help="Don't cache deterministic step outputs")
    parser.add_argument("--dry-run", action="store_true", help="Replay golden artifacts instead of calling models (checks your manifest and assertions)")
    args = parser.parse_args()

    skill_path = args.skill_path.resolve()
    manifest = load_manifest(skill_path)
    if manifest is None:
        sys.exit(f"No evals/steps.json found in {skill_path}")
    errors = validate_manifest(manifest, skill_path, load_evals(skill_path))
    if errors:
        sys.exit("Invalid step manifest:\n  - " + "\n  - ".join(errors))
    if args.runs < 1:
        sys.exit("--runs must be >= 1")

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        jobs = plan_jobs(skill_path, workspace, args.models, args.runs, args.evals, args.isolate,
                         args.label, args.timeout, use_cache=not args.no_cache)
    except ValueError as e:
        sys.exit(str(e))

    print(f"Running {len(jobs)} jobs ({len(args.models)} models x {args.runs} runs)...", file=sys.stderr)
    results = run_matrix(jobs, args.num_workers, args.grader_model, dry_run=args.dry_run)
    print(json.dumps({"jobs": len(jobs), "completed": len(results), "workspace": str(workspace)}, indent=2))
    if len(results) < len(jobs):
        sys.exit(1)


if __name__ == "__main__":
    main()
