# dig and dnsrecon

Two tools for the same subject at different scales: `dig` asks one DNS
question at a time and shows you exactly what came back; `dnsrecon`
automates asking many questions in a row.

## dig: one query, fully visible

```text
dig example.com
```
```text
;; QUESTION SECTION:
;example.com.                  IN      A

;; ANSWER SECTION:
example.com.            300    IN      A       93.184.216.34
```
- **QUESTION SECTION** — what you asked (name, class `IN`, record type `A`)
- **ANSWER SECTION** — what came back, including the **TTL** (300 seconds
  here — how long a resolver may cache this answer)

Ask for a different record type explicitly:
```text
dig example.com MX      # mail servers
dig example.com NS      # authoritative name servers
dig example.com TXT     # free-text records (SPF, verification strings, ...)
dig example.com ANY     # ask for everything at once (many servers refuse this)
```

Ask a *specific* resolver instead of the system default — useful once
you're investigating a particular resolver's behavior rather than "what's
the real answer":
```text
dig @10.0.0.5 example.com
```

Shorter output for scripting:
```text
dig +short example.com
```

## dnsrecon: the same questions, automated

```text
dnsrecon -d example.com
```
Runs a standard set of lookups (A/AAAA/MX/NS/TXT/SOA, a few common
subdomain guesses) and prints a running log of what it tried and what
answered. Where `dig` is "ask one precise question," `dnsrecon` is "ask a
reasonable spread of questions and show me which ones aren't empty."

```text
dnsrecon -d example.com -D /usr/local/share/wordlists/common.txt -t brt
```
`-t brt` is the brute-force subdomain mode: it tries `<word>.example.com`
for every word in a list and reports which ones resolve. Same underlying
mechanic as `ffuf`'s `FUZZ` substitution, just aimed at subdomains instead
of paths.

## Reading this together

If `dig` shows you a name server you don't recognize, or `whois` shows a
name server that doesn't match what `dig NS` returns, that's a real
inconsistency worth following up on by hand — these tools report what's
there, they don't tell you it's suspicious.
