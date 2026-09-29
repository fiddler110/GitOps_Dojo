# cert-autorenewal: achievements catalog (DRAFT for review)

Nothing here is built. Same format and rules as `workshops/git-fundamentals/ACHIEVEMENTS.md` (read its "How to read
it" first). Points are the defaults (milestone 10, funny 5, challenge 100, capstone 300, all settable in `.env`);
`core` counts toward the certificate (80% of the `core` set). Triggers: `shell:`, `verify:` (end state on demo-app / the CA), `ca:` (event from the CA log), `dns:` (dns-gate lines).

**Challenges and the capstone follow the "Rules for challenges and capstones" in `workshops/git-fundamentals/ACHIEVEMENTS.md`.**
Here the shared pieces are the CA (`step-ca`), `demo-app` and the `certs.dojo.test` zone. A challenge changes only the
student's own vhost directory (`/srv/webroot/{user}/`) and names under `{user}.certs.dojo.test`, which is exactly what
the DNS gate's per-student key already allows. No challenge reconfigures the CA, nginx or the zone's shared records.
The student's hostname is `{user}.certs.dojo.test` (not `{user}.demo`, as an earlier draft said).

**Every lab is mandatory**, so every lab milestone is `core`. Challenges, the capstone and funny unlocks are bonuses and
never count toward completion. The shared cheating and "bumped into your neighbour" unlocks live with the module.

## Lab 1: trust the CA

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| c1-root | Root of All Trust | "You fetched the CA's root certificate." | 10 | yes | shell: `curl` or `wget` for the root cert (exit 0) |
| c1-fingerprint | Fingerprint Frisk | "Checked the fingerprint, like a suspicious bouncer." | 10 | yes | shell: `openssl x509 ... -fingerprint` |
| c1-trust | Now We Trust You | "The system trusts the CA. Do not tell your bank." | 10 | yes | verify: `curl https://ca...` works with no `-k` |
| c1-tools | Trust Issues, Resolved | "certbot and acme.sh trust it too, separately." | 10 | yes | verify: both tools' trust config points at the root |

## Lab 2: certbot

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| c2-vhost | Port 80 Open for Business | "Your vhost answers the challenge." | 10 | yes | verify: `http://{user}.demo/.well-known/` served |
| c2-issue | Certified Fresh | "A real cert, minted by machine." | 10 | yes | ca: certificate issued for `{user}.demo` |
| c2-install | Installed and Padlocked | "HTTPS on. Green padlock energy." | 10 | yes | verify: demo-app serves that certificate |
| c2-verify | Trust, Verified | "You checked the chain with your own eyes." | 10 | yes | shell: `openssl s_client` or `curl -v https://...` |

## Lab 3: acme.sh

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| c3-issue | Same Job, Different Tool | "acme.sh did it in one line." | 10 | yes | ca: second certificate issued to the same student |
| c3-read | Reading the Tea Leaves | "You read the tool's output." | 10 | yes | shell: `acme.sh --list` or `--info` |

## Lab 4: automate renewal

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| c4-script | Script Kiddie (Proud) | "A renewal script that reinstalls too." | 10 | yes | verify: script exists, executable, runs with exit 0 |
| c4-installs | It Actually Installs | "Renewed and reloaded the server." | 10 | yes | verify: demo-app serves a cert with a newer serial |
| c4-cron | Set It and Forget It | "Wired into cron." | 10 | yes | shell: `crontab` shows the renewal entry |
| c4-watch | Watched a Pot Boil | "You saw the renewal fire by itself." | 10 | yes | verify: renewal ran from cron (log entry not from a shell) |

## Lab 5: the dns-01 challenge

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| c5-start | Challenge Accepted | "Started a dns-01 issuance." | 10 | yes | ca: dns-01 order created for the student |
| c5-txt | Prove You Own It | "TXT record deployed via the DNS pipeline." | 10 | yes | dns: `_acme-challenge.{user}` TXT present |
| c5-done | Wildcard Energy | "Issued through DNS. No open ports needed." | 10 | yes | ca: dns-01 order valid |

## Funny unlocks (5 points, any time)

| ID | Title | Joke | Pts | Trigger |
|---|---|---|---|---|
| f-untrusted | Trust No One | "`certificate verify failed`. Correct instinct." | 5 | shell: `curl` exits 60 |
| f-ratelimit | Too Eager | "Rate-limited. Slow down, tiger." | 5 | ca: `rateLimited` response for the student |
| f-expired | Expired Milk | "You looked at an expired certificate." | 5 | shell: `openssl x509 -enddate` shows a past date |
| f-staging | Practice Makes Perfect | "Used `--staging` or `--test`. Wise." | 5 | shell: `certbot --dry-run` or `--staging` |
| f-selfsigned | Self-Signed and Proud | "You made your own CA. Very independent." | 5 | shell: `openssl req -x509 -newkey` |

## Challenges (100 points, no steps given)

At open, the service seeds one wildcard A record `*.{user}.certs.dojo.test` to `demo-app` (through the DNS gate, in the
student's own scope), so any new hostname the challenge needs already resolves. Verifiers read the student's own
vhost directory and the certificate `demo-app` serves for their own hostnames only.

### C1: The Second Site (after Lab 2 or 3)
- **Goal:** "Give `shop.{user}.certs.dojo.test` its own trusted certificate, using either tool, without touching the first site."
- **Verify:** `demo-app` serves a valid chain for that hostname (checked over SNI); the first site's cert serial is unchanged.
- **Hint 1:** "Same steps as your first site, new hostname." **Hint 2:** "New vhost, new issuance, new install."
- **Collision check:** a second vhost in the student's own subdirectory; issuance goes through the shared CA, which
  handles concurrent orders for different names.

### C2: The Short Fuse (after Lab 4)
- **Goal:** "Certificates from this CA only last 5-10 minutes. Make `{user}.certs.dojo.test` renew on its own and stay
  valid for 20 minutes without you touching it."
- **Verify:** the served serial for the student's hostname changes at least twice within the window, and it never
  presents an expired cert.
- **Hint 1:** "Cron runs at most once a minute." **Hint 2:** "`renew` only acts when the cert is close to expiry."
- **Changed from the draft:** it said "the CA now issues 10-minute certificates", which reads as reconfiguring the
  shared CA. Its short lifetime is already set for the whole class; the challenge only uses it.

## Capstone (300 points): The Wildcard Heist (a friendly one)
- **Goal:** "Issue a wildcard certificate for `*.{user}.certs.dojo.test` using dns-01, install it on two different
  vhosts (`www` and `api` under your name), and set up renewal that works for both."
- **Seed:** the wildcard A record above. The two vhosts are created by the student in their own directory. The DNS
  pipeline is Lab 5's, using the student's own key, so the `_acme-challenge.{user}.certs.dojo.test` TXT record is theirs alone.
- **Verify:** both vhosts serve the same wildcard serial; a renewal entry exists; a forced renewal updates both.
- **Hints:** (1) "A wildcard only works through DNS." (2) "One cert file, two vhosts, one reload."
- **Collision check:** the challenge TXT name is under the student's own parent, so two students issuing at once never
  overwrite each other's record.
- **Badge tier:** capstone (stars).

## Rough totals

Core ~180 · funny up to 25 · challenges 200 · capstone 300 · plus bonuses. About 705.
