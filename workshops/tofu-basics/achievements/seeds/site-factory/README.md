# Capstone: Site Factory

Build, in this repo, a layout that deploys **two** differently named sites from one `for_each`
(`main.tf`, plus `variables.tf`, `outputs.tf` as you like):

- each site's name is `ci-{user}-<key>` (Dojo Cloud refuses a container group name that doesn't start with `ci-`)
  and its DNS label is `{user}-<key>`
- every site carries the tags `owner`, `env` and `challenge=capstone`
- an `output` maps each site name to its URL

Apply it, push to `main` (the check reads `main.tf` from `main`), run `dojo-check capstone` while the sites run, then
`tofu destroy` so nothing is left running. Needs 2 free container groups: finish Lab 10 first, and destroy any c1 or
c2 sites still running.
