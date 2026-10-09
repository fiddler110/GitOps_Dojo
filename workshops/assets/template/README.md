# {{title}}

{{description}}

Made with `./dojo new-workshop {{name}}`. Everything below marked TODO is a placeholder.

## Running it

```sh
./dojo {{name}} --dry-run    # what would build and start; checks manifests and image pins
./dojo {{name}}              # then open http://localhost:8080
```

## What's here

- [`workshop.env`](workshop.env): name, description, place in the learning path, Forgejo repo, modules.
- [`content/slides/`](content/slides/): the hub page (`index.md`), the deck (`presentation.md`), the labs index
  (`lab-index.md`), the lab overview (`labs.md`, also the workspace's Labs tab) and a cheat sheet. Marp markdown;
  the shared themes are under `assets/themes/` (mounted from `workshops/assets/`).
- [`content/lab/`](content/lab/): seeded into every student's `~/lab`, and readable in the browser from the labs index.
- [`content/sample-repo/`](content/sample-repo/): seeded into Forgejo as `{{org}}/{{repo}}`.

## Next steps

1. Write the deck and the labs (TODOs in each file), and list every lab in `content/slides/lab-index.md` and
   `content/lab/README.md`.
2. Need tools in the terminal, services or a web tool? Check `./dojo modules` first, then see "Adding a new
   workshop" in [`workshops/README.md`](../README.md).
3. Add a row to the workshop table in [`workshops/README.md`](../README.md).
4. Run it end to end, including the facilitator's `/admin` view, before a live session.
