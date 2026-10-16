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

A secret is a small set of key-value pairs at a path. `put` writes one (here two keys, `username` and `password`), `get` reads it back, and `-field` picks one value. `-field` prints just the value, which is what a script wants. `-format=json` gives everything, for tools like `jq`.

```text
bao kv put <path> key=value [key=value ...]
bao kv get [-field=<key>] <path>
```

**Your turn:** before you run these, predict what each `get` prints.

```sh
bao kv put secret/students/$USER/db username=app password=first-password
bao kv get secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db
```

<!-- dojo-reveal: Results of put and get -->

The first `get` shows both keys plus the secret's metadata (version 1). The second prints only `first-password`.

<!-- /dojo-reveal -->

### Keep the value off the command line

That `put` line has a problem. While a program runs, its whole command line is visible to every account on a shared machine: build servers, jump hosts, CI runners. `ps` lists processes with their arguments, so yours would show up; on an ordinary shared machine, so would a neighbour's `bao kv put ... password=...` while it runs. (Not here: this platform runs each of you in a process namespace of your own, so your `ps` shows only your processes. Most machines don't, so don't count on it.)

The fix is to hand the value to `bao` on its **standard input**. `password=-` means "read this value from stdin", and `printf` is part of the shell, not a separate program, so the value never shows in `ps`. Several keys at once go in as JSON, with a lone `-` for all of them: `echo '{"a": "1", "b": "2"}' | bao kv put <path> -`. (A value you type still lands in your shell history. For a real password, `read -rs PW` asks for it without showing it, then `printf '%s' "$PW" | ...`.) From here on the labs write secrets this way.

**Your turn:** try it with a stand-in for a slow command. Predict: will `ps` show the password?

```sh
python3 -c 'import time; time.sleep(30)' password=first-password &
ps -eo user,args | grep '[p]assword='
kill %1
```

<!-- dojo-reveal: Result of the ps demo -->

Yes: the argument `password=first-password` is plainly in the process list.

<!-- /dojo-reveal -->

Now write the secret the safe way:

```sh
printf '%s' 'first-password' | bao kv put secret/students/$USER/db username=app password=-
```

Open the same secret in the UI (**secret → students → your name → db**) and leave the tab open.

## 2. Versions

KV v2 keeps every version of a secret. `put` replaces the whole secret, so you give every key again; `patch` changes only the keys you give. `-version=N` reads an old one, and the **metadata** is the list of versions, with when each was made. `rollback` writes an old version's data as a new version, so nothing is lost.

```text
bao kv patch <path> key=value
bao kv get -version=<n> <path>
bao kv metadata get <path>
bao kv rollback -version=<n> <path>
```

**Your turn:** change the password twice, once with each way of writing. Predict what `version` will say at the end.

```sh
printf '%s' 'second-password' | bao kv put secret/students/$USER/db username=app password=-
printf '%s' 'third-password' | bao kv patch secret/students/$USER/db password=-
bao kv get secret/students/$USER/db
```

<!-- dojo-reveal: Result of the two changes -->

`version` went up each time, to 3, and the old ones are still there.

<!-- /dojo-reveal -->

**Your turn:** read version 1 and the metadata. Then somebody set a bad password: roll back to version 2 (this writes version 2's data as a new version 4). Predict which password you get back.

```sh
bao kv get -version=1 secret/students/$USER/db
bao kv metadata get secret/students/$USER/db
bao kv rollback -version=2 secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db
```

<!-- dojo-reveal: Results of the rollback -->

Version 1 still shows `first-password`. After the rollback the password is `second-password`, as version 4.

<!-- /dojo-reveal -->

In the UI, refresh and open **Version history**. You can see the old versions still there, even after rolling back to version 2, and see how each is an update so we are now on version 4 with version 2's value. One thing in version history is that you don't see actual values; only the keys and their metadata.

## 3. Delete, undelete, destroy

These three are different, and the difference matters when something leaks.

| Command           | What happens                        | Azure Key Vault calls it |
| ----------------- | ----------------------------------- | ------------------------ |
| `delete`          | Hidden; `undelete` brings it back   | soft delete / recover    |
| `destroy`         | That version's data is wiped        | purge                    |
| `metadata delete` | Every version and the history, gone | purge the whole secret   |

If a secret leaked, destroying old copies doesn't un-leak it. **Rotate first** (a new password where it's used), then destroy.

```text
bao kv delete <path>
bao kv undelete -versions=<n> <path>
bao kv destroy -versions=<n> <path>
```

**Your turn:** run the first four lines, then the last two, reading the output after each. Before each `get`, predict what it will say.

```sh
bao kv delete secret/students/$USER/db          # the newest version: hidden, recoverable
bao kv get secret/students/$USER/db             # "deleted"
bao kv undelete -versions=4 secret/students/$USER/db
bao kv get -field=password secret/students/$USER/db   # back

bao kv destroy -versions=1 secret/students/$USER/db   # version 1: gone for good
bao kv get -version=1 secret/students/$USER/db        # "destroyed"
```

<!-- dojo-reveal: Results of delete, undelete, destroy -->

After `delete`, the `get` reports the version as deleted. After `undelete`, the password is back. After `destroy`, version 1 reads as destroyed, with no data, and nothing brings it back.

<!-- /dojo-reveal -->

## 4. Knock on a neighbour's door

`list` shows what's in a folder. Nobody made a rule for you personally: there is **one** policy for the whole class. A **policy** is a list of paths, each with what may be done there (`read`, `create`, `delete`...). Anything a policy doesn't allow is denied.

**Your turn:** list the folders, then read and write a neighbour's secret. Predict which of the three succeed.

```sh
bao kv list secret/students/
bao kv get secret/students/student02/db
printf '%s' 'mine-now' | bao kv put secret/students/student02/db password=-
```

<!-- dojo-reveal: Results of the neighbour's folder -->

You can list the folders, but reading or writing anyone else's gives `permission denied`.

<!-- /dojo-reveal -->

Now read the policy that refused you:

```sh
bao policy read student

# Or with pretty colours
bao policy read student | bat --language=json
```

Find this block:

```hcl
path "secret/data/students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}
```

`{{identity.entity.name}}` is filled in on every request with the name of the entity asking, which is you. That one **templated policy** covers 30 students, or 3,000, with no per-person rule to keep up to date.

Notice that the path says `secret/data/...`, not `secret/...`. KV v2 keeps the value under `data/`, and the history under `metadata/`, `delete/`, `undelete/` and `destroy/`, so a policy can allow reading a secret without allowing its history to be wiped.

## Check yourself

1. Someone can `list` a folder but not `read` in it. What can they learn?

<!-- dojo-reveal: Show the answer -->

The names of the secrets, not the values. Names can still leak something, so keep them boring.

<!-- /dojo-reveal -->

2. You deleted the newest version by mistake. Which command undoes it?

<!-- dojo-reveal: Show the answer -->

`bao kv undelete -versions=<n>`. After `destroy`, nothing does.

<!-- /dojo-reveal -->

3. Why `printf ... | bao kv put ... password=-` and not `password=...`?

<!-- dojo-reveal: Show the answer -->

On a shared machine, a command line is visible to every account in `ps` while the command runs. Standard input isn't.

<!-- /dojo-reveal -->

**Rules used:** 1 (least privilege: deny by default, one folder each), 7 (plan for leaks: versions, rotate, then destroy), 8 (never in logs: nor on a command line).

**Next:** [lab4.md](lab4.md)
