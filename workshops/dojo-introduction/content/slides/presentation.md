---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
    @import url('assets/themes/presentation.css');
    .split { align-items: center; display: flex; gap: 48px; }
    .split > div { flex: 1; min-width: 0; }
    .split-40 > div:first-child { flex: 0 0 40%; }
    .split-60 > div:first-child { flex: 0 0 58%; }
    .mermaid { text-align: center; margin: 8px 0; }
    .mermaid:not([data-processed]) { visibility: hidden; }
    .mermaid svg { max-height: 420px; }
    .mermaid foreignObject p, .mermaid foreignObject div { margin: 0 !important; line-height: 1.35 !important; }
    .small { font-size: 0.85em; }
    .lede { color: var(--muted); font-size: 0.9em; }
footer: "[&larr; Hub](index.md) &nbsp;|&nbsp; Dojo Introduction | Engineering & IT Operations"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# GitOps Dojo

## A hands-on lab platform, from one URL

How it works, and what it can do

<!--
This is a look-at-this-cool-thing talk. Aim for 20 minutes, then click around: the last slide is a route through the
student view and the facilitator view.
-->

---

## The problem it solves

Hands-on training usually loses its first half hour to setup:

- "Which version of the tool do I need?" · "It works on my laptop."
- Installs blocked by corporate laptops, VPNs and proxies
- Shared accounts, stepping on each other's work
- The facilitator can't see who is stuck

> **One URL. Nothing to install. Everyone gets a real, private lab.**

---

## What a student gets

<div class="split split-40">
<div>

Open one address, type a name, and you have:

- **VS Code** in the browser
- a **terminal**
- a **git server** (Forgejo)
- the **slides** and lab guides
- whatever the workshop adds: a vault, a DNS server, a cloud

</div>
<div>

<div class="mermaid">
flowchart TB
  u["Browser"] --> l["One URL"]
  l --> id["Assigned an account<br/>(student07)"]
  id --> ide["VS Code"]
  id --> t["Terminal"]
  id --> g["Forgejo"]
  id --> s["Slides + labs"]
  id --> x["Workshop extras"]
</div>

</div>
</div>

---

## What the facilitator gets

The **/admin** workspace, behind its own login. Whatever a student can reach, the facilitator can too.

| Tab | What it is |
| --- | ---------- |
| **Roster** | A tile per student: status, a read-only view of their terminal, **Release** |
| **VS Code, Terminal, Forgejo, Slides** | The facilitator's own copies of the tools |
| **Workshop tabs** | Added by the workshop: Vault, Audit, Runners, DNS Admin, ... |
| **Status strip** | Green when each service answers |


---

## The whole picture

<div class="mermaid">
flowchart LR
  b["Browser"] --> gw["gateway (Caddy)<br/>the only door"]
  subgraph net["Internal networks: nothing here is reachable from outside"]
    al["allocator<br/>who is this?"]
    wt["web-terminal<br/>VS Code + terminal<br/>per account"]
    fg["Forgejo<br/>git + Actions"]
    pr["presentation<br/>Marp slides"]
    ex["workshop services<br/>vault, DNS, cloud, ..."]
  end
  gw --> al
  gw --> wt
  gw --> fg
  gw --> pr
  gw --> ex
  wt --> fg
  al -.-> wt
</div>

<p class="small">Everything is a container on internal networks. Only the gateway has a port to the outside.</p>

---

## How a request is checked

<div class="mermaid">
sequenceDiagram
  actor S as Browser
  participant G as gateway
  participant A as allocator
  participant W as web-terminal
  S->>G: /ide/ (class login + cookie)
  G->>A: who is this?
  A-->>G: student07, port 9007
  G->>W: proxy to that student's VS Code
  W-->>S: already signed in, no prompt
</div>

The gateway asks the allocator on **every** request, and it sets the identity headers itself. A client can't send its own.

---

## Names, slots and accounts

- The first person to type a name gets **studentNN**, claimed atomically; it sticks to that browser
- Each account is a real Linux user with its own home, VS Code and terminal process
- Forgejo has a matching user, in a team with write access to the workshop repo
- The facilitator's login can never be handed a student slot

<div class="mermaid">
flowchart LR
  bs["bootstrap<br/>(one-shot)"] --> o["org + repo + seed content"]
  bs --> u["student01 ... studentNN"]
  bs --> t["team with write access"]
</div>

---

## Three layers, so a new workshop is mostly content

<div class="split">
<div>

**engine/**
The shared runtime. Knows nothing about any one workshop.

**modules/**
Reusable pieces: a vault, a CI runner pool, a cloud, a DNS viewer. Each is a folder of compose file, front-door manifest and terminal tools.

**workshops/**
A pack: slides, labs, a seed repo, and the list of modules it wants.

</div>
<div>

```text
./run.sh dns-as-code
        │
        ├─ engine           always
        ├─ modules          MODULES="..."
        └─ workshop pack    content + extras
```

</div>
</div>

<!-- Adding a workshop never edits the engine. -->

---

## Front doors are declared, not hand-wired

A workshop or module ships an `extensions.json`:

```json
{ "cards":       [{ "id": "dns", "label": "DNS Zones", "href": "/dns/", "icon": "dns" }],
  "admin_tabs":  [{ "id": "dns", "label": "DNS Zones", "src": "/dns/" }],
  "routes":      [{ "id": "dns", "path": "/dns", "upstream": "zone-viewer:8080", "gate": "shared" }],
  "status_checks": [{ "label": "DNS Zones", "url": "http://zone-viewer:8080/dns/readyz" }] }
```

The engine turns it into the landing card, the facilitator tab, the gateway route and the status light, through **fixed templates**. A manifest can't inject raw config, and a bad one stops the start.

---

## Three gates

| Gate | Who gets through | The service receives |
| ---- | ---------------- | -------------------- |
| `shared` | anyone with the class login | no identity |
| `identity` | a student with a slot, or the facilitator | who they are, set by the gateway |
| `facilitator` | the facilitator only | who they are, set by the gateway |

<p class="lede">A service behind `identity` or `facilitator` still checks a shared token, because students can reach the internal network directly and only the gateway holds the token.</p>

---

## The terminal is built from layers

<div class="mermaid">
flowchart LR
  base["base image<br/>VS Code, ttyd, git"] --> m1["+ module tools<br/>bao, the cloud broker"]
  m1 --> w["+ workshop tools<br/>dnscontrol, step, tofu, sops"]
  w --> run["the image the class runs"]
</div>

- Student terminals have **no internet**: every tool is baked in, version-pinned and checksum-verified
- Start-up jobs run as small hooks after the accounts exist
- No `docker.sock` in any terminal, ever

---

## Keeping students in their lane

- Each student is a separate Linux user with a private home
- Students can reach the internal network, so **nothing trusts a source address**; services check the gateway's token, or a per-student credential
- Anything a student types is shown to the class as **text only**, with a strict content policy
- CI jobs run on runners that hold no control-plane access
- Every external image is pinned by digest

---

## The workshops

| Workshop | What it teaches |
| -------- | --------------- |
| **Git Fundamentals** | clone, branch, commit, push, pull request, undo, merge |
| **DNS as Code** | DNS records in git with dnscontrol, review, and a CI preview |
| **Certificate Autorenewal** | ACME with step-ca, certbot and acme.sh; renewal you can watch |
| **OpenTofu Basics** | init / plan / apply / destroy against Dojo Cloud |
| **Vault Fundamentals** | secrets out of code, git and pipelines; OpenBao |

All five are on the **Workshop library** page, each with its slides, labs and a cheat sheet.

---

## Modules: reusable building blocks

| Module | What it brings |
| ------ | -------------- |
| `forgejo-runner` | Forgejo Actions with one runner |
| `runner-pool` | single-use CI runners, scaled by a controller, and a **Runners** panel |
| `openbao` | OpenBao, its UI, sign-in with your Forgejo account, an audit view |
| `dojo-cloud` | an Azure-inspired training cloud: ARM-style API, portal, real containers |
| `dns-ui` | a live DNS Zones page, and PowerDNS-Admin for the facilitator |

---

## CI that can't hurt anything

<div class="mermaid">
flowchart LR
  push["git push"] --> fg["Forgejo Actions"]
  fg --> ctl["controller<br/>starts a runner"]
  ctl --> r["single-use runner<br/>own Linux user"]
  r --> job["the job"]
  job --> gone["runner + user deleted"]
</div>

- One job per runner, then it is deleted
- Runs on its own network, with no route to the control plane
- The facilitator's **Runners** tab shows the pool and its health

---

## The vault: OpenBao

<div class="split">
<div>

- Real OpenBao, the open-source Vault
- Sign in **with your Forgejo account**, in the UI and the CLI; no password to hand out
- A **namespace per student**, and a shared policy
- CI logs in with its **own identity**, not a stored secret
- The facilitator's **Audit** tab: every request, by student and path

</div>
<div>

```sh
bao status
bao kv get secret/students/$USER/welcome
```

```text
Key         Value
---         -----
Sealed      false
```

</div>
</div>

---

## DNS and certificates

<div class="mermaid">
flowchart LR
  git["dnsconfig.js in git"] --> dc["dnscontrol"]
  dc --> pdns["PowerDNS"]
  pdns --> zv["DNS Zones page"]
  pdns --> ca["step-ca<br/>checks names"]
  ca --> cert["short-lived certificate"]
  cert --> web["demo site"]
</div>

- Records are **declared in git** and pushed; a dashboard edit is undone by the next push
- The CA issues certificates in minutes, so renewal is something you can watch

---

## Dojo Cloud

An Azure-*inspired* cloud made for training: the same tools and workflow, nothing to pay for.

<div class="mermaid">
flowchart LR
  tofu["tofu apply"] --> api["cloud-api<br/>ARM-style API + portal"]
  api --> host["cloud-host<br/>real containers"]
</div>

- Students use the real `azurerm` provider, with their own credentials handed to the shell, never written in a file
- A policy layer enforces names, regions and tags, like a real landing zone
- The portal shows what each student deployed

---

## Practice without a class: demo bots

`./run.sh <workshop> --test 20` adds 20 demo students that work through a workshop's labs on their own.

- A full roster to look at, and real load on the stack
- Each workshop can supply its own bot script

It is how the platform is checked before a live session.

---

## Running it

```sh
./run.sh setup                  # first time: accounts and secrets
./run.sh list                   # the workshops
./run.sh dojo-introduction      # this tour
./run.sh dns-as-code --test 20  # a workshop with 20 demo students
./run.sh stop                   # removes every container and volume
```

- **Localhost** for a demo, or a hostname with TLS for a room full of people
- Runs on rootless podman or docker

---

## Your turn: a route through it

<div class="split">
<div>

**As a student**

1. Type a name at the landing page
2. **VS Code**: open `~/lab/tools-tour.md`
3. **Forgejo**: the `dojo-tour` repository
4. **Vault** (OpenBao): sign in with Forgejo
5. **DNS Zones**, **Dojo Cloud**
6. **Workshop Library**

</div>
<div>

**As the facilitator**

1. Sign in at `/admin`
2. **Roster**: watch a terminal
3. **Runners**: a job comes and goes
4. **Audit**: the vault's request log
5. **DNS Admin**: a dashboard edit
6. The status strip

</div>
</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Questions?

## Then let's click around

[Workshop library](workshops.md) · [Tool tour](lab-index.md)

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    fontFamily: "Manrope, sans-serif",
    flowchart: { htmlLabels: true, curve: "basis" },
    sequence: { mirrorActors: false, actorFontSize: 18, messageFontSize: 18, noteFontSize: 18, boxMargin: 8 },
    themeVariables: {
      fontSize: "18px",
      background: "#18242e",
      primaryColor: "#21313c",
      primaryTextColor: "#e8f0f2",
      primaryBorderColor: "#3dd6c3",
      secondaryColor: "#18242e",
      tertiaryColor: "#18242e",
      lineColor: "#a9bac2",
      edgeLabelBackground: "#18242e",
      clusterBkg: "#18242e",
      actorBkg: "#21313c",
      actorBorder: "#3dd6c3",
      actorTextColor: "#e8f0f2",
      signalColor: "#a9bac2",
      signalTextColor: "#e8f0f2",
      noteBkgColor: "#137f7a",
      noteTextColor: "#e8f0f2",
      noteBorderColor: "#3dd6c3",
    },
  })
  // Mermaid sizes each box from the text it measures, so it must measure
  // unscaled, in the real font. mermaid.run() measures inside the slide,
  // which Marp scales to the window: a window smaller than 1280x720 got boxes
  // too small and labels cut off. mermaid.render() draws in a scratch element
  // on <body> instead; the finished SVG then goes into the slide.
  async function draw() {
    const decode = document.createElement("textarea")
    let n = 0
    for (const el of document.querySelectorAll(".mermaid:not([data-processed])")) {
      decode.innerHTML = el.innerHTML
      const src = decode.value.replace(/<br\s*\/?>/gi, "<br/>").trim()
      const { svg, bindFunctions } = await mermaid.render(`mermaid-${n++}`, src)
      el.innerHTML = svg
      bindFunctions?.(el)
      el.setAttribute("data-processed", "true")
    }
  }
  document.fonts.load('18px Manrope').catch(() => {}).then(() => document.fonts.ready).then(draw)
</script>
