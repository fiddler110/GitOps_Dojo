# ctf-defend pilot checklist (2-3 people)

One-page runbook for tuning the three-target defend lab before a class. Settings are in
`workshops/ctf-defend/workshop.env`; the design is in `docs/CTF-WORKSHOP-PLAN.md` (8.13).

## Set up

- `./dojo ctf-defend` with real time (`CTF_TIME_SCALE=1`, dwell 480 s, stagger 0.5), no `--fast`.
- The facilitator must press start (`POST /achievements-admin/api/soc/start`, or the SOC tab's start
  control): the attacker-bot idles until then.
- 2-3 people, each on a different attack order. Check with `GET /schedule` that they got different rows
  (set `CTF_SCHEDULE_SEED` to make the run repeatable).
- Give them only the lab URL and the pack's README. No coaching during the run.

## Watch and record

| what | where | write down |
|---|---|---|
| time from first alert to first fix attempt | SIEM panel, repo PRs | per target, per person |
| which signal they found first | what they say aloud, SIEM filter use | any signal nobody found |
| fix PR outcomes | `dojo-check`, PR gate note | `broke-normal-use` count, retries |
| time contained vs `start_offset_s` | wall rows | targets still red at the end |
| stuck points | your notes | needed a hint? which fact was missing from the lab text |

## Decide

- **Stagger:** start near half the median time to contain. If people finish the first target before the second starts,
  the pile-up never happens: lower it. If all three are open and nobody has a first fix, raise it.
- **Dwell:** the window must fit detect, triage, fix, PR, merge, verify at the slowest person's pace plus a margin.
- **Weights 3/2/1:** only change if the ranking is dominated by the order a person drew.
- **Discoverability:** any fact someone could only learn from a hint or from you is a lab defect (CLAUDE.md rule); fix
  the text or the target page, not the hint.
- **Gate:** note any case where `/gate` and `dojo-check` disagree for the same code.

## After

- Put the numbers in the plan (8.13) and ROADMAP row 1; change `CTF_TARGET_STAGGER` / `CTF_DWELL_S` only through
  `workshop.env`, then re-run one person through once.
- `./dojo stop` when finished.
