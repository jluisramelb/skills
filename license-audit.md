# License audit

**Audit target:** the repository snapshot at `https://github.com/jluisramelb/skills`, reviewed on 2026-10-09. This is a source review, not legal advice or a legal-clearance opinion. The repository README identifies the collection as Anthropic's skills implementation and explicitly distinguishes Apache-licensed examples from source-available document skills. There is no repository-root `LICENSE`; assess each skill and bundled asset using its own notices.

## Classification key

- **ALLOW** — permission to reuse is evident and no material conditions apply.
- **CONDITIONAL** — reuse is permitted only if the license obligations are met.
- **CONCEPTS_ONLY** — study general techniques; do not copy the source's expression or implementation.
- **HOLD** — ownership, license, or permission is unresolved.
- **EXCLUDE** — do not use the material for this synthesis because its terms conflict with the intended reuse.

Statuses below describe suitability for this project: original, portable skills. A status is not a legal conclusion about other uses.

## Skill sources

The source for the entries below is the corresponding `SKILL.md` plus its local license file, where present. The license files name Anthropic, PBC as copyright holder. The 14 Apache-licensed skills carry `Copyright 2026 Anthropic, PBC`; the four restricted document skills carry `© 2025 Anthropic, PBC. All rights reserved.`

| Source skill | License and source evidence | Status | Applicable obligations / decision |
|---|---|---|---|
| `skills/academy-guide` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | If reproducing or adapting material, retain the license and copyright notices, identify modified files, include any applicable NOTICE material, and meet Apache-2.0 terms. This synthesis uses no copied expression. |
| `skills/algorithmic-art` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. No artwork, code, or wording is incorporated. |
| `skills/brand-guidelines` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. No brand assets or wording are incorporated. |
| `skills/canvas-design` | Apache-2.0; `LICENSE.txt`; bundled fonts have individual OFL notices | CONDITIONAL | Apache terms apply to the skill; each font has a separate OFL notice and must be handled under that license. No font or design asset is incorporated. |
| `skills/claude-api` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. No API examples or implementation are incorporated. |
| `skills/discernment-nudge` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. No prompts or wording are incorporated. |
| `skills/frontend-design` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. Only general design-review concepts inform the synthesis; no wording or design assets are copied. |
| `skills/internal-comms` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. Only the general idea of selecting guidance by task type informs the synthesis. |
| `skills/mcp-builder` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. Only high-level workflow and evaluation concepts inform the synthesis; no implementation or text is incorporated. |
| `skills/skill-creator` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. General validation and iteration ideas inform the synthesis; no code or text is copied. |
| `skills/slack-gif-creator` | Apache-2.0; `LICENSE.txt`; also see third-party notices | CONDITIONAL | Same Apache-2.0 obligations; bundled runtime dependencies have their own terms (below). No script, asset, or dependency is incorporated. |
| `skills/theme-factory` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. The included showcase PDF is not reused; its independent asset provenance was not verified. |
| `skills/web-artifacts-builder` | Apache-2.0; `LICENSE.txt`; includes `scripts/shadcn-components.tar.gz` | CONDITIONAL for skill; HOLD for archive contents | Apache obligations apply to skill material covered by that license. The archive has no license/readme entry in its file listing; do not reuse its contents without checking their origin and terms. |
| `skills/webapp-testing` | Apache-2.0; `LICENSE.txt` | CONDITIONAL | Same Apache-2.0 obligations. The reconnaissance-then-action concept informs verification; no code or wording is incorporated. |
| `skills/docx` | Custom terms in `LICENSE.txt`, copyright © 2025 Anthropic, PBC | EXCLUDE | The terms restrict extraction, retention, copying, derivative works, and third-party distribution. No content, code, or expression from this skill is used. |
| `skills/pdf` | Custom terms in `LICENSE.txt`, copyright © 2025 Anthropic, PBC | EXCLUDE | Same restrictions as `skills/docx`. No content, code, or expression from this skill is used. |
| `skills/pptx` | Custom terms in `LICENSE.txt`, copyright © 2025 Anthropic, PBC | EXCLUDE | Same restrictions as `skills/docx`. No content, code, or expression from this skill is used. |
| `skills/xlsx` | Custom terms in `LICENSE.txt`, copyright © 2025 Anthropic, PBC | EXCLUDE | Same restrictions as `skills/docx`. No content, code, or expression from this skill is used. |
| `skills/doc-coauthoring` | No skill-level license or copyright grant found | HOLD | Absence of a license is not permission. Not used as a source for the synthesis. |

The folder names and inventory were checked against the repository's top-level `README.md` and `.claude-plugin/marketplace.json`. Apache-2.0 terms are reproduced in each cited skill `LICENSE.txt` and point to <https://www.apache.org/licenses/LICENSE-2.0>. The custom document-skill terms identify Anthropic's Consumer and Commercial Terms (<https://www.anthropic.com/legal/consumer-terms> and <https://www.anthropic.com/legal/commercial-terms>); those terms state additional restrictions and no broader rights are inferred here.

## Bundled assets and third-party notices

| Material | Evidence and identified terms | Status / handling |
|---|---|---|
| 27 font families and 54 TTF files under `skills/canvas-design/canvas-fonts` | Each family has a corresponding `*-OFL.txt`, naming its authors and reproducing the SIL Open Font License 1.1. Example: `ArsenalSC-OFL.txt`; official license information: <https://openfontlicense.org>. | CONDITIONAL. OFL allows use and redistribution subject to its terms, including retaining the license and honoring Reserved Font Names. No fonts are included in the synthesized library. |
| ImageIO 2.37.0 and imageio-ffmpeg 0.6.0 | `THIRD_PARTY_NOTICES.md` identifies BSD 2-Clause notices. | CONDITIONAL. Preserve the copyright notice, conditions, and disclaimer when redistributing covered components. Not used. |
| FFmpeg 7.0.2 | `THIRD_PARTY_NOTICES.md` identifies GPL-3.0 and links the source archive. | CONDITIONAL. GPL-3.0 imposes distribution requirements; analyze the specific distribution/use before bundling. Not used. |
| `skills/web-artifacts-builder/scripts/shadcn-components.tar.gz` | Archive contains UI components; its listing contains no license, notice, or readme file. | HOLD. Component provenance and license are unresolved; archive is not used. |
| `skills/theme-factory/theme-showcase.pdf` | No separate copyright or license evidence was established in this review. | HOLD for reuse as a standalone asset. Not used. |

`THIRD_PARTY_NOTICES.md` is the authoritative notice file for the named third-party packages and includes their license texts. It does not establish permission for other unlisted bundle contents.

## Dependencies and integrations observed

This is a summary of dependencies declared in manifests or directly identified by skill instructions, not a complete software bill of materials. Package licenses were not separately audited unless noted above.

| Source | Declared or directly named runtime dependencies |
|---|---|
| `skills/mcp-builder` | `skills/mcp-builder/scripts/requirements.txt`: `anthropic>=0.39.0`, `mcp>=1.1.0`; separate upstream package terms need review before bundling. |
| `skills/slack-gif-creator` | `skills/slack-gif-creator/requirements.txt`: Pillow, ImageIO, imageio-ffmpeg, NumPy; see the ImageIO/FFmpeg notices above. |
| `skills/webapp-testing` | Python Playwright and a local application server, as named in `SKILL.md`; no requirements manifest is present. |
| `skills/skill-creator` | Python scripts import PyYAML; no package manifest was found in this skill folder. |
| `skills/docx` | `SKILL.md` names `docx` for Node.js, Pandoc, LibreOffice, and Poppler tools. Skill is EXCLUDE regardless of dependency licensing. |
| `skills/pdf` | `SKILL.md` and `reference.md` name PDF libraries/tools including pypdf, pdfplumber, ReportLab, pdf2image, pytesseract, pdf-lib, pdfjs-dist, and Poppler utilities. Skill is EXCLUDE regardless of dependency licensing. |
| `skills/pptx` | `SKILL.md` names `pptxgenjs`, LibreOffice, and Python/document utilities. Skill is EXCLUDE regardless of dependency licensing. |
| `skills/xlsx` | `SKILL.md` names openpyxl, pandas, markitdown, and LibreOffice. Skill is EXCLUDE regardless of dependency licensing. |
| Other skills | Instructions reference product APIs, model services, and standards (including Claude API and MCP). These are integrations or documentation references, not dependencies of the synthesized skill. |

The synthesized skill is text-only and adds no runtime package, remote service, copied code, or asset. This does not clear the dependencies of any source skill for redistribution.

## Unresolved questions and limits

- `doc-coauthoring` and the root `template/SKILL.md` have no explicit license grant in the checked snapshot. They are not reused.
- The component archive and showcase PDF need independent provenance review before any reuse.
- This audit does not inspect every third-party package's current license or resolve the scope of copyright in individual examples. Dependency owners, version-level license changes, and other jurisdiction-specific obligations may require further review.
- No license for the repository as a whole or for the newly authored skill is asserted. The repository owner should decide whether and under what terms to license the new skill before distributing it outside this repository.
- No similarity checker can establish legal clearance. Any similarity flag or unresolved provenance requires human review rather than an assumption of permission.
