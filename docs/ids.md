# ID policy (authoritative)

This document defines identifiers used in the project and the rules that make them stable over time.

## ID types

### `edition_id`

- Short lowercase slug (e.g., `wellmann`, `berendes`, `wechel`, `beck`).
- Must be stable once introduced.

### `segment_id` (edition-local)

Meaning:
- An edition-local textual segment (sub-chapter granularity) that can be anchored to TEI.

Stability:
- Stable *within an edition* once the edition’s segmentation is frozen for a given scope/version.

Recommended format (proposal):
- `SEG:<edition_id>:<citation_ref>:<seq>`
  - example: `SEG:wechel:1.29:0003`

Notes:
- The exact shape is less important than uniqueness, determinism, and TEI anchorability.
- Do not reuse IDs; if a segment is retired, mark it `deprecated` (do not delete).

### `unit_id` (global work unit; citation-stable)

Meaning:
- A global “work unit”: the smallest cross-edition chunk intended to represent the same underlying textual unit across witnesses.

Stability:
- **Citation-stable once frozen** (never renumber; never reuse).

Format:
- `DMMU` + 6-digit zero-padded integer
  - example: `DMMU000001`

Human readability:
- Store anchor metadata separately (anchor edition/book/chapter/sequence) and generate display labels as needed.
- Do not encode book/chapter/section into `unit_id` itself.

### `topic_id` (optional concept grouping)

Meaning:
- A concept/substance/topic grouping across work units (many-to-many).

Status:
- Optional; introduce only when there is a clear retrieval/use case that work units alone cannot satisfy.

## Split/merge and deprecations

### After freeze (citation-stable scope)

- Never renumber `unit_id`.
- If a unit must be split/merged after freeze:
  - create new `unit_id` values
  - mark old ones as `deprecated`
  - record relationships (`replaced_by`, `replaces`) explicitly

Rationale:
- Preserves citation stability while allowing scholarly correction.

## Ordering

- Use an explicit ordering key (derived from an anchor edition + sequence) rather than relying on lexical sorting of IDs.

