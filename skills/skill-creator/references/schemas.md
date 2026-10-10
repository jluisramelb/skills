# JSON Schemas

This document defines the JSON schemas used by skill-creator.

---

## evals.json

Defines the evals for a skill. Located at `evals/evals.json` within the skill directory.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's example prompt",
      "expected_output": "Description of expected result",
      "files": ["evals/files/sample1.pdf"],
      "expectations": [
        "The output includes X",
        "The skill used script Y"
      ]
    }
  ]
}
```

**Fields:**
- `skill_name`: Name matching the skill's frontmatter
- `evals[].id`: Unique integer identifier
- `evals[].prompt`: The task to execute
- `evals[].expected_output`: Human-readable description of success
- `evals[].files`: Optional list of input file paths (relative to skill root)
- `evals[].expectations`: List of verifiable statements

Optional fields for step-level evals (see [steps.json](#stepsjson)):
- `evals[].name`: Short descriptive name, used for the workspace directory (`eval-<id>-<name>`)
- `evals[].golden_dir`: Directory (relative to the skill root) holding a golden artifact for each step, named as in `steps.json` (`01-classify.json`, ...). Used for isolated-step runs and `--dry-run`, and as the recorded decision for human steps
- `evals[].step_fixtures`: `{step_id: path}` recorded decisions for human steps, overriding `golden_dir`
- `evals[].step_assertions`: `{step_id: [assertion, ...]}` checks for each step's artifact (see below)

**Step assertions.** Prefer the cheapest kind that can decide the question:

```json
{
  "id": "gather-excludes-stale",
  "text": "Progress leaves out work finished before the period",
  "kind": "programmatic",
  "critical": true,
  "check": {"type": "not_contains", "field": "progress", "value": "Android 13"}
}
```

- `kind`: `programmatic` (script checks), `reference` (compare with a golden file), or `llm` (rubric graded by a model; needs `rubric` instead of `check`)
- `critical`: if a critical check fails, every step downstream is marked `contaminated` and its failures count as inherited
- `check.type` for `programmatic`: `json_valid`, `json_required` (`fields`), `json_field_equals` (`field`, `value`, optional `case_insensitive`), `json_array_length` (`field`, `min`, `max`), `regex` (`pattern`, optional `flags` from `ims`, `should_match`), `contains` / `not_contains` (`value`, case-insensitive by default), `line_count` / `word_count` (`min`, `max`)
- `check.type` for `reference`: `exact_match`, `reference_similarity` (`min_similarity`, 0-1), `reference_json_fields` (`fields`); all take `reference` (path relative to the skill root)
- `field` is a dotted path into JSON artifacts (`a.b.0`). String checks with a `field` run on that value (lists and objects are serialized to JSON first)

---

## steps.json

Optional step manifest for step-level evals. Located at `evals/steps.json` within the skill directory. It maps the skill's workflow into typed steps, each writing exactly one artifact to `outputs/steps/<output>`.

```json
{
  "skill_name": "internal-comms",
  "steps": [
    {
      "id": "classify",
      "type": "probabilistic",
      "source_section": "SKILL.md > How to use this skill > 1. Identify the communication type",
      "description": "Decide which kind of communication is requested.",
      "inputs": [],
      "output": "01-classify.json",
      "format": "json",
      "schema": {"required": ["comm_type", "guideline_file"], "example": {"comm_type": "...", "guideline_file": "..."}}
    },
    {
      "id": "scope",
      "type": "human",
      "source_section": "examples/3p-updates.md > Workflow > 1. Clarify scope",
      "inputs": ["classify"],
      "output": "02-scope.json",
      "fixture": "evals/files/default-scope.json"
    },
    {
      "id": "format-check",
      "type": "deterministic",
      "source_section": "examples/3p-updates.md > Workflow > 4. Review",
      "inputs": ["draft"],
      "output": "05-format-check.json",
      "command": ["python", "scripts/check_3p_format.py", "{input:draft}", "{output}"]
    }
  ]
}
```

**Fields:**
- `steps[].id`: kebab-case, unique
- `steps[].type`: `probabilistic` (a model does it), `deterministic` (a bundled script does it), or `human` (a person decides)
- `steps[].source_section`: The SKILL.md (or reference file) section the step comes from. The ambiguity pass reads this section when the step is unstable
- `steps[].description`: Optional. Say *what* artifact to produce, not *how*. Instructions belong in SKILL.md; otherwise you end up testing the manifest instead of the skill
- `steps[].inputs`: Ids of earlier steps whose artifacts this step reads. Must form an acyclic graph
- `steps[].output`: `<NN>-<id>.<ext>`, with `NN` unique
- `steps[].format`: `json`, `markdown`, or `text` (inferred from the extension if omitted). JSON artifacts automatically get a critical "valid JSON" check
- `steps[].schema.required`: Required JSON fields (automatic critical check). `schema.example` is shown to the model as the expected shape
- `steps[].command`: Deterministic steps only. Run by the harness (not the model) from the skill root. Placeholders: `{input:<step-id>}`, `{output}`, `{skill}`; a leading `python` uses the current interpreter
- `steps[].fixture`: Human steps only. Default recorded decision, replayed in automated runs. Each eval can override it with `step_fixtures` or `golden_dir`

`quick_validate.py` checks that every step has a type and an output, the inputs form a valid order with no cycles, every human step has a recorded decision for every eval, and every step assertion is well-formed.

---

## history.json

Tracks version progression in Improve mode. Located at workspace root.

```json
{
  "started_at": "2026-01-15T10:30:00Z",
  "skill_name": "pdf",
  "current_best": "v2",
  "iterations": [
    {
      "version": "v0",
      "parent": null,
      "expectation_pass_rate": 0.65,
      "grading_result": "baseline",
      "is_current_best": false
    },
    {
      "version": "v1",
      "parent": "v0",
      "expectation_pass_rate": 0.75,
      "grading_result": "won",
      "is_current_best": false
    },
    {
      "version": "v2",
      "parent": "v1",
      "expectation_pass_rate": 0.85,
      "grading_result": "won",
      "is_current_best": true
    }
  ]
}
```

**Fields:**
- `started_at`: ISO timestamp of when improvement started
- `skill_name`: Name of the skill being improved
- `current_best`: Version identifier of the best performer
- `iterations[].version`: Version identifier (v0, v1, ...)
- `iterations[].parent`: Parent version this was derived from
- `iterations[].expectation_pass_rate`: Pass rate from grading
- `iterations[].grading_result`: "baseline", "won", "lost", or "tie"
- `iterations[].is_current_best`: Whether this is the current best version

---

## run_meta.json

Written by `run_step_eval.py` in each step-level run directory, so the run can be regraded on its own (`python -m scripts.grade_steps <run_dir>`).

```json
{
  "skill_path": "/path/to/skill",
  "eval_id": 1,
  "model": "claude-sonnet-5",
  "label": null,
  "run_number": 3,
  "mode": "chain",
  "isolated_step": null
}
```

`mode` is `chain` (all steps run in order) or `isolated` (only `isolated_step` runs, from golden upstream artifacts).

---

## grading.json

Output from the grader agent. Located at `<run-dir>/grading.json`.

```json
{
  "expectations": [
    {
      "text": "The output includes the name 'John Smith'",
      "passed": true,
      "evidence": "Found in transcript Step 3: 'Extracted names: John Smith, Sarah Johnson'"
    },
    {
      "text": "The spreadsheet has a SUM formula in cell B10",
      "passed": false,
      "evidence": "No spreadsheet was created. The output was a text file."
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "execution_metrics": {
    "tool_calls": {
      "Read": 5,
      "Write": 2,
      "Bash": 8
    },
    "total_tool_calls": 15,
    "total_steps": 6,
    "errors_encountered": 0,
    "output_chars": 12450,
    "transcript_chars": 3200
  },
  "timing": {
    "executor_duration_seconds": 165.0,
    "grader_duration_seconds": 26.0,
    "total_duration_seconds": 191.0
  },
  "claims": [
    {
      "claim": "The form has 12 fillable fields",
      "type": "factual",
      "verified": true,
      "evidence": "Counted 12 fields in field_info.json"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["Used 2023 data, may be stale"],
    "needs_review": [],
    "workarounds": ["Fell back to text overlay for non-fillable fields"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "The output includes the name 'John Smith'",
        "reason": "A hallucinated document that mentions the name would also pass"
      }
    ],
    "overall": "Assertions check presence but not correctness."
  }
}
```

**Fields:**
- `expectations[]`: Graded expectations with evidence
- `summary`: Aggregate pass/fail counts
- `execution_metrics`: Tool usage and output size (from executor's metrics.json)
- `timing`: Wall clock timing (from timing.json)
- `claims`: Extracted and verified claims from the output
- `user_notes_summary`: Issues flagged by the executor
- `eval_feedback`: (optional) Improvement suggestions for the evals, only present when the grader identifies issues worth raising

---

### Step-level grading.json

`grade_steps.py` writes the same `expectations` and `summary` fields (with the step id prefixed to each `text`, and pending LLM checks left out) so aggregation and the viewer keep working. It adds:

```json
{
  "mode": "chain",
  "isolated_step": null,
  "model": "claude-sonnet-5",
  "eval_id": 1,
  "run_number": 3,
  "steps": {
    "draft": {
      "type": "probabilistic",
      "artifact": "steps/04-draft.md",
      "exists": true,
      "inputs": ["scope", "gather"],
      "assertions": [
        {"id": "draft-no-stale", "text": "Draft leaves out the Android 13 migration", "kind": "programmatic",
         "critical": true, "passed": false, "evidence": "Unexpectedly found 'Android 13'"}
      ],
      "passed": 3, "failed": 1, "pending": 1, "total": 4, "pass_rate": 0.75,
      "critical_failed": true,
      "contaminated": true,
      "contaminated_by": ["gather"],
      "failure_origin": "inherited"
    }
  }
}
```

- `pending`: LLM-graded checks with no verdict yet (`passed: null`). They don't count towards `total`
- `contaminated_by`: Upstream steps with a failed critical check
- `failure_origin`: `null` (step passed), `own`, or `inherited` (failed while contaminated)
- Isolated runs grade only the isolated step and add `"inputs_source": "golden"`

---

## metrics.json

Output from the executor agent. Located at `<run-dir>/outputs/metrics.json`.

```json
{
  "tool_calls": {
    "Read": 5,
    "Write": 2,
    "Bash": 8,
    "Edit": 1,
    "Glob": 2,
    "Grep": 0
  },
  "total_tool_calls": 18,
  "total_steps": 6,
  "files_created": ["filled_form.pdf", "field_values.json"],
  "errors_encountered": 0,
  "output_chars": 12450,
  "transcript_chars": 3200
}
```

**Fields:**
- `tool_calls`: Count per tool type
- `total_tool_calls`: Sum of all tool calls
- `total_steps`: Number of major execution steps
- `files_created`: List of output files created
- `errors_encountered`: Number of errors during execution
- `output_chars`: Total character count of output files
- `transcript_chars`: Character count of transcript

---

## timing.json

Wall clock timing for a run. Located at `<run-dir>/timing.json`.

**How to capture:** When a subagent task completes, the task notification includes `total_tokens` and `duration_ms`. Save these immediately — they are not persisted anywhere else and cannot be recovered after the fact.

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3,
  "executor_start": "2026-01-15T10:30:00Z",
  "executor_end": "2026-01-15T10:32:45Z",
  "executor_duration_seconds": 165.0,
  "grader_start": "2026-01-15T10:32:46Z",
  "grader_end": "2026-01-15T10:33:12Z",
  "grader_duration_seconds": 26.0
}
```

---

## benchmark.json

Output from Benchmark mode. Located at `benchmarks/<timestamp>/benchmark.json`.

```json
{
  "metadata": {
    "skill_name": "pdf",
    "skill_path": "/path/to/pdf",
    "executor_model": "claude-sonnet-4-20250514",
    "analyzer_model": "most-capable-model",
    "timestamp": "2026-01-15T10:30:00Z",
    "evals_run": [1, 2, 3],
    "runs_per_configuration": 3
  },

  "runs": [
    {
      "eval_id": 1,
      "eval_name": "Ocean",
      "configuration": "with_skill",
      "run_number": 1,
      "result": {
        "pass_rate": 0.85,
        "passed": 6,
        "failed": 1,
        "total": 7,
        "time_seconds": 42.5,
        "tokens": 3800,
        "tool_calls": 18,
        "errors": 0
      },
      "expectations": [
        {"text": "...", "passed": true, "evidence": "..."}
      ],
      "notes": [
        "Used 2023 data, may be stale",
        "Fell back to text overlay for non-fillable fields"
      ]
    }
  ],

  "run_summary": {
    "with_skill": {
      "pass_rate": {"mean": 0.85, "stddev": 0.05, "min": 0.80, "max": 0.90},
      "time_seconds": {"mean": 45.0, "stddev": 12.0, "min": 32.0, "max": 58.0},
      "tokens": {"mean": 3800, "stddev": 400, "min": 3200, "max": 4100}
    },
    "without_skill": {
      "pass_rate": {"mean": 0.35, "stddev": 0.08, "min": 0.28, "max": 0.45},
      "time_seconds": {"mean": 32.0, "stddev": 8.0, "min": 24.0, "max": 42.0},
      "tokens": {"mean": 2100, "stddev": 300, "min": 1800, "max": 2500}
    },
    "delta": {
      "pass_rate": "+0.50",
      "time_seconds": "+13.0",
      "tokens": "+1700"
    }
  },

  "notes": [
    "Assertion 'Output is a PDF file' passes 100% in both configurations - may not differentiate skill value",
    "Eval 3 shows high variance (50% ± 40%) - may be flaky or model-dependent",
    "Without-skill runs consistently fail on table extraction expectations",
    "Skill adds 13s average execution time but improves pass rate by 50%"
  ]
}
```

**Fields:**
- `metadata`: Information about the benchmark run
  - `skill_name`: Name of the skill
  - `timestamp`: When the benchmark was run
  - `evals_run`: List of eval names or IDs
  - `runs_per_configuration`: Number of runs per config (e.g. 3)
- `runs[]`: Individual run results
  - `eval_id`: Numeric eval identifier
  - `eval_name`: Human-readable eval name (used as section header in the viewer)
  - `configuration`: Must be `"with_skill"` or `"without_skill"` (the viewer uses this exact string for grouping and color coding)
  - `run_number`: Integer run number (1, 2, 3...)
  - `result`: Nested object with `pass_rate`, `passed`, `total`, `time_seconds`, `tokens`, `errors`
- `run_summary`: Statistical aggregates per configuration
  - `with_skill` / `without_skill`: Each contains `pass_rate`, `time_seconds`, `tokens` objects with `mean` and `stddev` fields
  - `delta`: Difference strings like `"+0.50"`, `"+13.0"`, `"+1700"`
- `notes`: Freeform observations from the analyzer

**Important:** The viewer reads these field names exactly. Using `config` instead of `configuration`, or putting `pass_rate` at the top level of a run instead of nested under `result`, will cause the viewer to show empty/zero values. Always reference this schema when generating benchmark.json manually.

---

## comparison.json

Output from blind comparator. Located at `<grading-dir>/comparison-N.json`.

```json
{
  "winner": "A",
  "reasoning": "Output A provides a complete solution with proper formatting and all required fields. Output B is missing the date field and has formatting inconsistencies.",
  "rubric": {
    "A": {
      "content": {
        "correctness": 5,
        "completeness": 5,
        "accuracy": 4
      },
      "structure": {
        "organization": 4,
        "formatting": 5,
        "usability": 4
      },
      "content_score": 4.7,
      "structure_score": 4.3,
      "overall_score": 9.0
    },
    "B": {
      "content": {
        "correctness": 3,
        "completeness": 2,
        "accuracy": 3
      },
      "structure": {
        "organization": 3,
        "formatting": 2,
        "usability": 3
      },
      "content_score": 2.7,
      "structure_score": 2.7,
      "overall_score": 5.4
    }
  },
  "output_quality": {
    "A": {
      "score": 9,
      "strengths": ["Complete solution", "Well-formatted", "All fields present"],
      "weaknesses": ["Minor style inconsistency in header"]
    },
    "B": {
      "score": 5,
      "strengths": ["Readable output", "Correct basic structure"],
      "weaknesses": ["Missing date field", "Formatting inconsistencies", "Partial data extraction"]
    }
  },
  "expectation_results": {
    "A": {
      "passed": 4,
      "total": 5,
      "pass_rate": 0.80,
      "details": [
        {"text": "Output includes name", "passed": true}
      ]
    },
    "B": {
      "passed": 3,
      "total": 5,
      "pass_rate": 0.60,
      "details": [
        {"text": "Output includes name", "passed": true}
      ]
    }
  }
}
```

---

## analysis.json

Output from post-hoc analyzer. Located at `<grading-dir>/analysis.json`.

```json
{
  "comparison_summary": {
    "winner": "A",
    "winner_skill": "path/to/winner/skill",
    "loser_skill": "path/to/loser/skill",
    "comparator_reasoning": "Brief summary of why comparator chose winner"
  },
  "winner_strengths": [
    "Clear step-by-step instructions for handling multi-page documents",
    "Included validation script that caught formatting errors"
  ],
  "loser_weaknesses": [
    "Vague instruction 'process the document appropriately' led to inconsistent behavior",
    "No script for validation, agent had to improvise"
  ],
  "instruction_following": {
    "winner": {
      "score": 9,
      "issues": ["Minor: skipped optional logging step"]
    },
    "loser": {
      "score": 6,
      "issues": [
        "Did not use the skill's formatting template",
        "Invented own approach instead of following step 3"
      ]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "Replace 'process the document appropriately' with explicit steps",
      "expected_impact": "Would eliminate ambiguity that caused inconsistent behavior"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "Read skill -> Followed 5-step process -> Used validation script",
    "loser_execution_pattern": "Read skill -> Unclear on approach -> Tried 3 different methods"
  }
}
```

---

## benchmark.json: step_summary

Added by `aggregate_benchmark.py` when the workspace contains step-level runs (`eval-*/<model>/run-*/` and `eval-*/<model>/isolated/<step>/run-*/`). Configurations are the model directories (`<model>` or `<model>__<label>`).

```json
{
  "step_summary": {
    "steps": [{"id": "gather", "type": "probabilistic", "inputs": ["classify", "scope"], "artifact": "steps/03-gather.json"}],
    "configs": ["claude-opus-5", "claude-sonnet-5"],
    "cells": {
      "gather": {
        "claude-sonnet-5": {
          "runs": 5,
          "success_rate": 0.6,
          "pass_rate": {"mean": 0.88, "stddev": 0.11, "min": 0.75, "max": 1.0},
          "critical_failure_rate": 0.4,
          "contaminated_rate": 0.0,
          "failure_attribution": {
            "chain_failure_rate": 0.4, "own_failure_rate": 0.4, "inherited_failure_rate": 0.0, "source": "isolated"
          },
          "consistency": {
            "kind": "json", "exact_match_rate": 0.4, "mean_divergence": 0.21,
            "field_agreement": {"progress": 0.6, "plans": 1.0, "problems": 1.0, "excluded": 0.6}
          },
          "isolated": {"runs": 5, "pass_rate": {"mean": 0.9, "stddev": 0.1, "min": 0.75, "max": 1.0}, "failure_rate": 0.4},
          "nondeterministic": false,
          "flags": [{"reason": "inconsistent", "detail": "passes in 60% of 5 runs"}]
        }
      }
    },
    "propagation": [
      {"from": "gather", "to": "draft", "config": "claude-sonnet-5",
       "upstream_critical_failures": 2, "downstream_failures": 2, "rate": 1.0}
    ],
    "flags": [
      {"step": "gather", "config": "claude-sonnet-5", "reason": "inconsistent", "detail": "passes in 60% of 5 runs"},
      {"step": "gather", "config": null, "reason": "model_gap", "detail": "claude-opus-5 100% vs claude-sonnet-5 60%"}
    ],
    "thresholds": {"unstable_json_match": 0.6, "unstable_text_divergence": 0.35, "model_gap": 0.25}
  }
}
```

- `success_rate`: Share of chain runs in which every check on the step passed. `pass_rate` is the share of checks passed, averaged over runs
- `failure_attribution`: With isolated runs (`source: "isolated"`), own = isolated failure rate and inherited = chain failure rate minus own. Without them (`source: "contamination"`), failures in contaminated runs count as inherited
- `consistency`: Similarity of the artifacts across repeated runs of the same eval, averaged over evals. `exact_match_rate` is the share of runs matching the most common artifact (JSON compared canonically); `mean_divergence` is 1 minus the mean pairwise text similarity; `field_agreement` gives the same share for each top-level JSON field
- `propagation`: For each dependency edge, how often a critical failure upstream was followed by a failure downstream
- `flags[].reason`: `inconsistent` (some runs pass, some fail), `always_fails`, `unstable_output` (low agreement or high divergence on a probabilistic step), `nondeterministic` (a deterministic step gave different outputs for the same input), `inherited_failures` (inherited ≥ own), `model_gap` (success rates differ by at least `thresholds.model_gap` between configurations)

---

## ambiguity.json

Output from the analyzer's ambiguity pass (`agents/analyzer.md`). Located at `<workspace>/iteration-N/ambiguity.json`.

```json
{
  "findings": [
    {
      "step": "gather",
      "flags": ["inconsistent", "model_gap"],
      "source_section": "examples/3p-updates.md > Instructions",
      "ambiguous_text": "Progress: what the team has accomplished over the next time period.",
      "readings": [
        {"configs": ["claude-sonnet-5"], "runs": ["eval-1-3p-mobile-weekly/claude-sonnet-5/run-2"],
         "interpretation": "Includes everything in the notes, including work finished three weeks ago"},
        {"configs": ["claude-opus-5"], "runs": ["eval-1-3p-mobile-weekly/claude-opus-5/run-1"],
         "interpretation": "Only includes work finished during the update's week"}
      ],
      "evidence": "gather-excludes-stale fails in 2/5 sonnet runs; excluded[] is empty in those runs",
      "suggested_rewrite": "Progress: what the team accomplished during the period the update covers (usually the past week). Leave out older work, even if it appears in the notes, because readers want to know what changed this week.",
      "why": "'next time period' contradicts the gathering guidance below it and gives no rule for older items",
      "confidence": "high"
    }
  ],
  "not_ambiguity": [
    {"step": "draft", "flags": ["inherited_failures"], "explanation": "Failures disappear in isolated runs; fix gather first"}
  ]
}
```

