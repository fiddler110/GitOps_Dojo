---
marp: true
theme: default
paginate: false
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
  /* 13 labs + the cheat sheet: four columns keep the list on the slide. */
  section.lab-index .lab-links { columns: 4 !important; }
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

<p class="setup-label">Every lab works in your fork of the starter repo (Lab 0). Make it once, or run <code>lab-prep N</code> to catch up to lab N:</p>

```sh
curl --netrc -H "Content-Type: application/json" -d '{}' \
  http://git-server:3000/api/v1/repos/platform-team/cloud-policy-as-code/forks   # signs in with your token
cd ~/lab && git clone http://git-server:3000/$USER/cloud-policy-as-code.git
```

<ul class="lab-links">
<li><a href="assets/lab-reader.html?file=lab0.md.txt">Lab 0</a><span class="topic">Setup: fork, clone, CI secrets, deploy the app</span></li>
<li><a href="assets/lab-reader.html?file=lab1.md.txt">Lab 1</a><span class="topic">Why guardrails: the 403 and the Policy blade</span></li>
<li><a href="assets/lab-reader.html?file=lab2.md.txt">Lab 2</a><span class="topic">Anatomy of a definition</span></li>
<li><a href="assets/lab-reader.html?file=lab3.md.txt">Lab 3</a><span class="topic">Your first policy as code</span></li>
<li><a href="assets/lab-reader.html?file=lab4.md.txt">Lab 4</a><span class="topic">Audit and compliance</span></li>
<li><a href="assets/lab-reader.html?file=lab5.md.txt">Lab 5</a><span class="topic">Parameters and reuse</span></li>
<li><a href="assets/lab-reader.html?file=lab6.md.txt">Lab 6</a><span class="topic">Policy sets</span></li>
<li><a href="assets/lab-reader.html?file=lab7.md.txt">Lab 7</a><span class="topic">Modify and remediation</span></li>
<li><a href="assets/lab-reader.html?file=lab8.md.txt">Lab 8</a><span class="topic">Exemptions</span></li>
<li><a href="assets/lab-reader.html?file=lab9.md.txt">Lab 9</a><span class="topic">Shift left with Rego</span></li>
<li><a href="assets/lab-reader.html?file=lab10.md.txt">Lab 10</a><span class="topic">Testing policies</span></li>
<li><a href="assets/lab-reader.html?file=lab11.md.txt">Lab 11</a><span class="topic">Policy in the pipeline</span></li>
<li><a href="assets/lab-reader.html?file=lab12.md.txt">Lab 12</a><span class="topic">Drift, and the capstone</span></li>
<li><a href="assets/lab-reader.html?file=cheat-sheet.md.txt">Cheat sheet</a><span class="topic">Every command, plain text</span></li>
</ul>
