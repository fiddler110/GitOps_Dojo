# cert-autorenewal: achievements catalog (DRAFT for review)

Nothing here is built. Same format and rules as `workshops/git-fundamentals/ACHIEVEMENTS.md` (read its "How to read
it" first). Points are the defaults (milestone 10, funny 5, challenge 100, capstone 300, all settable in `.env`);
`core` counts toward the certificate (80% of the `core` set). Triggers: `shell:`, `verify:` (end state on demo-app / the CA), `ca:` (event from the CA log), `dns:` (dns-gate lines).

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

### C1: The Second Site (after Lab 2 or 3)
- **Goal:** "Give `{user}-shop.demo` its own trusted certificate, using either tool, without touching the first site."
- **Verify:** demo-app serves a valid chain for that hostname; the first site's cert serial is unchanged.
- **Hint 1:** "Same steps as your first site, new hostname." **Hint 2:** "New vhost, new issuance, new install."

### C2: The Short Fuse (after Lab 4)
- **Goal:** "The CA now issues certificates that last 10 minutes. Make `{user}.demo` renew on its own and stay valid
  for 20 minutes without you touching it."
- **Verify:** the served serial changes at least once within the window, and never presents an expired cert.
- **Hint 1:** "Cron runs at most once a minute." **Hint 2:** "`renew` only acts when the cert is close to expiry."

## Capstone (300 points): The Wildcard Heist (a friendly one)
- **Goal:** "Issue a wildcard certificate for `*.{user}.demo` using dns-01, install it on two different vhosts, and set
  up renewal that works for both."
- **Seed:** two extra vhosts per student on demo-app; the DNS pipeline from Lab 5.
- **Verify:** both vhosts serve the same wildcard serial; renewal entry exists; a forced renewal updates both.
- **Hints:** (1) "A wildcard only works through DNS." (2) "One cert file, two vhosts, one reload."
- **Badge tier:** capstone (stars).

## Rough totals

Core ~180 · funny up to 25 · challenges 200 · capstone 300 · plus bonuses. About 705.
