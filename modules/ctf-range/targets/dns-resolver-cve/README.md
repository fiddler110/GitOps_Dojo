# Target 6 — `dns-resolver-cve`

CTF-3 (plan §7.3 row 6, "Vulnerable and outdated components", ties
`dns-as-code`). **Has a real image slot**, same shape as `leaky-config` /
`ping-tool` / `policy-bypass` (not the "no image" shape 8/10/11 use). The
target container runs five things in one process space: the real uClibc-ng
1.0.39 agent as a subprocess, an in-process UDP DNS answerer on 127.0.0.1:5353,
the "real vault" TCP receiver on 127.0.0.1:9000, the "attacker's capture
point" TCP receiver on 127.0.0.2:9000, and the student-facing Flask control
panel on 0.0.0.0:5000 (plus the standard decoy :2222). See
`app.py`'s module docstring for the full topology and why.

## The flaw

**CVE-2022-30295** in uClibc / uClibc-ng ≤ 1.0.40: the stub resolver assigns
**monotonically increasing** DNS transaction IDs. An attacker who observes
one lookup knows the next TXID will be the previous one + 1 and can land a
single spoofed reply that redirects the lookup — the classic "the resolver
itself is an attack surface" lesson.

**Settled empirically on 2026-10-06** (see `docs/CTF-SPIKES.md`'s "Target 6"
addendum). A tiny static agent cross-compiled with the pinned Bootlin
`x86-64--uclibc--stable-2021.11-5` toolchain (uClibc-ng 1.0.39, confirmed
from `summary.csv`) ran against a logging UDP :53 answerer inside a rootless
Podman container; across 20 consecutive `getaddrinfo` calls the TXIDs were
**2, 3, 4, …, 21** — strictly +1 each query. Source ports were
kernel-ephemeral (33837, 50108, 41837, …), **not** static as some writeups
and the earlier plan draft claimed. The lab exposes both facts honestly in
`GET /observations`.

The agent linked into the lab is the same binary built the same way (see
`ctf-host/Dockerfile`'s `dns-resolver-cve-agent-build` stage, which pins the
tarball by sha256). This is **not** a Python simulation — every DNS lookup
the lab records at `/observations` was emitted by the actual uClibc 1.0.39
stub.

## The exploit chain

Two flags, both HMAC-derived per student (plan §5):

- **Flag 1** — `flag{dns-resolver-cve-token-<hex>}` — the service token the
  agent carries. Captured when the student lands a spoof. Submittable as
  `dojo-flag submit dns-resolver-cve-token <flag>`.
- **Flag 2** — `flag{dns-resolver-cve-<hex>}` — reached by replaying the
  captured token at `/admin`. Submittable as `dojo-flag submit dns-resolver-cve <flag>`.

```
GET  /observations                              → observe recent TXIDs
POST /spoof {"predicted_txid": last+1}          → arm one spoofed answer
GET  /captured  (poll ~2s)                      → flag 1 lands here
POST /admin  Authorization: Bearer <flag1>      → flag 2 in the response
```

The agent cycles every couple of seconds; on the next outgoing query whose
TXID matches the student's prediction, the DNS answerer serves the attacker
address (127.0.0.2) instead of the real vault (127.0.0.1), the agent connects
there and POSTs its token, the attacker's receiver stores it. One tick,
`/captured` returns the token.

## Why the attack is modelled on loopback, not across `ctf_net`

The earlier plan draft imagined an off-path attacker in a sibling slot on
`ctf_net` observing another slot's DNS query. The range's actual topology
forbids this: `ctf-host` runs every slot inside an inner dockerd started
with `--icc=false` and a DOCKER-USER drop on NEW outbound
(`ctf-host/entrypoint.sh`), so a slot cannot reach another slot across the
inner bridge at all — a cross-slot off-path attack is architecturally
impossible here. The CVE itself (predictable TXID, kernel-ephemeral source
port) stays real and observable; the mechanical staging is in-process on
loopback. The teaching holds: a service that trusts DNS to find its backend
hands its credentials to whoever controls resolution; the fix is to **update
the resolver pin past uClibc-ng 1.0.41**, not merely to pin one.

The slot container also runs with `CapDrop ["ALL"]` + no-new-privileges +
`ReadonlyRootfs` (`ctf-controller/docker_api.py`'s `build_create_request` —
a central property the controller must not weaken for one target). That
rules out the usual off-path raw-socket spoof regardless of topology: a
process without `CAP_NET_RAW` cannot forge a packet's source address. The
on-loopback cooperative spoof the lab stages is the only way the attack
can run inside this security model, and it's enough — the agent accepts
the spoofed answer *through the real uClibc stub*, not because the lab
hands it one directly.

## Verify

Run from inside the student's own terminal account — the slot is reachable at
`ctf-host:<attack-port>` the same way every other target in this range is.
`CTF_ATTACK_PORT_BASE` + the student's roster index × `CTF_ATTACK_PORT_BLOCK`
is the base; the real app's port is that first (`controller.py`'s
`attack_host_port`), the next two in the block are the decoy slots a target
may or may not bind (plan §7.3's nmap primer).

```sh
python3 exploit/solve.py --url http://ctf-host:16009
```

Prints `SOLVED:` and the two flag values when both land. Takes under 30
seconds in practice — one agent cycle to observe, one to land the spoof,
one HTTP round-trip to replay.

## Files

- `agent.c` — the uClibc-stub-linked check-in agent (cross-compiled to a
  static x86_64 ELF).
- `app.py` — the Flask control panel + in-process DNS answerer, vault
  receiver, attacker's receiver, decoy, and agent supervisor.
- `requirements.txt` — just Flask.
- `Dockerfile` — dev-only standalone build (ctf-host bakes a flattened rootfs
  of this image's final stage).
- `exploit/solve.py` — reference solve, same shape as every other target in
  this range.
