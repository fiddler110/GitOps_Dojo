# achievements module

Optional leaderboard, "achievement unlocked" toasts, end-of-lab challenges and a certificate over a workshop's labs (in progress: only the catalog core exists so far).

**Status.** Phase 1a of the plan in `ROADMAP.md` ("Achievements"): the catalog loader, validator and markdown generator.
There is no service, compose file or manifest yet, so no workshop lists this module and `MODULES="achievements"` does
nothing. The runtime comes in phase 2.

## The catalog

A workshop keeps its achievements as small data files beside its labs, so one joke, one lab or one challenge can be
edited without touching the rest:

```text
workshops/<name>/achievements/
  catalog.json          workshop id, title, intro text, lab list
  labs/lab1.json ...    one file per lab: its milestones
  funny.json            the workshop's funny unlocks
  challenges/c1.json .. one file per challenge
  capstone.json
  seeds/                (later) files the seed builders copy
modules/achievements/catalog/shared.json   cheating tiers and cross-workshop unlocks
```

- **Item** (a milestone or a funny unlock): `id`, `title`, `joke`, `when` (text for humans), `core` (milestones only),
  optional `points` (else the kind's default: milestone 10, funny 5, challenge 100, capstone 300), optional `note`,
  `retired`, and `match`, the structured trigger (`{"source": "shell", "cmd": "git commit", "exit": 0}`).
  An empty `match` is allowed for now and produces a warning: the item is listed but never fires.
- **Challenge and capstone:** `id` (`c1`, `c2`, ..., or `capstone`), `title`, `after`, `space` (the student's own space,
  must contain `{user}`), `goal`, `seed`, `verify_text`, `verify` (structured assertions, each mentioning `{user}`),
  exactly two `hints`, `answer`, `isolation` (how it avoids other students), `facilitator` (true only when a
  facilitator step is truly required), and `badge_tier: "capstone"` on the capstone.
- **Ids are forever.** Never rename or reuse one that a class may have earned. Retire it with `"retired": true`: it
  keeps its points for anyone who earned it and disappears for new classes.
- **The isolation rules** ("Rules for challenges and capstones" in every generated `ACHIEVEMENTS.md`, source
  `catalog/rules.md`) are enforced where they can be: a challenge without a per-student `space`, or with a `verify`
  assertion that never mentions `{user}`, is an error.

## Tools

Run from `modules/achievements/catalog/` (stdlib only, no stack needed):

| Command | What it does |
|---|---|
| `python3 -B render_md.py --all` | Regenerate every workshop's `ACHIEVEMENTS.md` from its JSON (the markdown is a review copy; never edit it) |
| `python3 -B render_md.py --all --check` | Exit 1 if a generated file is stale (the unit tests run this) |
| `python3 -B render_md.py workshops/<name>` | One workshop |
| `python3 -B -m unittest test_catalog` | The unit tests |

To change an achievement: edit its JSON, run `render_md.py --all`, commit both.
