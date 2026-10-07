# tcpdump and tshark

Both capture network traffic; they differ in how much they help you read
it back. `tcpdump` is the lean, universal option — one line per packet,
minimal interpretation. `tshark` (Wireshark's command-line twin) decodes
protocols for you, so a TCP handshake or an HTTP request shows up looking
like what it actually is.

## tcpdump: see that traffic exists

```text
tcpdump -i eth0
```
`-i` picks the interface. Each line is one packet: source, destination,
flags, a little payload info. Narrow it down with a filter expression:
```text
tcpdump -i eth0 host 10.0.0.5          # only traffic to/from this host
tcpdump -i eth0 port 80                # only this port
tcpdump -i eth0 tcp and port 80        # combine conditions
```

## Saving a capture to look at later

```text
tcpdump -i eth0 -w capture.pcap
```
`.pcap` is the standard capture format — the same file format you'd open
in a GUI copy of Wireshark, or read back with `tshark -r`.

## tshark: read a capture with protocol decode

```text
tshark -r capture.pcap
```
Where `tcpdump`'s line for an HTTP request is mostly raw bytes, `tshark`
recognizes the protocol and prints something closer to "GET /login
HTTP/1.1" directly.

Filter while reading:
```text
tshark -r capture.pcap -Y "http"           # display filter: only HTTP
tshark -r capture.pcap -Y "ftp"            # only FTP control traffic
```

## Pulling out a specific field across every matching packet

```text
tshark -r capture.pcap -Y "http.request" -T fields -e http.request.method -e http.request.uri
```
`-T fields -e ...` is tshark's way of saying "don't show me the whole
decoded packet, just these specific columns" — useful once you know what
you're looking for and want it as a short list instead of a scroll of
packets.

## Following one TCP conversation start to finish

```text
tshark -r capture.pcap -q -z follow,tcp,ascii,0
```
Reassembles stream `0` (the first TCP conversation in the file) into the
actual bytes exchanged, in order — closer to "what did the two sides
actually say to each other" than packet-by-packet output.

## Live capture with either tool

Both can also read live instead of from a file (`tcpdump -i eth0`, `tshark
-i eth0`) — a saved `.pcap` is just the same data frozen so you can filter
and re-read it without missing anything.
