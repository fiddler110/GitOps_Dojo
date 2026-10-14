# leaky-config

The Brightwave ops dashboard, a small Flask app.

- `GET /status` is a public health page.
- `GET /admin` and `GET /admin/logs` list the dashboard's log files; `GET /admin/logs/<name>` serves one.
  The ops team reads these.
- `GET /internal/metrics` is for the `metrics-agent` service account and needs HTTP Basic auth. It also
  holds this slot's secret.
- The app logs its own authentication problems at startup to `app.log`.

What the platform provides:

- The app is built from this repo's `Dockerfile` and listens on port 5000. There is no proxy or login in
  front of it: any request that reaches the app is anonymous unless the app checks it.
- The Basic auth check for the service account already exists in `app.py` as `_check_auth(request)`.
- Your pull request is built and tested before it can be merged; merging to `main` redeploys your slot.
- `dojo-check leaky-config` in your terminal reports whether the live app is still exploitable.
- File reads and authentication attempts appear in the security dashboard.
