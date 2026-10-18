# Lab 1: Staff login portal (`sqli-login`)

By the end of this lab you'll have logged in as `admin` without ever knowing their password, and you'll
understand why "the password is wrong" is sometimes the wrong thing for a login form to be checking.

---

## The briefing

Glasswing's ops team shares one internal portal. It's the plainest possible login form -- username,
password, a submit button -- fronting whatever's behind it. Nobody's touched the code in a while.

## 1. Start the target and scan it

Open the **Attack Range** card, start `sqli-login`, and note your slot's IP. Then:

```sh
nmap -sV -p- <your-slot-ip>
```

You'll see several open ports, and they are different on every box: nothing here is on a port you could
have guessed. Read each service banner. Some are decoys with nothing behind them (a file server that
rejects every login, a second web server that only ever answers `401`); one is the portal you came for.
Telling them apart is the point of scanning before guessing, and `curl -i http://<your-slot-ip>:<port>/`
against each web port shows you which one is a login page.

## 2. Look at the login, not just at it

Open the real port in a browser or with `curl`. Submit the login form with something ordinary first --
a wrong username, a wrong password -- and read exactly what comes back.

Then think about what the server has to do with what you typed to decide whether to log you in. Somewhere,
your username and password turn into a question the server asks its own records: *does a user matching
these two things exist?* The question is built out of **text you control**.

A login like this is usually backed by a SQL query that the program assembles as text. In a made-up
example, a notes site might build:

```text
SELECT * FROM notes WHERE owner = 'USER_TEXT' AND archived = 0
```

with `USER_TEXT` replaced by whatever was typed. The single quotes mark where a text value starts and
ends. If the typed text contains a quote of its own, the database sees the value end early and reads
whatever follows as part of the query. Whether this server does that is something you can test with the
login form and read from how the response changes.

> **Hint 1.** Try putting a single quote (`'`) into the username field by itself and see what changes in
> the response, if anything. A quote means something specific inside a database query -- what is it, and
> what happens if yours shows up somewhere the server didn't expect it?

> **Hint 2.** If the server is pasting your input straight into a query's `WHERE` clause as text, you don't
> need to know anyone's password at all -- you need to make the *condition* true regardless of what the
> password field says. What boolean expression is always true, and how do you close the username's quote
> early enough to add it?

## 3. Submit

Once you're logged in as `admin`, the flag is right there on the welcome page.

```sh
dojo flag '<flag>'
```

## Debrief

The login built its SQL query by gluing your text straight into the statement, so the database could not
tell your data from the program's own instructions. Input that closes the quote and adds logic became part of
the query, and the password check simply stopped mattering. The real fix is parameterized queries (prepared
statements), which send the values separately from the SQL, plus least-privilege database accounts and
hashed passwords so a slip does less damage. This is **OWASP A03:2021 Injection**.

Reflect: input validation or escaping at the form would also have helped, but why is parameterization the
more dependable defense? Where else in your own stack does user text end up inside a command or query?

## Still stuck?

Read [exploit-guide/sqli-login.md](exploit-guide/sqli-login.md) for the full walkthrough -- try the hints
above for real first.
