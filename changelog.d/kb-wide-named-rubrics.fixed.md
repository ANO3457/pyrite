Whole-KB QA validation now runs the named deterministic rubric checkers from
`kb.yaml`, as single-entry validation does. Missing and broken checker bindings
are reported instead of silently passing; existing identical SQL findings are
not repeated. This also applies to `ci`, MCP and REST callers of `validate_kb`.
