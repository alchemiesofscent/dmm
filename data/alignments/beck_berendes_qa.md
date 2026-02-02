# Beck ↔ Berendes alignment QA
- Source: `Materia Medica.xlsx`
- Edge rows: 959 (with beck_dmm_id: 826)
- Unique Beck dmm_id: 825
- Beck 1→N cases (degree>1): 1
- Berendes N→1 cases (degree>1): 0

## Notes
- Uses `berendes_teitok_id` as the Berendes stable id.
- Adds context from Desmoulins/Laguna/Wechel/Mattioli/Ruel/Lusitanus/Barbaro/Gunther/Wellmann where available.
- `berendes_chapter_raw` may be composite (e.g. `3.29;3.30`); `berendes_chapter_keys` is expanded.
- `cardinality` is computed per Beck dmm_id within this alignment sheet only.
