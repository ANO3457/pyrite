- Editing a KB's description or type through the API is refused when an
  operator defined that KB by hand in `config.yaml`: the change used to answer
  200 and revert on the next save or sync. Edit `config.yaml` and restart
  (`KB_DEFINED_IN_CONFIG`, #1116).
