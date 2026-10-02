# Tool tour

One capability at a time, in this terminal. Every command is safe to run: nothing here changes what anyone else sees
except where it says so. Use `$USER` as is; it is your account.

---

## 1. Git and Forgejo

```sh
cd ~/lab
git clone http://git-server:3000/dojo-team/dojo-tour.git
cd dojo-tour
git log --oneline
git checkout -b tour-$USER
```

Then open the **Forgejo** card on your landing page: the same repository, with pull requests, reviews and branch
protection. This is where everything else in the platform is driven from.

## 2. CI on single-use runners

```sh
cd ~/lab/dojo-tour
git commit --allow-empty -m "Run the pipeline"
git push -u origin tour-$USER
```

Open the repository's **Actions** tab in Forgejo: the `hello` workflow runs on a runner that is made for this one job and
deleted after it. The facilitator's **Runners** tab shows the pool grow and shrink.

## 3. DNS as code

Your own zone, `$USER.dojo.test`, is already set up as a small git repository in `~/lab/my-zone`.

```sh
cd ~/lab/my-zone
cat dnsconfig.js
dnscontrol preview
dnscontrol push
dig @dns-server www.$USER.dojo.test A +short
```

Open the **DNS Zones** card: your new records are there, live. The facilitator can then edit one in the **DNS Admin**
tab; run `dnscontrol preview` again and it shows the difference, and `dnscontrol push` puts your file's version back.
The file in git is the truth; the dashboard is not.

`~/lab/dojo-tour/dns` is a second, offline example: `dnscontrol check` validates it without a server.

## 4. Infrastructure as code (OpenTofu on Dojo Cloud)

```sh
dojo-env | sed 's/=.*/=…/'
cd ~/lab/dojo-tour/cloud
tofu init
tofu plan
```

`tofu apply` creates a resource group you can see in the **Dojo Cloud** portal card. The credentials are your own,
handed to your shell by a broker; nothing is written in the `.tf` files. `terraform` is the same program.
