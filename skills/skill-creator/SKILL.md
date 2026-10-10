---
name: skill-creator
description: Create, revise, validate, and evaluate reliable GitHub Copilot CLI skills. Use when turning a workflow or idea into a skill, fixing a skill that produces inconsistent results, improving skill instructions, or diagnosing why a skill fails to activate. Prefer minimal instructions, deterministic scripts for exact work, and evidence from evaluations over assumptions.
license: Apache-2.0. Complete terms in LICENSE.txt
---

# Skill Creator

Create the smallest skill that reliably completes its intended task. A skill is a folder with a `SKILL.md`. Copilot reads every skill's `name` and `description`, and loads the body when a task matches.

## Principles

These come from [pstack](https://github.com/cursor/plugins/tree/main/pstack). Apply them to the skills you write and to how you work.

- **Subtract before you add.** The best fix is often deleting the sentence that misleads. Every line in a skill costs attention on every run.
- **Minimize reader load.** A short SKILL.md body, details in `references/` one level deep, and a clear pointer telling the model when to read each file.
- **Encode lessons in structure.** If something must happen exactly, make it a script with tests, not a paragraph. If every test run reinvents the same helper, bundle it.
- **Prove it works.** "It looks right" isn't evidence. Run the evals and open the actual outputs.
- **Explain the number.** Before you trust a pass rate, check what limits it: pending checks, checks that pass without the skill, inherited failures, too few runs.
- **Fix root causes.** When models disagree, find the ambiguous sentence and sharpen it. Don't pile on MUSTs.
- **Never block on the human.** Make reasonable defaults and keep going. Show results and let the user correct you. Ask first only for things that are hard to undo, such as overwriting someone's skill.
- **Guard the context window.** The scripts run the matrix. Read `benchmark.md`, not raw logs, and hand bulk reading to subagents.

## 1. Determine the task

Choose the applicable path:
- **Idea:** identify the workflow, then create a skill (§2–3).
- **Existing draft:** inspect it, correct problems, and validate it (§2, then §3).
- **Unreliable skill:** reproduce the failure, identify the root cause, and test the fix (§3–4).
- **Activation problem:** inspect the description and test triggering behavior (§5).

Use the conversation as the primary source of requirements. Infer reasonable defaults and continue without asking questions unless a decision is consequential or difficult to reverse.

Before writing, establish:
- **Purpose:** what task the skill completes and what a good result looks like.
- **Triggers:** explicit requests and less obvious situations in which it should activate.
- **Inputs and outputs:** required information, output format, and missing-input behavior.
- **Constraints:** tools, dependencies, permissions, and safety boundaries.
- **Verification:** how to determine whether the result is correct. File transforms, extraction, code and fixed workflows deserve evals; for style-only skills a human look is usually enough.

Research external documentation when platform behavior or compatibility is uncertain.

If the user only wants a quick draft, write it, validate it, and skip the evals.

## 2. Write the skill

**Where it goes.** Copilot CLI discovers skills in:
- **Project skills:** `.github/skills/<name>/` (also `.claude/skills/` and `.agents/skills/`), for skills about one repository.
- **Personal skills:** `~/.copilot/skills/<name>/` (or `~/.agents/skills/`), for skills you use everywhere.

Pick the location that matches the skill's scope and tell the user. The folder name must equal `name`. A skill that is only `SKILL.md` can be installed with `copilot skill add <file>`; anything with bundled files needs the whole folder (§6). Run `/skills reload` afterward.

```
<name>/
├── SKILL.md          # frontmatter + instructions (required)
├── scripts/          # deterministic work, run rather than read
├── references/       # detail loaded only when needed
├── assets/           # templates and files used in the output
└── evals/            # evals.json, optional steps.json / triggers.json, files/
```

**Frontmatter:**
- `name`: kebab-case, at most 64 characters, the same as the folder.
- `description`: at most 1024 characters, no angle brackets. Copilot decides from this alone, so say what the skill does *and* when to use it. Lean slightly pushy, because models tend to under-use skills.
- Optional: `license`, `allowed-tools`, `disable-model-invocation: true` (load only when the user types `/name`), `user-invocable`, `argument-hint`.
- `allowed-tools` pre-approves tools. Don't pre-approve `shell` unless the user has reviewed every script and trusts the source.

**Body:**
- Write in the imperative and explain *why*, so the model can handle cases you didn't list.
- Give exact output templates where the format matters, and one or two short input → output examples.
- Keep the body under 500 lines. When a skill covers variants (AWS/GCP, or one guideline per document type), put each in its own reference file and say when to read it.
- Write scripts for anything that must be exact, and tell the model to run them, not reimplement them.
- Nothing in a skill should surprise the user if it were described to them. No malware, no exfiltration, no hidden behavior.

**Check it:**
- Validate with `python -m scripts.validate <skill>`, run from this skill's directory.
- In Copilot CLI, run `/skills reload`, then `/skills info <name>`, then try `/<name> <a real request>`.

## 3. Test it

Put the evals in the skill's `evals/` folder. Read `references/evals.md` for the formats and every option.

1. **Write 2–5 realistic prompts** in `evals/evals.json`, each with plain-language `expectations`. Use real detail: names, numbers, messy input files. Show them to the user and carry on.
2. **Map the steps** if the skill has distinct stages. In `evals/steps.json`, give each stage:
   - a type: `probabilistic` (the model), `deterministic` (a bundled script with its own tests) or `human` (a decision replayed from a fixture)
   - the SKILL.md section it comes from
   - its inputs
   - exactly one artifact

   Add golden artifacts and per-step checks: programmatic first, then a reference comparison, and an LLM rubric only when a script can't decide. Mark checks `critical` when a failure would poison later steps. Without a manifest, the whole skill is one step.
3. **Dry run.** Use `python -m scripts.run_evals --skill-path <skill> --workspace <ws>/iteration-0 --models dry --runs 1 --dry-run`. Every check should pass on the golden artifacts. If one doesn't, the check is wrong.
4. **Run the matrix** with your everyday model and your strongest model, at least 5 runs each. Also run a baseline: `--no-skill` for a new skill, or a snapshot of the old version with `--label old_skill`. Add `--isolate all` when there are steps, to separate a step's own failures from inherited ones. Each step is a `copilot -p --model` call. `--allow-all-tools` is required in non-interactive mode, so run evals only on skills you trust.
5. **Aggregate** with `python -m scripts.aggregate <ws>/iteration-N --skill-name <name>`, then read `benchmark.md`. Grade any pending LLM checks before you trust a pass rate. Open the artifacts behind surprising cells.
6. **Report** as described in [Report](#report).

## 4. Improve

- **Flagged steps:** run the ambiguity pass (references/evals.md §7) on steps flagged `model_gap`, `inconsistent`, `unstable_output` or `always_fails` whose failures are their own. Rewrite only the sentences it identifies, and give the reason in the text. Fix upstream steps first.
- **Generalize:** the skill will run on thousands of prompts that aren't your evals. Prefer a clearer explanation or a different framing over a narrow patch.
- **Cut what doesn't pull its weight:** read the run logs. If the skill sends the model down an unproductive path, delete that part and see what happens.
- **Bundle repeated work:** if every run wrote a similar helper, put it in `scripts/` and point to it.
- **Iterate:** rerun into `iteration-N+1`, with the previous version as the `old_skill` baseline.
- **Stop when:**
  - every step passes its checks and is stable across N runs on both models
  - the held-out evals pass
  - the user has nothing left to change

## 5. Triggering

Add about 20 queries to `evals/triggers.json`, roughly half that should trigger the skill. Make the negatives near-misses, not obviously unrelated. Then run `python -m scripts.trigger_eval --skill-path <skill> --model <model>`. For each failing query, adjust the `description` and recheck it on held-out queries, so you don't tune it to this exact list.

## 6. Install and share

- Copy the whole folder into one of the locations in §2.
- Or register a parent folder that holds several skills with `copilot skill add <dir>`.
- `copilot skill add <file>` copies only `SKILL.md`, so use it only for skills without bundled files.
- Then run `/skills reload` in Copilot CLI.

## Report

Tell the user:
- the skill's location and purpose
- the validation and tests completed
- evaluation results compared with the baseline, when measured
- known limitations and flagged failures
- a small number of concrete examples, with artifact paths when available

Never describe an unrun test as passing. Ask for feedback after presenting the working result, and make obvious improvements without waiting for approval.

## Scripts

Run these from this skill's directory. They need Python 3.10+, PyYAML for `validate`, and GitHub Copilot CLI (`copilot login`) for model runs.

| Script | Does |
|---|---|
| `scripts/validate.py <skill>` | frontmatter, name = folder, `evals/` files |
| `scripts/run_evals.py` | evals × models × runs, chain or isolated, baselines, dry run; grades each run |
| `scripts/grade.py <run_dir>...` | regrade runs, optionally with `--grader-model` |
| `scripts/aggregate.py <iteration>` | `benchmark.json` and `benchmark.md` |
| `scripts/trigger_eval.py` | trigger rate per query, from Copilot's `skill.invoked` events |

Tests: `python3 -m unittest discover -s tests -t .`

Adapted for GitHub Copilot CLI from Anthropic's skill-creator (Apache-2.0). This version has been modified.
