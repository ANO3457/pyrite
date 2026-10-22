**For plugin authors:** a `before_save` hook's changes no longer reach an
update's file. Create still persists the returned entry, a known implementation
gap, not a supported way to compute fields. Use hooks to refuse invalid writes;
derive computed values at read or index time under `derived`. The authoritative
lifecycle contract is `PyritePlugin.get_hooks` in `pyrite/plugins/protocol.py`.
