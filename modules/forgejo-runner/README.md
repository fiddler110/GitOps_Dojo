# forgejo-runner module

A Forgejo Actions runner for the workshop repo, so the sample repo's
`.forgejo/workflows/` run on every push and pull request. Add it with
`MODULES="forgejo-runner"` in a `workshop.env`.

| Part | What it does |
|---|---|
| `compose.yml` | Turns on Actions in `git-server`, adds `runner-setup` (one-shot registration) and `forgejo-runner`, the `runner_config` and `runner_data` volumes and the internal `runner_net` network. |
| `runner/register.sh` | Registers the runner server-side, scoped to `${FORGEJO_ORG}/${FORGEJO_REPO}`, with the label `host`. |
| `runner/Dockerfile` | Default runner image: upstream runner plus `curl` and `jq`. |

**Settings** (set in `workshop.env`): `RUNNER_NAME`, default `<FORGEJO_REPO>-runner`.

**Workflows** use `runs-on: host`. Jobs run inside the runner container, not in
job containers (there is no docker.sock in this stack), so every tool a job
calls must be in the runner image.

**Adding tools for your workshop's jobs**: build your own image and point the
service at it from your overlay:

```yaml
services:
  forgejo-runner:
    build:
      context: ../workshops/<name>/compose/runner
```

**Letting jobs reach a service**: the runner only sees `runner_net`. Put the
service on it too, in list form (`networks: [workshop_lab, runner_net]`).
Never put allocator or web-terminal on it: jobs run student-written code.

Used by: `dns-as-code`.
