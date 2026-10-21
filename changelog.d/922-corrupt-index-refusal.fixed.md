- An index file that is not a SQLite database (overwritten, truncated, or a
  directory at the path) now raises one `STORAGE_ERROR` refusal from the first
  connection, naming the index path and `pyrite index build`; `get`,
  `backlinks`, `search`, `create`, `index sync`, `index build` and
  `index health` exit 1 with the structured error instead of a traceback or
  the driver's text (#922). An empty file is still a new index and works.
- `search` keeps its file-search fallback for a real search-time failure, but
  no longer falls back when the index itself cannot be opened (#922).
