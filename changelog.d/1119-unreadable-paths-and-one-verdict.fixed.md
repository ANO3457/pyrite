- A path `index sync` lists but cannot read -- a dangling or looping symlink,
  or a non-regular file -- is reported by `index health` as unreadable and makes
  the index unhealthy, instead of being dropped from the report (#1119).
- `pyrite-admin index health` and QA's index check use the same verdict as
  `pyrite index health`: duplicate ids, content changes and error-severity
  off-list values no longer read healthy there, and QA reports an index whose
  only defect is orphaned entries (#1119).
