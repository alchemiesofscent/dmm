# Scripts Guardrails

- Use Python 3 and stdlib-only dependencies where possible.
- Emit deterministic outputs (stable headers, stable sorting).
- Preserve provenance fields and avoid silent coercion.
- Write explicit error queues (`needs_review_*`) instead of dropping bad rows.
- Phase 1 scripts must not use network access; read cached IIIF manifests from disk.
