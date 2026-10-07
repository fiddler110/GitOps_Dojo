# Lab 1: Fix the SQL injection and watch it redeploy

By the end of this lab, your own `customer-portal` target will be patched and redeployed live, with no
restart you trigger by hand -- the defend pipeline does it.

---

## 1. Clone your own copy

Your start-of-class provisioning already created `<you>/customer-portal` (not the shared
`ctf-defend-test/customer-portal` seed -- that one is the master copy the pipeline is never pointed at).

```sh
cd ~/lab
git clone http://git-server:3000/$(whoami)/customer-portal.git
cd customer-portal
```

---

## 2. Reproduce the exploit

```sh
python3 exploit/dump.py --url http://localhost:5000   # TODO: point at your running slot
```

Exit code `0` means the injection worked (vulnerable). Read `app.py`'s `/search` route: the `WHERE`
clause is built by string-concatenating the `q` parameter.

---

## 3. Fix it

Edit `app.py`. Replace the string-built query with a parameterized one (the `?` placeholder and a
params tuple) -- a safe version is written as a comment right beneath each vulnerable query.

---

## 4. Open a pull request

```sh
git checkout -b fix-sqli
git commit -am "Parameterize the search query"
git push -u origin fix-sqli
```

Open a PR in the Forgejo UI. The **Defend -- PR gate** workflow re-runs the exploit against your fix:
green means it now returns nothing.

---

## 5. Merge, and watch the redeploy

Merging to `main` runs **Defend -- rebuild and redeploy**: it rebuilds your image, pushes it to the
in-lab registry, and asks the range controller to swap your live slot in place. Run the exploit again
against your slot -- it should come back empty.
