"""Step manifest support for step-level skill evaluation.

A step manifest (`evals/steps.json` inside a skill) breaks the skill's
workflow into typed steps. Each step writes exactly one artifact to
`outputs/steps/<NN>-<step-id>.<ext>` so it can be checked on its own.

See references/schemas.md ("steps.json") for the full format.
"""

import json
import re
from pathlib import Path

STEP_TYPES = {"probabilistic", "deterministic", "human"}
STEP_FORMATS = {"json", "markdown", "text"}
ASSERTION_KINDS = {"programmatic", "reference", "llm"}

PROGRAMMATIC_CHECKS = {
    "json_valid",
    "json_required",
    "json_field_equals",
    "json_array_length",
    "regex",
    "contains",
    "not_contains",
    "line_count",
    "word_count",
}
REFERENCE_CHECKS = {
    "exact_match",
    "reference_similarity",
    "reference_json_fields",
}

MANIFEST_RELPATH = Path("evals") / "steps.json"
EVALS_RELPATH = Path("evals") / "evals.json"

_STEP_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_INPUT_PLACEHOLDER_RE = re.compile(r"\{input:([^}]+)\}")


def load_manifest(skill_path: Path) -> dict | None:
    """Load evals/steps.json from a skill, or return None if it doesn't exist."""
    path = Path(skill_path) / MANIFEST_RELPATH
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_evals(skill_path: Path) -> dict | None:
    """Load evals/evals.json from a skill, or return None if it doesn't exist."""
    path = Path(skill_path) / EVALS_RELPATH
    if not path.exists():
        return None
    return json.loads(path.read_text())


def steps_by_id(manifest: dict) -> dict[str, dict]:
    return {s["id"]: s for s in manifest.get("steps", []) if isinstance(s, dict) and "id" in s}


def topological_order(steps: list[dict]) -> list[str]:
    """Return step ids in dependency order. Raises ValueError on cycles.

    Ties are broken by manifest order so the result is stable.
    """
    ids = [s["id"] for s in steps]
    deps = {s["id"]: [i for i in s.get("inputs", []) if i in ids] for s in steps}
    order: list[str] = []
    state: dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(node: str, path: list[str]) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            cycle = path[path.index(node):] + [node]
            raise ValueError("Dependency cycle: " + " -> ".join(cycle))
        state[node] = 1
        for dep in deps[node]:
            visit(dep, path + [node])
        state[node] = 2
        order.append(node)

    for sid in ids:
        visit(sid, [])
    return order


def upstream(steps: list[dict], step_id: str) -> set[str]:
    """All transitive dependencies of a step."""
    by_id = {s["id"]: s for s in steps}
    seen: set[str] = set()
    stack = list(by_id.get(step_id, {}).get("inputs", []))
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in by_id:
            continue
        seen.add(cur)
        stack.extend(by_id[cur].get("inputs", []))
    return seen


def downstream(steps: list[dict], step_id: str) -> set[str]:
    """All steps that transitively depend on a step."""
    return {s["id"] for s in steps if step_id in upstream(steps, s["id"])}


def step_format(step: dict) -> str:
    """The artifact format of a step, inferred from the extension if not set."""
    if step.get("format"):
        return step["format"]
    suffix = Path(step.get("output", "")).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".md":
        return "markdown"
    return "text"


def golden_artifact(skill_path: Path, eval_item: dict, step: dict) -> Path | None:
    """Path to the golden artifact for a step in an eval, if one exists."""
    golden_dir = eval_item.get("golden_dir")
    if not golden_dir:
        return None
    path = Path(skill_path) / golden_dir / step["output"]
    return path if path.exists() else None


def resolve_fixture(skill_path: Path, step: dict, eval_item: dict | None) -> Path | None:
    """Find the recorded decision to replay for a human step.

    Order: the eval's `step_fixtures[step_id]`, then the eval's golden
    artifact, then the manifest's default `fixture`.
    """
    skill_path = Path(skill_path)
    if eval_item:
        override = eval_item.get("step_fixtures", {}).get(step["id"])
        if override:
            path = skill_path / override
            return path if path.exists() else None
        golden = golden_artifact(skill_path, eval_item, step)
        if golden:
            return golden
    default = step.get("fixture")
    if default:
        path = skill_path / default
        return path if path.exists() else None
    return None


def _validate_check(prefix: str, assertion: dict, skill_path: Path, errors: list[str]) -> None:
    kind = assertion.get("kind")
    if kind not in ASSERTION_KINDS:
        errors.append(f"{prefix}: 'kind' must be one of {sorted(ASSERTION_KINDS)}, got {kind!r}")
        return
    if not isinstance(assertion.get("text"), str) or not assertion["text"].strip():
        errors.append(f"{prefix}: missing 'text'")
    if kind == "llm":
        if not isinstance(assertion.get("rubric"), str) or not assertion["rubric"].strip():
            errors.append(f"{prefix}: llm assertions need a 'rubric'")
        return
    check = assertion.get("check")
    if not isinstance(check, dict):
        errors.append(f"{prefix}: {kind} assertions need a 'check' object")
        return
    allowed = PROGRAMMATIC_CHECKS if kind == "programmatic" else REFERENCE_CHECKS
    ctype = check.get("type")
    if ctype not in allowed:
        errors.append(f"{prefix}: check type {ctype!r} is not a valid {kind} check ({', '.join(sorted(allowed))})")
        return
    if ctype == "regex":
        try:
            re.compile(check.get("pattern", ""))
        except re.error as e:
            errors.append(f"{prefix}: invalid regex: {e}")
    if kind == "reference":
        ref = check.get("reference")
        if not ref:
            errors.append(f"{prefix}: reference checks need a 'reference' path")
        elif not (skill_path / ref).exists():
            errors.append(f"{prefix}: reference file not found: {ref}")


def validate_manifest(manifest: dict, skill_path: Path, evals: dict | None = None) -> list[str]:
    """Validate a step manifest (and the step parts of evals.json).

    Returns a list of human-readable errors; empty means valid.
    """
    skill_path = Path(skill_path)
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return ["steps.json must be a JSON object"]
    steps = manifest.get("steps")
    if not isinstance(steps, list) or not steps:
        return ["steps.json must have a non-empty 'steps' list"]

    seen_ids: set[str] = set()
    seen_prefixes: dict[str, str] = {}
    for idx, step in enumerate(steps):
        where = f"step #{idx + 1}"
        if not isinstance(step, dict):
            errors.append(f"{where}: must be an object")
            continue
        sid = step.get("id")
        if not isinstance(sid, str) or not _STEP_ID_RE.match(sid):
            errors.append(f"{where}: 'id' must be kebab-case, got {sid!r}")
            continue
        where = f"step '{sid}'"
        if sid in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(sid)

        if step.get("type") not in STEP_TYPES:
            errors.append(f"{where}: 'type' must be one of {sorted(STEP_TYPES)}, got {step.get('type')!r}")

        output = step.get("output")
        if not isinstance(output, str) or not output:
            errors.append(f"{where}: missing 'output' file")
        else:
            m = re.match(r"^(\d{2})-(.+)\.([A-Za-z0-9]+)$", output)
            if not m or m.group(2) != sid:
                errors.append(f"{where}: output must be named '<NN>-{sid}.<ext>', got {output!r}")
            elif m.group(1) in seen_prefixes:
                errors.append(f"{where}: output number {m.group(1)} is already used by step '{seen_prefixes[m.group(1)]}'")
            else:
                seen_prefixes[m.group(1)] = sid

        fmt = step.get("format")
        if fmt is not None and fmt not in STEP_FORMATS:
            errors.append(f"{where}: 'format' must be one of {sorted(STEP_FORMATS)}")
        schema = step.get("schema")
        if schema is not None and not (isinstance(schema, dict) and isinstance(schema.get("required", []), list)):
            errors.append(f"{where}: 'schema' must be an object with a 'required' list")

        inputs = step.get("inputs", [])
        if not isinstance(inputs, list):
            errors.append(f"{where}: 'inputs' must be a list of step ids")

        if step.get("type") == "deterministic":
            command = step.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
                errors.append(f"{where}: deterministic steps need a 'command' list (run by the harness, not the model)")
            else:
                for ref in _INPUT_PLACEHOLDER_RE.findall(" ".join(command)):
                    if ref not in inputs:
                        errors.append(f"{where}: command uses {{input:{ref}}} but '{ref}' is not in inputs")

    if errors:
        return errors

    for step in steps:
        for dep in step.get("inputs", []):
            if dep == step["id"]:
                errors.append(f"step '{step['id']}': cannot depend on itself")
            elif dep not in seen_ids:
                errors.append(f"step '{step['id']}': unknown input step '{dep}'")
    if errors:
        return errors

    try:
        topological_order(steps)
    except ValueError as e:
        errors.append(str(e))
        return errors

    eval_items = (evals or {}).get("evals", [])

    # Human steps must be replayable in automated runs.
    for step in steps:
        if step["type"] != "human":
            continue
        if step.get("fixture") and resolve_fixture(skill_path, step, None) is None:
            errors.append(f"step '{step['id']}': fixture not found: {step['fixture']}")
            continue
        if eval_items:
            for item in eval_items:
                if resolve_fixture(skill_path, step, item) is None:
                    errors.append(
                        f"step '{step['id']}': eval {item.get('id')} has no recorded decision "
                        "(add step_fixtures, a golden_dir artifact, or a manifest 'fixture')"
                    )
        elif not step.get("fixture"):
            errors.append(f"step '{step['id']}': human steps need a 'fixture' so automated runs can replay the decision")

    for item in eval_items:
        eid = item.get("id")
        golden_dir = item.get("golden_dir")
        if golden_dir and not (skill_path / golden_dir).is_dir():
            errors.append(f"eval {eid}: golden_dir not found: {golden_dir}")
        for sid in item.get("step_fixtures", {}):
            if sid not in seen_ids:
                errors.append(f"eval {eid}: step_fixtures references unknown step '{sid}'")
        step_assertions = item.get("step_assertions", {})
        if not isinstance(step_assertions, dict):
            errors.append(f"eval {eid}: 'step_assertions' must be an object keyed by step id")
            continue
        for sid, assertions in step_assertions.items():
            if sid not in seen_ids:
                errors.append(f"eval {eid}: step_assertions references unknown step '{sid}'")
                continue
            if not isinstance(assertions, list):
                errors.append(f"eval {eid}: step_assertions['{sid}'] must be a list")
                continue
            for a_idx, assertion in enumerate(assertions):
                prefix = f"eval {eid} step '{sid}' assertion #{a_idx + 1}"
                if not isinstance(assertion, dict):
                    errors.append(f"{prefix}: must be an object")
                    continue
                _validate_check(prefix, assertion, skill_path, errors)

    return errors


def validate_skill_steps(skill_path: Path) -> list[str]:
    """Validate a skill's step manifest if it has one. Returns errors."""
    skill_path = Path(skill_path)
    try:
        manifest = load_manifest(skill_path)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {MANIFEST_RELPATH}: {e}"]
    if manifest is None:
        return []
    try:
        evals = load_evals(skill_path)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {EVALS_RELPATH}: {e}"]
    return validate_manifest(manifest, skill_path, evals)
