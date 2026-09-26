# Lab 3 — Use the shared vault

**Goal:** store, read, version and delete secrets in the class's shared vault, and read the one policy that keeps everyone in their own folder.

`secret/` is a **KV version 2** engine: a key-value store that keeps every version of every secret. The whole class shares it, and each of you has one folder, `secret/students/<you>/`. This is how most companies start: one vault, one path per team.

It's the same shape as your `pass` store from lab 2: a path pointing at key/value pairs. The difference is where it lives: one copy on a server, and every request passes the vault's checks first.

**In this lab you will:**

1. Write a secret and read it back, whole and one value at a time.
2. Change it, look at old versions, and roll back.
3. Try the three ways to remove a secret, and see which ones can be undone.
4. Try a neighbour's folder, and read the one policy that refuses you.

All the commands are `bao kv ...`: `kv` is the part of `bao` that talks to key-value engines like `secret/`.

---

## 1. Put and get

A secret is a small set of key-value pairs at a path. `put` writes one (here two keys, `username` and `password`), `get` reads it back, and `-field` picks one value:

```bash
bao kv put secret/students/$USER/db username=app password=first-password
bao kv get secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db
```

`-field` prints just the value, which is what a script wants. `-format=json` gives everything, for tools like `jq`.

Open the same secret in the UI (**secret → students → your name → db**) and leave the tab open.

## 2. Versions

Change the password twice, once with each way of writing:

```bash
bao kv put secret/students/$USER/db username=app password=second-password
bao kv patch secret/students/$USER/db password=third-password
bao kv get secret/students/$USER/db
```

`put` replaces the whole secret, so you give every key again; `patch` changes only the keys you give. The `version` in the output went up each time, and the old ones are still there. Read version 1, then the secret's **metadata**: the list of versions, with when each was made:

```bash
bao kv get -version=1 secret/students/$USER/db
bao kv metadata get secret/students/$USER/db
```

Somebody set a bad password. Roll back to version 2 (this writes version 2's data as a new version 4, so nothing is lost):

```bash
bao kv rollback -version=2 secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db
```

In the UI, refresh and open **Version history**.

## 3. Delete, undelete, destroy

These three are different, and the difference matters when something leaks. Run the first four lines, then the last two, reading the output after each:

```bash
bao kv delete secret/students/$USER/db          # the newest version: hidden, recoverable
bao kv get secret/students/$USER/db             # "deleted"
bao kv undelete -versions=4 secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db   # back

bao kv destroy -versions=1 secret/students/$USER/db   # version 1: gone for good
bao kv get -version=1 secret/students/$USER/db        # "destroyed"
```

| Command | What happens | Azure Key Vault calls it |
| ------- | ------------ | ------------------------ |
| `delete` | Hidden; `undelete` brings it back | soft delete / recover |
| `destroy` | That version's data is wiped | purge |
| `metadata delete` | Every version and the history, gone | purge the whole secret |

If a secret leaked, destroying old copies doesn't un-leak it. **Rotate first** (a new password where it's used), then destroy.

## 4. Knock on a neighbour's door

Try the folders around yours. `list` shows what's in a folder; then read and write a neighbour's secret:

```bash
bao kv list secret/students/
bao kv get secret/students/student02/db
bao kv put secret/students/student02/db password=mine-now
```

You can list the folders, but reading or writing anyone else's gives `permission denied`. Nobody made a rule for you personally. There is **one** policy for the whole class. A **policy** is a list of paths, each with what may be done there (`read`, `create`, `delete`...). Read it:

```bash
bao policy read student
```

Find this block:

```hcl
path "secret/data/students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}
```

`{{identity.entity.name}}` is filled in on every request with the name of the entity asking, which is you. That one **templated policy** covers 30 students, or 3,000, with no per-person rule to keep up to date. Anything a policy doesn't allow is denied.

Notice that the path says `secret/data/...`, not `secret/...`. KV v2 keeps the value under `data/`, and the history under `metadata/`, `delete/`, `undelete/` and `destroy/`, so a policy can allow reading a secret without allowing its history to be wiped.

## Check yourself

1. Someone can `list` a folder but not `read` in it. What can they learn? *(The names of the secrets, not the values. Names can still leak something, so keep them boring.)*
2. You deleted the newest version by mistake. Which command undoes it? *(`bao kv undelete -versions=<n>`. After `destroy`, nothing does.)*

**Rules used:** 1 (least privilege: deny by default, one folder each), 7 (plan for leaks: versions, rotate, then destroy).

**Next:** [lab4.md](lab4.md)
