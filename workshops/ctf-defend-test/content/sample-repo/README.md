# customer-portal (master seed copy)

This is the **master seed copy** of target 14, `customer-portal` (`modules/ctf-range/targets/customer-portal/`),
pushed to `ctf-defend-test/customer-portal` by the standard bootstrap mechanism. It is not the repo the lab or
the defend pipeline actually use: `/etc/dojo/start.d/90-ctf-defend-test.sh` pushes this same source into each
student's own `<student>/customer-portal`, with the `CTF_FLAG`/`CTF_BUILD_TOKEN`/`CTF_CONTROL_TOKEN` secrets
and the `CTF_REGISTRY` Actions variable the `.forgejo/workflows/` already in this tree need -- so
`defend-main.yml`'s `github.repository_owner` lines up with a real `ctf-controller` slot (`student01`, …).

See `modules/ctf-range/targets/customer-portal/README.md` for the flaw and the fix.
