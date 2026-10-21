- A `sqlite3.DatabaseError` raised mid-command when an interior index page is corrupt
  is mapped to `STORAGE_ERROR` naming the index path and suggesting `pyrite index build`,
  preventing non-search CLI commands from falling through to `NO_OUTCOME` (#1182).
