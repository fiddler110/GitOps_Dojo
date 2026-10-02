# Capstone: Site Factory

Build, in this repo, a layout that deploys **two** differently named sites from one `for_each`
(`main.tf`, plus `variables.tf`, `outputs.tf` as you like):

- names and DNS labels carry your username: `{user}-<key>`
- every site carries the tags `owner`, `env` and `challenge=capstone`
- an `output` maps each site name to its URL

Apply it, run `dojo-check capstone` while the sites run, push to `main`, then `tofu destroy` so nothing is left running.
Needs 2 free container groups: finish Lab 10 first.
