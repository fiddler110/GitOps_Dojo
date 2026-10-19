# Lab 3: Accounts API (`api-mass-assignment`)

By the end of this lab you'll have turned your own ordinary account into an admin account, using nothing
but a field you added to a request you were always allowed to make.

API-only -- no browser UI here. Drive it with `curl`/`httpie`/`jq`.

---

## The briefing

Glasswing's **Kestrel Accounts API** lets a logged-in user read and update their own profile. You already
have an account on it -- your own terminal username, password `changeme123` -- and you're allowed to
`PATCH` your profile's `bio` field. The question for this lab is whether `bio` is the *only* field that
update actually accepts.

## 1. Start the target and scan it

Open the **Attack Range** card, start `api-mass-assignment`, note your slot's IP, and scan it:

```sh
nmap -sV -p- <your-slot-ip>
```

More than one port, same as every target this session -- only one is the API.

## 2. Log in and look at your own record

```sh
curl -s -X POST http://<ip>:5000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<your-username>","password":"changeme123"}' | jq
```

Save the token you get back, then:

```sh
curl -s http://<ip>:5000/users/me -H "Authorization: Bearer <token>" | jq
```

You'll see your record, including a `role` field set to `student`. The API also documents its own
routes -- check `GET /spec` (linked from the API's root page) for the full list of routes, the fields
each one accepts, and which routes are meant to require which role. Nothing there tells you how to
change your role -- think about what `PATCH /users/me` is actually *for*, and what it does with a JSON
body it wasn't told to filter.

> **Hint 1.** A `PATCH` is supposed to update specific fields. Try `PATCH`ing your `bio` -- it works, as
> expected. Now ask: does the server check *which* fields it writes, or does it write whatever keys show
> up in your JSON body?

> **Hint 2.** If every key in the body lands on your user record, nothing stops you from including a key
> the UI never exposes. What field did `GET /users/me` show you that you might also be able to `PATCH`?

## 3. Reach the admin route

Once your own record shows `role: admin`, there's an admin-only report endpoint that checks exactly that
field before letting you through.

## 4. Submit

```sh
dojo flag '<flag>'
```

## Debrief

The update route copied every key in the request body onto the user record, so a field that was only ever meant to be set by the server was writable by its owner. Frameworks that bind a JSON body straight onto an object make this easy to do by accident, and the interface never shows the extra fields, which is why it goes unnoticed.

The real fix is an explicit allow-list of client-settable fields, or separate input and storage models, with sensitive attributes such as role changed only through a privileged path.

OWASP API Security Top 10 2023: API3 Broken Object Property Level Authorization (mass assignment). In the 2021 web list it sits under A04 Insecure Design.

Reflect: which fields on your own models would be dangerous if a client set them?

## Still stuck?

Read [exploit-guide/api-mass-assignment.md](exploit-guide/api-mass-assignment.md) for the full
walkthrough -- try the hints above for real first.
