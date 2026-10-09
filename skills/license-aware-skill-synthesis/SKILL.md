---
name: license-aware-skill-synthesis
description: Researches existing AI skills, audits source terms and dependencies, and designs original portable skills with traceable provenance. Use when comparing or synthesizing skills, prompts, agent instructions, or related workflow assets.
---

# License-aware skill synthesis

Create original skills from eligible general techniques. Begin with a source and license audit; do not draft the synthesis until source use has been classified. This workflow is for research and documentation, not legal advice or a claim of legal clearance.

## 1. Define the work

Confirm the intended use, audience, output format, and whether the result will be shared or redistributed. Set a bounded source list. Do not fetch, upload, or transmit private source material to an unapproved service. Distinguish skill instructions from scripts, examples, datasets, fonts, images, archives, and software dependencies.

## 2. Audit before studying for ideas

For every source and bundled component:

1. Locate its own license, copyright notices, attribution file, and source documentation. Prefer the license attached to the material and authoritative project documentation over summaries or metadata.
2. Record source identity and location, license evidence, named owners, dependencies, integration requirements, restrictions, and missing evidence. Do not infer permission from public availability, a repository-wide description, or an absent notice.
3. Check included and invoked dependencies separately. Record their version and license evidence where available; flag transitive, bundled, or unversioned dependencies that remain unchecked.
4. Assign one status, with a short evidence-based explanation:
   - **ALLOW:** reuse is permitted and no material conditions apply.
   - **CONDITIONAL:** reuse is permitted only when stated obligations are met.
   - **CONCEPTS_ONLY:** study general techniques; do not copy expression, code, or assets.
   - **HOLD:** permission, ownership, or license is unclear; do not use until resolved.
   - **EXCLUDE:** source terms or intended use make reuse unsuitable.
5. Treat status as scope-specific. An eligible source can still contain independently licensed assets or dependencies that must be assessed separately.

If a source is HOLD or EXCLUDE, do not draw on its protected expression or implementation. Keep its uncertainty visible in the audit.

## 3. Distill eligible concepts

From eligible sources only, describe techniques abstractly: goals, decision criteria, workflow structure, verification methods, and general lessons. Keep observations separate from proposed design. Do not paraphrase passages, reproduce distinctive examples, translate code into prose, or use AI rewriting to bypass a restriction.

Compare eligible approaches. Identify compatible elements, trade-offs, conflicts, and repetition. Choose a design based on the user's context, not source resemblance. Prefer a small number of portable steps over unnecessary frameworks, packages, or provider-specific integrations.

## 4. Synthesize and implement

Write the new skill independently. Use clear triggers, scope, decision points, expected outputs, and failure or escalation paths. Reuse only material whose permission and obligations are understood. When using any licensed material, retain required notices and record the actual material and license in provenance.

Unless requested otherwise, produce:

- `license-audit.md`: sources, evidence, statuses, obligations, dependencies, and unresolved questions.
- `synthesis.md`: abstracted concepts, design choices, and source-to-design rationale.
- `provenance.yaml`: each new skill, its informing sources, assessed status, and material actually incorporated.
- A self-contained skill directory with its primary `SKILL.md` and only necessary references or scripts.

Do not claim a new skill is legally cleared. If its own redistribution terms are not established, say so and leave a licensing decision for the owner.

## 5. Verify and report

Before delivery:

- Confirm every source considered is accounted for and every status has evidence.
- Check that notices required for incorporated material are present, and independently audit each reused asset and dependency.
- Verify that the required output files exist, provenance entries match the audit, and links and paths resolve.
- Review the new work against source examples for suspiciously similar distinctive wording or implementation. A similarity alert is a reason for human review, not proof either way.
- Test any added scripts using the repository's existing test or validation tools. Do not add dependencies just to validate a text-only skill.
- Report exclusions, holds, missing evidence, and verification limits plainly.
