# Zellij Guide

If you opened the **terminal workspace**, your window is a [Zellij](https://zellij.dev) session with three parts:

- a **file list** on the left that shows the folder your shell is in. It updates by itself when you `cd` or when
  files are created, and you cannot type into it,
- your **shell** on the right, where you type the lab commands,
- a **tab bar** along the top and a **key-hint bar** along the bottom.

Nothing here is required for the labs.

## Three commands that open things in a pane

| Command | What it does |
|---|---|
| `e <file>` | Edit a file in a floating pane over your work. `Ctrl+S` saves, `Ctrl+Q` quits and the pane goes away |
| `show <file>` | Read a file in a floating pane (Markdown is formatted). `q` closes it |
| `guide` | List the guides; `guide quick-start` has the commands you will use most |

Add `-s` to put the pane beside your work instead of over it, for example `show -s lab1.md` to keep a lab open while you type.

## Your keys go to your program

Zellij starts **locked**: every key goes to the shell or the editor, so `Ctrl+S` and `Ctrl+Q` do what you expect in the editor. Zellij's own shortcuts are off until you press `Ctrl+g`; the bar at the bottom then shows them. Press `Ctrl+g` again to lock.

## The bar at the bottom tells you the keys

When you unlock, Zellij has *modes* (pane, tab, scroll, and so on), and the bar always shows which keys work in the mode you are in. `Esc` or `Enter` takes you back to normal.

## Mouse first

- **Click** a pane to move to it.
- **Scroll** with the mouse wheel to see output that has gone off the top.
- **Drag** to select text; it is copied when you let go. If your browser does not paste it, hold `Shift` while you drag to use the browser's own selection instead.

## Panes (`Ctrl+g`, then `Ctrl+p`)

Unlock with `Ctrl+g`, press `Ctrl+p` for pane mode, then one key:

| Key | What it does |
|---|---|
| `n` | New pane |
| `x` | Close the pane you are in |
| `f` | Make this pane full screen (press again to restore) |
| arrow keys | Move to a neighbouring pane |

Press `Esc`, then `Ctrl+g` to lock again.

**More:** [README.md](README.md) for the lab menu, or <https://zellij.dev/documentation/> for everything else.
