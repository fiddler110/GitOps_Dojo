# ctf-secrets-config

Seeded into Forgejo as `training/ctf-secrets-config` because every workshop pack seeds a repo. This is
**not** the same thing as your own `<student>/internal-tools` repo -- that one is provisioned separately
for Lab 2's `git-secrets` target (see `~/lab/lab2.md`) and holds the actual exercise. This repo is just
the engagement brief, mirrored for anyone who wants it in git form.

If you want the engagement brief in a form you can `git clone` and read offline, it's here. The real
brief -- the scenario, the rules of engagement, and how the Attack Range card works -- is in the slides
(`presentation.md`) and `~/lab/README.md`; this file just mirrors the short version.

## The engagement, in short

Brightwave Ops and Forgeline Deploy asked for an assessment of two systems before they go further into
production: an internal ops dashboard, and a deploy-trigger service whose only credential lives in a git
repo's history. Scope is your own slot only, and these techniques are only legal against systems you own
or are explicitly authorized to test.
