#!/usr/bin/env python3
"""Check that a 3P update follows the strict format in examples/3p-updates.md.

Usage:
    python scripts/check_3p_format.py <draft.md> [<result.json>]

Writes (or prints) a JSON report:
    {"valid": bool, "errors": [...], "sections": {"progress": {"sentences": n}, ...}}

Exits 0 even when the draft is invalid; the report carries the verdict.
The output depends only on the input, so the same draft always gives
the same report.
"""

import json
import re
import sys
from pathlib import Path

SECTIONS = ["Progress", "Plans", "Problems"]
MAX_SENTENCES = 3
MARKDOWN_RE = re.compile(r"(\*\*|__|^#|^\s*[-*] |`)", re.MULTILINE)
SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def count_sentences(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    ends = len(SENTENCE_END_RE.findall(text))
    # A trailing fragment without final punctuation still counts as a sentence.
    return ends if text[-1] in ".!?" else ends + 1


def check_3p(draft: str) -> dict:
    errors: list[str] = []
    lines = [line.strip() for line in draft.strip().splitlines() if line.strip()]
    report: dict = {"valid": False, "errors": errors, "sections": {}}

    if len(lines) != 4:
        errors.append(f"Expected exactly 4 non-empty lines (header + 3 sections), found {len(lines)}")

    if MARKDOWN_RE.search(draft):
        errors.append("Uses markdown formatting (bold, headings, bullets or code); the format is plain lines only")

    if lines:
        header = lines[0]
        if header[0].isascii():
            errors.append("Header must start with an emoji")
        if not re.search(r"\([^)]*\d[^)]*\)\s*$", header):
            errors.append("Header must end with the dates covered in parentheses")
    else:
        errors.append("Draft is empty")

    for idx, name in enumerate(SECTIONS, start=1):
        key = name.lower()
        if idx >= len(lines):
            errors.append(f"Missing '{name}:' line")
            continue
        line = lines[idx]
        prefix = f"{name}: "
        if not line.startswith(prefix):
            errors.append(f"Line {idx + 1} must start with '{prefix}'")
            continue
        n = count_sentences(line[len(prefix):])
        report["sections"][key] = {"sentences": n}
        if not 1 <= n <= MAX_SENTENCES:
            errors.append(f"'{name}' has {n} sentences (allowed 1-{MAX_SENTENCES})")

    report["valid"] = not errors
    return report


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    report = check_3p(Path(sys.argv[1]).read_text())
    out = json.dumps(report, indent=2) + "\n"
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(out)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
