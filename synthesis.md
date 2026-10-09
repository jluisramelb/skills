# Synthesis rationale

## Scope and method

This synthesis uses only broad workflow concepts from the Apache-2.0 skill examples identified in `license-audit.md`. It does not reuse source phrasing, code, templates, graphics, or bundled dependencies. Skills with restrictive terms were excluded; sources without a clear grant remain on hold. The resulting design is an independently written, tool-agnostic skill for auditing and synthesizing other skills.

## Distilled concepts

- **Match the method to the task.** Start by establishing the request, intended audience, use, and constraints; route work to only the relevant sources and resources.
- **Make research evidence traceable.** Record where a claim came from, separate verified facts from assumptions, and revisit information likely to become stale.
- **Use a staged workflow.** Research and plan before implementation; keep inspection, synthesis, implementation, and verification as distinct checkpoints.
- **Prefer focused, portable units.** Give each tool or instruction set a clear purpose, limit unnecessary dependencies, and make outputs understandable without one agent framework.
- **Verify against observable criteria.** Check structure and behavior, use realistic test cases, and review results rather than treating generation as proof of quality.
- **Iterate from findings.** Treat checks as feedback for revisions, and report unresolved issues instead of silently filling evidence gaps.
- **Make deliberate choices.** Tailor the result to the user's context rather than repeating a generic pattern; favor clarity and remove unnecessary complexity.

These are general methods, not permission to reproduce any source's protected expression or code.

## Design decisions

1. **License audit comes first.** A research workflow must not start by extracting attractive techniques and asking about permission later. The skill creates a source register first, including licenses, notices, copyright evidence, dependencies, and open questions.
2. **Permission categories gate use.** A missing grant means HOLD; restrictive source terms can mean EXCLUDE; conditional licenses remain visible in provenance. A concept-only source contributes no text, code, or asset.
3. **Separate findings from synthesis.** The audit records evidence and uncertainty, while the synthesis explains which general principles shaped the original design. This makes the decision path independently reviewable.
4. **Build for portability.** The synthesized library is a single Markdown skill with no scripts, package dependencies, network requirement, or vendor-specific API assumption. It asks the operator to use whatever approved local or research tools are available.
5. **Make verification concrete.** Before delivery, check the required artifacts, internal links and claims, license notices, dependencies, and potentially copied passages; report limits rather than making a clearance claim.
6. **Track provenance at the concept level.** The provenance map identifies each source, its assessed terms, and the limited general idea that informed the design. It explicitly states that no source expression or implementation was incorporated.

## Source-to-design mapping

| Eligible source | General idea used | How the new design differs |
|---|---|---|
| `skills/skill-creator/SKILL.md` (Apache-2.0; conditional) | Validate an artifact against explicit criteria and use findings for an iteration. | Defines license evidence and provenance checks as deliverable acceptance criteria; no evaluator code, schema, or wording is copied. |
| `skills/mcp-builder/SKILL.md` (Apache-2.0; conditional) | Separate research, planning, implementation, and evaluation. | Applies distinct checkpoints to license-aware research and original skill design, not server development. |
| `skills/webapp-testing/SKILL.md` (Apache-2.0; conditional) | Inspect an actual result before acting and verify behavior after changes. | Uses a general inspect-build-review loop without Playwright-specific steps or source wording. |
| `skills/internal-comms/SKILL.md` (Apache-2.0; conditional) | Select a suitable process based on task type. | Routes source treatment by license status rather than communication format. |
| `skills/frontend-design/SKILL.md` (Apache-2.0; conditional) | Make choices specific to the brief and critique generic defaults. | Requires an independent solution grounded in eligible general techniques, without borrowing stylistic expression or examples. |

No material from the four custom-terms document skills, the unlicensed co-authoring skill, third-party assets, or source code was used.

## Limits

The design supplies a conservative research workflow; it is not legal advice. The source audit can only establish what was visible in the checked repository snapshot. It cannot determine ownership where notices are absent, license compatibility for every downstream use, or whether a similarity concern is legally significant. Those matters remain explicit review items.
