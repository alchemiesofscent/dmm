# Alignment model (pause note)

Your A/B/C breakdown is the right decomposition, and it also explains why the current spreadsheet-first alignment feels “sloppy”: we don’t yet have a stable notion of (1) *edition-local textual units* and (2) *a chosen segmentation level* that alignments can reliably target.

## 1) Edition-local citation units (A)

- For each edition, define a stable, edition-internal reference system that matches the printed text (book/chapter/etc) and can be anchored to TEI and/or IIIF later.
- This becomes your **edition citation id** space (e.g., `ruel:001.001` or `ruel-001-001`, whichever convention you standardize).
- Practically: this answers “where is it in the book?”.

## 2) Entries / segments (B)

- Separately, define the *units you actually want to align* (starting “by substance” is a good initial choice).
- These units will sometimes be 1:1 with a printed chapter, but often are **split/merged** relative to printed chaptering.
- So you define an **entry id** space that can represent:
  - a whole printed unit,
  - a subrange within a printed unit,
  - or a join across multiple printed units.
- This is what TEI `<div>/<seg>` structure ultimately represents.

## 3) Alignments (C)

- Once entries exist, the alignment table becomes well-defined: it links **entry ids** across editions, not raw printed chapter refs.
- Alignment types then become meaningful (`equivalent`, `contains/part_of`, `related`) and you can do a semantic pass first, then refine.

## 4) IIIF manifests (attachment layer)

- IIIF manifests (and ideally page/canvas mapping) per edition are an *attachment layer* to the citation units/entries:
  - citation unit → page range(s) / canvas range(s)
  - entry → page/canvas range(s) (derived from its covered citation units)
- You don’t need IIIF to start aligning, but you do want it to make the system verifiable and navigable.

## Summary

Keeping these as distinct concepts/tables (even if they start life in one spreadsheet) is the clean model:

- `citations` (edition-local printed structure)
- `entries` (your chosen alignment granularity; can reference one-or-more citations)
- `alignments` (entry↔entry graph)
- `iiif_sources` + `iiif_ranges` (manifest + mapping to citations/entries)

This matches the direction: humans scan a clean UI, code operates underneath, and alignments live in a table linking all editions—*after* citations and segments are defined.

