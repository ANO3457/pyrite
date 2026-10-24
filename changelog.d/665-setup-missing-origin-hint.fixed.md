- **Worktree setup gives actionable remote errors (#665).** The default
  `origin/dev` path reports a missing origin or preserves Git's fetch error,
  with a project-remote hint for forks without `dev`. Explicit local branch,
  tag, or commit start-points work without an origin. The affected-test diff
  hint also names `--base <REF>`.
