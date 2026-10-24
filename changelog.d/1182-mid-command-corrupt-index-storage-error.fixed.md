- When an index page is corrupt or the file is not a database, a SQLite error raised mid-command
  is mapped to `STORAGE_ERROR` naming the index path and suggesting `pyrite index build`,
  preventing non-search CLI commands from falling through to `NO_OUTCOME` (#1182).
  Query errors and locks are not reclassified as corruption. SQLite storage
  errors use the shared constructor in `pyrite.storage.errors`.
