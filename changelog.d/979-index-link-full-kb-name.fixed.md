- A `[[short:id]]` link is indexed under the KB's full name, as ADR-0049 says
  (#952, #979): the index used to store the prefix as written, so backlinks,
  the graph, `index health` and `qa check-links` called every shortname link
  broken while `resolve_entry` found it. A frontmatter `links:` item's `kb`
  resolves the same way. The prefix as written is kept beside the resolved
  name (`link.target_prefix`, index migration v28), and `index health` warns
  about rows it cannot stand behind: `links_to_unknown_kb` (a row indexed
  before this change still naming a shortname) and `links_stale_prefix` (a
  shortname renamed in config since the file was indexed). **Run
  `pyrite index rebuild` after upgrading**, and after renaming a shortname:
  an unchanged file is not re-read by `index sync`, so its rows keep the old
  resolution until a rebuild. A prefix that names no KB is still stored as
  written and counted broken. `pyrite batch-read kb:id ...` resolves the KB in
  each spec before reading anything: an unknown KB or a shortname in any one
  spec is refused with `KB_NOT_FOUND` (exit 1) for the whole call, not
  reported under `not_found`.
