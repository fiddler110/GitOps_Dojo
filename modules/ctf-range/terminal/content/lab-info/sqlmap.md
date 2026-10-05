# sqlmap

An automated tool for finding and confirming SQL injection in a URL
parameter, a form field, or an HTTP header — it sends a structured series
of probe requests and watches how the responses change to tell injectable
input apart from input that's handled safely.

This primer covers flags and how to read the output. It does not walk
through finding or exploiting a real vulnerability — that's the lab's job,
not this library's (see the top-level Lab Info README for why).

## Pointing it at a request

```text
sqlmap -u "http://$TARGET/search?q=test"
```
sqlmap treats `q`'s value as the thing to test, sends a battery of probes
varying it, and reports what it finds. Run against a parameter that
*isn't* injectable (most ordinary, well-written code), it correctly
reports nothing — that's expected, not a failure of the tool.

For a request that isn't a simple `GET` — a login form `POST`, say — give
it the whole request instead of trying to express it as a URL:
```text
sqlmap -r request.txt
```
where `request.txt` is a raw HTTP request (headers and body) saved from
`httpie --offline` or captured with `tcpdump`/`tshark`. `--data` works too
for a quick one-off `POST` body:
```text
sqlmap -u "http://$TARGET/login" --data "username=test&password=test"
```

## Reading the output

```text
[INFO] testing connection to the target URL
[INFO] testing if GET parameter 'q' is dynamic
[WARNING] GET parameter 'q' does not appear to be dynamic
[INFO] heuristic (basic) test shows that GET parameter 'q' might be injectable
[INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[INFO] GET parameter 'q' is 'AND boolean-based blind...' injectable
```
sqlmap narrates its own reasoning as it goes: first whether the parameter
even changes behavior at all ("dynamic"), then which injection *technique*
it's trying, then whether that technique succeeded. A clean report of "not
injectable" after a full pass is itself useful information, not a dead
end.

## Once it confirms something

```text
sqlmap -u "..." --dbs            # list databases the connection can see
sqlmap -u "..." -D mydb --tables  # tables in one database
sqlmap -u "..." -D mydb -T users --dump  # dump one table
```
Each of these is a separate, explicit step — sqlmap doesn't dump data by
default, you ask it to, each time, which is a deliberate design choice in
the tool worth noticing.

## Why this is worth automating at all

The manual version of what sqlmap does is exactly the `' OR '1'='1` style
probing the Linux/SQL fundamentals cover elsewhere in this course — sqlmap
just runs many variations, faster and more systematically than typing them
by hand, and recognizes the subtler "blind" cases (where the page looks
identical either way and only *timing* or a true/false difference gives
it away) that are easy to miss manually.
