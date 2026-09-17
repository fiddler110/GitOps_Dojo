---
marp: true
theme: default
paginate: false
size: 16:9
html: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Manrope:wght@400;600;700&display=swap');
  :root {
    --accent: #ef8144;
    --accent-deep: #9b532c;
    --bg-black: #0b0b0c;
    --muted: #c9c9cc;
  }
  section.hub {
    align-items: center;
    background:
      radial-gradient(circle at 25% 15%, rgba(239, 129, 68, 0.35), transparent 55%),
      radial-gradient(circle at 80% 85%, rgba(239, 129, 68, 0.16), transparent 50%),
      var(--bg-black);
    color: #fff;
    display: flex;
    flex-direction: column;
    font-family: 'Manrope', sans-serif;
    justify-content: center;
    text-align: center;
  }
  .hub .logo {
    display: block;
    margin: 0 auto 22px;
    max-width: 520px;
    width: 70%;
  }
  .hub .logo img { display: block; width: 100%; }
  .hub h1 { color: #fff; font-size: 64px; margin-bottom: 4px; }
  .hub p.tag {
    color: var(--muted);
    font-size: 24px;
    margin: 0 auto;
    max-width: 640px;
  }
  .hub .links {
    display: flex;
    gap: 20px;
    justify-content: center;
    margin-top: 44px;
  }
  .hub .enter {
    background: linear-gradient(135deg, var(--accent), var(--accent-deep));
    border: 2px solid var(--bg-black);
    border-radius: 10px;
    box-shadow: 0 16px 34px rgba(0, 0, 0, 0.45);
    color: #fff;
    display: inline-block;
    font-size: 24px;
    font-weight: 700;
    padding: 16px 32px;
    text-decoration: none;
  }
  .hub .enter:hover { filter: brightness(1.1); }
  .hub .enter.secondary {
    background: transparent;
    border: 2px solid var(--muted);
  }
  .hub .enter.secondary:hover { border-color: #fff; }
  .hub .meta {
    color: var(--muted);
    font-size: 16px;
    letter-spacing: 0.04em;
    margin-top: 70px;
    text-transform: uppercase;
  }
---

<!-- _class: hub -->

<span class="logo"><img src="GitOps_Dojo_Dark.png" alt="GitOps Dojo"></span>

# DNS as Code

<p class="tag">Managing DNS records the way we manage everything else — builds on Git Fundamentals, same workflow, a new kind of file.</p>

<div class="links">
<a class="enter" href="presentation.md">Open the deck &rarr;</a>
<a class="enter secondary" href="labs.md">Lab overview</a>
<a class="enter secondary" href="cheat-sheet.md">Cheat sheet</a>
</div>

<p class="meta">Talk + hands-on lab · Engineering &amp; IT Operations</p>
