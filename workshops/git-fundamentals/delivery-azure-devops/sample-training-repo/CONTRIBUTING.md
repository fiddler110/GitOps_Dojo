# How to Contribute

This is a hands-on sandbox for practicing git. Follow these steps to add yourself to the team roster and complete the training lab.

## Steps

### 1. Clone the repo
```bash
git clone <this-repo-url>
cd sample-training-repo
```

### 2. Create your branch
```bash
git checkout -b add-yourname
```
*(Replace `yourname` with your actual name, e.g., `add-alice`, `add-bob`)*

### 3. Edit the roster
Open `roster/team.yaml` and add a new line with your information:
```yaml
- name: Your Name
  role: Your Role (e.g., Engineer, Ops, etc.)
```

### 4. Check what changed
```bash
git status
git diff
```

### 5. Stage and commit
```bash
git add roster/team.yaml
git commit -m "Add [Your Name] to team roster"
```

### 6. Push your branch
```bash
git push -u origin add-yourname
```
Replace `add-yourname` with the branch name you created above.

### 7. Open a pull request
- Go to the repository in Azure DevOps.
- You'll see a prompt to open a pull request for your branch.
- Click **Create Pull Request** and add a brief comment (optional).

### 8. Wait for review & merge
The facilitator will review your PR and merge it during or after the session.

---

**That's it!** You've just completed the full git workflow: branch → edit → commit → push → pull request.

## Troubleshooting

- **Can't clone?** Check your git credentials and repository access.
- **Merge conflict?** The facilitator will walk through this in the session — don't panic!
- **Lost track of your changes?** Run `git status` and `git log` to see where you are.
- **Need to start over?** Ask the facilitator to reset your branch, and try again.

## Next Steps

Once this session is complete, check out the next sessions in the series to learn about branching workflows, team conventions, conflict handling, and automation.
