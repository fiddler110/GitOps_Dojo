# Lab 8 — Secrets in the pipeline: Forgejo Actions secrets

**Goal:** give a CI job a secret the way most teams start: a **repository secret** in the CI system. Watch the log hide it, then see how little that hiding protects, and who can really read it.

Your jobs run on the class's **single-use runners**: each runner takes one job and is then thrown away.

**In this lab you will:**

1. Make your own copy (a fork) of the team's repo, and clone it.
2. Store a secret in the repo's CI settings.
3. Write a workflow that uses it, push, and read the job's log.
4. Print the secret in a form the log's mask doesn't catch.
5. Work out who can really read a repository secret, then clean up.

A **workflow** is a YAML file in `.forgejo/workflows/` that tells Forgejo Actions what to run, and when. Each push starts a **run**; each run has **jobs**, and each job has **steps**, shown one by one in the log.

---

## 1. Your own copy of the repo

The team's repo is `platform-team/vault-fundamentals`. Each of you works in your own **fork**, a copy under your account, so your pipelines and secrets are yours alone. This asks Forgejo's API to make the fork (`--netrc` signs in as you; `-d '{}'` sends an empty request body):

```bash
curl --netrc -H "Content-Type: application/json" -d '{}' \
  http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks
```

No password prompt: your terminal came with a Forgejo **access token** for your account, which `curl --netrc` reads from `~/.netrc` and git reads from `~/.git-credentials`. A block of JSON means it worked; `repository is already forked` means you made it earlier.

Clone it (download it into `~/lab/vault-fundamentals`):

```bash
cd ~/lab
git clone http://git-server:3000/$USER/vault-fundamentals.git
cd vault-fundamentals
```

The folder appears in VS Code's Explorer as **vault-fundamentals**.

A token in a plain-text file sounds like what this workshop warns against, so look at what makes it acceptable here. `ls -l ~/.netrc ~/.git-credentials` shows `-rw-------`: only you can read them. It's a token, not a password: limited to repositories, revocable on its own, and it can't sign in to the Forgejo web page. And the platform issued it (secret zero again, as in lab 0). For your own accounts, prefer a credential manager or git's in-memory `cache` helper.

## 2. Add a repository secret

In the browser, open the **Forgejo** card, then your fork (**studentXX/vault-fundamentals**) → **Settings** → **Actions** → **Secrets** → **Add secret**:

| Field | Value |
| ----- | ----- |
| Name | `DEMO_API_KEY` |
| Value | `demo-key-` followed by anything you like, e.g. `demo-key-blue-giraffe-42` |

Once saved, the value can't be shown again, not even to you. It's stored encrypted, and handed only to jobs.

## 3. A workflow that uses it

Make the folder Forgejo looks in for workflows:

```bash
mkdir -p .forgejo/workflows
```

In VS Code, create **vault-fundamentals → .forgejo → workflows → `secrets-demo.yml`**. Indentation matters in YAML: keep the spaces exactly as they are.

```yaml
name: secrets-demo
on: push
jobs:
  demo:
    runs-on: host
    steps:
      - name: Where does this job run?
        run: |
          echo "runner user: $(id -un)   home: $HOME"
          echo "processes this job can see: $(ls -d /proc/[0-9]* | wc -l)"
      - name: Use the secret
        env:
          API_KEY: ${{ secrets.DEMO_API_KEY }}
        run: |
          echo "The key is $API_KEY"
          echo "It is ${#API_KEY} characters long"
```

Read it top to bottom:

- `on: push`: run on every push, to any branch.
- `jobs: demo:`: one job, called `demo`. `runs-on: host` picks the class runners.
- **Where does this job run?**: prints the runner's Linux user and how many processes it can see. You'll use that in a moment.
- **Use the secret**: `env:` hands the step the secret as the environment variable `API_KEY`. `${{ secrets.DEMO_API_KEY }}` is filled in by Forgejo when the job starts; the file itself never holds the value. The step then prints it, and its length (`${#API_KEY}`).

Save it. Commit and push it; the push starts the workflow:

```bash
git add .forgejo/workflows/secrets-demo.yml
git commit -m "Add a workflow that uses a repository secret"
git push
```

`git push` signs in with your token; nothing to type.

Open your fork in Forgejo → **Actions** → the newest run → the **demo** job, and open each step.

- **"The key is \*\*\*"**: Forgejo replaces the secret's exact value with `***` in the log.
- **The runner user** is named like `pool-3f9a1c`. It was created for this job and deleted after it. Push again (`git commit --allow-empty -m again && git push`) and the next run gets a different one: nothing one job leaves behind reaches the next, not even another student's.
- **Processes this job can see**: only its own handful, although the runners share one machine.

## 4. Masking is not protection

Masking only matches the exact value. In VS Code, add one more step at the end of `secrets-demo.yml`, at the same indent as the other `- name:` lines, and save:

```yaml
      - name: Print it in a form the mask doesn't know
        env:
          API_KEY: ${{ secrets.DEMO_API_KEY }}
        run: |
          echo "$API_KEY" | base64
          echo "$API_KEY" | sed 's/./& /g'
```

It prints the key twice more: **base64-encoded** (a common way to turn any bytes into letters, not encryption), and with a space after every character (`sed 's/./& /g'`). Commit and push:

```bash
git commit -am "Show that masking is only cosmetic"
git push
```

In the new run, the last step shows both, unmasked. Decode it in your terminal (paste the base64 line from the log):

```bash
echo 'PASTE-THE-BASE64-LINE-HERE' | base64 -d
```

So **anyone who can change a workflow in this repo can read every one of its secrets**: a branch is enough, no review needed, because a push runs the workflow as the pusher wrote it. Masking stops accidents, not people.

## 5. Who can read a repository secret?

| Who | Can they get the secret? |
| --- | ------------------------ |
| Anyone with **write** access to the repo | **Yes**: push a branch with a changed workflow, as you just did. |
| A **pull request from a fork** (`on: pull_request`) | No: Forgejo gives those runs no secrets, because the fork's author wrote the workflow. |
| A workflow on `pull_request_target` | **Careful**: it runs the *base* repo's workflow *with* secrets. If it checks out and runs the pull request's code, that code gets the secrets. |
| Anyone who reads the **job log** | Only what a workflow printed: never print a secret, even masked. |

And the secret itself never changes by itself: it is valid until someone rotates it, however many people have had the chance to see it.

## 6. Clean up: rotate what leaked

The key is now in your job logs in two readable forms. In real life you'd **rotate it** at its source first (rule 7), then update the repository secret. Here, delete it: Forgejo → your fork → **Settings** → **Actions** → **Secrets** → **Remove** next to `DEMO_API_KEY`.

Then remove the demo workflow, so later pushes don't run it. `git rm` deletes the file and stages the deletion:

```bash
git rm .forgejo/workflows/secrets-demo.yml
git commit -m "Remove the secrets demo"
git push
```

## Check yourself

1. A job's log shows `***`. Is the secret safe? *(No: masking hides exact matches only. Any transformation, such as base64, prints it.)*
2. Who can read a repository secret? *(Anyone who can push a workflow to the repo, plus whoever reads a log that printed it.)*
3. Why does it matter that each runner is used for one job only? *(A job can leave files and processes behind. On a single-use runner, the next job, maybe someone else's, starts clean.)*

Lab 9 replaces the stored secret with the job's own identity.

**Rules used:** 8 (never in logs), 7 (plan for leaks: rotate), 1 (least privilege: who can push is who can read), 4 (the repository secret is this pipeline's secret zero).
