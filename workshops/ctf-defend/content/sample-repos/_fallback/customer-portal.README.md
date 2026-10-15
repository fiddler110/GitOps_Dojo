# customer-portal

An internal lookup tool for support staff: search customers by name, or log in as one. It runs live on your
slot (the address is on your landing page). The data is in a SQLite file the app builds with `seed.py`.

## Running it yourself

```sh
python3 seed.py && python3 app.py      # listens on :5000 (PORT to change it)
```

## What the platform does

- A pull request runs the **PR gate**: it starts your branch's app, tries to break it the way an attacker would,
  and sends one normal request to make sure it still works. Advisory: it never blocks the merge.
- Merging to `main` rebuilds the image and redeploys your slot in place.
- `dojo-check customer-portal` in your terminal asks the same question of your live slot.
