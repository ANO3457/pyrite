- `embedding_service.is_available()` answers from the import system's finder
  instead of importing sentence-transformers and torch: every CLI, server and
  test path that asks saves about 300 MB of work per process. A package the
  finder can see but whose import fails is now named at the first model load,
  with the install line (#1101).
