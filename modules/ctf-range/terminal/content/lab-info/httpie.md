# httpie

An HTTP client built to be read, not just run — colored, formatted output,
and a request syntax that skips most of `curl`'s quoting. Reaches for this
instead of `curl` whenever the response is JSON, which is most of what the
API-only targets on this range speak.

## The command is `http`, not `httpie`

```text
http GET http://$TARGET/users/1
```
`GET` is actually the default, so this works the same:
```text
http $TARGET/users/1
```

## Reading the output

```text
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": 1,
    "name": "alice",
    "role": "user"
}
```
Status line, headers, then a body that's pretty-printed and
syntax-highlighted automatically when it's JSON. No piping through `jq`
needed just to make it readable (though `jq` is still the right tool once
you want to *filter* or *extract* a field — see `jq.md`).

## Sending data

A `key=value` after the URL becomes a JSON body automatically (httpie sets
`Content-Type: application/json` for you):
```text
http POST http://$TARGET/users name=bob role=user
```
Sends `{"name": "bob", "role": "user"}`. Use `key:=value` for a non-string
value (number, bool, nested JSON):
```text
http POST http://$TARGET/users age:=30 active:=true
```

## Headers and auth

```text
http $TARGET/admin "Authorization:Bearer sometoken"
http -a user:pass $TARGET/secure
```

## Other HTTP methods

```text
http PATCH http://$TARGET/users/me role=admin
http DELETE http://$TARGET/users/5
```

## Seeing the request you're about to send, before it goes

```text
http --offline POST http://$TARGET/users name=bob
```
`--offline` builds and prints the request without sending it — useful for
checking exactly what headers/body httpie constructed before you fire it
at anything.
