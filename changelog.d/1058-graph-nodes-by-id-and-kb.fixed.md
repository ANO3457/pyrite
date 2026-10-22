- The whole-index graph chooses its nodes by entry id *and* KB, as the
  centered walk already did: with `ka/s` linking `[[x]]`, `kb:x` no longer
  appears as an unlinked node and takes a slot of `limit` (#1058).
