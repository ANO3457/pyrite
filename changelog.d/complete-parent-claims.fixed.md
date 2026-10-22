- Task updates to `claimed` now share the refusal for parents whose subtasks are all resolved. The refusal gives an open-subtask creation command; after adding new work, ordinary claim succeeds.
- Parents at open whose children are all resolved can also record explicit done without a claim; this exception does not change plugin workflow defaults.

- Editing the title or body of an already-claimed parent remains allowed when its children finish; the claim refusal applies to entering `claimed` (#743, #832).
