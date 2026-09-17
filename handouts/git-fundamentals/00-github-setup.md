# Setup — Your Own GitHub Practice Repo

The workshop ran against a local Forgejo server that only existed for the
session. To keep practicing on your own, you'll do the exact same
clone → branch → edit → commit → push → pull request loop against a real,
free **GitHub.com** account instead. Nothing here costs money.

---

## 1. Create a free GitHub account

If you don't already have one: go to <https://github.com/signup> and
follow the prompts (email, username, password). The free plan covers
everything in these labs — unlimited public *and* private repositories,
no credit card required.

---

## 2. Install Git locally

You need a real terminal and Git on your own machine now — the workshop's
browser-based terminal isn't available anymore.

- **Windows:** install [Git for Windows](https://git-scm.com/download/win) —
  this also gives you "Git Bash," a terminal that behaves like the one you
  used in the workshop.
- **macOS:** run `git --version` in Terminal first — macOS often prompts
  you to install the Xcode Command Line Tools, which includes Git. Or
  `brew install git` if you use [Homebrew](https://brew.sh/).
- **Linux:** `sudo apt install git` (Debian/Ubuntu), `sudo dnf install git`
  (Fedora), or your distro's equivalent.

Verify it:

```sh
git --version
```

### Optional but recommended: the GitHub CLI (`gh`)

Makes signing in and creating repos a one-line command instead of a
browser trip. Install from <https://cli.github.com/>, then:

```sh
gh auth login
```

Follow the prompts (pick **GitHub.com**, **HTTPS**, and **Login with a web
browser** is the easiest path). This also quietly fixes authentication for
plain `git push`/`git pull` over HTTPS — you won't be prompted for a
password on every push.

If you'd rather not install `gh`, everything in these labs still works —
you'll just create the repo and open pull requests from github.com in your
browser instead of from the terminal, and you'll need to set up an SSH key
or a [personal access token](https://github.com/settings/tokens) the first
time you push (GitHub's own docs cover this well:
<https://docs.github.com/en/authentication>).

### The helper tools the workshop terminal had

`z`, `rg` (ripgrep), `batcat`/`bat`, and `glow` were preinstalled
conveniences in the workshop, not requirements. Everything in these labs
works fine with `cat`, `less`, or any text editor instead. If you want
them anyway: `brew install bat ripgrep glow zoxide` (macOS/Linuxbrew), or
your package manager's equivalent.

---

## 3. Set your git identity

The workshop pre-configured this for you. On your own machine, set it once:

```sh
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Use the same email as your GitHub account (or add it as a secondary email
in GitHub settings) so your commits show up correctly attributed to you.

---

## 4. Create your practice repository

Pick **one** of the two paths below.

### Option A — GitHub CLI (fastest)

```sh
gh repo create git-fundamentals-practice --private --clone
cd git-fundamentals-practice
```

`--private` just means only you can see it by default — either visibility
works fine for practice. `--clone` also clones it locally in one step, so
you're already inside it.

### Option B — GitHub web UI

1. Go to <https://github.com/new>.
2. Repository name: `git-fundamentals-practice` (any name works).
3. Choose **Public** or **Private** — either is fine.
4. Leave "Initialize this repository with a README" **unchecked** — you'll
   push the starter content yourself in the next step.
5. Click **Create repository**, then copy the HTTPS clone URL it shows you.
6. In your terminal:
   ```sh
   git clone https://github.com/<your-username>/git-fundamentals-practice.git
   cd git-fundamentals-practice
   ```

---

## 5. Add the starter content

Copy the files from this handout's [`starter-repo/`](starter-repo/)
folder into your freshly cloned repo (same `roster/team.yaml` +
`README.md` you'd have found in the workshop's sample repo), then push
them to `main`:

```sh
# from inside your cloned git-fundamentals-practice/ folder
cp -r /path/to/handouts/git-fundamentals/starter-repo/. .

git add .
git commit -m "Initial roster"
git push -u origin main
```

(If you used Option B without a README, `main` doesn't exist on the
remote yet — this first push creates it.)

---

## You're ready

Open [`lab1.md`](lab1.md) and start the same core workflow you practiced
in the workshop — clone is already done, so pick up from **Create a
branch**.
