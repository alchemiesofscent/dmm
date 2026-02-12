# `src/` contents

This directory contains **source TEI/XML editions** (often large, uneven quality) plus a small amount of **configuration/registry XML** used by TEITOK-era workflows.

Early alignment work should rely on **standoff mappings + IIIF** rather than editing these TEI/XML files directly.

## Files

- `dmm-defs.xml` — TEITOK definitions: field dictionary, display defaults, and link templates for item records; also contains a `listBibl` bibliography block.
- `sources.xml` — supplementary source/bibliography registry (editions/scans/links; some TEITOK IDs).

### TEI/XML source texts (varying completeness)

- `tlg0656001.xml` — TEI generated from TLG via Diogenes; note the file itself mentions potential licensing restrictions (treat as restricted until confirmed).
- `wellman (3).xml` — TEI for Wellmann-based Greek text (with TEI header + structure).
- `berendes (1).xml` — TEI for Berendes (German translation; includes `pb` facsimile links).
- `beck (3).xml` — TEI-like OCR/tokenized XML with page breaks and token bounding boxes.
- `gunther (1).xml` — TEI for Gunther (“The Greek Herbal of Dioscorides”).
- `matthioli.xml` — TEI for Matthioli commentary (contains HTML-like markup in places).
- `latin12995.xml` — TEI-like Latin witness/transcription with facsimile links (mixed markup).
- `sl-grk.xml` — TEI/XML for a Greek track (project-specific; confirm provenance as needed).
- `sl-esp.xml` — TEI/XML for a Spanish track (project-specific; confirm provenance as needed).
- `ces1985.xml` — TEI wrapper with `pb/@facs` image links (NDK/MZK image server URLs).
- `ces2003 (1).xml` — similar TEI wrapper with `pb/@facs` image links and Czech content near the start.

## Notes

- Filenames currently include spaces/parentheses for some sources; do not rename casually without updating any downstream references.
- Not all sources are “clean TEI”; some are tokenized/OCR-style XML with embedded facsimile links.
- For non-transcribed editions, IIIF coverage should be treated as required data (see `docs/validation.md`).
