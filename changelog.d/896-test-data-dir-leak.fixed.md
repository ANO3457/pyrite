- Fix the intermittent `experimental`-job failures of the zettelkasten report
  tests (`test_cli_reports.py` seeing an empty index under xdist):
  `test_mcp_info_is_404_not_the_spa_when_mcp_is_unmounted` set
  `PYRITE_DATA_DIR` with `os.environ.setdefault`, leaking it into later tests
  in the same worker, where `_apply_env_overrides` repointed their
  `load_config()` at the deleted temp dir's empty `index.db`. The test now
  uses `monkeypatch.setenv` (#896).
