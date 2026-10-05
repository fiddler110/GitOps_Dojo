# jq

A filter for JSON, the same way `grep` is a filter for text lines. You pipe
JSON in, write a short expression for the shape you want out, and get JSON
(or plain text) back.

## The identity filter

```text
echo '{"id": 1, "name": "alice"}' | jq .
```
`.` just means "the whole thing," pretty-printed. Start every exploration
here to see what you're actually working with.

## Picking a field

```text
echo '{"id": 1, "name": "alice", "role": "user"}' | jq '.name'
"alice"
```
Chain fields with more dots: `.user.address.city`.

## Arrays

```text
echo '[{"id":1,"name":"alice"},{"id":2,"name":"bob"}]' | jq '.[0]'       # first element
echo '[{"id":1,"name":"alice"},{"id":2,"name":"bob"}]' | jq '.[].name'   # just the names, one per line
echo '[{"id":1,"name":"alice"},{"id":2,"name":"bob"}]' | jq 'length'     # how many elements
```

## Filtering with `select`

```text
echo '[{"id":1,"role":"user"},{"id":2,"role":"admin"}]' | jq '.[] | select(.role == "admin")'
```
Keeps only the elements matching the condition — the JSON equivalent of
`grep`.

## Raw output (no quotes) for scripting

```text
curl -s http://$TARGET/users/1 | jq -r '.name'
alice
```
`-r` strips the surrounding `"..."` so the value is a plain string, safe
to drop straight into a shell variable or another command.

## Building a quick pipeline

```text
curl -s http://$TARGET/users | jq -r '.[] | select(.role == "admin") | .id'
```
Fetch a list, keep only admins, print just their ids, one per line — the
same "small pieces chained with pipes" idea from the Linux primer, just
with a JSON-aware filter in the middle instead of `grep`.

## httpie already formats JSON for you

If you only need to *look* at a response, `httpie.md`'s formatted output
is often enough on its own. Reach for `jq` once you need to extract or
filter a specific value, especially inside a script.
