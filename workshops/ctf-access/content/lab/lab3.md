# Lab 3: Support ticket archive (`idor-pcap`)

By the end of this lab you'll have read a support ticket that was never meant for you, found a working
credential inside it, and reused that credential to unlock an admin panel.

---

## The briefing

Glasswing keeps an archive of old support tickets "for reference." Each one is numbered, and each one has
a packet-capture file attached -- someone's habit of saving network traces when diagnosing a problem,
never cleaned up afterward.

## 1. Start the target and scan it

Open the **Attack Range** card, start `idor-pcap`, note your slot's IP, and scan it:

```sh
nmap -sV -p- <your-slot-ip>
```

More than one port again. This target's decoys are themed around what the archive actually leaks later --
worth remembering once you know what that is.

## 2. Ask for a ticket that isn't yours

The archive serves tickets at `/data/<n>` for some small, guessable range of `n`. Try a few numbers. Notice
what the server does *not* ask you for before handing one back.

Once you've found a ticket with an actual `.pcap` attached, you have a real packet capture to read, not a
puzzle to solve by eye. **Lab Info**'s `tcpdump-tshark.md` covers reading a capture for cleartext protocol
exchanges -- this one has one, and the protocol doesn't encrypt its login step.

> **Hint 1.** Not every ticket number has something interesting. Think about what "for reference" tickets
> would realistically be numbered in the single digits, and read the ones that *do* return a capture file,
> not just the first one you try.

> **Hint 2.** Whatever credential you find in that capture was good enough to log in somewhere once -- it's
> worth trying it again, somewhere else on this same box that asks for a username and password.

## 3. Submit

Once you've reused the leaked credential to reach the admin area, the flag -- and an explanation of the
privilege-escalation step this target's shape can't fully demonstrate -- is right there.

```sh
dojo-flag submit idor-pcap '<flag>'
```

## Still stuck?

Read [exploit-guide/idor-pcap.md](exploit-guide/idor-pcap.md) for the full walkthrough -- try the hints
above for real first.
