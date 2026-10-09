---
name: skill-design-workbench
description: Helps create, revise, and evaluate AI agent skills. Use whenever a user wants a new skill, wants existing instructions improved, or needs to check whether a skill triggers and performs reliably.
---

# Skill design workbench

Help the user turn a recurring task into clear, testable agent instructions. Adapt the depth of the process to the task: do not force a formal evaluation when the user prefers a quick draft, but make trade-offs clear.

## 1. Establish the target

Gather from the request and conversation:

- What task should the skill improve, and who will use it?
- In what situations should it activate, including nearby requests where it should not?
- What should it produce or change?
- What constraints, tools, examples, or edge cases matter?
- How will the user know it succeeded?

Summarize the proposed scope and ask only for missing decisions that materially affect the result. Do not make up user-specific policy or dependencies.

## 2. Draft the skill

Create a focused skill directory with a `SKILL.md` containing YAML frontmatter (`name`, `description`) and instructions. Use a concise description that identifies both the work and the situations that call for it.

Organize the body around the task's decisions and outcomes:

1. State the job and boundaries.
2. Lay out an ordered workflow with decision points.
3. Specify required inputs, output shape, and quality checks.
4. Explain what to do when information is missing, tools are unavailable, or an action needs user approval.
5. Add references or scripts only when they provide necessary detail or repeatable value.

Keep the skill independent of a particular model or agent platform unless the user requires otherwise. Do not add a dependency merely to make the instructions appear more complete.

## 3. Check whether it works

For a new skill, propose a compact test set before running anything:

- A clear in-scope request.
- A realistic ambiguous or edge-case request.
- A similar out-of-scope request that should not activate the skill.

For editing an existing skill, include a case that previously failed and cases likely to regress. Agree on success criteria with the user when outcomes are subjective or policy-sensitive.

Use available evaluation tools only when present and appropriate. Otherwise, inspect a sample response against the criteria, and say what was and was not tested. Do not invent benchmark results.

## 4. Improve from evidence

Compare observed behavior to the agreed criteria. Make targeted edits for specific gaps, such as missed activation, unnecessary steps, unsupported assumptions, or incomplete output. Recheck the cases affected by the edit. Stop when the result meets the user's bar or explain remaining limitations.

## 5. Deliver

Report the skill path, its activation scope, important assumptions, and verification performed. Identify optional next improvements separately. Do not claim reliability beyond the cases actually checked.
