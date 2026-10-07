# john (John the Ripper)

An offline password-hash cracker: given a hash and a list of candidate
passwords (or a pattern to generate them), it hashes each candidate the
same way and reports a match. "Offline" matters — there's no login attempt
involved and so no rate limit to trip; the entire thing happens against a
hash you already have in hand.

This primer covers flags and output against a **toy hash you generate
yourself**, not any lab's real data — same reason as `sqlmap.md`.

## Making a toy hash to practice on

```text
echo -n 'hunter2' | md5sum
f3f91ff32cfa9b601bd91ab074995662  -
```
(Any hash algorithm `john` supports works for practicing the commands
below — MD5 here only because it's a one-liner to generate.)

## A minimal input file and a wordlist attack

```text
echo 'toyuser:f3f91ff32cfa9b601bd91ab074995662' > hashes.txt
john --format=raw-md5 --wordlist=/usr/local/share/wordlists/common.txt hashes.txt
```
`john` tries every word in the wordlist, hashes it the same way, and
compares. The wordlist shipped in this image (`wordlists`'s shared
`common.txt`) is generic and small — real wordlist attacks against real
passwords use much larger, purpose-built lists; the mechanic is identical
either way.

## Reading the output

```text
Loaded 1 password hash (Raw-MD5 [MD5 128/128 SSE2 4x3])
hunter2          (toyuser)
1g 0:00:00:00 DONE
```
First line: what it loaded and which format it's using. The cracked line
shows the recovered plaintext next to the account name it belonged to.
The summary line (`1g` = 1 guess found) tells you it's done, not still
working.

## Checking progress or results again later

```text
john --show hashes.txt
```
Prints anything already cracked without re-running the attack — `john`
keeps a `john.pot` file of everything it's ever cracked, so re-running the
same hash against the same wordlist is instant the second time.

## Other attack modes, by name only

- `--incremental` — brute force by character pattern instead of a
  wordlist; much slower, no list needed.
- `--rules` — mutate each wordlist word (capitalize, append digits, common
  substitutions) before trying it, closer to how people actually vary a
  base password.

Both exist to be aware of; this primer isn't the place to practice tuning
them, since doing so meaningfully needs a real target hash, which is
exactly what this library doesn't provide.

## Why this matters even with rate-limiting lessons elsewhere

A rate limit (see the auth-related primers and labs) stops *online*
guessing against a live login form. It does nothing once a hash has
already leaked — which is why `leaky-config`-style lessons about credential
exposure matter independently of login-throttling lessons. The two defend
against different stages of the same mistake.
