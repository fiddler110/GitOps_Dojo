# Record type reference

Syntax for the record types used in this lab's `dnsconfig.js`. Full
reference: [dnscontrol.org DNS record types](https://docs.dnscontrol.org/language-reference/domain-modifiers).

All of these go inside the zone's `D("dojo.test", REG, DnsProvider(PDNS),
...)` block, one per line, comma-separated.

## A — point a name at an IPv4 address

```js
A("@", "203.0.113.10"),
A("mail", "203.0.113.20"),
```

- `"@"` means the bare apex domain (`dojo.test` itself).
- `203.0.113.0/24` is IETF-reserved "documentation" address space (RFC
  5737) — used throughout this lab's example records for the same reason
  `dojo.test` is used as the zone: it's guaranteed never to be a real,
  routable address.

## CNAME — alias one name to another hostname

```js
CNAME("app", "dojo.test."),
```

- The target **must end with a trailing dot** — it's a fully-qualified
  domain name, not relative. Forgetting it is the single most common
  mistake — dnscontrol usually catches it at `preview` time as a config
  error, but always double-check.
- A CNAME can't coexist with other records on the same name (you can't have
  both a `CNAME` and a `TXT` on `app`) — this is a DNS-wide rule, not
  specific to this project.

## MX — mail routing

```js
MX("@", 10, "mail.dojo.test."),
```

- Second argument is priority (lower = preferred). Multiple `MX` lines on
  the same name give you a preference-ordered fallback list.
- Target needs the trailing dot, same as CNAME.

## TXT — arbitrary text (SPF, DKIM, DMARC, verification codes)

```js
TXT("@", "v=spf1 -all"),
TXT("_dmarc", "v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s;"),
```

- The SPF example (`v=spf1 -all`) means "no servers are authorized to send
  mail for this domain" — appropriate here since `dojo.test` doesn't
  actually send email.
- Multiple `TXT` records can exist on the same name — just add multiple
  lines, one per value.
- SPF/DKIM/DMARC changes affect email deliverability and anti-spoofing in a
  real zone — treat as high-risk, same as MX, even though this lab zone
  isn't live.

## TTL and DefaultTTL

```js
DefaultTTL(300),
```

`DefaultTTL(300)` at the top of the `D(...)` block sets the zone-wide
default (300 seconds = 5 minutes). Override per-record with a trailing
`TTL(seconds)` argument if one record needs a different value than the
rest of the zone.

## Where to look up anything not covered here

The full, authoritative list of record types and their arguments lives in
the dnscontrol docs:
<https://docs.dnscontrol.org/language-reference/domain-modifiers>.
