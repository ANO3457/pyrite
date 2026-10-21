- An exclusive save whose `os.link` created the target but reported an error
  (EIO, or EEXIST on an NFS retransmit) now checks whether the target is the
  temp file's inode and treats that as the publish it is, instead of raising
  `FileExistsError` with the new file already at the target (#914).
- The placeholder-cleanup tests now assert that a failed `fstat` raises and
  that a file another writer put at the path is left alone (#914).
