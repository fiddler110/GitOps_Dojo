# cloud-policy-as-code: facilitator guide

The technical reference is [`README.md`](README.md). **Honest status:** built from a brief and checked piece by
piece (opa tests, conftest, `tofu validate`); not run end to end with bots or a room yet. Do the rehearsal.

## Before the session

1. `./run.sh setup` if there is no `.env`; set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`, `STUDENT_COUNT`.
2. `./run.sh cloud-policy-as-code`. Wait for **Forgejo**, **Terminals**, **Slides**, **Dojo Cloud** and the runner
   pool to go green in the `/admin` status strip. `tofu-mirror-init` runs once and exits (that is normal).
3. `./run.sh capacity cloud-policy-as-code --students 30`: Dojo Cloud's `cloud-host` is the big one.
4. **Rehearse as a student** in a private window: Labs 0-3 at least. Check that `lab-prep 0` saves four secrets and
   protects `main`, and that a PR's `Policy check` job runs and can merge when green.
5. Check the facilitator view: `/admin` has Roster, VS Code, Terminal, Forgejo, Slides and the Dojo Cloud tab (the
   **Policy** blade there shows every student's assignments and compliance).

## During

- **Say it first:** policy applies are slow (about 3.5 min), on purpose of the provider, not a hang. Students read the
  next section while it runs. If everyone applies at once in labs 3, 5, 6 and 7, expect Dojo Cloud to be busy.
- Watch for: students waiting 100 s and cancelling mid-apply (leaves a half-created definition: re-run apply); a
  definition they cannot delete (`PolicyDefinitionInUse`: delete the assignment first, the lesson of Lab 6);
  Lab 4's legacy RG, which stays non-compliant by design until Lab 8 waives it; CI queueing on the runner pool in
  Labs 11-12; a PR that will not merge because `pr.yml` is red (that is the point).
- Lagging student: `lab-prep N` brings them to the start of lab N. Its policy applies are slow too.
- Never delete a student's `terraform.tfstate`; ask for a **Purge** of their subscription in the Dojo Cloud tab instead.

## After

`./run.sh stop` wipes everything, including every deployed container and all policy objects.
