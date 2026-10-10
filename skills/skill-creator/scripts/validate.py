#!/usr/bin/env python3
"""Validate a skill folder for GitHub Copilot CLI.

Checks the SKILL.md frontmatter, that the folder name matches `name`
(Copilot discovers skills by folder), and evals/steps.json + evals/evals.json
when present.

Usage:
    python -m scripts.validate <skill_directory>
"""

import re
import sys
from pathlib import Path

import yaml

try:
    from scripts.manifest import validate_skill_evals
except ImportError:  # run directly as `python validate.py`
    from manifest import validate_skill_evals

# Fields Copilot CLI reads, plus the Agent Skills spec's optional ones.
ALLOWED_KEYS = {
    "name", "description", "license", "allowed-tools", "user-invocable",
    "disable-model-invocation", "argument-hint", "metadata", "compatibility",
}
MAX_BODY_LINES = 500


def validate_skill(skill_path) -> tuple[bool, str]:
    """Return (valid, message). Warnings are appended to a valid message."""
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text()
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not match:
        return False, "SKILL.md must start with YAML frontmatter between --- lines"
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"
    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML mapping"

    unexpected = set(frontmatter) - ALLOWED_KEYS
    if unexpected:
        return False, (f"Unexpected frontmatter key(s): {', '.join(sorted(unexpected))}. "
                       f"Allowed: {', '.join(sorted(ALLOWED_KEYS))}")

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        return False, "Missing 'name' in frontmatter"
    name = name.strip()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        return False, f"Name '{name}' must be kebab-case (lowercase letters, digits, single hyphens)"
    if len(name) > 64:
        return False, f"Name is too long ({len(name)} characters, max 64)"
    if name != skill_path.resolve().name:
        return False, f"Name '{name}' must match the folder name '{skill_path.resolve().name}'"

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        return False, "Missing 'description' in frontmatter"
    if "<" in description or ">" in description:
        return False, "Description cannot contain angle brackets (< or >)"
    if len(description.strip()) > 1024:
        return False, f"Description is too long ({len(description.strip())} characters, max 1024)"

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None and (not isinstance(compatibility, str) or len(compatibility) > 500):
        return False, "Compatibility must be a string of at most 500 characters"
    for key in ("user-invocable", "disable-model-invocation"):
        if key in frontmatter and not isinstance(frontmatter[key], bool):
            return False, f"'{key}' must be true or false"

    errors = validate_skill_evals(skill_path)
    if errors:
        return False, "Invalid evals:\n  - " + "\n  - ".join(errors)

    message = "Skill is valid!"
    body_lines = len(match.group(2).splitlines())
    if body_lines > MAX_BODY_LINES:
        message += (f"\nWarning: SKILL.md body is {body_lines} lines (aim for under {MAX_BODY_LINES}); "
                    "move detail into references/ and point to it.")
    return True, message


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.validate <skill_directory>")
        sys.exit(1)
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
