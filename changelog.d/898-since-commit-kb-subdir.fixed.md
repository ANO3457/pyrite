- `pyrite index build --with-attribution --since <commit>` (and a `repo pull`
  that reindexes) re-reads the changed files of a KB that lives in a repo
  subdirectory again. `git diff --name-only` prints repo-root-relative paths,
  so the KB's prefix is now stripped before a path is joined onto the KB, as
  `get_file_log` already did (#898).
