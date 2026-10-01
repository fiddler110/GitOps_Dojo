# Capstone: The Bad Push

The last commit here was pushed by someone else. It added a record you want to keep and a record that sends traffic
to the wrong address. Get the zone to the right state (keep the good record, drop the bad one) without rewriting
history, and push.

This repo holds your own zone, `{user}.dojo.test` (the same zone `~/lab/my-zone` pushes to: whichever you push last
wins, so finish Labs 1-2 first). Work here with `dnscontrol preview` and `dnscontrol push`; `creds.json` uses your own
key (`$DNS_API_KEY`), which only changes your own zone. Check the live result with `dig @dns-server <name>.{user}.dojo.test`.

When you think it's done: `dojo-check capstone`. A wrong answer costs nothing; `dojo-check hint capstone` gives a hint for
part of the points, and `dojo-challenge reset capstone` rebuilds this repo from scratch.
