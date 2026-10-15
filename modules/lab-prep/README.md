# lab-prep

Installs `/usr/local/lib/dojo/lab-prep-lib.sh` in the terminal image. A workshop's own
`compose/terminal/lab-prep` sets `LAST_LAB` (and `MIN_LAB` when its first lab is 1), defines
`usage()`, sources the library and calls `lab_arg "$@"`; the library supplies `say`, `done_`,
`run`, `die` and the lab-number check. List it in `MODULES=`.
