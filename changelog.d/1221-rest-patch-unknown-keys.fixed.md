- REST `PATCH /api/entries/{id}` refuses undeclared body keys with 400
  `VALIDATION_FAILED` naming them, before writing anything (#1221). A misspelt
  `vaule` no longer silently writes null. An explicit `value: null` and the
  existing field operations remain supported.
