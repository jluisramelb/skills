#!/usr/bin/env python3
"""Measure whether Copilot CLI picks a skill for the right prompts.

Copies the skill into a temporary project's `.github/skills/` under a
unique name, runs each query with `copilot -p --output-format=json`
several times, and counts a trigger when Copilot emits a `skill.invoked`
event for that skill (or calls its `skill` tool with the skill's name).
Shell and file writes are denied, and a run stops as soon as the skill
is invoked.

Queries file (default: <skill>/evals/triggers.json):

    [{"query": "turn this workflow into a skill", "should_trigger": true},
     {"query": "what's the weather in Lisbon", "should_trigger": false}]

Usage:
    python -m scripts.trigger_eval --skill-path <skill> --model <model> [--runs 3] [--queries FILE]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from scripts.utils import parse_skill_md
except ImportError:
    from utils import parse_skill_md


def detect_trigger(lines, skill_name: str) -> bool:
    """True if Copilot's JSONL event stream shows the skill being invoked."""
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        data = event.get("data") or {}
        if event.get("type") == "skill.invoked" and data.get("name") == skill_name:
            return True
        if (event.get("type") == "tool.execution_start" and data.get("toolName") == "skill"
                and skill_name in json.dumps(data.get("arguments"))):
            return True
    return False


def stage_skill(skill_path: Path, project: Path) -> str:
    """Copy the skill into project/.github/skills/<unique-name>/ and return that name."""
    name, _, content = parse_skill_md(skill_path)
    unique = f"{name}-trigger-{uuid.uuid4().hex[:6]}"
    target = project / ".github" / "skills" / unique
    shutil.copytree(skill_path, target, ignore=shutil.ignore_patterns("evals", "__pycache__", "*.pyc"))
    renamed = re.sub(r"^name:.*$", f"name: {unique}", content, count=1, flags=re.MULTILINE)
    (target / "SKILL.md").write_text(renamed)
    return unique


def run_query(query: str, skill_name: str, project: Path, model: str, timeout: int) -> bool:
    cmd = [
        "copilot", "-p", query, f"--model={model}", "--output-format=json", "--no-ask-user",
        "--no-custom-instructions", "--no-color", f"--add-dir={project}", "--allow-all-tools",
        "--deny-tool=shell", "--deny-tool=write",
    ]
    proc = subprocess.Popen(cmd, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        for line in proc.stdout:
            if detect_trigger([line], skill_name):
                return True
        return False
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def evaluate(queries: list[dict], runs: int, threshold: float, run_once) -> dict:
    """Score queries given run_once(query) -> bool. Pure, so it can be tested."""
    jobs = [(i, q["query"]) for i, q in enumerate(queries) for _ in range(runs)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda job: (job[0], run_once(job[1])), jobs))
    results = []
    for i, q in enumerate(queries):
        triggers = sum(1 for idx, hit in outcomes if idx == i and hit)
        rate = triggers / runs
        results.append({
            "query": q["query"],
            "should_trigger": q["should_trigger"],
            "triggers": triggers,
            "runs": runs,
            "trigger_rate": round(rate, 4),
            "pass": (rate >= threshold) == q["should_trigger"],
        })
    passed = sum(r["pass"] for r in results)
    return {"results": results, "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results)}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure skill triggering in Copilot CLI")
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--model", required=True, help="Model Copilot uses to decide whether to load the skill")
    parser.add_argument("--queries", type=Path, default=None, help="Queries JSON (default: <skill>/evals/triggers.json)")
    parser.add_argument("--runs", type=int, default=3, help="Runs per query (default: 3)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Trigger rate that counts as triggering")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per run")
    parser.add_argument("--output", type=Path, default=None, help="Write results JSON here as well")
    args = parser.parse_args()

    skill_path = args.skill_path.resolve()
    queries_path = args.queries or skill_path / "evals" / "triggers.json"
    queries = json.loads(queries_path.read_text())
    if not isinstance(queries, list) or not all(
            isinstance(q, dict) and isinstance(q.get("query"), str) and isinstance(q.get("should_trigger"), bool)
            for q in queries):
        sys.exit(f"{queries_path}: expected a list of {{'query': str, 'should_trigger': bool}}")
    if shutil.which("copilot") is None:
        sys.exit("copilot not found; install GitHub Copilot CLI and run `copilot login`")

    with tempfile.TemporaryDirectory(prefix="trigger-eval-") as tmp:
        project = Path(tmp)
        name = stage_skill(skill_path, project)
        report = evaluate(queries, args.runs, args.threshold,
                          lambda q: run_query(q, name, project, args.model, args.timeout))

    for r in report["results"]:
        mark = "PASS" if r["pass"] else "FAIL"
        want = "should" if r["should_trigger"] else "should not"
        print(f"[{mark}] {r['triggers']}/{r['runs']} ({want} trigger): {r['query'][:80]}", file=sys.stderr)
    s = report["summary"]
    print(f"{s['passed']}/{s['total']} queries behave as expected", file=sys.stderr)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
