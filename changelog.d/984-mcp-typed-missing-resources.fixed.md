- MCP `kb_read_body` and `kb_delete` answer a missing entry with
  `ENTRY_NOT_FOUND` and a KB that does not exist with `KB_NOT_FOUND`, both
  `retryable: false`, as `kb_get` and `kb_update` already do (#761). Their old
  codes stay in `legacy_error_code` for one release: `NOT_FOUND` for
  `kb_read_body`, which answered everything with it, and for a missing entry
  on `kb_delete`; `DELETE_FAILED` for a missing KB on an unscoped `kb_delete`,
  whose call used to reach the handler that answered it `retryable: true`
  (#984).
