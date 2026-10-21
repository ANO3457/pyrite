REST entry updates refuse undeclared top-level keys with `VALIDATION_FAILED`
instead of silently dropping them; type-specific fields belong in `metadata`.
