---
name: okf-project-knowledge
description: Bootstrap or maintain a project knowledge bundle in Google's Open Knowledge Format (OKF). Use when asked to document a software project's architecture, data model, APIs, dependencies, decisions, or to create or update an agent-readable project wiki using GitHub Copilot.
license: Apache-2.0
---

# OKF Project Knowledge

Create and maintain a grounded, portable knowledge bundle for a software project using Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). Use this skill with GitHub Copilot; do not depend on Claude Code commands, configuration, or hooks.

## Operating principles

- Work in the current project and use `knowledge/` as the default bundle directory. If a bundle already exists elsewhere, preserve its location and conventions.
- Read actual source files and existing documentation before writing. Never invent schema, behavior, architecture, rationale, verification, or source details.
- Adapt the bundle to the project's language, framework, and structure. Omit areas that do not apply.
- Follow the current OKF specification when available. The core format is Markdown with YAML frontmatter; `type` is the only required field. Optional fields and document conventions must remain conformant with the specification.
- Use standard Markdown links between concepts, not wiki-style `[[backlinks]]`. Prefer bundle-root paths such as `/architecture.md`.
- Prefer a small set of rich, source-grounded concepts over many thin pages. Avoid copying large source files into the bundle.
- Keep the bundle human-editable and useful without a particular indexer, plugin, or runtime.

## Bootstrap or refresh workflow

1. **Inspect the project.** Identify its languages and frameworks, persistence and schema sources, entry points, module boundaries, configuration, tests, dependency manifests, and CI/deployment setup. Check for existing knowledge documents and agent instructions before choosing a location or structure.
2. **Plan the bundle.** Choose concept groups that match the codebase, such as `models/`, `apis/`, `services/`, `packages/`, or `operations/`. Create only groups that are useful. Ask before replacing or reorganizing an existing bundle.
3. **Read authoritative sources.** For each topic, inspect the actual implementation, relevant tests, configuration, and documentation. Consult version history only when it is available and useful for explaining why a decision was made; distinguish evidence from inference.
4. **Write concepts.** Create one Markdown document per coherent topic. Use concise OKF frontmatter and structured content. Suitable concepts may include:
   - A data model overview and grouped entity or schema pages, if the project persists data.
   - API, route, event, or CLI entry-point maps, if present.
   - Architecture and domain/module pages explaining responsibilities and dependencies.
   - Dependency notes, architectural decisions, and active areas only when supported by evidence.
5. **Create navigation and history.** Add a root `index.md` with links and short summaries, and an append-only `log.md` describing the bootstrap or update. These are OKF-reserved filenames, not concept documents. Add nested `index.md` files when they make a large bundle easier to navigate.
6. **Check for gaps.** Compare the new pages against the inspected project structure. Record important undocumented areas, uncertain claims, and unanswered questions in a `gaps.md` concept if useful. Do not imply that the bundle is complete when it is not.
7. **Verify the result.** Check that each concept has valid YAML frontmatter with `type`, links point to the intended bundle paths, the index reflects the actual pages, and the log records the work. Summarize the project areas covered, pages created or updated, and remaining gaps.

## OKF document conventions

- `type` is required and should be a clear, descriptive concept type, for example `Architecture`, `Data Model`, `API`, `Decision`, or `Dependency`.
- Use recommended fields such as `title`, `description`, `resource`, and `tags` when they add reliable value. Point `resource` to the code or system asset described when one exists.
- Record provenance in `sources` when a concept relies on specific source materials, using a bundle-relative path or URI as each source's `resource`. Attribute individual claims with source footnotes when that improves traceability.
- If using OKF trust or lifecycle fields such as `generated`, `verified`, `status`, or `stale_after`, follow the current specification exactly. Never invent an actor, timestamp, verification event, or freshness claim. In particular, do not mark content human-reviewed unless a human actually reviewed it.
- Keep body sections relevant to the concept. Use tables for fields and relationships, code blocks for examples, and links to related concepts.

Example:

```yaml
---
type: Architecture
title: Request processing
description: How incoming requests are routed and handled.
resource: /src/routes/
tags:
  - architecture
  - requests
---
```

## Ongoing maintenance

When asked to update an existing bundle, read the relevant code changes and the current concepts first. Update only affected pages, add concepts only when needed, keep the index accurate, and append a concise entry to `log.md`. Preserve human edits and existing metadata unless the user asks to change them.

Do not install git hooks, Copilot hooks, background agents, indexing tools, or other automation by default. If the user explicitly requests automatic updates, explain the trigger and permissions, then use GitHub Copilot CLI hooks documented at [GitHub Copilot hooks](https://docs.github.com/en/copilot/reference/hooks-reference) where available. Do not configure an automatic hook to run an agent with broader permissions than the user approved.

For an explicit CLI invocation, start GitHub Copilot CLI from the project root and ask it to use this skill for the requested bootstrap or update. Do not substitute Claude Code commands such as `claude -p`, or add `.claude/settings.json` configuration.
