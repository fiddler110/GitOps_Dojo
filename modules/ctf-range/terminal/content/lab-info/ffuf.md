# ffuf

A fast content/directory discovery tool: it takes a wordlist, substitutes
each word into a URL, and reports which substitutions get an interesting
response. The idea generalizes past "find hidden directories" — anywhere a
URL has a part you could guess, ffuf can try guesses fast.

## The core idea: `FUZZ`

You write the URL with the literal word `FUZZ` where you want substitution
to happen, and point `-w` at a wordlist:

```text
ffuf -w /usr/local/share/wordlists/common.txt -u http://$TARGET/FUZZ
```
ffuf requests `http://$TARGET/<word>` once per line in the wordlist and
prints every response, with its status code, size, and word count.

## Reading the output

```text
admin                   [Status: 403, Size: 278, Words: 42, Lines: 10]
backup                  [Status: 200, Size: 1104, Words: 210, Lines: 38]
nonexistent-word        [Status: 404, Size: 196, Words: 12, Lines: 8]
```
- A **403** found something real that exists but refuses you — worth
  noting, not necessarily worth stopping at.
- A **200** found something that actually rendered.
- Most pages will 404; that's the baseline you're filtering against.

## Filtering out the noise

A common trap: a site returns a "nice" 200-looking page for *everything*,
including words that don't exist, which buries real hits. Filter by
response size or status once you've seen the pattern:

```text
ffuf -w list.txt -u http://$TARGET/FUZZ -fs 1104     # hide responses of this exact size
ffuf -w list.txt -u http://$TARGET/FUZZ -fc 404       # hide a status code
ffuf -w list.txt -u http://$TARGET/FUZZ -mc 200,301,403  # only show these codes
```

## FUZZ isn't just for paths

```text
ffuf -w list.txt -u http://$TARGET/?id=FUZZ           # a query parameter value
ffuf -w list.txt -u http://$TARGET/ -H "X-Api-Key: FUZZ"  # a header value
```
Same mechanic, different slot.

## The wordlist that ships with this image

`/usr/local/share/wordlists/common.txt` — a small, generic set of common
web paths and usernames. It's small and generic on purpose: it teaches the
mechanic without hinting at any specific lab's answer. Feel free to add
your own words to a copy of it, or write a short list by hand for a
specific guess you want to test.

## Rate and noise

```text
ffuf -w list.txt -u http://$TARGET/FUZZ -p 0.1-0.5    # add a small random delay between requests
```
Not needed against anything on this range (it's your own target, and
there's no rate limiting to trip), but worth knowing the flag exists —
hammering a real-world target is both rude and often what gets a scan
noticed and blocked.
