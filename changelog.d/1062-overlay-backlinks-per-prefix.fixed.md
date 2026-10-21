- Through the overlay backend, one source's two spellings of a link
  (`[[ops:x]]` and `[[ops-kb:x]]`) are two backlinks and two outlinks again,
  as the index keeps them; backlink and outlink rows now carry the written
  `prefix`, so a merge can tell them apart (#1062).
