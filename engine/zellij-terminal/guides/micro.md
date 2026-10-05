# micro, the editor

`micro` is a small editor that works like the ones on your desktop. Open a file with it, or from your shell:

```sh
e roster/team.yaml        # opens in a floating pane over your work
micro roster/team.yaml    # opens in this pane instead
```

Close the editor with `Ctrl+Q`; the floating pane goes away with it. If the file does not exist, micro starts an empty one and creates it when you save.

## The keys you need

| Key | What it does |
|---|---|
| `Ctrl+S` | Save |
| `Ctrl+Q` | Quit (it asks if you have unsaved changes) |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / cut / paste |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+A` | Select everything |
| `Ctrl+F` | Find |
| `Ctrl+E` | Command bar (for example `set tabsize 4`) |
| `Shift` + arrow keys | Select text |

The mouse works too: click to move the cursor, drag to select, scroll with the wheel.

## Pasting text from outside

Copy the text in your browser, then paste into micro with `Ctrl+Shift+V` (or your browser's paste shortcut). It arrives as if you had typed it, so check the indentation in a YAML file before you save.

## Other editors

`nano file` is a simpler editor (the keys are listed along its bottom), and `vim file` is there if you already know it.
