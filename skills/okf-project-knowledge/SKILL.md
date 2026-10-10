---
name: okf-project-knowledge
description: Bootstrap or maintain a source-grounded OKF job graph for agents navigating a multi-repository codebase. Use when asked to define agent jobs and hand-offs for investigating Bitbucket repositories, while treating code as the source of truth.
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

## Cross-repository job graph

When the goal is to help agents navigate a multi-repository codebase, model the graph as jobs and hand-offs. A graph node is an agent job: a bounded unit of work with a purpose and a verifiable result. A directed edge is a hand-off: the context or artifact one job passes to the next job. Repositories, modules, APIs, services, and data stores are not graph nodes; they are codebase resources that jobs discover, inspect, and reference. The graph routes investigation; source code, repository configuration, and contracts remain the source of truth.

### Job nodes

Represent each job as an OKF concept with `type: Job`, a stable readable bundle path, and a clear title. A job definition should state:

- **Purpose:** What question or result this job addresses, and when it should run.
- **Inputs:** Required user request, prior hand-off artifacts, and any known constraints.
- **Work:** The investigation to perform, including how to locate relevant repositories or source.
- **Outputs:** The concrete result to hand off, such as selected repository and revision, source paths, findings, unresolved questions, or a proposed change.
- **Completion criteria:** What evidence makes the job done and how outputs should be checked.
- **Access constraints:** Which Bitbucket repositories or permissions are required; never presume access.

Keep jobs small enough to have clear inputs and outputs, but not so small that the graph becomes a list of trivial tool calls. Add job types only when they describe materially different work. A reusable investigation flow may include jobs such as:

1. **Frame request** — extract the user's goal, constraints, and expected outcome.
2. **Select repository** — use the central catalog to identify candidate Bitbucket repositories; return the reason and unknowns.
3. **Locate code area** — inspect an authorized repository to find the likely module, entry point, contract, or data access code.
4. **Trace behavior** — follow the actual implementation and verified cross-repository calls, events, or contracts.
5. **Verify source** — check conclusions against current source and configuration, recording paths and revision.
6. **Respond or update knowledge** — answer the request or propose/update relevant OKF job definitions and navigation guidance.

Treat these as examples, not mandatory stages; select and connect only jobs useful for the actual workflow.

### Hand-off edges

Represent each hand-off as a standard Markdown link from the producing job to the receiving job. Describe it from the producer's perspective and state what is passed, why the next job needs it, and any condition for taking that path. A hand-off may carry a user request, candidate repository list, source locations, evidence, findings, or explicit unresolved questions. The target job must not rely on unstated context from the prior job.

Use explicit hand-off wording in the source job, for example:

> On successful repository identification, hand off the repository slug, Bitbucket URL, inspected revision, and selection evidence to [Locate code area](/jobs/locate-code-area.md).

Record conditional branches and parallel paths clearly. Multiple jobs may receive hand-offs from one job, and a later job may combine their outputs; document required inputs so missing results are visible. Distinguish a hand-off (transfer of work/context) from a relationship found in code. Do not create graph edges such as `calls`, `depends on`, or `contains` to represent software architecture; those facts belong in the job's findings and source references.

### Source references and multi-repository context

- Keep a central OKF bundle as the workflow entry point, with `index.md` linking to job concepts and explaining how to start.
- In job concepts and hand-off outputs, identify Bitbucket resources with verified workspace/repository slugs, URLs, useful source paths, and the inspected immutable commit/revision where available. A branch name alone is not a fixed revision.
- Treat repository/module/API/service/data-store information as job input, output, evidence, or source references—not as graph vertices.
- Use OKF `sources` for authoritative code/configuration materials when practical; scope relative paths to an unambiguous repository identity. Record enough provenance for the next job or human to reopen the evidence.
- Do not copy source code into the knowledge bundle. Repo-local knowledge may supplement the central workflow when practical, but identify the canonical job definition and avoid competing versions.
- Preserve Bitbucket authorization boundaries: disclose only metadata appropriate for the audience, and never assume access to the bundle grants access to a linked repository.

### Agent routing and freshness

For a codebase question or change, agents should start at the central `index.md`, choose the job matching the request, and follow only the hand-offs needed to complete it. Each receiving job uses the explicit hand-off payload, confirms authorization, and inspects current Bitbucket source before relying on codebase claims. If a repository is inaccessible, a path is missing, or a revision cannot be resolved, report that limitation and do not invent a replacement edge or conclusion.

The job graph describes a workflow, not current code facts. On refresh, validate job instructions and hand-offs against actual agent tasks and source navigation outcomes; update source references or routing guidance only after checking evidence. Record stale or unverified references as such. Keep automated Bitbucket-triggered updates opt-in, use least-privilege credentials, and do not bypass repository permissions.

### Pilot evaluation

Pilot the graph on representative real tasks that cross repository boundaries. Check whether agents select the right jobs, receive the context needed at each hand-off, locate the relevant authorized repository and source, and verify results against the code. Track wrong or unnecessary hand-offs, missing payload fields, stalled routes, inaccessible repositories, and unsupported conclusions. Refine job boundaries and hand-off contracts based on these failures.

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
