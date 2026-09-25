# Lab 2 — Use the shared vault

**Goal:** store, read, version and delete secrets in the class's shared vault, and read the one policy that keeps everyone in their own folder.

`secret/` is a **KV version 2** engine: a key-value store that keeps every version of every secret. The whole class shares it, and each of you has one folder, `secret/students/<you>/`. This is how most companies start: one vault, one path per team.

---

## 1. Put and get

A secret is a small set of key-value pairs at a path:

```bash
bao kv put secret/students/$USER/db username=app password=first-password
bao kv get secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db
```

`-field` prints just the value, which is what a script wants. `-format=json` gives everything, for tools like `jq`.

Open the same secret in the UI (**secret → students → your name → db**) and leave the tab open.

## 2. Versions

Change the password twice:

```bash
bao kv put secret/students/$USER/db username=app password=second-password
bao kv patch secret/students/$USER/db password=third-password
bao kv get secret/students/$USER/db
```

`put` replaces the whole secret; `patch` changes only the keys you give. The `version` in the output went up each time. The old ones are still there:

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

These three are different, and the difference matters when something leaks.

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

```bash
bao kv list secret/students/
bao kv get secret/students/student02/db
bao kv put secret/students/student02/db password=mine-now
```

You can list the folders, but reading or writing anyone else's gives `permission denied`. Nobody made a rule for you personally. There is **one** policy for the whole class:

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

**Next:** [lab3.md](lab3.md)
