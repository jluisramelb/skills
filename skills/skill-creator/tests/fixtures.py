"""Hand-built fixtures for step-level eval tests.

`make_skill` writes a tiny skill with a four-step manifest:

    extract (probabilistic, json) -> approve (human, json) -> write (probabilistic, md) -> count (deterministic, json)
"""

import json
import re
from pathlib import Path

SKILL_MD = """---
name: tiny-skill
description: A tiny skill used to test step-level evaluation.
---

# Tiny skill

1. Extract the topic from the request.
2. Ask the user to approve the topic.
3. Write one sentence about the topic.
4. Count the words with scripts/count_words.py.
"""

COUNT_SCRIPT = """import json, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
Path(sys.argv[2]).write_text(json.dumps({"words": len(text.split())}) + "\\n")
"""

RANDOM_SCRIPT = """import json, sys, uuid
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps({"words": uuid.uuid4().hex}) + "\\n")
"""

GOLDEN = {
    "01-extract.json": {"topic": "otters"},
    "02-approve.json": {"approved": True},
    "03-write.md": "Otters hold hands while they sleep.\n",
    "04-count.json": {"words": 6},
}


def manifest(count_script: str = "scripts/count_words.py") -> dict:
    return {
        "skill_name": "tiny-skill",
        "steps": [
            {"id": "extract", "type": "probabilistic", "source_section": "1. Extract", "inputs": [],
             "output": "01-extract.json", "schema": {"required": ["topic"]}},
            {"id": "approve", "type": "human", "source_section": "2. Ask", "inputs": ["extract"],
             "output": "02-approve.json"},
            {"id": "write", "type": "probabilistic", "source_section": "3. Write", "inputs": ["extract", "approve"],
             "output": "03-write.md"},
            {"id": "count", "type": "deterministic", "source_section": "4. Count", "inputs": ["write"],
             "output": "04-count.json", "command": ["python", count_script, "{input:write}", "{output}"]},
        ],
    }


def evals() -> dict:
    return {
        "skill_name": "tiny-skill",
        "evals": [{
            "id": 1,
            "name": "otters",
            "prompt": "Write a sentence about otters.",
            "golden_dir": "evals/files/golden/otters",
            "step_assertions": {
                "extract": [
                    {"id": "topic", "text": "Topic is otters", "kind": "programmatic", "critical": True,
                     "check": {"type": "json_field_equals", "field": "topic", "value": "otters"}},
                ],
                "write": [
                    {"id": "mentions", "text": "Mentions otters", "kind": "programmatic", "critical": True,
                     "check": {"type": "contains", "value": "otter"}},
                    {"id": "short", "text": "One short sentence", "kind": "programmatic",
                     "check": {"type": "word_count", "max": 12}},
                    {"id": "fun", "text": "Is fun", "kind": "llm", "rubric": "The sentence is delightful."},
                ],
                "count": [
                    {"id": "count-ref", "text": "Count matches golden", "kind": "reference",
                     "check": {"type": "exact_match", "reference": "evals/files/golden/otters/04-count.json"}},
                ],
            },
        }],
    }


def make_skill(root: Path, manifest_data: dict | None = None, evals_data: dict | None = None,
               random_script: bool = False) -> Path:
    skill = root / "tiny-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "evals" / "files" / "golden" / "otters").mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL_MD)
    (skill / "scripts" / "count_words.py").write_text(COUNT_SCRIPT)
    (skill / "scripts" / "random_words.py").write_text(RANDOM_SCRIPT)
    for name, content in GOLDEN.items():
        path = skill / "evals" / "files" / "golden" / "otters" / name
        path.write_text(content if isinstance(content, str) else json.dumps(content))
    m = manifest_data or manifest("scripts/random_words.py" if random_script else "scripts/count_words.py")
    (skill / "evals" / "steps.json").write_text(json.dumps(m, indent=2))
    (skill / "evals" / "evals.json").write_text(json.dumps(evals_data or evals(), indent=2))
    return skill


def scripted_executor(outputs_by_model: dict[str, dict[str, str]]):
    """Fake `claude -p`: returns a canned artifact per (model, output file)."""
    def run(prompt, model, cwd, skill_path, timeout):
        output = re.search(r"OUTPUT_FILE: (\S+)", prompt).group(1)
        content = outputs_by_model.get(model, {}).get(output)
        if isinstance(content, list):  # vary by run number (cwd is .../run-R)
            run_number = int(Path(cwd).name.split("-")[1])
            content = content[(run_number - 1) % len(content)]
        if content is None:
            content = GOLDEN[output] if isinstance(GOLDEN[output], str) else json.dumps(GOLDEN[output])
        return {"text": f"Sure.\n<artifact>\n{content}\n</artifact>", "duration_ms": 1000, "tokens": 10,
                "is_error": False}
    return run
