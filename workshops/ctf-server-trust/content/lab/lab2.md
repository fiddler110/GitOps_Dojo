# Lab 2: URL preview feature (`ssrf-fetcher`)

By the end of this lab you'll have made a "preview this URL" feature fetch something its own developers
never meant anyone outside the box to reach -- without ever leaving the network it's supposedly previewing
the public internet from.

---

## The briefing

Glasswing's **Linkly Previews** tool fetches whatever URL you give it, server-side, and shows you the
first couple thousand bytes back. Handy for link previews -- and worth asking *where* that fetch is
actually allowed to go.

## 1. Start the target and scan it

Open the **Attack Range** card, start `ssrf-fetcher`, note your slot's IP, and scan it:

```sh
nmap -sV -p- <your-slot-ip>
```

Same as last time: more than one port, only one worth your attention from outside.

## 2. Think about what "server-side" means

Try previewing a normal public URL first -- it works exactly as you'd expect. Now think about the
difference between a request your *browser* makes and a request the *server* makes on your behalf: the
server's own fetch runs from inside its own container, on its own network view. If nothing restricts
which addresses that fetch is allowed to reach, "preview a URL" quietly becomes "make a request from
inside this box, to anywhere this box can reach."

The ladder row this maps to calls out that this box runs **two** things, not one: the public preview app
you can see, and something else, not published, that only something *inside* the container could ever
reach.

> **Hint 1.** "Not published" (no port mapped to the outside world) and "not reachable" are not the same
> claim. A service bound only to `127.0.0.1` is unreachable from outside the container -- but the preview
> feature's own fetch runs *inside* that same container. What address would let a process inside the box
> reach something nothing outside the box ever could?

> **Hint 2.** The internal app on loopback listens on a different port than the public one. Guessing one
> port over from the public port is a reasonable start for an internal "admin" service that was never
> meant to need a firewall, because nothing outside was ever supposed to reach it directly.

## 3. Submit

Once the preview feature fetches the internal admin endpoint for you, the flag is in what it hands back.

```sh
dojo-flag submit ssrf-fetcher '<flag>'
```

## Debrief

The preview feature fetched whatever address it was given, from inside the container, so "not published" turned out to mean only "not reachable from outside the host", not "not reachable by the app itself". Any server-side fetch of a user-supplied URL lets the user borrow the server's network position, including loopback services, internal admin panels and cloud metadata endpoints.

The real fix is to allow-list schemes and destinations, resolve the host and reject private, loopback and link-local addresses (re-checking after redirects), and to put egress controls and authentication on internal services so that being on the box is not enough.

OWASP Top 10 2021: A10 Server-Side Request Forgery.

Reflect: which of your internal services trust a caller only because of where the request came from?

## Still stuck?

Read [exploit-guide/ssrf-fetcher.md](exploit-guide/ssrf-fetcher.md) for the full walkthrough -- try the
hints above for real first.
