# Master build QA

- Source: `Materia Medica.xlsx`
- Register rows: 10443
- Concordance rows (chapter_key): 952

## Rows by edition
- barbaro: 963 rows (missing chapter_key: 0)
- beck: 959 rows (missing chapter_key: 11)
- berendes: 949 rows (missing chapter_key: 0)
- desmoulins: 950 rows (missing chapter_key: 0)
- gunther: 974 rows (missing chapter_key: 24)
- laguna: 969 rows (missing chapter_key: 3)
- lusitanus: 961 rows (missing chapter_key: 0)
- matthiolo: 963 rows (missing chapter_key: 0)
- ruel: 956 rows (missing chapter_key: 0)
- wechel: 968 rows (missing chapter_key: 3)
- wellmann: 831 rows (missing chapter_key: 16)

## Notes
- `chapter_key_raw` preserves composite keys (e.g. `3.29;3.30`) while `chapter_key` is expanded.
- `all` sheet is intentionally not used because it contains Excel numeric-format collisions (e.g., `1.10` -> `1.1`).
