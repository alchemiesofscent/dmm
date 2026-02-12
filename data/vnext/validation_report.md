# Phase 1 Validation Report

Inputs:
- citations.csv: 9218 rows
- citation_iiif_map.csv: 3970 rows
- iiif_manifests.csv: 5 rows

Coverage (non-TEI editions in scope):
- barbaro: 404/404 (100%) status=provisional
- desmoulins: 813/813 (100%) status=provisional
- lusitanus: 799/799 (100%) status=provisional
- ruellius: 951/951 (100%) status=provisional
- wechel: 1003/1003 (100%) status=provisional

Provisional manifests:
- barbaro: No manifest URL in repo; biusante image template in src/dmm-defs.xml (ba_img/ba_pag).
- desmoulins: No manifest URL in repo; biusante image template in src/dmm-defs.xml (mo_pag).
- lusitanus: No manifest URL in repo; biusante image template in src/dmm-defs.xml (lu_pag).
- ruellius: Archive.org item BIUSante_00815 in revised_ed/editions_table.tsv; manifest URL not identified.
- wechel: No in-repo manifest or viewer URL identified.

Needs review counts:
- needs_review_missing_manifest.csv: 5
- needs_review_missing_iiif.csv: 0
- needs_review_ambiguous_iiif.csv: 0
- needs_review_bad_rows.csv: 0
