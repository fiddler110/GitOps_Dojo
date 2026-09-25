---
marp: true
theme: default
paginate: false
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Hub](index.md)'
---

<!-- _class: lead lab-index -->

# Labs

<p class="nav">Everything for this workshop's labs, in one place — pick a lab below, or start with the overview.</p>

<div class="cards">
<div>
<h3><a href="labs.md">Lab overview &rarr;</a></h3>
<p>Tracks, timing, and what to expect before you start.</p>
</div>
<div>
<h3><a href="assets/lab-reader.html?file=README.md.txt">Full lab README &rarr;</a></h3>
<p>The complete lab guide, read right here in the browser.</p>
</div>
</div>

<p class="setup-label">Every lab needs the step CLI to trust the CA (Lab 1). Run this once, whichever lab you start from:</p>

```sh
step ca bootstrap --ca-url https://step-ca:9443 \
  --fingerprint "$(step certificate fingerprint /opt/step-ca-root/root_ca.crt)"
```

<ul class="lab-links">
<li><a href="assets/lab-reader.html?file=lab1.md.txt">Lab 1</a><span class="topic">Trusting the CA: bootstrap, inspect the root cert</span></li>
<li><a href="assets/lab-reader.html?file=lab2.md.txt">Lab 2</a><span class="topic">Issue and install a certificate with certbot</span></li>
<li><a href="assets/lab-reader.html?file=lab3.md.txt">Lab 3</a><span class="topic">The same task with acme.sh</span></li>
<li><a href="assets/lab-reader.html?file=lab4.md.txt">Lab 4</a><span class="topic">Automating renewal, and watching it happen</span></li>
<li><a href="assets/lab-reader.html?file=lab5.md.txt">Lab 5</a><span class="topic">Capstone: the dns-01 challenge</span></li>
<li><a href="assets/lab-reader.html?file=cheat-sheet.md.txt">Cheat sheet</a><span class="topic">Every command, plain text</span></li>
</ul>
