# Setup — Your Own GitHub Repo for DNS-as-Code Practice

Same idea as [Git Fundamentals' setup guide](../git-fundamentals/00-github-setup.md):
the workshop ran against a local Forgejo server that only existed for the
session. To keep practicing, you'll use a free **GitHub.com** repo
instead — the git side of the workflow (clone, branch, commit, push, PR)
is identical either way.

If you already did the Git Fundamentals setup and have Git/GitHub
configured, skip to step 3 — you just need a second repo.

---

## 1. Create a free GitHub account (if you don't have one)

<https://github.com/signup> — free, no credit card required.

## 2. Install Git locally, set your identity

```sh
git --version   # installed? if not, see git-fundamentals/00-github-setup.md
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Optional but recommended: install the [GitHub CLI](https://cli.github.com/)
and run `gh auth login` once — it makes both plain `git push` and
`dnsctl.py`'s pull-request commands (Lab 3+) work without repeated
password prompts.

---

## 3. Create your DNS-as-code practice repository

### Option A — GitHub CLI

```sh
gh repo create dns-as-code-practice --private --clone
cd dns-as-code-practice
```

### Option B — GitHub web UI

1. <https://github.com/new> → name it `dns-as-code-practice` (any name
   works) → **Public** or **Private**, your choice.
2. Leave "Initialize with a README" **unchecked**.
3. Create it, then clone the URL it gives you:
   ```sh
   git clone https://github.com/<your-username>/dns-as-code-practice.git
   cd dns-as-code-practice
   ```

---

## 4. Next: pick your DNS backend

An empty repo isn't useful yet — you need something for `dnsconfig.js` to
actually manage. Pick one:

- **[01-local-powerdns-stack.md](01-local-powerdns-stack.md)** — free,
  local, uses the same `dojo.test` reserved test zone from the workshop.
  **Recommended** — do this first, regardless of whether you also want
  the real-domain path later.
- **[02-cloudflare-domain-setup.md](02-cloudflare-domain-setup.md)** —
  a real, purchased domain on a real Cloudflare account. More involved,
  costs a small amount of money, entirely optional.

Either one walks you through copying this handout's `starter-repo/`
content into the repo you just created, and gets you to the point where
[lab1.md](lab1.md) is ready to go.
