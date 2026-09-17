# Pre-Session Checklist for Attendees

**Session:** Git Fundamentals: What/Why/How + Hands-on Lab
**Date/Time:** [INSERT DATE & TIME]
**Duration:** 60 minutes (30 min tutorial + 30 min lab)

**Facilitator:** [YOUR NAME] | **Questions?** Reach out on Teams or email.

---

## Why We're Asking You to Prepare

This session includes a hands-on lab where you'll clone a repo, create a branch, commit changes, and open a pull request — all in real-time. A few minutes of setup now means we can jump right into the good stuff without waiting for installs. Do not clone the training repository during pre-work; the first lab activity starts with that clone.

**Estimated setup time:** 10-15 minutes. Do this 24 hours before the session if possible.

---

## Pre-Work Checklist

Complete **all items** below. If any step fails or you have trouble, **reply to this message or DM me** — I'm happy to help.

### 1. ✅ Verify Git is Installed

Open your terminal/command prompt and run:
```bash
git --version
```

**Expected output:** Something like `git version 2.42.0` (version number may differ).

**If it fails** ("command not found"):
- **Mac:** Install Homebrew (https://brew.sh), then `brew install git`
- **Windows:** Download from https://git-scm.com/download/win
- **Linux:** `sudo apt install git` (Ubuntu/Debian) or equivalent for your distro
- **Ask for help:** Reach out, and I can guide you or provide installation steps for your OS.

---

### 2. ✅ Configure Git (If You Haven't Already)

In your terminal, run:
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@company.com"
```

Verify it worked:
```bash
git config --global user.name
git config --global user.email
```

**Why?** Git needs to know who you are so your commits have your name on them.

---

### 3. ✅ Create/Verify Your Azure DevOps Account

You need an Azure DevOps account to access the sample repo and open pull requests.

- **If you have a Microsoft/corporate Entra ID account:** You may already have Azure DevOps access. Try visiting: `https://dev.azure.com/[YOUR_ORGANIZATION]` (ask your team for the organization URL).
- **If you don't have access yet:** Contact your team admin or IT to add you to the Azure DevOps project for this training.
- **Verify access:** Once added, you should be able to see the project and browse repos.

**Can't get access?** Let me know ASAP, and I can work with your admin to fast-track it before the session.

---

### 4. ✅ Verify Access to Azure Repos

The facilitator will provide the final sample repository URL. Verify that you
can open the repository in Azure DevOps and that your account has access. Do
not create a local clone yet; cloning is the first step of Lab 1.

#### Option A: Browser check

Open the repository URL in Azure DevOps and confirm that you can browse the
files. This is the preferred pre-work check.

#### Option B: HTTPS connectivity check

In your terminal:
```bash
git ls-remote https://dev.azure.com/[ORGANIZATION]/[PROJECT]/_git/sample-training-repo
```

Replace `[ORGANIZATION]` and `[PROJECT]` with your org/project (I'll send these before the session).

**Expected output:** A clean working tree message (no errors).

**If asked for credentials:** Use the credential method approved by your
organization, such as Git Credential Manager or an approved token flow. Do not
put passwords or tokens in a clone URL.

---

#### Option C: SSH (Advanced, Skip if the browser or HTTPS check works)

If your team uses SSH:
```bash
ssh -T git@ssh.dev.azure.com
```

**Expected output:** A welcome message from Azure DevOps.

**If it fails:** You may need to upload an SSH key to Azure DevOps. Ask your team for guidance, or stick with HTTPS (Option A).

---

### 5. ✅ Set Up Your Editor (Optional but Recommended)

We recommend **VS Code** for the lab, but any text editor works.

- **Have VS Code?** Great — open it and confirm it's working. No plugins needed.
- **Don't have VS Code?** Download from https://code.visualstudio.com (free).
- **Using something else (Sublime, Vim, Notepad, etc.)?** That's fine too — just make sure you can open and edit a YAML file.

---

### 6. ✅ Open Your Terminal/Command Prompt

Make sure you're comfortable with the basics:
- Opening a terminal (Terminal app on Mac, PowerShell on Windows, or Git Bash).
- Running commands and reading output.
- Navigating folders with `cd` and listing files with `ls` (Mac/Linux) or `dir` (Windows).

**Never used a terminal before?** No worries — I'll walk everyone through it. Just get comfortable with opening one.

---

## Troubleshooting

| Issue                                          | Fix                                                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `git --version` returns "command not found"    | Git not installed. See item 1 above.                                                             |
| Repository access check fails                  | Confirm the URL and Azure DevOps permissions with the facilitator. Do not clone during pre-work. |
| SSH key check fails                            | Use the browser or HTTPS check, or ask the facilitator for the approved authentication method.   |
| Clone works, but `git config` shows wrong name | Run the config commands again (item 2) with your correct name/email.                             |
| Can't find your Azure DevOps organization      | Ask your team for the organization URL or check email invites.                                   |
| Still stuck?                                   | DM or email me — I'm here to help, and setup issues are totally normal.                          |

---

## What to Bring to the Session

- Your laptop (with git and an editor installed).
- Headphones/mic (if joining remotely).
- A text editor open and ready.
- The cheat sheet I'll send you (or bring a notebook to jot down commands).
- Curiosity and a willingness to try! 😊

---

## What You'll Do in the Lab

Don't worry if you're not 100% comfortable with everything above — the lab is hands-on and I'll walk you through each step. Here's a preview:

1. **Clone** the sample repo (copy it to your machine).
2. **Create a branch** (your own independent copy to work on).
3. **Make a small change** (add yourself to a team roster file).
4. **Commit** your change (save it with a message).
5. **Push** your commit (send it to Azure Repos).
6. **Open a pull request** (ask for review in the Azure DevOps portal).
7. **See your change merged** (I'll demonstrate or merge yours live).

**You'll walk away knowing:** How to clone a repo, branch, commit, push, and open a PR — the entire everyday workflow. This is gold.

---

## Questions Before the Session?

- **Technical issues:** Send me a message on Teams or email.
- **General questions:** Feel free to ask during the session — no such thing as a dumb question.
- **Want to review the materials early?** I can send you the session plan and cheat sheet before the day.

---

**See you at the session! You've got this.** 🚀

---

**Quick Reference for the Setup Attempts Above:**

- **Terminal command to run:** `git --version`
- **Sample repo URL:** `https://dev.azure.com/[ORG]/[PROJECT]/_git/sample-training-repo`
- **Azure DevOps portal:** `https://dev.azure.com`
- **Facilitator contact:** [YOUR EMAIL] or Teams

