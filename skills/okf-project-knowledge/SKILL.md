---
name: okf-project-knowledge
description: Bootstrap or maintain a source-grounded project knowledge bundle or cross-repository code navigation graph in Google's Open Knowledge Format (OKF). Use when asked to document architecture, data models, APIs, dependencies, decisions, or help agents route through a multi-repository codebase using GitHub Copilot.
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

## Cross-repository code navigation graph

When the goal is to help agents navigate a multi-repository codebase, model the bundle as a graph of OKF concepts connected by standard Markdown links. The graph is a routing aid, not an authority: source code, repository configuration, and contracts remain the source of truth.

### Node types

Use descriptive OKF `type` values for these concepts. Create only types that correspond to real, useful navigation targets:

| Node type | Purpose |
| --- | --- |
| `Repository` | Identifies one Bitbucket Cloud repository and its purpose; the graph's entry point for locating code. |
| `Module` | Identifies a meaningful package, module, or code area within a repository; narrows investigation to a source subtree. |
| `Service` | Identifies a deployable or runtime application/component; connects code locations to runtime responsibilities. |
| `Entry Point` | Identifies where behavior begins, such as a route, handler, command, scheduled job, or event consumer. |
| `API` | Identifies a contract or interface, including HTTP APIs, schemas, RPC interfaces, or shared library interfaces. |
| `Data Store` | Identifies a database, queue, object store, or other persistence system when it is important for tracing behavior. |
| `Schema` | Identifies the authoritative schema or migration set for a data resource. |
| `Team` | Identifies an owning team only when ownership is confirmed from an authoritative source and useful for routing. |

A node is one coherent concept, not every file or symbol. Group small or tightly coupled code areas when that produces a clearer route. Give each concept a stable, readable bundle path; qualify repository identities with the Bitbucket workspace and repository slug to avoid collisions.

### Edge types and direction

Represent edges as ordinary Markdown links with explicit relationship wording in the surrounding sentence or table. Keep the link on the target concept and write each relationship from the source node's perspective:

| Relationship | Direction and meaning | Evidence to look for |
| --- | --- | --- |
| `contains` | Repository or module → contained module, service, entry point, API, or schema. Structural location only; it does not imply runtime coupling. | Repository tree, build configuration, package boundaries. |
| `depends on` | Consumer → dependency; identifies build-time or runtime dependency. | Import/manifests, dependency injection, deployment or service configuration. State whether build-time or runtime when known. |
| `calls` | Caller/entry point → invoked service, API, or module; follows synchronous execution. | Call sites, generated clients, routing or invocation configuration. |
| `implements` | Implementation module/service → API or contract it fulfills. | Handler registration, interface implementation, schema/client generation configuration, contract tests. |
| `publishes` | Producer → event/topic/queue contract or destination. | Producer code and broker/topic configuration. |
| `consumes` | Consumer → event/topic/queue contract or source. | Consumer registration and broker/topic configuration. |
| `routes to` | Route or entry point → handler/service that receives the request or work. | Router, framework registration, gateway configuration. |
| `reads` / `writes` | Component → data store or schema it reads from or writes to. | Queries, repository/data-access code, migrations, ORM mappings, runtime configuration. |
| `owned by` | Repository or component → team concept. | Authoritative CODEOWNERS, Bitbucket project/repository metadata, or confirmed ownership record. |

Do not infer an edge from naming similarity, directory co-location, or a README claim alone when implementation or authoritative configuration can be checked. If the relationship is plausible but unverified, record it as an open question in the concept or gaps page, not as a confirmed graph edge. Include brief qualifiers where direction alone is insufficient, such as protocol, dependency kind, or event/topic name.

### Identity, provenance, and multi-repository layout

- Give each repository concept a Bitbucket Cloud URL and verified workspace/repository slug. Record the default branch only after checking Bitbucket metadata or repository configuration.
- For every code-backed concept, identify its repository and the narrowest useful source paths. Record the branch/commit or other revision inspected so agents can detect whether the description may be stale. Do not present a branch name as an immutable revision.
- Use OKF `sources` for source materials when practical. Source paths should be scoped to the repository concept and be resolvable by an authorized agent; use a Bitbucket URL or an unambiguous repository-relative path plus repository identity. Attribute important claims with source footnotes when that helps verification.
- Prefer a central OKF bundle as the cross-repository catalog and graph entry point. It should contain repository and system-level concepts, linking to component concepts. Repo-local OKF bundles are optional replicas or focused details: avoid competing definitions, identify the canonical concept, and link back to it.
- Do not copy source code into the graph. Preserve Bitbucket authorization boundaries: only expose metadata to agents permitted to see it, and never assume that access to the central bundle grants access to linked repositories.

### Agent routing and freshness

For a codebase question or change, agents should:

1. Start at the central `index.md`, find the relevant system or repository concept, and follow only the links needed to identify likely components, entry points, contracts, and data resources.
2. Confirm the agent is authorized to access each linked repository, then inspect the referenced source and current repository revision in Bitbucket.
3. Treat graph descriptions as search hints. Resolve disagreements in favor of current source/configuration, and correct the graph only after confirming the evidence.
4. If a link is broken, a repository is inaccessible, or the referenced revision has moved, report that limitation and search the source directly where authorized. Never fill a gap with an assumed relationship.

On refresh, compare each concept's recorded source revision with the revision inspected. Re-check edges affected by changed source paths, manifests, routes, contracts, ownership, or persistence configuration; update relevant concepts and the index, and append a `log.md` entry. Flag concepts whose source or revision cannot be verified as potentially stale. Do not mark a concept verified or current merely because an automated refresh ran. Keep automated Bitbucket-triggered updates opt-in, use least-privilege credentials, and do not bypass repository permissions.

### Pilot evaluation

Before scaling the graph across all repositories, test a representative set of real tasks. For each task, check whether an agent can identify the relevant repository, component, behavior entry point, cross-repository dependencies, and authoritative source paths; then verify those choices against Bitbucket code. Track incorrect or missing routes, unsupported edges, inaccessible links, and stale revision references. Refine node/edge definitions and coverage based on those failures rather than adding speculative graph detail.

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
