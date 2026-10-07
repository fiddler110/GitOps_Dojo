# ncat

A general-purpose tool for talking to a TCP or UDP port directly, with
nothing in between you and the raw connection. Where `httpie`/`curl`
understand HTTP specifically, `ncat` understands nothing except "send
bytes, receive bytes" — which makes it the right tool whenever you need to
see exactly what a service sends before anything interprets it for you, or
whenever the thing on the other end isn't HTTP at all.

## Connecting to a port (client mode)

```text
ncat $TARGET 80
```
Opens a raw connection. Nothing happens until you type something — this is
the point: you control exactly what goes out.
```text
GET / HTTP/1.1
Host: example.com

```
(a blank line after `Host:` ends the request — HTTP needs it). The server's
raw response, headers and all, prints right back at you.

## Grabbing a banner

Plenty of services announce themselves the moment you connect, before you
send anything:
```text
ncat $TARGET 22
SSH-2.0-OpenSSH_9.2p1 Debian-2
```
That one line can already tell you what's running and roughly which
version, without needing `nmap -sV` at all.

## Listening (server mode)

```text
ncat -lvnp 4000
```
`-l` listen, `-v` verbose, `-n` don't resolve DNS, `-p` the port. This
turns your terminal into something that *waits* for an incoming
connection — the receiving end of a reverse shell, or just a way to see
what another host sends you. On this range, your listener ports are
assigned to you specifically (see your lab briefing) and firewalled so
only your own `target-NN` can reach them.

## UDP mode

```text
ncat -u $TARGET 53
```
Everything above works the same for UDP with `-u` added; the difference is
there's no handshake, so "connected" just means ncat is ready to send, not
that anything on the other end is listening.

## Where this sits next to the HTTP-specific tools

If a response is plain HTTP and you just want the content, `httpie` or
`curl` is less typing and does more for you (redirects, JSON formatting).
Reach for `ncat` when you want to see the exact bytes, when the protocol
isn't HTTP, or when you need the listening side of a connection at all.
