# curl

The standard command-line HTTP client. Every web target on this range speaks
HTTP, so this is the tool you will reach for most. It sends exactly the
request you describe and prints exactly what comes back, which is what you
want when you are working out how a service behaves.

All examples use `$TARGET` for the host and port you are testing, for
example `10.0.0.5:5000`.

## Start by reading the front page

```sh
curl -s http://$TARGET/
```
`-s` hides the progress meter so only the response body prints. A service's
front page often lists what it offers: links, forms, route names. Read it
before you guess at anything.

## Reading the response, not just the body

```sh
curl -si http://$TARGET/some/path
```
`-i` adds the status line and headers. The status code tells you what the
server thinks of your request:

| Code | Usually means |
|---|---|
| `200` / `201` | worked / created something |
| `301` / `302` | go somewhere else (see the `Location` header) |
| `400` | the request was malformed: read the message, it often names what is missing |
| `401` | authentication needed: check the `WWW-Authenticate` header for the scheme |
| `403` | the server understood you and refused: who you are, or what you sent, was not allowed |
| `404` | nothing at that path |

Only the code, for scripting or quick checks:

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://$TARGET/some/path
```

`-v` shows the whole exchange, request included. Use it when a request
behaves differently from what you expected.

## Sending data

A form submission (`application/x-www-form-urlencoded`):

```sh
curl -s -X POST http://$TARGET/form -d 'field=value&other=value2'
```

Values with spaces or special characters need encoding. Let curl do it:

```sh
curl -s -X POST http://$TARGET/form --data-urlencode 'field=some value & more'
```

A JSON body. The `Content-Type` header matters: many services ignore a JSON
body that is not labelled as JSON, and answer as if you sent nothing:

```sh
curl -s -X POST http://$TARGET/api/things \
  -H 'Content-Type: application/json' \
  -d '{"name": "example", "tags": {"key": "value"}}'
```

A request body from a file, such as a certificate or a document:

```sh
curl -s -X POST http://$TARGET/upload --data-binary @file.pem
```

`PATCH`, `PUT` and `DELETE` work the same way with `-X`.

## Credentials

HTTP Basic authentication (a username and password):

```sh
curl -s -u 'username:password' http://$TARGET/protected
```

A bearer token, or any custom header:

```sh
curl -s -H 'Authorization: Bearer <token>' http://$TARGET/protected
curl -s -H 'X-Some-Header: value' http://$TARGET/protected
```

Cookies: save them from one request and send them on the next:

```sh
curl -s -c jar.txt -d 'username=a&password=b' http://$TARGET/login
curl -s -b jar.txt http://$TARGET/account
```

## Working with JSON responses

Pipe the body to `jq` (see [`jq.md`](jq.md)) to read or pick fields:

```sh
curl -s http://$TARGET/api/things | jq .
curl -s http://$TARGET/api/things | jq -r '.items[].name'
```

## When a request does not do what you expect

1. Add `-i` and read the status line and headers, not only the body.
2. Check the method (`-X`) and the path, including a trailing slash.
3. For a JSON body, check the `Content-Type` header and that the JSON is valid.
4. Read the error message in the body. A `400` or `403` often says exactly
   what it wanted.
