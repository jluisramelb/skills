# Step-level evaluation

Use this for multi-step skills whose results are inconsistent, or when the user wants the skill to hold up across models (for example their everyday model and their strongest one). Whole-run grading tells you *that* an output is wrong. Step-level evaluation tells you *which step* went wrong, whether it went wrong on its own or inherited a bad input, and *which sentence* in the skill the models read differently. It's optional; skills without a step manifest keep working exactly as in the main loop in SKILL.md.

## 1. Map the skill into typed steps

Read the workflow in SKILL.md and split it into steps, each marked as:
- **probabilistic**: a model does it (classifying, extracting, drafting)
- **deterministic**: code does it, so it should be a bundled script in `scripts/` with ordinary tests, not instructions the model follows. If the workflow asks the model to do something mechanical (validate a format, count, convert), that's a strong hint to move it into a script
- **human**: a person decides (confirming scope, approving a draft)

Write the map to `evals/steps.json`. Give each step its `source_section`, the steps whose artifacts it reads, and exactly **one artifact** it writes, named `<NN>-<step-id>.<ext>`. Prefer structured artifacts (JSON, or Markdown with fixed headings) so checks can parse them. Keep step descriptions about *what* to produce; the *how* belongs in SKILL.md, or you'll be testing the manifest instead of the skill. See `references/schemas.md` for the format and, in the anthropics/skills repository, `skills/internal-comms/evals/` for a worked example.

Human decisions are replayed from recorded fixtures (a golden artifact or `step_fixtures`), so automated runs don't pause and stay comparable.

## 2. Write checks for each step

Add `step_assertions` (keyed by step id) to each eval in `evals/evals.json`, alongside the end-to-end `expectations`. Use the cheapest check that can decide:
1. **Programmatic**: schema, required fields, counts, regex, exact match for deterministic steps
2. **Reference**: compare against a golden artifact in the eval's `golden_dir`
3. **LLM-graded**: a rubric, only when a script can't decide

Mark checks `critical` when a failure would poison later steps. Downstream steps are then flagged as contaminated, and their failures count as inherited rather than their own.

Run `python -m scripts.quick_validate <skill-path>` to check the manifest (types, outputs, no cycles, recorded decisions for human steps, well-formed checks). Then do a dry run from the skill-creator directory (like the other scripts), which replays the golden artifacts instead of calling models. Every check should pass on the golden artifacts; if one doesn't, fix the check or the golden file before spending tokens:

```bash
python -m scripts.run_step_eval --skill-path <skill> --workspace <ws>/iteration-0 --models dry --runs 1 --dry-run
```

## 3. Run the matrix

```bash
python -m scripts.run_step_eval --skill-path <skill> --workspace <skill-name>-workspace/iteration-N \
  --models <everyday-model> <strongest-model> --runs 5 --isolate all [--grader-model <model>]
```

Each probabilistic step runs as its own `claude -p --model` call that reads SKILL.md, the request and the upstream artifacts. Deterministic steps run the manifest's command, are cached by input hash, and run twice on a cache miss to prove they're reproducible. `--isolate` also re-runs each step from golden upstream artifacts; comparing that with the full chain separates a step's own failures from inherited ones. Results go to `eval-<id>-<name>/<model>/run-R/` (with `outputs/steps/`, `logs/`, `timing.json`, `grading.json`). Without `--grader-model`, LLM checks stay pending (`passed: null`). Either grade them with `agents/grader.md` by filling in `passed`/`evidence` in each run's `grading.json` and then rerunning `python -m scripts.grade_steps <run_dir>` to update the summaries (filled-in verdicts are kept), or run `python -m scripts.grade_steps <run_dir> --grader-model <model>`.

For an existing skill, snapshot it first and run the snapshot with `--label old_skill` as the baseline, as in the main loop in SKILL.md.

## 4. Aggregate, diagnose, review

Run `aggregate_benchmark.py` as usual. When step-level runs are present it adds a `step_summary`: for each step × model, the success rate, pass rate (mean ± stddev), output consistency across runs, own vs inherited failures, how failures propagate along each dependency, and flags. The viewer gets a **Steps** tab with the grid, a side-by-side drill-down of artifacts and the propagation arrows.

Then do the **ambiguity pass** (`agents/analyzer.md`, "Ambiguity Pass"). For each unstable step, or each step with a gap between models, it reads the step's SKILL.md section and the differing artifacts. It then names the exact sentence that was read differently and suggests a sharper rewrite that explains why.

## 5. Close the loop

Rewrite only the flagged sentences (fix inherited failures at their source step first), then rerun the matrix into `iteration-N+1` and launch the viewer with `--previous-workspace`. Stop when every step passes its checks and is stable across the N runs on both the everyday and the strongest model, and the user's feedback in the viewer is empty. If you have enough evals, keep a few out of the iteration loop (select the others with `--evals`) and only run them at the end, so the wording doesn't overfit to the test cases.
