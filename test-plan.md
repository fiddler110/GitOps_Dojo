# tofu-basics — manual test plan (T9.4, T9.9)

Everything else in `workshops/tofu-basics/PLAN.md` is done and live-verified. These are the two
remaining items before P9 closes and M5 (release-ready) is reached. This file is scratch for running
them — results go back into `PLAN.md`, not here.

## 1. Get the lab up and running

```sh
cd engine
./run.sh setup            # first time only: creates engine/.env (needs PUBLIC_BASE_URL + GATEWAY_TOKEN)
./run.sh stop              # if anything from a previous run is still up
./run.sh tofu-basics       # build (first time: several minutes) and start
```

Open `http://localhost` (or whatever `PUBLIC_BASE_URL` is set to in `engine/.env`) in a real browser —
not curl, not the API directly.

- Facilitator workspace: `/admin` (VS Code, Terminal, Forgejo, Slides, Dojo Cloud tabs)
- Student landing page: the base URL, one tab per student session
- Portal (Dojo Cloud console): `/cloud/`

To add demo bot traffic alongside your own manual pass (optional, only stresses git — bots don't drive
tofu-basics itself):

```sh
./run.sh tofu-basics --test        # 3 bots
./run.sh tofu-basics --test 14     # N bots
```

When done for the day:

```sh
./run.sh stop              # wipes everything: all student state, all deployed containers, all volumes
```

## 2. T9.9 — Real-browser pass (solo)

Nothing below has been clicked through in an actual browser yet — the P6/P4 verification only drove
the portal through `/cloud/api` and cross-checked labels against `app.js` source.

### Track A (rebuild the image first if you haven't already)

- [ ] Lab 0 — Get the repo and take the tour
- [ ] Lab 1 — First run: `init`, `plan`, `apply`
- [ ] Lab 2 — Change a value and read the plan
- [ ] Lab 3 — Tear it down
- [ ] HCL syntax highlighting renders correctly in code-server (never checked visually — only that the
      extension is installed)

### Track B / portal (click, don't call the API)

- [ ] Lab 4 — Meet Dojo Cloud
- [ ] Lab 5 — Deploy hello
- [ ] Lab 6 — Break a policy on purpose (each policy error should read cleanly in the terminal)
- [ ] Lab 7 — Drift: when reality changes behind your back
- [ ] Lab 8 — Change types: in-place vs replace
- [ ] Lab 9 — Scale it: `for_each` and quotas
- [ ] Lab 10 — Clean up
- [ ] Portal: Add tag
- [ ] Portal: Save tags
- [ ] Portal: Delete dialog
- [ ] Portal: Browse (to the deployed `dojo/hello` site)
- [ ] Portal: Quota tile
- [ ] Portal: Refresh now
- [ ] Attention-tile text reads as `code: message` (fixed in `25a7176`, only offline-tested so far)

### Facilitator side (same coverage rule as students, from `/admin`)

- [ ] `/admin` → Slides tab renders in its iframe
- [ ] `/admin` → Dojo Cloud tab renders in its iframe
- [ ] `/admin` → Terminal, VS Code, Forgejo tabs still fine (regression check, not new)

## 3. T9.4 — Human dry-run (needs 3–5 people)

- [ ] Run 3–5 people through the workshop live, start to finish (decide up front whether they do Track A
      only, or A + B — full A+B is ~103 min per the lab README's own estimates)
- [ ] Note every point someone got confused, misread an instruction, or got stuck
- [ ] Time the actual walkthrough against the slide deck's talk timings (P7 flagged these as guesses,
      never measured against real people)
- [ ] Fix labs / slides / README based on what you find

## 4. After running these

Report back (pass/fail per section, plus any confusion points or bugs found) and `PLAN.md` gets
updated: T9.4 and T9.9 marked `[x]`, M5 closed, and this file can be deleted.
