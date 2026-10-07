# Lab Info

A reference library, not a walkthrough. Every tool installed in this
terminal image gets a primer here: what it is, how to read its output, the
common flags, and a worked example against a neutral target (your own box,
or a local toy file) — never a working step for any specific lab.

**Same library for every CTF session.** You get every primer whether or not
today's session uses that tool. A primer's presence here says nothing about
what today's targets need — it can't, because the library never changes
between sessions. The labs themselves will tell you what to look for; this
library only tells you how a tool behaves once you've decided to reach for
it.

**What this isn't.** No injection strings, no reverse-shell one-liners, no
cracked-hash walkthroughs, no CVE steps, and no hints about which lab needs
which tool. If you came here looking for "the answer," you won't find it —
that's by design (see `rules.md` in your lab folder for the two-hint rule).

**The legal boundary.** Every tool below is real security tooling, the same
binaries a professional penetration tester uses. Point them only at your own
`target-NN` on this range — the firewall only lets you reach that one host
anyway. Running any of this against a system you don't own or don't have
explicit written authorization to test is illegal in most jurisdictions,
full stop. The skills transfer directly to legitimate work (bug bounties,
authorized pentests, your own homelab); the authorization does not.

## Start here

- [`00-linux-and-shell.md`](00-linux-and-shell.md) — shell navigation, pipes, permissions,
  processes, and the networking/HTTP basics everything else below assumes.

## Recon and discovery

- [`nmap.md`](nmap.md) — host and port discovery, service/version detection, reading results
- [`ffuf.md`](ffuf.md) — content and directory discovery, and the wordlist that ships with it
- [`whois.md`](whois.md) — domain/IP registration lookups
- [`dig-dnsrecon.md`](dig-dnsrecon.md) — DNS queries and enumeration

## Talking to a service once you've found it

- [`ncat.md`](ncat.md) — raw TCP/UDP: probing ports, catching a listener, reading banners
- [`httpie.md`](httpie.md) — a readable, JSON-first HTTP client
- [`jq.md`](jq.md) — slicing and filtering JSON on the command line

## Capture and analysis

- [`tcpdump-tshark.md`](tcpdump-tshark.md) — packet capture, from raw counts to protocol decode

## Specialist tools

- [`sqlmap.md`](sqlmap.md) — automated SQL injection discovery (flags and output only)
- [`john.md`](john.md) — offline password-hash cracking (flags and output only)
- [`opa.md`](opa.md) — evaluating Open Policy Agent / Rego policy, the same engine
  `cloud-policy-as-code` teaches

## Versions installed in this image

Pinned the same way every tool in this image is pinned — a version bump here
means a version bump in `modules/ctf-range/terminal/Dockerfile` too, so this
table always matches what you actually have:

| Tool | Version | How it's pinned |
|---|---|---|
| `nmap`, `ncat`, `tcpdump`, `tshark`, `sqlmap`, `jq`, `john`, `dig` (`dnsutils`), `dnsrecon`, `httpie`, `whois` | Debian stable's packaged version | `apt-get install`, verified against Debian's signed repo metadata |
| `ffuf` | 2.3.0 | static binary, sha256-pinned per architecture |
| `opa` | 1.21.1 | static binary, sha256-pinned per architecture |

Check what you actually have with `<tool> --version` (or `dpkg -l <pkg>` for
the apt-installed ones) — this table can drift from a running container if
the image hasn't been rebuilt since the Dockerfile changed.
