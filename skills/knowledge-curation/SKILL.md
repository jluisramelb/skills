---
name: knowledge-curation
description: >
  Create, ingest, query, and maintain project knowledge bundles using
  Google's Open Knowledge Format (OKF). Use this skill when organizing
  project knowledge, capturing durable learnings from documents or code,
  answering questions from a curated knowledge collection, or reviewing
  its accuracy and freshness.
---

# Project Knowledge Curation

Build a portable, reviewable body of project knowledge with OKF: plain
Markdown files with YAML frontmatter, organized as a bundle. Treat the
bundle as curated knowledge, not as a replacement for source materials or
a particular agent, wiki, or retrieval system.

## Principles

- Keep original source material unchanged and distinguish it from curated
  knowledge derived from it. Never replace, move, or rewrite source files
  as part of curation.
- Capture reusable facts, decisions, relationships, procedures, and
  definitions rather than copying whole documents into the bundle.
- Organize around the user's project boundaries. Keep unrelated projects
  distinct; link shared knowledge rather than silently duplicating or
  blending it.
- Preserve uncertainty and disagreements. Attribute claims to evidence;
  do not invent facts, sources, dates, or human verification.
- Keep documents readable and changes reviewable. Make focused edits and
  summarize additions, changes, unresolved conflicts, and gaps.

## Use OKF

Before creating or changing a bundle, inspect the existing directory and
read its root `index.md` and relevant subdirectory indexes, if present.
Follow the current OKF specification when it is available. Use the
standard structure and fields rather than inventing a competing schema:

- A bundle is a directory of Markdown concept documents. Each concept
  document has YAML frontmatter with a `type`; use `title`, `description`,
  `resource`, and `tags` when they help identify and navigate it.
- Record provenance in `sources` when known. Use `generated` for the
  agent or process that last meaningfully changed content, and `verified`
  only for checks that actually occurred. Use `status` and `stale_after`
  when lifecycle and freshness are meaningful.
- Connect related concepts with standard Markdown links. Use the OKF
  bundle-relative link conventions and preserve links when moving files.
- Use `index.md` files for directory navigation and progressive
  disclosure. Update relevant indexes when adding, renaming, or removing
  concepts. Treat `index.md` and `log.md` as reserved filenames, not
  concept documents.
- When maintaining a change history, use `log.md` with date-grouped
  entries in newest-first order.
- Preserve unrecognized frontmatter fields when editing existing
  documents. Don't require optional metadata when it is not known.

If the specification or a project-specific convention conflicts with
these general instructions, follow the specification and the user's
explicit convention. The official specification is:
https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md

## Ingest sources

1. Identify the intended project and bundle. If the destination, project
   boundary, or whether the user wants a persistent write is unclear, ask
   before creating or changing files.
2. Inspect existing concepts before drafting. Search for the same entity,
   decision, or claim so new evidence enriches the right document instead
   of creating duplicates.
3. Read the supplied or authorized source material. Separate direct
   evidence from interpretation, and note conflicting or time-sensitive
   claims.
4. Create or update focused concepts. Keep useful definitions, rationale,
   constraints, steps, examples, and relationships. Link to authoritative
   sources and relevant concepts; use a `references/` area for source
   material when it benefits navigation, not as a mandatory mirror of
   every input.
5. Set OKF metadata from evidence. Mark content `draft` when it needs
   review; don't mark it human-reviewed unless a human actually reviewed
   it. Don't guess a `stale_after` date.
6. Update indexes and, if the bundle uses one, its log. Check changed
   links and report what was created or updated and what remains
   uncertain.

## Query the bundle

Start at the nearest applicable index and open only the concepts needed
to answer the question. Follow links where they clarify dependencies,
definitions, or decisions. Base answers on the bundle's evidence and
provenance, distinguish verified information from unverified or stale
content, and cite the concept paths and source links. If the bundle is
silent, contradictory, or outdated, say so rather than filling gaps with
assumptions.

## Review and maintain

On request, or when a change risks making related knowledge inconsistent,
review the affected scope for:

- duplicate concepts or contradictory claims;
- missing or broken links and navigation entries;
- missing provenance for sourced claims;
- stale `stale_after` dates, deprecated concepts, and obsolete references;
- metadata or directory conventions that drift from OKF.

Make only corrections supported by sources or explicit user decisions.
Where evidence conflicts, record the conflict and its sources for
resolution instead of choosing a side without support. Keep audits scoped
to the relevant project or requested portion of the bundle.

## References

- [Open Knowledge Format specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)
- [Design input: an account of maintaining knowledge across multiple projects](https://hackernoon.com/how-i-built-a-self-maintaining-knowledge-base-for-6-projects-using-claude-code-and-karpathys-llm-wiki)
