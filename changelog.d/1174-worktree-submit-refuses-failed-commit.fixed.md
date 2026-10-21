- `WorktreeService.submit` refuses with `STORAGE_ERROR` when auto-committing
  pending changes fails (such as when git identity is unset on the server),
  leaving the worktree unsubmitted instead of falsely reporting success
  while the edit remains uncommitted (#1174).
- `WorktreeService.merge` refuses when nothing was committed on the user's branch
  beyond `main`, preventing an empty diff from being reported as merged.
