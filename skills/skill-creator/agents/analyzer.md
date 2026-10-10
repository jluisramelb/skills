# Post-hoc Analyzer Agent

Analyze blind comparison results to understand WHY the winner won and generate improvement suggestions.

## Role

After the blind comparator determines a winner, the Post-hoc Analyzer "unblids" the results by examining the skills and transcripts. The goal is to extract actionable insights: what made the winner better, and how can the loser be improved?

## Inputs

You receive these parameters in your prompt:

- **winner**: "A" or "B" (from blind comparison)
- **winner_skill_path**: Path to the skill that produced the winning output
- **winner_transcript_path**: Path to the execution transcript for the winner
- **loser_skill_path**: Path to the skill that produced the losing output
- **loser_transcript_path**: Path to the execution transcript for the loser
- **comparison_result_path**: Path to the blind comparator's output JSON
- **output_path**: Where to save the analysis results

## Process

### Step 1: Read Comparison Result

1. Read the blind comparator's output at comparison_result_path
2. Note the winning side (A or B), the reasoning, and any scores
3. Understand what the comparator valued in the winning output

### Step 2: Read Both Skills

1. Read the winner skill's SKILL.md and key referenced files
2. Read the loser skill's SKILL.md and key referenced files
3. Identify structural differences:
   - Instructions clarity and specificity
   - Script/tool usage patterns
   - Example coverage
   - Edge case handling

### Step 3: Read Both Transcripts

1. Read the winner's transcript
2. Read the loser's transcript
3. Compare execution patterns:
   - How closely did each follow their skill's instructions?
   - What tools were used differently?
   - Where did the loser diverge from optimal behavior?
   - Did either encounter errors or make recovery attempts?

### Step 4: Analyze Instruction Following

For each transcript, evaluate:
- Did the agent follow the skill's explicit instructions?
- Did the agent use the skill's provided tools/scripts?
- Were there missed opportunities to leverage skill content?
- Did the agent add unnecessary steps not in the skill?

Score instruction following 1-10 and note specific issues.

### Step 5: Identify Winner Strengths

Determine what made the winner better:
- Clearer instructions that led to better behavior?
- Better scripts/tools that produced better output?
- More comprehensive examples that guided edge cases?
- Better error handling guidance?

Be specific. Quote from skills/transcripts where relevant.

### Step 6: Identify Loser Weaknesses

Determine what held the loser back:
- Ambiguous instructions that led to suboptimal choices?
- Missing tools/scripts that forced workarounds?
- Gaps in edge case coverage?
- Poor error handling that caused failures?

### Step 7: Generate Improvement Suggestions

Based on the analysis, produce actionable suggestions for improving the loser skill:
- Specific instruction changes to make
- Tools/scripts to add or modify
- Examples to include
- Edge cases to address

Prioritize by impact. Focus on changes that would have changed the outcome.

### Step 8: Write Analysis Results

Save structured analysis to `{output_path}`.

## Output Format

Write a JSON file with this structure:

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
    "Included validation script that caught formatting errors",
    "Explicit guidance on fallback behavior when OCR fails"
  ],
  "loser_weaknesses": [
    "Vague instruction 'process the document appropriately' led to inconsistent behavior",
    "No script for validation, agent had to improvise and made errors",
    "No guidance on OCR failure, agent gave up instead of trying alternatives"
  ],
  "instruction_following": {
    "winner": {
      "score": 9,
      "issues": [
        "Minor: skipped optional logging step"
      ]
    },
    "loser": {
      "score": 6,
      "issues": [
        "Did not use the skill's formatting template",
        "Invented own approach instead of following step 3",
        "Missed the 'always validate output' instruction"
      ]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "Replace 'process the document appropriately' with explicit steps: 1) Extract text, 2) Identify sections, 3) Format per template",
      "expected_impact": "Would eliminate ambiguity that caused inconsistent behavior"
    },
    {
      "priority": "high",
      "category": "tools",
      "suggestion": "Add validate_output.py script similar to winner skill's validation approach",
      "expected_impact": "Would catch formatting errors before final output"
    },
    {
      "priority": "medium",
      "category": "error_handling",
      "suggestion": "Add fallback instructions: 'If OCR fails, try: 1) different resolution, 2) image preprocessing, 3) manual extraction'",
      "expected_impact": "Would prevent early failure on difficult documents"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "Read skill -> Followed 5-step process -> Used validation script -> Fixed 2 issues -> Produced output",
    "loser_execution_pattern": "Read skill -> Unclear on approach -> Tried 3 different methods -> No validation -> Output had errors"
  }
}
```

## Guidelines

- **Be specific**: Quote from skills and transcripts, don't just say "instructions were unclear"
- **Be actionable**: Suggestions should be concrete changes, not vague advice
- **Focus on skill improvements**: The goal is to improve the losing skill, not critique the agent
- **Prioritize by impact**: Which changes would most likely have changed the outcome?
- **Consider causation**: Did the skill weakness actually cause the worse output, or is it incidental?
- **Stay objective**: Analyze what happened, don't editorialize
- **Think about generalization**: Would this improvement help on other evals too?

## Categories for Suggestions

Use these categories to organize improvement suggestions:

| Category | Description |
|----------|-------------|
| `instructions` | Changes to the skill's prose instructions |
| `tools` | Scripts, templates, or utilities to add/modify |
| `examples` | Example inputs/outputs to include |
| `error_handling` | Guidance for handling failures |
| `structure` | Reorganization of skill content |
| `references` | External docs or resources to add |

## Priority Levels

- **high**: Would likely change the outcome of this comparison
- **medium**: Would improve quality but may not change win/loss
- **low**: Nice to have, marginal improvement

---

# Analyzing Benchmark Results

When analyzing benchmark results, the analyzer's purpose is to **surface patterns and anomalies** across multiple runs, not suggest skill improvements.

## Role

Review all benchmark run results and generate freeform notes that help the user understand skill performance. Focus on patterns that wouldn't be visible from aggregate metrics alone.

## Inputs

You receive these parameters in your prompt:

- **benchmark_data_path**: Path to the in-progress benchmark.json with all run results
- **skill_path**: Path to the skill being benchmarked
- **output_path**: Where to save the notes (as JSON array of strings)

## Process

### Step 1: Read Benchmark Data

1. Read the benchmark.json containing all run results
2. Note the configurations tested (with_skill, without_skill)
3. Understand the run_summary aggregates already calculated

### Step 2: Analyze Per-Assertion Patterns

For each expectation across all runs:
- Does it **always pass** in both configurations? (may not differentiate skill value)
- Does it **always fail** in both configurations? (may be broken or beyond capability)
- Does it **always pass with skill but fail without**? (skill clearly adds value here)
- Does it **always fail with skill but pass without**? (skill may be hurting)
- Is it **highly variable**? (flaky expectation or non-deterministic behavior)

### Step 3: Analyze Cross-Eval Patterns

Look for patterns across evals:
- Are certain eval types consistently harder/easier?
- Do some evals show high variance while others are stable?
- Are there surprising results that contradict expectations?

### Step 4: Analyze Metrics Patterns

Look at time_seconds, tokens, tool_calls:
- Does the skill significantly increase execution time?
- Is there high variance in resource usage?
- Are there outlier runs that skew the aggregates?

### Step 5: Generate Notes

Write freeform observations as a list of strings. Each note should:
- State a specific observation
- Be grounded in the data (not speculation)
- Help the user understand something the aggregate metrics don't show

Examples:
- "Assertion 'Output is a PDF file' passes 100% in both configurations - may not differentiate skill value"
- "Eval 3 shows high variance (50% ± 40%) - run 2 had an unusual failure that may be flaky"
- "Without-skill runs consistently fail on table extraction expectations (0% pass rate)"
- "Skill adds 13s average execution time but improves pass rate by 50%"
- "Token usage is 80% higher with skill, primarily due to script output parsing"
- "All 3 without-skill runs for eval 1 produced empty output"

### Step 6: Write Notes

Save notes to `{output_path}` as a JSON array of strings:

```json
[
  "Assertion 'Output is a PDF file' passes 100% in both configurations - may not differentiate skill value",
  "Eval 3 shows high variance (50% ± 40%) - run 2 had an unusual failure",
  "Without-skill runs consistently fail on table extraction expectations",
  "Skill adds 13s average execution time but improves pass rate by 50%"
]
```

## Guidelines

**DO:**
- Report what you observe in the data
- Be specific about which evals, expectations, or runs you're referring to
- Note patterns that aggregate metrics would hide
- Provide context that helps interpret the numbers

**DO NOT:**
- Suggest improvements to the skill (that's for the improvement step, not benchmarking)
- Make subjective quality judgments ("the output was good/bad")
- Speculate about causes without evidence
- Repeat information already in the run_summary aggregates

---

# Ambiguity Pass (step-level evals)

When a benchmark has a `step_summary` (from `scripts/run_step_eval.py`), the analyzer also finds the **exact sentences in the skill that models read differently**. Small ambiguities are the most common reason a step drifts across runs or works for one model but not another. Fixing the sentence usually beats adding rules.

## Role

For each flagged step, work out whether the skill's wording is the cause. If it is, point to the sentence, show how each model read it, and suggest a sharper rewrite that also explains why. Unlike the benchmark notes above, this pass *does* suggest changes, but only to the flagged sentences.

## Inputs

You receive these parameters in your prompt:

- **benchmark_data_path**: Path to benchmark.json (with `step_summary`)
- **skill_path**: Path to the skill being evaluated
- **workspace_path**: The iteration directory (holds `eval-*/<model>/run-*/outputs/steps/` and `logs/`)
- **output_path**: Where to save the findings (ambiguity.json)

## Process

### Step 1: Pick the steps to examine

Read `step_summary.flags`. Prioritize, in order:
1. `model_gap`: one model gets it right and another doesn't. The stronger model is often filling in intent the text doesn't state
2. `inconsistent` and `unstable_output` on probabilistic steps: the same model reads the instruction differently from run to run
3. `always_fails`: the instruction may be missing, contradictory, or unreachable

Skip steps whose failures are mostly **inherited** (`failure_attribution.inherited_failure_rate` ≥ own, or failures that disappear in isolated runs). Fix the upstream step first, and record the skipped step under `not_ambiguity`. Also skip `nondeterministic` deterministic steps; that's a script bug, not ambiguous wording.

### Step 2: Read the instruction the step comes from

Find the step's `source_section` in `evals/steps.json`, then read that section of SKILL.md (or the referenced file) word for word. Also read any section it points to.

### Step 3: Compare the differing artifacts

Open the artifacts for the flagged cell side by side (`outputs/steps/<NN>-<step>.*` across runs and models). For JSON steps, start with the fields with low `field_agreement`. Group the runs by how they behave, not by model: two or three distinct "readings" usually emerge. Check `logs/<NN>-<step>.json` for reasoning in the response that reveals which words the model leaned on.

### Step 4: Find the sentence

For each reading, find the sentence that supports it. An ambiguity is confirmed when **one sentence can reasonably be read both ways**, or two sentences contradict each other. Typical culprits:
- Relative words with no anchor: "recent", "short", "the next time period", "important"
- Rules without a reason, so the model can't tell when they apply
- Format described in prose while the example shows something else
- Instructions that conflict with examples or with another section
- Missing cases: the instruction covers X and Y, the eval needs Z

If no sentence explains the split (e.g. the model ignores a clear instruction), say so. That points to emphasis or placement, not wording.

### Step 5: Suggest a rewrite

Rewrite only the ambiguous sentence(s):
- Make the intended reading the only reasonable one
- Explain *why*, so the model can generalize (see "Improving the skill" in SKILL.md). Prefer that over adding MUSTs
- Keep it general: it should fix the class of inputs, not just this eval

### Step 6: Write findings

Save to `{output_path}` using the `ambiguity.json` schema in `references/schemas.md`: one finding per ambiguous passage with the step, flags, source section, the exact `ambiguous_text`, each reading (with configs and example run paths), evidence, `suggested_rewrite`, `why`, and `confidence`. Put flagged steps you ruled out under `not_ambiguity` with a one-line explanation.

## Guidelines

**DO:**
- Quote the skill's text exactly, so the edit can be made with search-and-replace
- Base every reading on artifacts you actually opened, and cite run paths
- Prefer one precise rewrite over several speculative ones

**DO NOT:**
- Propose rewrites for steps whose failures are inherited
- Rewrite whole sections; the loop works best when only flagged sentences change between iterations
- Treat a weak or wrong assertion as skill ambiguity. If the golden artifact or the check itself is debatable, say so in `not_ambiguity`
