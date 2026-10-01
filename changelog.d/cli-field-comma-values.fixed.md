- **CLI `--field` values preserve commas unless the schema declares a list field.**
  `create`, `update`, and `task create` now keep ordinary text such as `1,600`
  or `Portland, OR` as strings while still splitting comma-separated values for
  declared `list`, `multi-select`, and `tags` fields; JSON string literals are
  also accepted.