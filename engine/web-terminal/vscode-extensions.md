# code-server extension trim

Reference for what's been removed from the stock code-server install in
`Dockerfile`, why, and how to add something back for a future workshop.
Keep this in sync with the `rm -rf` list in `Dockerfile` whenever either
changes -- this file is documentation, not enforced by anything.

## Target experience

Student workspace is meant to cover exactly: browse files (Explorer), open
and edit them, preview markdown, and use a terminal. Git is a first-class
part of every workshop and is used heavily (both via the CLI and, per this
trim, the built-in Source Control panel/decorations) -- it is deliberately
**kept**, not treated as extra weight. Nothing else (debugging, task
runners beyond the one shell task, notebooks, embedded browser, PHP) is
needed today.

## Removed (deleted at build time, `Dockerfile`)

| Extension | What it backs | Why it's gone |
|---|---|---|
| `copilot`, `copilot-chat` | AI chat/inline-suggest | Can't function anyway -- no network route out once the stack is up (see `docker-compose.yml`'s internal-only networks) |
| `microsoft-authentication`, `github-authentication` | Sign-in flows that back Copilot/Settings Sync | Same reason -- nothing to authenticate against with no egress |
| `mermaid-markdown-features` | Mermaid diagram rendering in markdown preview | No lab content uses mermaid diagrams (checked `workshops/*/content`) |
| `debug-auto-launch`, `debug-server-ready` | Run & Debug helpers (auto-attach, launch-on-ready) | No workshop has a launch config; nothing to debug |
| `ms-vscode.js-debug`, `ms-vscode.js-debug-companion`, `ms-vscode.vscode-js-profile-table` | JavaScript/Node debugger, its browser-attach companion, and the CPU-profile viewer that ships with it | Same reason -- no workshop debugs anything, and there's no JS in the labs |
| `ms-python.debugpy` (curated set, see below) | Python debugger, pulled in as a soft `extensionPack` companion of `ms-python.python` | Same reason. Not an `extensionDependency`, so `ms-python.python` still works without it (syntax highlighting / basic support is all it gives here anyway) |
| `node_modules/@github/copilot*` (not an extension -- code-server's own runtime deps) | Copilot's ~137 MB native runtime and SDK, loaded only by the AgentHost feature | Removing the `copilot`/`copilot-chat` extensions above doesn't touch this; it's a separate ~137 MB. Verified code-server still starts and serves the workbench without it |
| `npm` | "NPM SCRIPTS" Explorer section + npm task provider | No workshop has a `package.json` |
| `simple-browser` | "Open with Simple Browser" embedded webview command | Unused; `presentation` service and Forgejo are opened in the real browser, not embedded |
| `php`, `php-language-features` | PHP syntax highlighting/IntelliSense | No lab content has `.php` files |
| `ipynb`, `notebook-renderers` | Jupyter notebook (`.ipynb`) file format + output rendering | No lab content has notebooks |

## Explicitly kept (do not remove without checking with the facilitator first)

- `git`, `git-base`, `merge-conflict` -- Source Control panel, inline diff
  gutters/decorations, Timeline entries. Git is used heavily across every
  workshop; this is core to the experience, not dead weight.
- `html`, `html-language-features`, `css-language-features` -- kept even
  though no current lab content uses HTML/CSS, in case a future workshop
  does. Cheap to keep; revisit if that stays true for a long time.
- All other language grammar/basics extensions (`yaml`, `json`,
  `json-language-features`, `python`, `shellscript`, `markdown-basics`,
  `markdown-language-features`, `ini`, `log`, `docker`, `xml`, `sql`, etc.)
  -- needed for legible syntax highlighting when viewing/editing lab files.
- `markdown-language-features` specifically backs the built-in markdown
  preview students use -- required, do not touch.

## Curated (non-built-in) extensions installed separately

Fetched from Open VSX and installed into the shared, read-only
`/opt/code-server-extensions` dir -- see the `fetch_ext` block in
`Dockerfile` for versions/hashes and how to add one:

- `redhat.vscode-yaml`
- `GitHub.github-vscode-theme` (the `GitHub Dark` theme set in
  `entrypoint.sh`'s shipped `settings.json`)
- `ms-python.python`

(`ms-python.debugpy` is deliberately absent even though installing
`ms-python.python` pulls it in -- see the removed table above.)

`ms-python.python`'s Jedi language server is switched off too
(`"python.languageServer": "None"` in the shipped `settings.json`, see
`entrypoint.sh`): it costs ~75MB per account that opens a `.py` file
(measured), and only completion/hover depend on it -- syntax highlighting
doesn't. Delete that line from both `settings.json` heredocs to get it
back.

## Adding something back to the shared base image (every workshop)

Only do this if the extension is genuinely useful to *every* workshop —
otherwise use the per-workshop override below instead, per
`workshops/README.md`'s "reach for this only when..." guidance.

1. Delete its line from the `rm -rf \` list in `Dockerfile` (or add a
   `fetch_ext` line if it's a Marketplace/Open VSX extension, not a
   built-in).
2. Update the tables above.
3. Rebuild: `./run.sh <workshop-name>` from `engine/` (rebuilds the base
   `web-terminal` image).

## Installed by one workshop, not the base image

- `tofu-basics` installs the OpenTofu extension (`opentofu.vscode-opentofu`, HCL highlighting for `.tf` and `.tfvars`)
  in its own terminal image (`workshops/tofu-basics/compose/terminal/Dockerfile`). The base image still ships no
  Terraform/OpenTofu tooling, so the `hashicorp.terraform` note in `Dockerfile` remains true for every other workshop.

## Adding something for one workshop only

The base image is built and tagged `gitopsdojo/web-terminal:base` before
any workshop overlay builds (see `engine/run.sh` and the comment on the
`web-terminal` service in `engine/docker-compose.yml`) specifically so a
workshop can extend it without touching this Dockerfile or affecting any
other workshop. `dns-as-code` and `cert-autorenewal` already do this for
extra CLI tools (`dns-as-code/compose/terminal/Dockerfile`,
`cert-autorenewal/compose/terminal/Dockerfile`) — the same pattern works
for a VS Code extension the base image deliberately doesn't carry.

Worked example: a hypothetical `mermaid-as-code` workshop that needs
Mermaid diagram rendering in the markdown preview (removed from the base
image above as `mermaid-markdown-features`, since no current workshop uses
it). The same extension is published standalone on Open VSX by its
original author, under a different id, specifically for cases like this
one where it isn't bundled:

`workshops/mermaid-as-code/compose/terminal/Dockerfile`:
```dockerfile
FROM gitopsdojo/web-terminal:base

# Re-adds Mermaid rendering to the built-in markdown preview for this
# workshop only -- deliberately not in the shared base image (see
# engine/web-terminal/vscode-extensions.md). Find the current version +
# sha256 on open-vsx.org (same steps as the fetch_ext block in
# engine/web-terminal/Dockerfile) before filling these in.
RUN set -eux; \
    wget -O /tmp/markdown-mermaid.vsix \
      "https://open-vsx.org/api/bierner/markdown-mermaid/<version>/file/bierner.markdown-mermaid-<version>.vsix"; \
    echo "<sha256>  /tmp/markdown-mermaid.vsix" | sha256sum -c -; \
    code-server --extensions-dir /opt/code-server-extensions \
        --install-extension /tmp/markdown-mermaid.vsix --force; \
    rm -f /tmp/markdown-mermaid.vsix

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
```

`workshops/mermaid-as-code/compose/docker-compose.override.yml`:
```yaml
services:
  web-terminal:
    build:
      context: ../workshops/mermaid-as-code/compose/terminal
```

Then point `COMPOSE_OVERLAY` at that file in the workshop's
`workshop.env`, per `workshops/README.md`'s "Adding a new workshop" steps.
No change to `engine/` at all, and no other workshop's image is affected.

## Known limitation (not being worked around)

Search, Source Control, Run & Debug, and Extensions icons in the Activity
Bar are core VS Code workbench UI, not extension contributions -- deleting
the extension behind one only removes its *functionality*; if a future
change removes Search/Run&Debug/Extensions-backing extensions again, their
icons will stay visible but empty. There's no supported
`settings.json`/`product.json` way to hide them without a custom
`product.json` patch, which isn't worth the added per-code-server-version
maintenance burden here.
