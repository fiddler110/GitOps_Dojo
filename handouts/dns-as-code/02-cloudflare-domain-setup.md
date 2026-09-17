# Real Domain + Cloudflare Setup (Optional, Costs Money)

This path gives you the closest thing to production DNS-as-Code: a real,
publicly resolvable domain, managed through a real Cloudflare account,
with `dnsctl.py`'s "Cloudflare" prompts finally meaning something instead
of being inert lab flavor text. It's more involved than
[01-local-powerdns-stack.md](01-local-powerdns-stack.md) and it costs a
small amount of real money for the domain — do this if you want the full
experience, not as a prerequisite for finishing the five labs.

**You don't need this to complete Labs 1-5.** The free local PowerDNS
stack covers every command and concept. Come back to this once you're
comfortable and want the real thing.

---

## What this costs

- A domain name: typically **$8–$20/year** depending on the TLD (`.com`,
  `.dev`, `.xyz`, etc. all differ). You're paying a registrar for the
  right to that name for a year at a time.
- Cloudflare's DNS hosting itself: **free**, on Cloudflare's free plan —
  no credit card required for that part.

Pick a throwaway-feeling domain if cost is a concern — a `.xyz` or similar
budget TLD registered for a single year of practice is a legitimate,
cheap option.

---

## 1. Buy a domain

You have two reasonable options:

### Option A — Cloudflare Registrar

Cloudflare sells domains at close to wholesale cost (no markup) and
automatically sets it up on Cloudflare DNS with nothing further to
configure. Downside: you must already have a Cloudflare account and add
the domain as a zone first, then transfer/register through
**Cloudflare dashboard → Domain Registration → Register Domain**. See
step 2 below to create the account first, then come back here.

### Option B — Any other registrar (Namecheap, Porkbun, Google Domains, etc.)

Buy the domain wherever you like — this is the more common path if you
already have a preferred registrar. You'll point its nameservers at
Cloudflare afterward (step 3).

Either way: **you do not need any hosting, website, or email attached to
this domain.** You're only using it to manage DNS records — it can (and
for this exercise, should) point at nothing real.

---

## 2. Create a free Cloudflare account

Go to <https://dash.cloudflare.com/sign-up> — email + password, no
credit card required for the free plan.

---

## 3. Add your domain to Cloudflare

1. In the Cloudflare dashboard, click **Add a Site**.
2. Enter your domain name and select the **Free** plan.
3. Cloudflare scans for any existing DNS records and shows you a list —
   review it, but don't worry about getting it perfect; `dnsconfig.js`
   is about to become the real source of truth anyway.
4. Cloudflare gives you **two nameservers** (something like
   `aida.ns.cloudflare.com` / `bob.ns.cloudflare.com`).
5. **If you bought the domain elsewhere (Option B):** go to your
   registrar's dashboard, find the nameserver / DNS settings for the
   domain, and replace whatever's there with the two Cloudflare
   nameservers. This step is different for every registrar — search
   "`<your registrar>` change nameservers" if you can't find it.
6. **If you registered through Cloudflare (Option A):** this is already
   done for you.
7. Nameserver changes can take anywhere from a few minutes to 24 hours to
   propagate. Cloudflare emails you once it detects the switch and
   activates the zone.

---

## 4. Create a scoped Cloudflare API token

Don't use your account's Global API Key — create a token scoped to only
what dnscontrol needs, so a leak or mistake has limited blast radius.

1. **Cloudflare dashboard → My Profile → API Tokens → Create Token.**
2. Use the **Edit zone DNS** template, or build a custom token with:
   - Permissions: `Zone` → `DNS` → `Edit`
   - Zone Resources: `Include` → `Specific zone` → your domain
3. Create it, then **copy the token immediately** — Cloudflare only shows
   it once.

---

## 5. Point your repo at Cloudflare instead of PowerDNS

Starting from the same [`starter-repo/`](starter-repo/) you used for the
local PowerDNS path (or a fresh copy if you're keeping that one
separate), make these changes:

**`.env`** (copy from `.env.example` if you haven't already):

```sh
CLOUDFLARE_API_TOKEN=<the token you just created>
```

**`creds.json`** — replace the `powerdns` entry with:

```json
{
  "cloudflare": {
    "TYPE": "CLOUDFLAREAPI",
    "apitoken": "$CLOUDFLARE_API_TOKEN"
  }
}
```

**`dnsconfig.js`** — replace the provider setup at the top and the zone
name. Cloudflare manages its own SOA/apex nameserver records
automatically, so — unlike the PowerDNS version — you don't declare
`SOA(...)`/`NAMESERVER(...)` yourself:

```js
var CF = NewDnsProvider("cloudflare");
var REG = NewRegistrar("none");   // "none" = Cloudflare/registrar isn't managed by dnscontrol here

D("yourdomain.com", REG,
	DnsProvider(CF),
	DefaultTTL(300),

	A("@", "203.0.113.10"),
	A("www", "203.0.113.10"),
	CNAME("app", "yourdomain.com."),
	TXT("@", "v=spf1 -all"),
);
```

Use your actual registered domain in place of `yourdomain.com`, and feel
free to keep it minimal at first — add records incrementally the same
way you did in the labs.

---

## 6. Run the same workflow — for real this time

```sh
dnscontrol preview   # now diffing against your REAL Cloudflare zone
dnscontrol push       # applies for real — this domain is now genuinely live
dig yourdomain.com A +short   # no @dns-server or custom port needed — this is real, public DNS
```

Everything from [lab1.md](lab1.md) onward works the same way. A few
differences worth knowing:

- **`dig` needs no special target** — drop the `@dns-server` (or
  `@127.0.0.1 -p 5353`) you used elsewhere; you're querying real, public
  DNS now, which can take a few minutes to propagate after a `push`
  (Cloudflare is usually fast, often seconds).
- **`dnsctl.py`'s "Proxy through Cloudflare (orange cloud)?" prompt is
  now meaningful.** Answering `y` routes traffic for that record through
  Cloudflare's proxy (CDN/DDoS protection, hides your origin IP);
  answering `n` (a "DNS only," grey-cloud record) just publishes the raw
  IP, closer to what PowerDNS did in the labs. Either is fine for
  practice — `n` is the more direct analogy to what you already did.
- **CI works for real here, unlike the local PowerDNS path** — a
  GitHub-hosted Actions runner *can* reach the Cloudflare API over the
  internet, so if you copy [`advanced-github-actions/`](advanced-github-actions/)`/preview.yml`
  and `apply.yml` into `.github/workflows/` and change `runs-on:
  self-hosted` back to `runs-on: ubuntu-latest` (you don't need a
  self-hosted runner here — see the advanced section of
  [01-local-powerdns-stack.md](01-local-powerdns-stack.md) for why it was
  needed there), you get the full "merge → CI applies it" loop with no
  self-hosted runner needed.

---

## Safety notes

- This is a **real, public domain**. Anyone can query it. Don't put
  anything sensitive in a TXT record, and don't point it at infrastructure
  you care about without understanding the record first.
- Mistakes are cheap to fix (this is DNS-as-Code — `dnscontrol preview`
  still shows you the diff before anything changes), but they're publicly
  visible until fixed, unlike the local PowerDNS stack which nobody but
  you could ever query.
- If you stop paying for the domain at renewal, it eventually gets
  released back to the registry — there's no ongoing obligation beyond
  the annual renewal fee, and you can let it lapse anytime once you're
  done practicing.
