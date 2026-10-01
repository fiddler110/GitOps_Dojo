# Challenge c2: The Cutover

`app.{user}.dojo.test` must point at the new server `10.20.0.{n}`, and `www` must become an alias of `app`. Do it
in one commit, push it, and leave every other record as it is.

This repo holds your own zone, `{user}.dojo.test` (the same zone `~/lab/my-zone` pushes to: whichever you push last
wins, so finish Labs 1-2 first). Work here with `dnscontrol preview` and `dnscontrol push`; `creds.json` uses your own
key (`$DNS_API_KEY`), which only changes your own zone. Check the live result with `dig @dns-server <name>.{user}.dojo.test`.

When you think it's done: `dojo-check c2`. A wrong answer costs nothing; `dojo-check hint c2` gives a hint for
part of the points, and `dojo-challenge reset c2` rebuilds this repo from scratch.
