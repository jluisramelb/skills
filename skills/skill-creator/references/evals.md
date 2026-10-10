# Evals reference

Read this when you set up or run evals. Contents:

1. [Files and layout](#1-files-and-layout)
2. [evals.json](#2-evalsjson)
3. [steps.json (optional)](#3-stepsjson-optional)
4. [Checks](#4-checks)
5. [Running](#5-running)
6. [Reading the results](#6-reading-the-results)
7. [Ambiguity pass](#7-ambiguity-pass)
8. [Trigger evals](#8-trigger-evals)

## 1. Files and layout

Inside the skill:

```
<skill>/evals/
├── evals.json        # test prompts and checks (required to run evals)
├── steps.json        # optional: the workflow as typed steps
├── triggers.json     # optional: should/shouldn't trigger queries
└── files/            # inputs, golden artifacts, recorded human decisions
```

Outside the skill, one directory per iteration (`<skill-name>-workspace/iteration-N/`):

```
eval-<id>-<name>/<model>[__<label>]/run-R/
├── run_meta.json
├── outputs/steps/<NN>-<step>.<ext>    # one artifact per step
├── outputs/...                        # other files the run created
├── logs/<NN>-<step>.json              # prompt, response, errors
├── timing.json                        # {"duration_ms": ...}
└── grading.json
eval-<id>-<name>/<model>/isolated/<step>/run-R/   # with --isolate
benchmark.json, benchmark.md                      # from aggregate.py
```

`<label>` marks a baseline: `no_skill` (`--no-skill`) or `old_skill` (a snapshot, `--label old_skill`).

## 2. evals.json

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "name": "short-descriptive-name",
      "prompt": "What a real user would type, with real detail",
      "files": ["evals/files/input.csv"],
      "expectations": ["The summary names the three largest accounts"],
      "golden_dir": "evals/files/golden/short-descriptive-name",
      "step_fixtures": {"approve": "evals/files/approve-yes.json"},
      "step_assertions": {"result": [{"text": "At most 200 words", "kind": "programmatic", "check": {"type": "word_count", "max": 200}}]}
    }
  ]
}
```

- `id`, `prompt`: required. `name` names the workspace folder.
- `files`: input paths relative to the skill root.
- `expectations`: plain-language end-to-end checks. They're graded by a model against the final step's artifact and the files the run created.
- `golden_dir`: the correct artifact for each step, named like the step outputs. Used by `--dry-run`, by isolated runs, by `reference` checks, and as the recorded decision for human steps.
- `step_fixtures`: `{step_id: path}` recorded human decisions that override `golden_dir`.
- `step_assertions`: `{step_id: [check, ...]}`. Without `steps.json`, the only step is `result`.

## 3. steps.json (optional)

Without it, a skill is one probabilistic step, `result` (`01-result.md`), that does the whole task with all tools. Add a manifest when the skill has distinct stages and you need to know which one breaks.

```json
{
  "skill_name": "internal-comms",
  "steps": [
    {"id": "classify", "type": "probabilistic", "source_section": "SKILL.md > How to use this skill",
     "description": "Decide which kind of communication is requested.",
     "inputs": [], "output": "01-classify.json",
     "schema": {"required": ["comm_type"], "example": {"comm_type": "3p-update"}}},
    {"id": "scope", "type": "human", "inputs": ["classify"], "output": "02-scope.json",
     "fixture": "evals/files/default-scope.json"},
    {"id": "format-check", "type": "deterministic", "inputs": ["draft"], "output": "05-format-check.json",
     "command": ["python", "scripts/check_3p_format.py", "{input:draft}", "{output}"]}
  ]
}
```

- `type`: `probabilistic` (a model does it), `deterministic` (a bundled script does it, run by the harness), `human` (a person decides; replayed from a recorded decision).
- `output`: `<NN>-<id>.<ext>`, NN unique. `.json` artifacts get automatic critical checks for valid JSON and `schema.required`.
- `inputs`: earlier steps whose artifacts this step reads. Must not form a cycle.
- `source_section`: where the step's instructions live. The ambiguity pass reads it.
- `description`: say *what* artifact to produce, not *how*. Instructions belong in SKILL.md, or you end up testing the manifest instead of the skill.
- `tools`: `read` (default: the shell and file writes are denied) or `all` (the step may run commands and write files in its run directory).
- `command`: deterministic steps only. Runs from the skill root without a shell. Placeholders: `{input:<id>}`, `{output}`, `{skill}`. A leading `python` uses the current interpreter. The output is cached by input hash and must be identical on two runs.
- `fixture`: human steps only. The default recorded decision.

`python -m scripts.validate <skill>` checks all of this, including that every human step has a decision for every eval.

## 4. Checks

Use the cheapest kind that can decide the question:

```json
{"id": "no-stale-items", "text": "Progress leaves out work finished before the period",
 "kind": "programmatic", "critical": true,
 "check": {"type": "not_contains", "field": "progress", "value": "Android 13"}}
```

- `programmatic`: `json_valid`, `json_required` (`fields`), `json_field_equals` (`field`, `value`, `case_insensitive`), `json_array_length` (`field`, `min`, `max`), `regex` (`pattern`, `flags` from `ims`, `should_match`), `contains` / `not_contains` (`value`), `line_count` / `word_count` (`min`, `max`).
- `reference`: `exact_match`, `reference_similarity` (`min_similarity` 0–1), `reference_json_fields` (`fields`); all take `reference`, a path relative to the skill root.
- `llm`: `rubric` instead of `check`. Use only when a script can't decide.
- `field` is a dotted path into JSON (`a.b.0`).
- `critical: true`: if it fails, every downstream step is marked `contaminated` and its failures count as inherited, not its own.

A good check fails on a bad output. If it would pass on an empty or generic answer, it's measuring nothing.

## 5. Running

Run these from the skill-creator directory.

```bash
python -m scripts.validate <skill>
python -m scripts.run_evals --skill-path <skill> --workspace <ws>/iteration-0 --models dry --runs 1 --dry-run
python -m scripts.run_evals --skill-path <skill> --workspace <ws>/iteration-N \
  --models <everyday-model> <strongest-model> --runs 5 [--isolate all] [--grader-model <model>]
python -m scripts.run_evals --skill-path <skill> --workspace <ws>/iteration-N --models <everyday-model> --runs 5 --no-skill
python -m scripts.aggregate <ws>/iteration-N --skill-name <name>
```

- The dry run replays the golden artifacts. Every check should pass on them; if one doesn't, fix the check or the golden file before spending model calls.
- Each probabilistic step is one `copilot -p --model=<m> --silent --no-ask-user --no-custom-instructions --allow-all-tools` call in its run directory. Read-only steps add `--deny-tool=shell --deny-tool=write`. `--allow-all-tools` is required in non-interactive mode, so only run evals on skills you trust, and run `tools: all` steps somewhere you don't mind files being written.
- `--isolate all` also runs each probabilistic step from the golden upstream artifacts. Steps without golden upstream artifacts are skipped with a warning.
- Baselines: `--no-skill` for a new skill. For an existing skill, `cp -r <skill> <ws>/skill-snapshot` before editing, then `--skill-path <ws>/skill-snapshot --label old_skill`.
- Without `--grader-model`, LLM checks stay pending (`passed: null`). Either rerun `python -m scripts.grade <run_dir>... --grader-model <model>`, or fill in `passed` and `evidence` in grading.json yourself and rerun `python -m scripts.grade <run_dir>...`. Filled-in verdicts are kept.
- `--evals 1 3` runs a subset. Keep a few evals out of the loop and run them at the end, so the wording doesn't overfit.

## 6. Reading the results

`benchmark.md` has:
- Per configuration: pass rate and time (mean ± stddev), and the delta of the skill vs. each baseline.
- Step breakdown (step × configuration): share of runs where every check passed, and own vs. inherited failures.
- Failure propagation (upstream critical failure → downstream failure) and flags.
- Failing checks, each with how often it failed and an example run directory.

Flags in `step_summary.flags`:

| Flag | Meaning | Next move |
|---|---|---|
| `inconsistent` | passes in some runs, not others | ambiguity pass |
| `unstable_output` | artifacts differ a lot across runs (JSON exact match < 0.6, text divergence > 0.35) | ambiguity pass; check `field_agreement` |
| `model_gap` | success rates differ by ≥ 25 points between configurations | ambiguity pass; the stronger model is filling in intent the text doesn't state |
| `always_fails` | never passes | instruction missing or wrong, or the check is wrong |
| `inherited_failures` | most failures come from upstream | fix the upstream step first |
| `nondeterministic` | a deterministic step gave different outputs for the same input | script bug |

Before you trust a number, explain it:
- How many checks were pending?
- Does a check pass with and without the skill? Then it's non-discriminating.
- Is a failure the step's own, or inherited from upstream?
- Is a pass rate based on two runs?

Open the actual artifacts behind any surprising cell.

## 7. Ambiguity pass

For each `model_gap`, `inconsistent`, `unstable_output` or `always_fails` step whose failures are mostly its own (delegate this to a subagent when there are several):

1. Read the step's `source_section` word for word.
2. Open the differing artifacts across runs and models, and group them by how they behave. Two or three distinct "readings" usually emerge. The responses in `logs/` show which words the model leaned on.
3. Find the sentence that supports each reading. The ambiguity is confirmed when one sentence can reasonably be read both ways, or two sentences contradict each other. Usual culprits:
   - relative words with no anchor ("recent", "short", "the next time period")
   - rules without a reason
   - prose that disagrees with an example
   - cases the text doesn't cover
4. Rewrite only that sentence, so the intended reading is the only reasonable one, and add *why*. Keep the rewrite general.
5. Write `<ws>/iteration-N/ambiguity.json`:

```json
{"findings": [{"step": "gather", "flags": ["model_gap"], "source_section": "examples/3p-updates.md > Instructions",
   "ambiguous_text": "exact quote", "readings": [{"configs": ["m1"], "runs": ["eval-1-x/m1/run-2"], "interpretation": "..."}],
   "suggested_rewrite": "...", "why": "...", "confidence": "high"}],
 "not_ambiguity": [{"step": "draft", "explanation": "failures disappear in isolated runs; fix gather first"}]}
```

Don't rewrite steps whose failures are inherited. Don't treat a weak check or a debatable golden file as skill ambiguity; put those under `not_ambiguity`.

## 8. Trigger evals

`evals/triggers.json`: about 20 realistic queries, roughly half `should_trigger: true`. The useful negatives are near-misses that share keywords but need something else.

```bash
python -m scripts.trigger_eval --skill-path <skill> --model <model> --runs 3
```

The script copies the skill into a temporary project's `.github/skills/` under a unique name, runs each query with `copilot -p --output-format=json` (shell and file writes denied), and counts a trigger when Copilot emits a `skill.invoked` event for it. For a failing query, rewrite the `description`:
- Copilot decides from `name` and `description` alone.
- Say what the skill does and the situations it's for, including ones where the user doesn't name it.
- Rerun on a held-out half of the queries before you keep the change.
