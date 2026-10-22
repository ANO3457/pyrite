- MCP `kb_read_body` and `kb_delete` answer a missing entry with
  `ENTRY_NOT_FOUND` and a KB that does not exist with `KB_NOT_FOUND`, both
  `retryable: false`, as `kb_get` and `kb_update` already do (#761). Their old
  codes stay in `legacy_error_code` for one release: `NOT_FOUND` for
  `kb_read_body`, which answered everything with it, and for `kb_delete`,
  whose missing-KB refusal was already `NOT_FOUND`; `UPDATE_FAILED` continues
  for an unscoped `kb_update` (#981, #984).
