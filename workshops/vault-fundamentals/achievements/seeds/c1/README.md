# The Shared Secret

Your teammate's app logs in as the AppRole `buddy-{user}`. It has no policy yet, so it can read nothing.

Run `sh seed.sh` once to set up your namespace (it needs your token, which every shell has). It makes a KV
engine `challenge/` with two secrets, `challenge/one` and `challenge/two`, and the AppRole.

Goal: let `buddy-{user}` read `challenge/one`, and nothing else. It must not be able to read `challenge/two`.

Work in your own namespace: `export BAO_NAMESPACE=students/$USER`. Then run `dojo-check c1`.
