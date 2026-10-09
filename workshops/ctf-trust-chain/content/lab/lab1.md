# Lab 1: Internal DNS-backed agent (`dns-resolver-cve`)

By the end of this lab you'll have made a service hand its own credentials to you, not by breaking into
anything, but by answering a question it asked before you did.

---

## The briefing

One of Glasswing's internal agents finds its backend the way a lot of services do: it looks up a
hostname, then connects to whatever address comes back. Nobody's touched the resolver it uses in years --
it still works, so it was never a priority. This lab has **two flags**, not one: the first is a credential
you capture, the second is what that credential gets you when you use it the way it was meant to be used.

## 1. Start the target and scan it

Open the **Attack Range** card, start `dns-resolver-cve`, and note your slot's IP. Then:

```sh
nmap -sV -p- <your-slot-ip>
```

You'll see more than one open port. Only one of them is the control panel you care about; it exposes a
few JSON endpoints, starting with `GET /observations`.

## 2. Watch the agent think out loud

The agent on this box resolves an internal hostname every few seconds and connects to whatever address
the lookup returns. `GET /observations` shows you the DNS lookups it's already made -- including the
**transaction ID** (TXID) each one used. A DNS transaction ID exists so a resolver can tell *its own*
query apart from anyone else's reply; if you could predict the next one before the real answer arrives,
you could potentially get your answer accepted instead.

Pull `/observations` a couple of times and look at how the TXID changes between one lookup and the next.
Is it random? Is there a pattern?

> **Hint 1.** It isn't random. The resolver this agent is linked against has a well-known weakness
> (CVE-2022-30295): it assigns transaction IDs by **counting up by one each time**. If you've seen the
> last one, you already know the next one -- no guessing, no brute force.

> **Hint 2.** `POST /spoof` takes a single field, `predicted_txid`. Given what you now know about how the
> next TXID is chosen, what should you send? The agent cycles every couple of seconds, so once you've
> armed a prediction, give it a moment and poll `GET /captured` -- if your prediction was right, the
> agent's *next* lookup lands somewhere other than its real backend, and whatever it was carrying shows up
> there.

Once `/captured` returns a token, that's **flag 1**. Submit it:

```sh
dojo-flag submit dns-resolver-cve-token '<flag>'
```

## 3. Use what you captured

The token you captured is a service credential -- the kind of thing the agent was supposed to present only
to its real backend. The control panel has an `/admin` endpoint that expects exactly this kind of
credential, presented the normal way an API expects a bearer token.

> **Hint 3.** `Authorization: Bearer <captured-token>` on a `POST /admin` is the same shape as any other
> authenticated API call you've made this session -- nothing new to figure out here except that the
> credential came from somewhere unusual.

The response to a correctly authorized `/admin` call is **flag 2**:

```sh
dojo-flag submit dns-resolver-cve '<flag>'
```

## Still stuck?

Read [exploit-guide/dns-resolver-cve.md](exploit-guide/dns-resolver-cve.md) for the full walkthrough --
try the hints above for real first.
