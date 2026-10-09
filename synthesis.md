# Synthesis rationale

## Scope and method

This synthesis is limited to the `skill-creator` and `mcp-builder` skills. It uses only general workflow concepts from those Apache-2.0 sources, whose license conditions are recorded in `license-audit.md`; it does not reuse their phrasing, code, examples, or dependencies. The requested document skills (`docx`, `pdf`, `pptx`, and `xlsx`) are audited but excluded from synthesis because their attached terms restrict copying, derivative works, and third-party distribution. The result is an independently written, tool-agnostic skill.

## Distilled concepts

- **Separate phases.** Research and plan before implementation, then evaluate the result against stated goals.
- **Design for effective use.** Make components discoverable, purpose-specific, and easy to understand; avoid unnecessary complexity.
- **Verify with explicit criteria.** Use realistic checks and review the result rather than treating generation as proof of quality.
- **Iterate from findings.** Treat evaluation as feedback for revision and document unresolved limitations.

These are general methods, not permission to reproduce any source's protected expression or code.

## Design decisions

1. **Gate synthesis on source terms.** The two Apache-2.0 sources permit reuse subject to their license obligations; this work takes only general concepts and does not incorporate source expression or code. The document skills are excluded rather than treated as a source for paraphrasing.
2. **Combine complementary phases.** The skill-creator's evaluation-and-iteration approach complements MCP-builder's research, planning, implementation, and review sequence. Together they inform a simple research-to-delivery cycle.
3. **Create separate task skills.** `skill-design-workbench` turns the skill-creation and evaluation cycle into a practical authoring workflow. `mcp-server-workbench` applies the research, architecture, implementation, and verification phases specifically to MCP integrations.
4. **Make verification concrete.** Both skills require success criteria and representative checks; they distinguish performed checks from proposed or unavailable ones.
5. **Build for portability.** Keep both skills text-only, without scripts, added packages, or required vendor-specific APIs; defer implementation choices to the user's project and current documentation.
6. **Track evidence and limits.** Record source identity, applicable terms, the concepts used, and unresolved issues; do not claim legal clearance.

## Source-to-design mapping

| Eligible source | General idea used | How the new design differs |
|---|---|---|
| `skills/skill-creator/SKILL.md` (Apache-2.0; conditional) | Validate an artifact against explicit criteria and use findings for an iteration. | Defines license evidence and provenance checks as deliverable acceptance criteria; no evaluator code, schema, or wording is copied. |
| `skills/mcp-builder/SKILL.md` (Apache-2.0; conditional) | Separate research, planning, implementation, and evaluation. | Applies distinct checkpoints to license-aware research and original skill design, not server development. |

The `skill-design-workbench` draws only on the general cycle of defining a skill, drafting it, checking representative outcomes, and revising against evidence from `skill-creator`. The `mcp-server-workbench` draws only on the general stages of researching requirements, choosing capabilities, implementing, and verifying from `mcp-builder`. Both describe original workflows and omit source-specific scripts, examples, API implementations, and wording.

The `docx`, `pdf`, `pptx`, and `xlsx` skills are in the requested audit scope but contribute no concepts or materials to the synthesis. Their custom terms, reproduced in their respective `LICENSE.txt` files, prohibit creating derivative works and distributing the materials. No document-skill instructions, code, examples, assets, or dependencies are used.

## Limits

The design supplies a conservative research workflow; it is not legal advice. The source audit can only establish what was visible in the checked repository snapshot. It cannot determine ownership where notices are absent, license compatibility for every downstream use, or whether a similarity concern is legally significant. Those matters remain explicit review items.
