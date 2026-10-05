# whois

Looks up registration records for a domain name or an IP address block:
who registered it, when, through which registrar, and (for an IP) which
network operator it belongs to.

```text
whois example.com
```
Useful fields in the output:
- **Registrar** — who the domain is registered through
- **Creation / Updated / Expiry date** — the domain's age and lifecycle
- **Name servers** — which DNS servers are authoritative for it (a lead
  into `dig`/`dnsrecon`)

```text
whois 93.184.216.34
```
For an IP, you get the allocation instead — which organization or ISP
holds that address block, and sometimes an abuse-contact email.

## Where this fits in recon

`whois` tells you *who* owns something and roughly *how old* it is. It
doesn't tell you what's running there — that's `nmap`'s job — and it
doesn't tell you what subdomains or DNS records exist — that's
`dig`/`dnsrecon`. Think of it as the first, broadest step: establishing
who you're even looking at before you start probing.

## On this range

Everything you'll point tools at here is an internal address with no real
public registration, so `whois` against `target-NN` itself won't show
anything interesting. It's included because it's a tool you'll genuinely
reach for in real engagements and in `dns-as-code`-adjacent work, not
because a lab on this range specifically needs it.
