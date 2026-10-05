# Linux and shell primer

If you've never used a Linux terminal before, start here. Everything else in
Lab Info assumes you can already do what's on this page.

## Finding your way around

```text
pwd                 # where am I
ls -la               # what's here, including hidden files and permissions
cd some/dir          # go there
cd ..                # go up one level
cd ~                 # go home
cat file.txt         # print a file
less file.txt        # page through a file ('q' to quit, '/word' to search)
```

## Pipes: the one idea that matters most

A pipe (`|`) sends one command's output straight into the next command's
input, so you can build a small chain of simple tools instead of one
complicated one:

```text
cat access.log | grep "POST" | wc -l
```

Reads as: print the file, keep only lines containing `POST`, count the
lines. Each tool does one thing; the pipe is the glue. `grep`, `jq` (JSON),
`sort`, `uniq -c`, `head`, `tail` are the pipe-stage tools you'll reach for
constantly:

```text
cat access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head
```
Same idea, bigger chain: print the file, keep just the first column (often
the client IP in a default access-log format), sort it, collapse duplicates
into counts, sort by count descending, show the top few.

## grep basics

```text
grep "needle" haystack.txt      # lines containing "needle"
grep -i "needle" haystack.txt   # case-insensitive
grep -v "needle" haystack.txt   # lines that DON'T match
grep -c "needle" haystack.txt   # just a count
grep -rn "needle" some-dir/     # recursive, with line numbers
```

## File permissions, briefly

```text
ls -l file
-rw-r--r-- 1 alice alice 220 Jan  1 00:00 file
```
The first character is the type (`-` regular file, `d` directory, `l`
symlink). Then three groups of three: owner / group / everyone-else, each
`r`/`w`/`x` (read/write/execute, or enter-this-directory for a directory).
`chmod 600 file` sets owner-only read+write — the pattern you'll see used
for anything holding a secret.

## Processes

```text
ps aux               # everything running, with owner and command
ps aux | grep nginx   # narrow it down
kill <pid>           # ask a process to stop
kill -9 <pid>        # force it
```

## Networking basics you'll need everywhere below

- An **IP address** identifies a host; a **port** (0-65535) identifies one
  service on that host. `10.0.0.5:8080` means "port 8080 on that host."
- **TCP** is connection-oriented and reliable (web, SSH, most things); **UDP**
  is connectionless and fire-and-forget (DNS queries, by default). A tool
  that scans or listens usually needs to know which one you mean.
- Common ports you'll recognize in output: 22 (SSH), 53 (DNS), 80/443
  (HTTP/HTTPS), 3306/5432 (MySQL/Postgres). A port being open just means
  something is listening there — it says nothing about whether that
  something is safe.

## HTTP request anatomy

Every request has a **method** (`GET` to fetch, `POST` to submit, `PATCH`
to partially update, ...), a **path** (`/users/42`), **headers** (metadata —
`Content-Type`, `Authorization`, cookies), and sometimes a **body** (the
submitted data, often JSON). A response has a **status code** (`200` ok,
`301`/`302` redirect, `401`/`403` auth problems, `404` not found, `500`
server error) plus its own headers and body. `httpie.md` and `jq.md` cover
reading these comfortably from the command line.

## The legal boundary (repeated here on purpose)

Point every tool in this library only at `target-NN` — your own target on
this range. The firewall enforces it (a scan of the subnet shows exactly one
live host), but the rule exists independently of the enforcement: these are
real tools, and using them against anything you don't own or aren't
explicitly authorized to test is illegal outside this range.
