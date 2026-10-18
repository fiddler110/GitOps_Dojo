# ctf-defend pilot: tuning the stagger and dwell

The three-target defend lab ([`CTF-WORKSHOP-PLAN.md`](CTF-WORKSHOP-PLAN.md) 8.13) ships with a stagger of 0.5 x dwell
and a dwell of 480 s. Those are guesses. This pilot, with 2-3 real people, replaces them with numbers. Bots cannot do
it: they do not open fix PRs, so only people give a real time to fix.

## What you are tuning

| Setting | Default | Meaning |
|---|---|---|
| `CTF_DWELL_S` | 480 | Quiet time before a student's first target is attacked |
| `CTF_TARGET_STAGGER` | 0.5 | Gap between a student's targets, as a multiple of the dwell |

Too small a stagger and breaches pile up before anyone can fix the first (the point is some pile-up, not a drowning
student). Too large and the lab turns back into attack-then-next. The starting rule is **stagger interval = half the
median time to fix**.

## Run it

1. Pick 2-3 people who have not seen the lab. Tell them nothing beyond the workshop's own lab text.
2. Start at real time, no `--test`: `./dojo ctf-defend` (or `--env home` to use phones and laptops over the VPN).
   Leave `CTF_TIME_SCALE` unset.
3. Each person logs in as a student. The facilitator opens `/admin`, then Achievements, then **Start Attack Swarm**.
4. Let it run for the full timebox. Do not coach, but note by hand where each person got stuck.
5. When all three targets have been fixed or the timebox ends, save the state before stopping:

   ```bash
   curl -c jar --data-urlencode username=admin --data-urlencode password=... <base-url>/login
   curl -b jar <base-url>/achievements-admin/api/state > pilot-state.json
   ```

6. Summarise it:

   ```bash
   python3 -B -I workshops/ctf-defend/tools/pilot-report.py pilot-state.json            # --dwell N if you changed it
   ```

7. `./dojo stop`.

## Reading the report

- **Per target:** how many were hit, how many fixed, median / mean / slowest time to fix. A target nobody fixed means
  the hint ladder or the fix is too hard, not that the stagger is wrong.
- **Gaps between breaches:** the stagger as it actually happened for each student.
- **Peak unfixed:** the most breaches open at once. 2 is the intended pile-up; 3 means a student was fully underwater.
- **Suggested `CTF_TARGET_STAGGER`:** 0.5 x median fix time / dwell.

## Deciding

- If the median fix time is under about half the dwell, keep 0.5 and shorten `CTF_DWELL_S` instead.
- If people reached "peak unfixed 3" often and were still working on the first target, raise the stagger.
- With only 2-3 people the numbers are rough. Treat the suggestion as a better default, not a proof, and write
  the result into `workshops/ctf-defend/workshop.env` and the plan.
