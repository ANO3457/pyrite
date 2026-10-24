- **`pyrite qa validate` checks task references (#935).** The new
  `task_references` rule reports missing dependency or deliverable entry IDs as
  errors and an already-existing non-task deliverable as a warning for open
  tasks. Cross-KB `kb:id` references respect the caller's read scope. The rule
  also runs through `pyrite ci`.
