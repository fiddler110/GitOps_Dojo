# Lab 4: Internal ops API (`api-bfla`)

By the end of this lab you'll have reached an administrative route using nothing but your own, perfectly
ordinary login token -- no privilege escalation step, no stolen credential, just a route that checks the
wrong thing.

API-only -- no browser UI here. Drive it with `curl`/`httpie`/`jq`.

---

## The briefing

Glasswing's **Helix Ops API** has routes for ordinary users and routes meant only for facilitators. You
have a perfectly normal account -- your own terminal username, password `changeme123` -- with the
ordinary `student` role. This lab is about what the server actually checks before it runs an
administrative action, versus what it *looks* like it checks.

## 1. Start the target and scan it

Open the **Attack Range** card, start `api-bfla`, note your slot's IP, and scan it:

```sh
nmap -sV -p- <your-slot-ip>
```

As before: more than one port, and only one is the API you care about.

## 2. Log in and look at what you are

```sh
curl -s -X POST http://<ip>:5000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<your-username>","password":"changeme123"}' | jq
```

```sh
curl -s http://<ip>:5000/me -H "Authorization: Bearer <token>" | jq
```

`GET /me` confirms it: you're logged in, and your role is `student`. There's also an administrative route,
`POST /admin/reset-all`, that a facilitator would use to reset the whole room's progress. Think about the
*two* separate questions a route like that should ask before doing anything: is this request from someone
who successfully logged in, and is this request from someone who's *allowed to do this specific thing*.
A route can get the first answer right and never ask the second.

> **Hint 1.** Try calling `/admin/reset-all` with your own ordinary token, exactly as-is -- no special
> header, nothing extra. What does it check before it answers? Does an error, or a success, tell you
> more about which of the two questions above it actually asked?

> **Hint 2.** If the response carries a flag at all, the authorization bug is already proven -- that's by
> design here. You do **not** need to send anything beyond your ordinary bearer token to see it. (A
> `confirm`-style header exists that would additionally mutate shared state; don't use it -- it's never
> needed to prove the bug, and doing so against a shared range affects other students.)

## 3. Submit

```sh
dojo-flag submit api-bfla '<flag>'
```

## Debrief

Your token proved who you were, and the route stopped there. It never asked whether that identity was allowed to perform this administrative function. Authentication and authorization are separate questions, and function-level checks are easy to forget on routes that the interface simply never links to.

The real fix is to enforce authorization on the server for every route, deny by default, and centralise role checks in middleware or a decorator so a new endpoint cannot ship without one. Hiding the route is not a control.

OWASP Top 10 2021: A01 Broken Access Control. OWASP API Security Top 10 2023: API5 Broken Function Level Authorization.

Reflect: could you list every route in your service and the role each one requires?

## Still stuck?

Read [exploit-guide/api-bfla.md](exploit-guide/api-bfla.md) for the full walkthrough -- try the hints
above for real first.
