# Status dashboard

Last updated: 2026-02-12

**Phase 1 dashboard**

| edition_id | in_scope_for_phase1 | tei_backed | citations_normalized | manifest_status | iiif_coverage_target | iiif_coverage_current | notes/blockers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| wellmann | yes | yes | done | unknown | n/a |  | Headerless TSV normalized; citations present. |
| sprengel | no | no | not started | unknown | n/a |  | No Phase 1 citation TSV identified. |
| desmoulins | yes | no | done | provisional | 100% | 100% | Uses biusante template from `src/dmm-defs.xml` (mo_pag); manifest URL still missing. |
| matthioli | yes | yes | done | unknown | n/a |  | Roman chapter labels parsed. |
| monardes | no | no | not started | unknown | n/a |  | No Phase 1 citation TSV identified. |
| laguna | yes | yes | done | unknown | n/a |  | Uses `laguna_scan_id` and `laguna_iiif` keys. |
| wechel | yes | no | done | provisional | 100% | 100% | Placeholder target_url scheme `wechel:scan/{scan_id}`; needs real viewer URL. |
| ruellius | yes | no | done | provisional | 100% | 100% | Archive.org `/page/n` template from `revised_ed/editions_table.tsv`; confirm ruel_web semantics. |
| lusitanus | yes | no | done | provisional | 100% | 100% | Uses biusante template from `src/dmm-defs.xml` (lu_pag); confirm `lusitanus_iiif` semantics. |
| berendes | yes | yes | done | unknown | n/a |  | Citation ref is `berendes_book.chapter`. |
| barbaro | yes | no | done | provisional | 100% | 100% | Uses biusante template from `src/dmm-defs.xml` (ba_img); confirm `barbaro_iiif` semantics. |
| beck | no | yes | done | unknown | n/a |  | `revised_ed/beck.tsv` is index-like; kept for provenance only. |
| gunther | yes | yes | done | unknown | n/a |  | Chapter description preserved in `notes`. |

**How to update this dashboard**

- After running Phase 1 validation, use `data/vnext/validation_report.md` to fill `iiif_coverage_current` and update `citations_normalized` to `done` or `blocked`.
- Use `data/vnext/needs_review_missing_manifest.csv` to update `manifest_status` and add blockers for editions still marked `provisional`.
- Use `data/vnext/needs_review_missing_iiif.csv` and `data/vnext/needs_review_ambiguous_iiif.csv` to populate `notes/blockers` with concrete issues.
- When citations are regenerated deterministically, update `citations_normalized` and record any unresolved parsing issues from `data/vnext/needs_review_bad_rows.csv`.
