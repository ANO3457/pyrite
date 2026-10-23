- `sw_create_adr` numbers a new ADR from the files on disk rather than the index, matching `pyrite sw new-adr` and resolving the single configured KB when `kb_name` is omitted (#1175).
- Implicit ADR KB selection considers only readable KBs and refuses an unresolved
  selection without naming hidden KBs. CLI and MCP share the resolver; unreadable
  non-UTF-8 files are skipped with a warning while numbering.
