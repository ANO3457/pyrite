- `pyrite sw new-adr` numbers from the ADR files as well as the index, so a
  KB that was registered but not synced no longer answers `ENTRY_EXISTS:
  adr-0001` for a file it already holds; the pipeline's own duplicate-id
  refusal is unchanged (#1082).
