# Student guide

You need a browser. That is all. There is nothing to install, no account to create and no setup to debug. Your
facilitator gives you one web address and a class sign-in (usually on a slide).

## 1. Getting in

1. Open the address you were given.
2. Sign in with the **class username and password** shown by your facilitator. Everyone in the room uses the same one.
3. Type your **name** when asked. The lab gives you the next free account, such as `student07`, and shows you a
   page that says so. That account is yours for the session: your own Linux user, your own Forgejo (git) account, and
   your own space in anything the workshop adds (a DNS zone, a cloud subscription, a vault namespace).
4. You never type another password. Your browser, your terminal and your git are already signed in as you.

> The class login proves you are in the class. Your **account** (`studentNN`) is what identifies *you*. If you close
> the tab and come back with the same browser, you get the same account.

If a page ever sends you back to the start screen ("Release"), your facilitator freed your seat. Open the address
again and you are reassigned (usually to the same account).

## 2. What you see

The landing page shows a card for each tool in this workshop. Every workshop has:

| Card | What it is |
|---|---|
| **VS Code** | A full code editor in your browser, with a terminal inside it (not in Zellij workshops) |
| **Terminal** | A shell in your own account, ready for the lab commands |
| **Forgejo** | The git server. Pull requests, reviews, branches. You arrive already signed in |
| **Slides** | The talk, the lab guides and the cheat sheet |

Some workshops add more cards: **Dojo Cloud** (a practice cloud portal), **DNS Zones** (a live view of DNS
records), **Site Inspector**, **Vault**, **Runners**-style status pages, **Lab Info** (tool primers), **Attack
Range** (CTF targets) and so on. If achievements are on you also see a score and a leaderboard.

### Two ways to work

- **Split mode** (the default landing page): open each tool in its own tab.
- **Workspace** (the **Open workspace** card): one tabbed page with **Labs**, **VS Code**, **Terminal**, **Forgejo**,
  **Slides** and a tab for every extra card, each loaded the first time you click it. Your choice is remembered. Add
  `?split` to the address to get back to the landing page.

### Which terminal you have

Most classes give you **VS Code plus a tmux terminal**. Some give you a terminal-only **Zellij** workspace (a file
list on the left, a shell, and a small editor called `micro`). Everything in the labs works in both. Guides for the
multiplexers are in your `~/lab`: `tmux-guide.md` (Ctrl+b then %, ", arrow keys) and `zellij-guide.md`.

Your terminal has **no internet** and no Docker. Every tool a lab needs is already installed. Inside the terminal,
the git server is `git-server:3000`, **not** `localhost`.

## 3. The lab loop

Your lab guides are in `~/lab` in the terminal and also readable in the browser (Slides → Labs). Open one with:

```sh
cd ~/lab
glow lab1.md        # a rendered view; or nano / batcat / open it in VS Code
```

In the browser's lab reader, commands that mention `studentXX` show your real account name.

A typical lab:

1. Read the step, run the commands in the terminal.
2. Look at the output. Labs show what you should see, and many include a **"You see | Cause / fix"** table for
   common errors.
3. Check yourself against the lab's checkpoints before moving on.

Keep **`cheat-sheet.md`** open in a second pane or tab: it lists every command used across the labs.

### Typical flow in a git-based workshop

```sh
git clone http://git-server:3000/ORG/REPO      # the lab tells you the exact address
cd REPO
git switch -c my-change
# edit files in VS Code or micro
git add -A && git commit -m "Describe why"
git push -u origin my-change
```

Then open **Forgejo** (the card) and open a pull request. Git is already signed in with your own token, so it never
asks for a password. If a push does ask for one, tell your facilitator.

### Joining late or coming back

Run `lab-prep N` in the terminal to set up whatever lab N needs from the earlier ones (git-fundamentals,
dns-as-code, cert-autorenewal, tofu-basics and cloud-policy-as-code have it; it is safe to run twice and never
undoes your work).

## 4. Getting help

| Need | Do |
|---|---|
| Understand an error you just saw | `sensei why` reads the last screen and explains the nearest known error |
| Find the answer in the lab text | `sensei ask "how do I undo a commit"` searches the lab guides (offline, never reveals challenge answers) |
| A human | `sensei hand "I am stuck on step 4"` raises your hand with your last screen attached; check replies with `sensei inbox` |
| Where am I? | `sensei check` lists your milestones for the current lab (workshops with a scoreboard) |
| A wedged terminal | Tell the facilitator; **Release** gives you a fresh process, **Reset** returns your account to the start |

Sensei is an offline helper, not an AI model. It will not hand you challenge solutions.

## 5. Practice pull requests and Sensei

In some workshops Sensei acts as a friendly reviewer:

- **git-fundamentals**: you add yourself to `roster/team.yaml` and open a PR. Sensei checks it, merges a good one with
  a comment, and tells you what is wrong with a bad one.
- **dns-as-code**: Sensei approves a clean one-record change (peer review is still practised: review a classmate's
  PR with `sensei review`, then `sensei approve`). **You merge your own PR.**

## 6. Achievements and challenges (when switched on)

- Points for milestones, a leaderboard on the landing page, and "achievement unlocked" toasts in the browser and
  terminal. Some are jokes. Nothing you type is stored; only whether a milestone was reached.
- End-of-lab **challenges** give a goal and no steps, in a space of your own. Start one with the button at the end of
  the lab (or `dojo-challenge start c1`), check it with `dojo-check c1`, and use `dojo-check hint c1` if you need a
  hint (hints cost points). Challenges are bonus points; they never count against finishing the workshop.
- Do not try to tamper with the scoring client or forge events. It costs points and is part of the joke.

## 7. Rules of the lab

- It is a **private practice environment**. DNS zones, certificates, cloud resources and secrets belong to the lab, so
  breaking things is part of learning.
- Your work is **not saved** after the session. `git push` to the lab's Forgejo is not a backup. If you want to keep
  something, copy it out before the facilitator ends the class.
- Stay inside your own account. Other students' processes and files are deliberately invisible to you.
- Offensive-security workshops (CTF series) have explicit rules of engagement on their first slide. Targets exist only
  inside the Attack Range.

## 8. Quick troubleshooting

| Symptom | Try |
|---|---|
| VS Code or terminal shows a blank or 502 page right after opening | Wait two seconds and reload; it starts on first use |
| "Reload window" after being away | Normal after a few minutes idle; reload |
| Sent back to the start screen | Your seat was released; open the address again |
| `git push` rejected | Check you cloned the repo the lab names, and `git remote -v` |
| Command not found | Tools are pre-installed; check the lab spelling, or run `sensei why` |
| Nothing responds | Ask the facilitator; they can see service health |
