# Lab 2 — Keep it encrypted on your own machine

**Goal:** keep secrets encrypted on your own machine with `pass`, see how its store is laid out (the same shape a vault uses), and find where it stops working for a team.

Lab 1 showed that a secret in a file ends up in git. A git-ignored `.env` is better, but it's still plain text: in backups, in `grep -r`, readable by anything running as you. `pass` ("the standard unix password manager") keeps each secret as a small **encrypted file** in a folder tree. It's a vault in miniature: a **path**, pointing at an **encrypted file**, holding **key/value pairs**. Hold on to that picture; the next lab puts it on a server.

Everything here stays on your own terminal.

---

## 1. A key of your own

`pass` encrypts with GPG. Make yourself a key pair (the public half locks, the private half unlocks):

```bash
gpg --quick-gen-key "$USER <$USER@dojo.test>" default default 1y
```

A box asks for a **passphrase**, twice. Pick one with a number or symbol in it (three words and a number is fine), or GPG warns and asks again. The passphrase protects the private key file: whoever copies `~/.gnupg` still needs it.

```bash
gpg --list-secret-keys
```

`[expires: ...]`: the key lives a year, then you make a new one. Remember that for rule 3.

## 2. A store, and a secret in it

Point a new store at your key, and keep its history in git:

```bash
pass init "$USER@dojo.test"
pass git init
```

Add the database login the app from lab 1 needs. `-m` takes several lines; type them, then press **Ctrl+D** on an empty line:

```bash
pass insert -m dojo/db
```

```text
first-password
username: app
host: db.internal
```

By convention the first line is the password and the rest are `key: value` lines. Typing it at the prompt, instead of `echo ... | pass insert`, keeps it out of your shell history.

Let `pass` make the next one for you, 32 random characters nobody has to type:

```bash
pass generate dojo/api-token 32
```

## 3. What's on disk

```bash
pass
tree -a ~/.password-store
```

The path `dojo/db` **is** a folder and a file: `~/.password-store/dojo/db.gpg`. Look inside it:

```bash
head -c 120 ~/.password-store/dojo/db.gpg | cat -v; echo
gpg --list-packets ~/.password-store/dojo/db.gpg 2>&1 | head -3
```

Noise, and a note saying who it's encrypted for: your key. Now read it the way you'd use it:

```bash
pass show dojo/db
pass show dojo/db | head -1
pass show dojo/db | sed -n 's/^username: //p'
```

GPG asked for your passphrase once and remembers it for about 10 minutes, then asks again.

## 4. History

Change the password:

```bash
EDITOR=nano pass edit dojo/db
```

In the editor, change `first-password` to `second-password`, then save and quit (**Ctrl+O**, **Enter**, **Ctrl+X**). `pass` decrypts to a temporary file in memory (`/dev/shm`), not on disk. Every change was a commit:

```bash
pass git log --oneline
pass git log -p dojo/db.gpg
```

`pass git init` told git how to decrypt `.gpg` files for a diff, so on **your** machine the history shows the old password next to the new one. That's versions, like the vault's KV store keeps in lab 3.

The store is encrypted, so could you push it to a git server as a backup? The values, yes. The **names** (`dojo/db`, `prod/payments/stripe`) and every commit time are plain text. Keep names boring.

## 5. Sharing it with a teammate

A teammate needs `dojo/db`. Pretend to be them for a moment and make their key (no passphrase, only because it's pretend):

```bash
gpg --batch --passphrase '' --quick-gen-key "teammate <teammate@dojo.test>" default default 1y
```

`pass` shares a folder by **encrypting every file in it again**, once for each person:

```bash
pass init -p dojo "$USER@dojo.test" teammate@dojo.test
gpg --list-packets ~/.password-store/dojo/db.gpg 2>&1 | grep -A1 'encrypted with'
```

Two keys can open it now. Your teammate pulls the store and reads it on their own laptop.

## 6. ...and taking it back

The teammate moves to another team. Take them off:

```bash
pass init -p dojo "$USER@dojo.test"
gpg --list-packets ~/.password-store/dojo/db.gpg 2>&1 | grep -A1 'encrypted with'
```

The new file is yours alone. Now look at the one before it:

```bash
pass git show HEAD~1:dojo/db.gpg | gpg --list-packets 2>&1 | grep -A1 'encrypted with'
```

Every copy they already pulled still opens with their key, forever. Removing someone doesn't un-share anything. The only real fix is the one from lab 1: **rotate** every secret they could read.

## 7. Where `pass` stops

`pass` is a good home for **your own** secrets. For a team or an app, it runs out:

| You need... | With `pass` | With a vault (next labs) |
| ----------- | ----------- | ------------------------ |
| To give access | Re-encrypt the folder for each person | One policy line; nothing is copied |
| To take access back | Re-encrypt, then rotate everything they saw | Revoke the token; it can't read again |
| To know who read what, when | Nobody knows | The audit log (lab 12) |
| A secret that expires by itself | No | Leases and TTLs (labs 5, 11) |
| An app or a pipeline to read it | Give it a private key: another secret to hide | It logs in with its own identity (labs 9, 10) |

The vault keeps the same shape (a path, pointing at key/value pairs), but it keeps **one** copy on a server, and every read passes a gate that checks who's asking.

## At work: on your own machine

Store your personal tokens and passwords like this rather than in a `.env` file, a note or a shell profile:

- **Linux:** `sudo apt install pass` (or your distro's package), and GPG.
- **macOS:** `brew install pass gnupg`.
- **Windows:** **gopass**, a `pass`-compatible tool that runs natively: `winget install gopass.gopass` and `winget install GnuPG.Gpg4win`, then `gopass setup`. It reads and writes the same store format, so a mixed team can share one (it also runs on Linux and macOS).

Your company may already give you a password manager with a CLI; the idea is the same: encrypted, one place, never plain text on disk.

## Check yourself

1. Someone copies your whole `~/.password-store` folder. What do they have? *(Encrypted files and their names. Without your private key and its passphrase, not the values.)*
2. You remove a teammate with `pass init -p`. Are the secrets safe from them now? *(No. They keep every copy they pulled. Rotate.)*

**Rules used:** 8 (never in git in plain text, and never plain text on disk), 7 (plan for leaks: removing access means rotating), 4 (secret zero: your GPG key and its passphrase are the one secret that protects all the others).

**Next:** [lab3.md](lab3.md)
