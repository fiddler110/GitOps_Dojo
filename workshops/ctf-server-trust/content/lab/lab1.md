# Lab 1: Network diagnostics page (`ping-tool`)

By the end of this lab you'll have gotten a diagnostics page to run a second command you chose, read a
file it was never meant to show you, and used what's in it to unlock a hidden endpoint.

---

## The briefing

Glasswing runs a small internal tool called **NetPulse Diagnostics**: type a hostname, it looks it up for
you, server-side. Nobody's touched the code in a while.

## 1. Start the target and scan it

Open the **Attack Range** card, start `ping-tool`, and note your slot's IP. Then:

```sh
nmap -sV -p- <your-slot-ip>
```

You'll see more than one open port. Only one of them is NetPulse; `nmap`'s version-detection banner on
the other tells you it isn't worth your time today -- that's the point of scanning before guessing.

## 2. Look at what the page actually does

Open the real port and submit the form with an ordinary hostname (`example.com`). It works, and the page
shows you a normal lookup result.

Now think about *how* that result got made: something on the server took the text you typed and ran a
real system command with it. If your input becomes part of a command line, the question is whether it
stays *data* the whole way through, or whether it can become more commands.

> **Hint 1.** Shells treat certain characters as instructions, not data -- a semicolon (`;`) is one way to
> tell a shell "now run a second, completely different command." What happens if you put one in the
> hostname field, followed by something harmless like `echo hi`?

> **Hint 2.** If a second command runs, it runs as whatever user the diagnostics tool itself runs as --
> which means it can read any file that user can read. This box keeps one specific note written to disk
> at startup, describing a privileged command a real sysadmin left configured for passwordless use. Find
> that note (think about where a service would write a scratch file) and read it with your injected
> command.

## 3. Use what the note gives you

The note describes a tool this account can run with elevated rights, no password required -- and gives
you a token. There's a second endpoint on this same app, `/escalate`, that wants exactly that token.

## 4. Submit

Once `/escalate` accepts your token, the flag is in its response.

```sh
dojo-flag submit ping-tool '<flag>'
```

## Still stuck?

Read [exploit-guide/ping-tool.md](exploit-guide/ping-tool.md) for the full walkthrough -- try the hints
above for real first.
