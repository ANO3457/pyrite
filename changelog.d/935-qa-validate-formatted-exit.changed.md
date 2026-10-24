- **`pyrite qa validate` exits 1 when any validation rule reports an error,
  in every output format, including the default JSON format (#935, ADR-0046).**
  Previously formatted output returned success before evaluating the verdict.
  Scripts consuming the JSON must now handle this nonzero exit status; warnings
  alone still return success.
