# customer-portal

A small customer lookup service for a credit union, written in Flask over a SQLite database.

- `GET /` is a search form; `GET /search?q=NAME` returns the customers whose name contains `NAME` as JSON
  (`{"results": [...]}`); `POST /login` takes `email` and `password` form fields; `GET /healthz` answers `ok`.
- The database lives at `$CTF_DB_PATH` and is seeded when the container starts. The service account row
  holds this slot's secret.

What the platform provides:

- The app is built from this repo's `Dockerfile` and listens on port 5000.
- Your pull request is built and tested before it can be merged; merging to `main` redeploys your slot.
- `dojo-check customer-portal` in your terminal reports whether the live app is still exploitable.
- Request logs from your slot appear in the security dashboard.
