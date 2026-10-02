# Challenge c2: Quota Whisperer

`main.tf` declares 5 sites but your subscription only holds 2 container groups in total. Make
`tofu apply` succeed without asking for more quota. Every site is tagged `challenge=c2`; the free
quota depends on what you still run from the labs, so the count you end with doesn't need to be exact.

Commit and push `main.tf` to this repo (`git push origin main`), then run `dojo-check c2`.
