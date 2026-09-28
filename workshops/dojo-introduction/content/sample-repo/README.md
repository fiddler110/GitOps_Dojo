# dojo-tour

The team's repository for the Dojo Introduction. It holds one small example for each part of the platform, so there is
something real to open in VS Code and run in the terminal.

| Folder | What it shows | Try |
| ------ | ------------- | --- |
| `.forgejo/workflows/` | CI on Forgejo Actions: a single-use runner takes the job | push a change, then open the repo's **Actions** tab |
| `dns/` | DNS as code: a zone declared in `dnsconfig.js` (offline; your live zone is `~/lab/my-zone`) | `cd dns && dnscontrol check` |
| `cloud/` | OpenTofu against Dojo Cloud, with no credentials in the files | `cd cloud && tofu init && tofu plan` |

No secrets live here. The vault, the certificate authority and the DNS server are shown from the terminal: see
`~/lab/tools-tour.md`.
