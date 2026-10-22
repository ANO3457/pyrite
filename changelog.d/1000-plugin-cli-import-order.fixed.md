- An extension's command group is registered whichever module the process
  imports first: `pyrite` mounts plugin CLI groups when the app is first used,
  not while `pyrite.cli` is still importing (#1000, #1109).
