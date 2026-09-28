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

## One URL, nothing to install

Hands-on training loses its first half hour to setup: versions, blocked installs, shared accounts, and a facilitator who can't see who is stuck.

<div class="split">
<div>

**A student** opens one address, types a name, and gets their own:

- **VS Code** and a **terminal**, in the browser
- a **Forgejo** git server account
- the **slides** and lab guides
- the workshop's extras: a vault, DNS, a cloud

</div>
<div>

**The facilitator** gets `/admin`, with everything a student can reach, plus:

- **Roster**: a tile per student, a read-only view of their terminal, **Release**
- the workshop's own tabs: Vault, Audit, Runners, DNS Admin
- a **status strip**: green when each service answers

</div>
</div>

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

<p class="small">Everything is a container. The first person to type a name gets <b>studentNN</b>: a real Linux user, and a matching Forgejo account.</p>

---

## Every request is checked

<div class="split">
<div>

<div class="mermaid">
sequenceDiagram
  actor S as Browser
  participant G as gateway
  participant A as allocator
  participant W as web-terminal
  S->>G: /ide/ (login + cookie)
  G->>A: who is this?
  A-->>G: student07, port 9007
  G->>W: that student's VS Code
</div>

</div>
<div>

- The gateway asks the allocator on **every** request
- Caddy sets the identity headers itself: a client **can't send its own**
- Students share a network, so **nothing trusts a source address**
- Student-typed text is shown to the class as **text only**

</div>
</div>

---

## Three layers: a new workshop is mostly content

<div class="split">
<div>

**engine/** the shared runtime; knows nothing about any workshop

**modules/** reusable pieces: vault, CI runners, cloud, DNS viewer

**workshops/** slides, labs, a seed repo, and the modules it wants

</div>
<div>

Each declares its front door in an `extensions.json`:

| Gate | Who gets through |
| ---- | ---------------- |
| `shared` | anyone with the class login |
| `identity` | a student with a slot, or the facilitator |
| `facilitator` | the facilitator only |

</div>
</div>

<p class="small">Cards, <code>/admin</code> tabs, routes and status lights all come from fixed templates: a manifest can't inject raw config.</p>

---

## One terminal with every tool

<div class="mermaid">
flowchart LR
  base["base image<br/>VS Code, ttyd, git"] --> m1["+ module tools<br/>bao, the cloud broker"]
  m1 --> w["+ workshop tools<br/>dnscontrol, step, tofu, sops"]
  w --> run["the image the class runs"]
</div>

- Terminals have **no internet** and no `docker.sock`: every tool is baked in, version-pinned and checksum-verified
- Each student is a separate Linux user with a private home
- Every external image is pinned by digest

---

## What is in the box

| Workshop | Teaches | Brings |
| -------- | ------- | ------ |
| **Git Fundamentals** | clone, branch, commit, PR, undo, merge | Forgejo |
| **DNS as Code** | DNS in git with dnscontrol, review, CI preview | `forgejo-runner`, `dns-ui` |
| **Certificate Autorenewal** | ACME: step-ca, certbot, acme.sh | `dns-ui` |
| **OpenTofu Basics** | init / plan / apply / destroy | `dojo-cloud` |
| **Vault Fundamentals** | secrets out of code, git and pipelines | `openbao`, `runner-pool` |

<p class="small">All five, with slides, labs and cheat sheets, are on the <a href="workshops.md">Workshop library</a>. Not running in this tour: the app host and its database (vault labs 11-13) and the DNS review flow (they need their own workshop).</p>

---

## What you can click through

| Capability | How it works | Where to look |
| ---------- | ------------ | ------------- |
| **CI** | a single-use runner per job, in its own user, on a network with no route to the control plane | Forgejo **Actions**, facilitator **Runners** |
| **Vault** | real OpenBao; sign in with Forgejo, a namespace per student, CI logs in by identity | **Vault** card, **Audit** tab |
| **DNS and certificates** | records declared in git, pushed to PowerDNS; step-ca issues short-lived certs | **DNS Zones**, **DNS Admin** |
| **Dojo Cloud** | an Azure-*inspired* cloud: ARM-style API, real containers, policy | **Dojo Cloud** card, `tofu` in the terminal |

---

## Running it, and your route through it

```sh
./run.sh setup                  # first time: accounts and secrets
./run.sh dojo-introduction      # this tour
./run.sh dns-as-code --test 20  # a workshop with 20 demo students
./run.sh stop                   # removes every container and volume
```

<div class="split">
<div>

**As a student:** type a name, open `~/lab/tools-tour.md` in **VS Code**, then **Forgejo**, **Vault**, **DNS Zones**, **Dojo Cloud**

</div>
<div>

**As the facilitator:** sign in at `/admin`, watch the **Roster**, then **Runners**, **Audit**, **DNS Admin** and the status strip

</div>
</div>

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
