# Challenge c1: Tag Team

Deploy a second site named `{user}-second` that passes every Dojo Cloud policy, and add an
`output "url"` that prints its URL. Needs 1 free container group (destroy an old site first if
the quota says no). This folder has its own state; everything it creates is tagged `challenge=c1`.

When it runs, commit and push `main.tf` to this repo (`git push origin main`), then run `dojo-check c1`.
