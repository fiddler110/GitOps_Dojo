---
marp: true
theme: default
paginate: false
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
  .shelf { display: grid; gap: 14px; grid-template-columns: 1fr 1fr 1fr; margin-top: 16px; }
  .shelf > div { background: var(--surface) !important; border: 1px solid var(--line) !important; border-left: 6px solid var(--blue) !important; border-radius: 6px; padding: 10px 16px; }
  .shelf h3 { font-size: 26px !important; margin: 0 0 4px !important; }
  .shelf p { color: var(--muted) !important; font-size: 17px !important; margin: 0 !important; }
  .shelf .with { font-size: 14px !important; margin-top: 6px !important; }
footer: '[&larr; Hub](index.md)'
---

<!-- _class: lead lab-index -->

# Workshop library

<p class="nav">Five workshops, each with its slides, labs and cheat sheet. Pick one to open its own hub.</p>

<div class="shelf">
<div>
<h3><a href="w/git-fundamentals/index.md">Git Fundamentals &rarr;</a></h3>
<p>Clone, branch, commit, push and open a pull request. The base for everything else.</p>
<p class="with">Forgejo</p>
</div>
<div>
<h3><a href="w/dns-as-code/index.md">DNS as Code &rarr;</a></h3>
<p>Manage DNS records from git with dnscontrol, behind review and a CI preview.</p>
<p class="with">PowerDNS · dnscontrol · Actions</p>
</div>
<div>
<h3><a href="w/cert-autorenewal/index.md">Certificate Autorenewal &rarr;</a></h3>
<p>Issue and renew real TLS certificates with ACME: step-ca, certbot and acme.sh.</p>
<p class="with">step-ca · certbot · acme.sh</p>
</div>
<div>
<h3><a href="w/tofu-basics/index.md">OpenTofu Basics &rarr;</a></h3>
<p><code>init</code>, <code>plan</code>, <code>apply</code>, <code>destroy</code> and repo layout, on Dojo Cloud.</p>
<p class="with">OpenTofu · Dojo Cloud</p>
</div>
<div>
<h3><a href="w/vault-fundamentals/index.md">Vault Fundamentals &rarr;</a></h3>
<p>Keep secrets out of code, git and pipelines: OpenBao, identity, CI logins, dynamic credentials.</p>
<p class="with">OpenBao · sops · runners</p>
</div>
<div>
<h3><a href="index.md">Dojo Introduction &rarr;</a></h3>
<p>This tour: how the platform is built, and all of it running at once.</p>
<p class="with">Everything above</p>
</div>
</div>
