# tofu-basics: achievements catalog (DRAFT for review)

Nothing here is built. Same format and rules as `workshops/git-fundamentals/ACHIEVEMENTS.md` (read its "How to read
it" first). Points are the defaults (milestone 10, funny 5, challenge 100, capstone 300, all settable in `.env`);
`core` counts toward the certificate (80% of the `core` set). Triggers: `shell:`, `cloud:` (Dojo Cloud Activity log, an event adapter on the dojo-cloud module), `verify:` (`resource_state`).

**Every lab is mandatory**, so every lab milestone is `core`. Challenges, the capstone and funny unlocks are bonuses and
never count toward completion. The shared cheating and "bumped into your neighbour" unlocks live with the module.

**Both tracks are mandatory** (decided): Track A (labs 0-3) and Track B (labs 4-10) are one workshop, so every lab
milestone is core.

## Lab 0: repo and tour

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t0-fork | Forked Over | "Your own copy of the starter repo." | 10 | yes | forgejo: fork created |
| t0-clone | Cloned Around | "Now it is on your machine." | 10 | yes | shell: `git clone` of the fork |
| t0-tour | Is It Terraform? | "It is OpenTofu. Same thing. Mostly." | 10 | yes | shell: `tofu version` or `terraform version` |

## Lab 1: first run

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t1-init | Initialised | "Downloaded providers. Digital groceries." | 10 | yes | shell: `tofu init` (exit 0) |
| t1-validate | Syntax Approved | "The parser has no complaints." | 10 | yes | shell: `tofu validate` (exit 0) |
| t1-plan | Plan Before Act | "Previewed. Changed nothing. Wise." | 10 | yes | shell: `tofu plan` (exit 0) |
| t1-apply | It Is Alive | "First apply. Frankenstein noises." | 10 | yes | shell: `tofu apply` (exit 0) |

## Lab 2: change and read the plan

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t2-idem | Idempotent, Baby | "Applied twice, changed once." | 10 | yes | shell: second `tofu apply` reports 0 changes |
| t2-change | Tilde Time | "An in-place change, read carefully." | 10 | yes | shell: `tofu plan` shows `~` |
| t2-replace | Out With the Old | "Forced a replacement." | 10 | yes | shell: `tofu apply -replace=...` or plan `-/+` |
| t2-broke | Broke It On Purpose | "Errors are teachers." | 10 | yes | shell: `tofu validate` or `plan` exits 1 |

## Lab 3: tear it down

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t3-destroy | Scorched Earth | "Everything created is gone." | 10 | yes | shell: `tofu destroy` (exit 0) |
| t3-state | What the State Remembers | "Looked at what is left behind." | 10 | yes | shell: `tofu state list` or `ls terraform.tfstate*` |

## Lab 4: meet Dojo Cloud

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t4-portal | Cloud Tourist | "Opened the portal." | 10 | yes | cloud: first portal request by the student |
| t4-creds | Keys to the Kingdom | "Your credentials are in your environment." | 10 | yes | shell: `env` or `echo $ARM_*` (values are never logged) |
| t4-provider | Provider Installed | "azurerm, but a friendlier universe." | 10 | yes | shell: `tofu init` in the Track B folder (exit 0) |

## Lab 5: deploy hello

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t5-plan | Read the Blueprint | "A plan for a real container." | 10 | yes | shell: `tofu plan` in Track B |
| t5-apply | Hello, World | "A real container in a real (practice) cloud." | 10 | yes | cloud: container created; verify: `resource_state` running |
| t5-site | It Is on the Internet | "Opened your own site." | 10 | yes | cloud: request served by the student's container |

## Lab 6: policy

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t6-tag | Untagged and Rejected | "The cloud wants tags." | 10 | yes | cloud: policy denial for a missing tag |
| t6-region | Wrong Neighbourhood | "Region not allowed." | 10 | yes | cloud: policy denial for the region |
| t6-size | Too Big to Ship | "Over the size limit." | 10 | yes | cloud: policy denial for the size |

## Lab 7: drift

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t7-tag | Somebody Retagged It | "Drift noticed by `plan`." | 10 | yes | shell: `tofu plan` shows drift after a portal edit |
| t7-delete | It Vanished | "The container was deleted behind your back." | 10 | yes | cloud: activity log shows a delete by the student in the portal |
| t7-restored | Back in Business | "Apply restored the declared state." | 10 | yes | shell: `tofu apply` after drift (exit 0) |

## Lab 8: change types

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t8-inplace | Fix It In Place | "A tag changes without a rebuild." | 10 | yes | shell: `tofu apply` with `~` only |
| t8-replace | Rebuilt from Scratch | "The message forces a new container." | 10 | yes | shell: `tofu apply` with `-/+` |
| t8-forced | Because I Said So | "`-replace` on demand." | 10 | yes | shell: `tofu apply -replace=` |

## Lab 9: scale

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t9-foreach | One Block, Many Sites | "`for_each` made the copies." | 10 | yes | verify: 3+ containers from one resource block |
| t9-quota | Quota Reached | "You met the limit." | 10 | yes | cloud: quota denial for the student |
| t9-fixed | Code Meets Reality | "Reduced the code to what fits." | 10 | yes | shell: `tofu plan` reports no changes after the quota |

## Lab 10: clean up

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| t10-destroy | Leave No Trace | "Destroyed and verified." | 10 | yes | shell: `tofu destroy` (exit 0); verify: `resource_state` empty |
| t10-commit | Committed | "Your work is saved in git." | 10 | yes | forgejo: push from the student's fork after the destroy |

## Funny unlocks (5 points, any time)

| ID | Title | Joke | Pts | Trigger |
|---|---|---|---|---|
| f-nolock | Locked Out | "State lock in the way." | 5 | shell: `tofu` exits with an `Error acquiring the state lock` |
| f-typo | Fat Fingers | "A typo in a resource name." | 5 | shell: `tofu validate` exits 1 with `Reference to undeclared` |
| f-yes | Auto Approve Bravado | "`-auto-approve` on the first try." | 5 | shell: `tofu apply -auto-approve` |
| f-destroyfirst | Destroy First | "Ran `destroy` before anything was created." | 5 | shell: `tofu destroy` on empty state |
| f-statecommit | State in Git | "Committed `terraform.tfstate`. Lab 3 warned you." | 5 | forgejo: push containing `terraform.tfstate` |

## Challenges (100 points, no steps given)

### C1: Tag Team (after Lab 5 or 6)
- **Goal:** "Deploy a second site named `{user}-second` that passes every policy, with an output that prints its URL."
- **Verify:** `resource_state`: second container running, policy-compliant; an `output` named `url` in the state.
- **Hint 1:** "Copy your first site, and remember what the policy asked for." **Hint 2:** "Tags, region, size, and a new name."

### C2: Quota Whisperer (after Lab 9)
- **Goal:** "Your code declares 5 sites, the quota allows `{quota}`. Make the plan apply cleanly without touching the quota."
- **Seed:** a starter `main.tf` per student with a `for_each` over 5 names.
- **Verify:** `resource_state`: exactly the allowed count running, `plan` clean.
- **Hint 1:** "The error tells you the limit." **Hint 2:** "The list feeding `for_each` is what decides how many."

## Capstone (300 points): Site Factory
- **Goal:** "Build, from scratch, one module-like layout that deploys three differently named sites from one
  `for_each`, each with the required tags, an output map of names to URLs, then destroys cleanly and shows
  an empty cloud."
- **Verify:** three containers live; an output map with three URLs; after destroy, `resource_state` is empty; the code is
  pushed to the student's fork.
- **Hints:** (1) "Lab 9 plus Lab 10, in one go." (2) "`for_each` gives you `each.key`; outputs can use a `for` expression."
- **Badge tier:** capstone (stars).

## Rough totals

Core ~330 (33 milestones) · funny up to 25 · challenges 200 · capstone 300 · plus bonuses. About 855.
