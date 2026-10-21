- **CI smoke job now installs Hugo 0.151.2 and runs live frontmatter oracle tests (#1050).**
  The 31 live Hugo frontmatter splitter comparison rows in `tests/test_frontmatter_splitter.py`
  now execute during CI smoke runs instead of skipping when Hugo is absent.
