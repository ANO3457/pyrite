- A `[[short:id]]` link is indexed under the KB's full name, as ADR-0049 says
  (#952, #979): the index used to store the prefix as written, so backlinks,
  the graph, `index health` and `qa check-links` called every shortname link
  broken while `resolve_entry` found it. A prefix that names no KB is still
  stored as written and counted broken. `pyrite batch-read kb:id` resolves
  the KB in each spec before reading: an unknown KB or a shortname is refused
  with `KB_NOT_FOUND` (exit 1), not reported under `not_found`.
