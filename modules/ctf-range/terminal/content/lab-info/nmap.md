# nmap

The standard tool for finding what's listening on a host: which ports are
open, what service is behind each one, and sometimes its version. This is
the deepest primer in the library — almost every lab starts with some form
of "what's actually running here."

## The three questions nmap answers, in order

1. **Is the host up?** (host discovery)
2. **Which ports are open?** (port scanning)
3. **What's running on each open port, and what version?** (service/version
   detection)

## Host and port discovery

```text
nmap $TARGET
```
Default behavior: pings the host, then scans the 1000 most common TCP ports.
Fine as a first look, but "most common" can miss something real:

```text
nmap -p- $TARGET          # every TCP port, 1-65535 (slower, thorough)
nmap -p 80,443,8080 $TARGET  # just the ports you care about
nmap -sU $TARGET          # UDP instead of TCP (DNS, some services)
```

Reading the output:
```text
PORT     STATE SERVICE
22/tcp   open  ssh
80/tcp   open  http
111/tcp  closed rpcbind
```
- **open** — something accepted the connection.
- **closed** — nothing listening, but the host answered (it's reachable).
- **filtered** — no answer at all; usually a firewall silently dropping
  the probe. This is exactly what you should see scanning any host on this
  range other than your own `target-NN` — the firewall doesn't refuse, it
  just drops, so a scan of a classmate's slot should show every port
  filtered or simply time out.

## Service and version detection

```text
nmap -sV $TARGET
```
Adds a `VERSION` column by probing each open port and matching the response
against nmap's signature database:
```text
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.57 ((Debian))
```
This is often the single most useful line in a scan — it turns "a web
server is running" into "a *specific, version-pinned* web server is
running," which is the starting point for "is this version affected by
anything."

## A reasonable "give me everything" command

```text
nmap -sV -p- -T4 $TARGET
```
`-T4` is a timing template (faster, still polite). On a small, local target
like the ones on this range, this finishes in seconds, not minutes.

## Scripts (`-sC` / `--script`)

```text
nmap -sC -sV $TARGET
```
`-sC` runs nmap's default "safe" script set — banner grabs, common
misconfiguration checks — against whatever's open. Treat script output as
a lead to follow up on by hand, not a verdict.

## A note on "stealth" flags

You'll see `-sS` (SYN scan) referenced everywhere online as the "stealthy"
default. On this range it changes nothing you'd notice — there's no IDS
watching, and the firewall behavior (filtered vs. closed) is the same
either way. It's worth knowing the name, not worth worrying about here.
