---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-4: Trusting the Wrong Thing | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Session mechanics, not tool tutorials

For tool mechanics (`nmap`, `curl`, `openssl`, `jq`, ...) see the **Lab Info** card -- this page is just
the commands specific to running this session.

---

## The Attack Range card

```text
Start   -- boot the target you picked; stops whichever one was live
Stop    -- tear your slot down
Reset   -- return the current target to its untouched state
```

Only one target is live in your slot at a time. The card shows your slot's **IP only** -- find the ports
yourself.

---

## Scan first, every time

```sh
nmap -sV -p- <your-slot-ip>
```

Expect more than one open port. Some are decoys -- that's by design, not a bug in the range.

---

## Submit a flag

```sh
dojo flag '<flag>'
```

The flag names its own target, so there is nothing else to type. You can also paste it into the **Found a flag?** box on your landing page. Target names are the short names on the card or Lab 3's own repo: `dns-resolver-cve` (two separate submissions --
`dns-resolver-cve-token` for the captured credential, `dns-resolver-cve` for the replay), `policy-bypass`.

---

## Core commands: look around

```sh
nmap -sV -p- <ip>                           # open ports and services
curl -s http://<ip>:<port>/                 # read the front page first
curl -si http://<ip>:<port>/<path>          # plus status line and headers
ffuf -w /usr/local/share/wordlists/common.txt \
     -u http://<ip>:<port>/FUZZ -fc 404 -ic # guess paths
```

Read links, forms and page source before you guess. When `ffuf` finds a section, run it again one level
down (`/<section>/FUZZ`).

---

## Core commands: send a request

```sh
curl -s -X POST <url> -d 'a=1&b=2'                                    # form
curl -s -X POST <url> -H 'Content-Type: application/json' \
     -d '{"name": "x"}'                                              # JSON body
curl -s -u 'user:pass' <url>                                         # HTTP Basic
curl -s -H 'Authorization: Bearer <token>' <url>                     # token header
curl -s -X POST <url> --data-binary @file.pem                        # raw body
```

Cookies: `-c jar` saves them, `-b jar` sends them back.

---

## Core commands: read the answer

```text
400 malformed: read the message      401 needs credentials: see WWW-Authenticate
403 understood, refused              404 nothing there
```

```sh
curl -s <url> | jq .                         # pretty-print JSON
curl -s <url> | jq -r '.items[].name'        # pick fields
printf '%s' 'text' | sha256sum               # hash a string
echo '<b64>' | base64 -d                     # decode base64
```

More on every tool is on the **Lab Info** card (`curl`, `jq`, `ffuf`, `nmap`).
