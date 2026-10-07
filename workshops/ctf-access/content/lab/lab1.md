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

You'll see more than one open port. Only one of them is the portal; `nmap`'s version-detection banner on
the other tells you it isn't worth your time today (there's nothing behind it to exploit here) -- that's
the point of scanning before guessing.

## 2. Look at the login, not just at it

Open the real port in a browser or with `curl`. Submit the login form with something ordinary first --
a wrong username, a wrong password -- and read exactly what comes back.

Then think about what the server has to do with what you typed to decide whether to log you in. Somewhere,
your username and password turn into a question the server asks its own records: *does a user matching
these two things exist?* The question is built out of **text you control**.

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
dojo-flag submit sqli-login '<flag>'
```

## Still stuck?

Read [exploit-guide/sqli-login.md](exploit-guide/sqli-login.md) for the full walkthrough -- try the hints
above for real first.
