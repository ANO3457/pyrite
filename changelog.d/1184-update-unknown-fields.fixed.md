REST entry writes share one unknown-key refusal rule across POST, PUT and PATCH.
A client that PUTs a whole GET response (including `id` or `file_path`) now gets
400 `VALIDATION_FAILED`, rather than 200 with silently dropped keys. ADR-0034
transport markers are accepted consistently and are never stored.
