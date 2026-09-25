# Team Training Roster

A simple git sandbox for self-paced practice after the **Git Fundamentals**
workshop. It's a low-stakes, relatable space to practice the core git
workflow: branching, committing, pushing, and opening a pull request —
against your own free GitHub repo this time, instead of the workshop's
Forgejo server.

## What's Here

- **`roster/team.yaml`** — A simple list of team members and their roles.
- **`README.md`** — This file.

## How To Contribute

Full step-by-step instructions are in [`../lab1.md`](../lab1.md) through
[`../lab5.md`](../lab5.md) in this handout. The short version:

```sh
git clone https://github.com/<your-username>/git-fundamentals-practice.git
cd git-fundamentals-practice
git checkout -b add-yourname
# edit roster/team.yaml
git add roster/team.yaml
git commit -m "Add Your Name to team roster"
git push -u origin add-yourname
```

Then open a pull request on GitHub — see [`../00-github-setup.md`](../00-github-setup.md)
if you haven't created the repo yet.
