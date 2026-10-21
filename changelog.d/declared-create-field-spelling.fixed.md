Field-based creates now write KB-schema-declared fields at their canonical
top-level spelling for typed entries too, including fields supplied through
`metadata`. The entry's metadata remains available to hooks; undeclared extras
and fields loaded from an existing file retain their existing spelling.
