# Target 11 — `tfstate-treasure`

CTF-3 (plan §7.3 row 11, ties `tofu-basics` + `vault-fundamentals`). **No
image** — unlike every other attack-ladder target, the foothold here is
entirely in a Forgejo repo and an OpenBao policy, not a container in
`ctf-host`. This directory is docs + a reference exploit; the provisioning
itself lives in two hooks:

- `workshops/ctf-secrets-config/compose/openbao-setup.d/60-tfstate-treasure.sh`
  (openbao-setup, provisioner token): per student, a `tfstate-treasure-<user>`
  policy that reads exactly `secret/data/tfstate-treasure/<user>` and nothing
  else, an AppRole role bound to it, and the flag itself written to that path.
- `workshops/ctf-secrets-config/compose/terminal/start.d/95-tfstate-treasure.sh`
  (web-terminal): seeds each student's own `<user>/infra-state` Forgejo repo
  with a committed `terraform.tfstate` whose one resource is a
  `vault_approle_auth_backend_login` — the AppRole `role_id`/`secret_id`, in
  plaintext, exactly as a real tfstate would hold a leaked cloud credential.

## The flaw

A student's own OpenBao login (SSO through Forgejo, or the terminal's CLI
login) carries **no policy at all** in this pack — it can authenticate, and
nothing more. The *only* path to `secret/data/tfstate-treasure/<user>` is the
AppRole login whose `role_id`/`secret_id` sit in the committed
`terraform.tfstate` — state files are secrets too, and this one was never
moved to a remote backend.

Both hooks derive the same `role_id`/`secret_id` independently from
`STUDENT_PASSWORD_SEED` (the same HMAC-SHA256 formula as every flag/token in
this range, `flags.py`'s `render()`, minus the `flag{...}` wrapper) — two
copies, not shared code, the same idiom `git-secrets`' `CTF_TARGET_TOKEN`
uses. `60-tfstate-treasure.sh` runs in the openbao module's own Alpine image,
which has no python3/openssl, so that hook does the HMAC by hand with
`sha256sum`; checked against RFC 4231's test vector before being trusted for
a real flag.

## Escalation

1. Clone (or read through the API) `<user>/infra-state` from Forgejo.
2. Read `role_id`/`secret_id` out of `terraform.tfstate`.
3. `POST /v1/auth/approle/login` on OpenBao with them → a Vault token scoped
   to the `tfstate-treasure-<user>` policy.
4. `GET /v1/secret/data/tfstate-treasure/<user>` with that token → the flag.

## Debrief: the breach is visible after the fact, not during

This target has no live defend loop — the lesson is detection, not patching.
The facilitator's `/admin` **Vault Audit** tab (`modules/openbao`) shows the
AppRole login and the subsequent read in `students`' namespace's audit trail
(OpenBao's file audit device is always on, `modules/openbao/config.hcl`), the
same shape the plan's A09 lesson uses room-wide (CTF-5's SOC feed).

## Verify

Run from inside the student's own terminal account — both `git-server` and
`openbao` are reachable directly there (`workshop_lab`), the same way every
other lab/exploit in this range reaches its targets; there is no image here
to `docker run`.

```sh
python3 exploit/solve.py --repo student01/infra-state --user student01
```

Reads `terraform.tfstate` from Forgejo's API (default
`http://git-server:3000`), extracts `role_id`/`secret_id`, logs in to
OpenBao's AppRole auth method (default `http://openbao:8200`), and reads
`secret/data/tfstate-treasure/<user>`; checks for the flag.

## Files

- `exploit/solve.py` — reference clone-the-state-login-with-it solve.
