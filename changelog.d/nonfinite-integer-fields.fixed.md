Reading entries with YAML infinity in integer fields uses the existing invalid-value fallback instead of raising OverflowError and losing access to the entry. Source frontmatter is not rewritten.
