# Azure DevOps Setup Guide — For Facilitators

This guide walks you through setting up a sample training repo in Azure DevOps and verifying attendee access.

---

## Prerequisites

- Access to an **Azure DevOps organization** (if you don't have one, create a free one at https://dev.azure.com).
- Permissions to **create a new Git repository** in a project.
- (Optional) Existing team project — or create one just for this training.

---

## Step 1: Create or Identify Your Project

### Option A: Use an Existing Project
If your organization already has an Azure DevOps project:
1. Go to `https://dev.azure.com/<your-organization>`
2. Select the project where you want the training repo.
3. Note the **project name** — you'll need it later.

### Option B: Create a New Project (Recommended for Training)
If you want an isolated space for training:
1. Go to `https://dev.azure.com/<your-organization>`
2. Click **+ New project**
3. Name it: `Git-Training` (or similar)
4. Visibility: **Private** (if you want to limit access) or **Public** (if training is org-wide)
5. Click **Create**

**Note the project name and URL for later.**

---

## Step 2: Create the Sample Repo in Azure Repos

1. Go to your project's **Repos** section (left menu).
2. Click **+ New repository** (top right).
3. **Repository name:** `sample-training-repo` (matches the name of the `sample-training-repo/` folder alongside this guide).
4. **Type:** Git
5. Click **Create**

---

## Step 3: Seed the Repo with Files

Your new Azure Repos repository is empty. We need to add the files from `sample-training-repo/` (alongside this guide) in this training repository.

### Option A: Clone, Add Files, Push (Command Line)
```bash
# Clone the empty repo
git clone https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo
cd sample-training-repo

# Create the directory structure
mkdir roster

# Create files (copy from the training repo, or create manually):

# 1. README.md
cat > README.md << 'EOF'
# Team Training Roster
...
EOF

# 2. CONTRIBUTING.md
cat > CONTRIBUTING.md << 'EOF'
# How to Contribute
...
EOF

# 3. roster/team.yaml
cat > roster/team.yaml << 'EOF'
# Team Roster
...
EOF

# Add, commit, push
git add .
git commit -m "Initial training repo setup"
git push -u origin main
```

**Easier way:** Copy the files from `sample-training-repo/` (alongside this guide) directly into your Azure Repos repo (manually via the portal or via your local clone).

### Option B: Upload via Azure DevOps Portal
1. In your Azure Repos repo (in the portal), click **Upload files**.
2. Drag or select the files from `sample-training-repo/` (alongside this guide):
   - `README.md`
   - `CONTRIBUTING.md`
   - Create folder `roster/`, then add `team.yaml`
3. Commit with message: "Initial training repo setup"

---

## Step 4: Verify the Repo Structure

In Azure DevOps portal, your repo should look like:
```
📁 sample-training-repo/
  📄 README.md
  📄 CONTRIBUTING.md
  📁 roster/
    📄 team.yaml
```

If it looks good, the repo is ready!

---

## Step 5: Share Repo Access with Attendees

### Add Users to the Project

1. Go to **Project Settings** (bottom left).
2. Click **Members** (left menu).
3. Click **+ Add members**.
4. Enter attendee email addresses (one per line or comma-separated).
5. Choose role: **Member** (standard; can commit) or **Reader** (view-only, not useful for this training).
6. Click **Add**.

Azure DevOps will send invites to attendees.

### Verify They Can Access

Ask an attendee to:
1. Go to `https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo`
2. They should see the repo and be able to clone it.

---

## Step 6: Generate the Repo Clone URL

You'll need to provide attendees with the clone URL in the pre-work checklist and during the session.

**HTTPS URL format:**
```
https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo
```

**SSH URL format (if using SSH keys):**
```
git@ssh.dev.azure.com:v3/<ORG>/<PROJECT>/sample-training-repo
```

Replace:
- `<ORG>` — Your Azure DevOps organization name
- `<PROJECT>` — Your project name (e.g., `Git-Training`)

**Find the exact URL in Azure DevOps:**
1. Go to the repo in the portal.
2. Click **Clone** (top right).
3. Copy the HTTPS or SSH URL.

---

## Step 7: Test the Repo (Facilitator Only)

Before the session, verify you can:

1. **Clone the repo:**
   ```bash
   git clone https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo
   cd sample-training-repo
   ```

2. **Create a test branch:**
   ```bash
   git checkout -b test-branch
   echo "test" > test.txt
   git add test.txt
   git commit -m "Test commit"
   git push -u origin test-branch
   ```

3. **Open a Pull Request in the portal:**
   - Go to **Repos → Pull Requests** in Azure DevOps.
   - Click **New pull request**.
   - Source: `test-branch`, Target: `main`.
   - Click **Create**.
   - Review the PR (it should show your test file).
   - Click **Complete** to merge.
   - Delete the branch.

4. **Verify the merge:**
   - Go back to `main`.
   - Check out main locally: `git checkout main`
   - Pull the changes: `git pull`
   - Verify `test.txt` is in the repo.

---

## Step 8: Update Documentation with Repo Details

Before sending the pre-work checklist to attendees, fill in these details:

**In [pre-work-checklist.md](pre-work-checklist.md):**
- Replace `[ORGANIZATION]` with your Azure DevOps org name.
- Replace `[PROJECT]` with your project name.
- Replace `[YOUR NAME]` with your name.
- Replace `[YOUR EMAIL]` with your email.

**In [facilitator-guide.md](facilitator-guide.md):**
- Add your repo URL to the "Pre-Session Checklist" section.

**Example:**
```
Organization: contoso-engineering
Project: Git-Training
Repo URL: https://dev.azure.com/contoso-engineering/Git-Training/_git/sample-training-repo
```

---

## Step 9: Verify the Default Branch Policy

The organization's Azure DevOps environment protects `main` by default. Verify
that the sample repository inherits the expected policy before the session:

1. Go to **Repos → Branches** in Azure DevOps.
2. Find `main` and click **...** → **Branch policies**.
3. Enable:
   - **Require a minimum number of reviewers** (set to 1 for training).
   - **Require comment resolution** (good practice).
   - **Build validation** (optional, skip if no CI/CD set up).
4. If the policy is not inherited, ask the project administrator to apply the
   organization's default rather than weakening the lab workflow.

**Effect:** During the lab, attendees can push branches, but merging will require approval (demonstrating code review).

## Contingency: Temporary Self-Hosted Git Service

Azure DevOps should remain the default path because it matches the team's real
workflow. If one or more attendees cannot receive Azure DevOps access in time,
the facilitator can provide a temporary **Gitea** instance as a fallback. Gitea
is a good fit for this lab because it is lightweight, supports standard Git
clone/push operations, and provides repositories, users, and pull requests
without requiring a full production platform.

Use this only as a separate lab environment:

1. Run Gitea on a facilitator-controlled laptop, VM, or internal container host.
2. Create one temporary organization and private training repository.
3. Create attendee accounts or a controlled temporary account per participant.
4. Import the same sample repo and configure the default branch as `main`.
5. Require pull requests for `main` and provide the temporary HTTPS clone URL.
6. Test the complete flow from an attendee device before the session.
7. Remove the instance, accounts, and repository after the training window.

Do not ask attendees to install or host Gitea individually. The fallback should
preserve the Git learning objectives, but the portal screenshots and exact PR
labels will differ from Azure DevOps. Attendees using the fallback should still
follow the same Lab 1 commands and use the Gitea web UI only for the pull
request step.

For a larger or longer-lived disconnected environment, GitLab Community Edition
is another option, but it has a larger operational footprint than this session
needs. A hosted temporary repository is preferable when organizational policy
allows it.

---

## Step 10: Communicate with Attendees

### Pre-Session (24 hours before)

Send attendees:
1. **Pre-work checklist** ([pre-work-checklist.md](pre-work-checklist.md)) — with repo URL filled in.
2. **Cheat sheet** ([cheat-sheet.md](cheat-sheet.md)) — for reference.
3. **Session details:** Time, Zoom/Teams link, duration (~60 min).

### During Session

- Share the repo URL in chat (ready to paste).
- Remind attendees to clone from the URL in the pre-work checklist.

### After Session

- Post the recording (if recorded).
- Post the cheat sheet and facilitator notes (for follow-up).
- Mention Session 2 date/time.

---

## Troubleshooting

| Issue                                   | Fix                                                                                      |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| Attendee can't clone — "Repo not found" | Verify they're added to the project (Members). Give them 5 mins to accept the invite.    |
| Attendee can't open a PR                | Branch not pushed yet. Remind them: `git push -u origin <branch-name>`.                  |
| PR doesn't show up in portal            | Wait 5-10 seconds and refresh the browser. Azure DevOps can be slightly laggy.           |
| "SSL: CERTIFICATE_VERIFY_FAILED"        | Corporate firewall. Advise HTTPS clone URL or ask IT for SSH key setup.                  |
| Can't merge because branch policies     | This is expected (you set it up in Step 9). You (facilitator) approve & merge as a demo. |
| Attendee's PR shows merge conflicts     | This is the conflict demo from the lab! Walk them through resolving it together.         |

---

## Azure DevOps Portal Quick Reference

**Key URLs for the session:**
- **Your org:** `https://dev.azure.com/<ORG>`
- **Your project:** `https://dev.azure.com/<ORG>/<PROJECT>`
- **Your repo:** `https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo`
- **Pull Requests:** `https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo/pullrequests`
- **Branches:** `https://dev.azure.com/<ORG>/<PROJECT>/_git/sample-training-repo/branches`

---

## Tips for Facilitator During Lab

- Have the **Pull Requests** tab open in Azure DevOps during the lab so you can see attendee PRs in real-time.
- When showing a live demo of merging, use the portal to show the PR, review, and click **Complete**.
- Point out the branch graph in the portal — it visually shows the workflow attendees just did.

---

## After Session 1

- Archive the training repo or delete attendee branches.
- Consider creating a fresh repo for the next session or reusing the same one.
- Collect feedback on the setup process (was cloning easy? Did anyone struggle?).

---

## Further Help

- **Azure DevOps Docs:** https://learn.microsoft.com/en-us/azure/devops/repos/
- **Azure Repos Git:** https://learn.microsoft.com/en-us/azure/devops/repos/git/
- **Pull Requests in Azure DevOps:** https://learn.microsoft.com/en-us/azure/devops/repos/git/pull-requests-overview

