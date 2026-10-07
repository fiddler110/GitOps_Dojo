# ctf-server-trust

Seeded into Forgejo as `training/ctf-server-trust` because every workshop pack seeds a repo, but **this
session's labs don't use it** -- there's no git exercise in CTF-2 (see the engine's bootstrap).

If you want the engagement brief in a form you can `git clone` and read offline, it's here. The real
brief -- the scenario, the rules of engagement, and how the Attack Range card works -- is in the slides
(`presentation.md`) and `~/lab/README.md`; this file just mirrors the short version.

## The engagement, in short

Glasswing Systems asked for an assessment of four systems before they go further into production: a
network diagnostics page, a URL preview feature, an accounts API, and an internal ops API -- each one
trusting something (input, a destination, a request body, a login) a little more than it should. Scope is
your own slot only, and these techniques are only legal against systems you own or are explicitly
authorized to test.
