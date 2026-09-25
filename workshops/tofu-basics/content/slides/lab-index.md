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

<p class="setup-label">Every lab works in your fork of the starter repo (Lab 0). Make it once, or run <code>lab-prep N</code> to catch up to lab N:</p>

```sh
curl -u "$USER" -H "Content-Type: application/json" -d '{}' \
  http://git-server:3000/api/v1/repos/iac-team/tofu-basics/forks   # asks for your Forgejo password
cd ~/lab && git clone http://git-server:3000/$USER/tofu-basics.git
```

<ul class="lab-links">
<li><a href="assets/lab-reader.html?file=lab0.md.txt">Lab 0</a><span class="topic">Tour the repo, terraform = tofu</span></li>
<li><a href="assets/lab-reader.html?file=lab1.md.txt">Lab 1</a><span class="topic">init, validate, plan, apply</span></li>
<li><a href="assets/lab-reader.html?file=lab2.md.txt">Lab 2</a><span class="topic">Read the plan, state and outputs</span></li>
<li><a href="assets/lab-reader.html?file=lab3.md.txt">Lab 3</a><span class="topic">destroy, and what's left behind</span></li>
<li><a href="assets/lab-reader.html?file=lab4.md.txt">Lab 4</a><span class="topic">Meet Dojo Cloud, the portal, init</span></li>
<li><a href="assets/lab-reader.html?file=lab5.md.txt">Lab 5</a><span class="topic">Deploy hello, watch the portal</span></li>
<li><a href="assets/lab-reader.html?file=lab6.md.txt">Lab 6</a><span class="topic">Break a policy on purpose</span></li>
<li><a href="assets/lab-reader.html?file=lab7.md.txt">Lab 7</a><span class="topic">Drift: portal changes, then plan</span></li>
<li><a href="assets/lab-reader.html?file=lab8.md.txt">Lab 8</a><span class="topic">In-place vs replace, -replace</span></li>
<li><a href="assets/lab-reader.html?file=lab9.md.txt">Lab 9</a><span class="topic">for_each, and a quota</span></li>
<li><a href="assets/lab-reader.html?file=lab10.md.txt">Lab 10</a><span class="topic">Clean up and verify the portal is empty</span></li>
<li><a href="assets/lab-reader.html?file=cheat-sheet.md.txt">Cheat sheet</a><span class="topic">Every command, plain text</span></li>
</ul>
