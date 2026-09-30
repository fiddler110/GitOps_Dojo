**How to read it.** Points are the defaults (milestone 10, funny 0, challenge 100, capstone 300, all settable in
`.env`). `core` means the milestone counts toward the certificate (80% of the `core` set). Triggers (the *When*
column) name where the event comes from:

- `shell:` the student ran this command and it exited as stated (shell hook; the command and the branch are logged)
- `forgejo:` a Forgejo webhook event for that student
- `dns:`, `ca:`, `cloud:`, `bao:` an audit or activity line from that service, read by the module that owns it
- `verify:` the achievements service checks the end state (verifiers, run by `dojo-check` or after an event)

`{user}` is the student's login (`student07`). Jokes are the toast text.

**Funny unlocks are worth nothing on purpose.** They never move the score; a student sees each one they earned, and
what they did to earn it, in their own "Moments" table on the landing page. Cheating is the only thing that subtracts
(at most 1 point).

**Every lab is mandatory**, so every lab milestone is `core`. Challenges, the capstone and the funny unlocks are
bonuses and never count toward completion. The shared cheating and "bumped into your neighbour" unlocks live with the
module, not in a workshop.
