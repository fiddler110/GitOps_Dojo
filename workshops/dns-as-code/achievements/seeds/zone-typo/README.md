# Challenge c1: The Typo

One record in `dnsconfig.js` points at the wrong hostname, and `dnscontrol` refuses the file because of it. Find
it and fix it without touching any other record, then push.

This repo holds your own zone, `{user}.dojo.test` (the same zone `~/lab/my-zone` pushes to: whichever you push last
wins, so finish Labs 1-2 first). Work here with `dnscontrol preview` and `dnscontrol push`; `creds.json` uses your own
key (`$DNS_API_KEY`), which only changes your own zone. Check the live result with `dig @dns-server <name>.{user}.dojo.test`.

When you think it's done: `dojo-check c1`. A wrong answer costs nothing; `dojo-check hint c1` gives a hint for
part of the points, and `dojo-challenge reset c1` rebuilds this repo from scratch.
