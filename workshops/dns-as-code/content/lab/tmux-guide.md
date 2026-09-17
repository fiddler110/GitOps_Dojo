# tmux Guide

Your terminal — whether you open it with the **Open Terminal** button or from the integrated terminal panel inside **Open VS Code** — runs inside `tmux`, a terminal multiplexer. You don't need to know anything about it to do the labs, but it's genuinely useful once you do: split your terminal into multiple panes, keep long-running commands going, and reconnect to exactly where you left off after a reload or a dropped connection.

One thing worth knowing up front: your facilitator can open a read-only view of your terminal from their own dashboard, to help you troubleshoot without needing to see your screen over your shoulder. They can watch; they can't type into your session from there.

---

## The prefix key

Every tmux command starts with a *prefix* key combo, then a second key. The default prefix is `Ctrl+b`. Below, `<prefix>` always means "press `Ctrl+b`, release it, then press the next key" — it's two separate keypresses, not held together.

---

## Splitting panes

```
<prefix> %      # split vertically (side by side)
<prefix> "      # split horizontally (stacked)
```

Move between panes:

```
<prefix> <arrow key>     # move to the pane in that direction
<prefix> o                # cycle to the next pane
```

Close a pane: type `exit` or press `Ctrl+d` in it — same as closing any shell.

Resize the current pane:

```
<prefix> Ctrl+<arrow key>
```

Temporarily zoom a pane to fill the whole window (press again to restore):

```
<prefix> z
```

---

## Windows

A tmux *window* is a full-screen tab within a session — different from a pane (a split within one window).

```
<prefix> c          # create a new window
<prefix> n           # next window
<prefix> p           # previous window
<prefix> 0-9         # jump straight to window number 0-9
<prefix> w           # list all windows and pick one
<prefix> ,           # rename the current window
```

---

## Detaching and reattaching

```
<prefix> d      # detach -- leaves everything running in the background
```

You won't usually need this here: reloading the browser tab reattaches you to the same session automatically (that's the whole point of running through tmux). But it's worth knowing that closing the tab doesn't kill anything — whatever's running keeps running.

To see what's still alive, or reattach manually from a fresh terminal:

```sh
tmux ls                    # list your sessions
tmux attach -t <name>      # reattach to one by name
```

---

## Scrolling and copying

tmux captures your terminal's scrollback itself, so your browser/terminal's normal scroll may not work as expected. Enter *copy mode* to scroll and select text:

```
<prefix> [                 # enter copy mode
<arrow keys / Page Up/Down>  # scroll
q                           # exit copy mode
```

---

## Quick reference

| Command | What it does |
| --- | --- |
| `<prefix> %` | Split pane vertically |
| `<prefix> "` | Split pane horizontally |
| `<prefix> <arrow>` | Move to another pane |
| `<prefix> z` | Zoom/unzoom the current pane |
| `<prefix> c` | New window |
| `<prefix> n` / `p` | Next / previous window |
| `<prefix> w` | List windows |
| `<prefix> d` | Detach (leaves session running) |
| `<prefix> [` then `q` | Scroll / exit scroll mode |
| `tmux ls` | List sessions (from a fresh terminal) |

None of this is required for the labs — plain typing and `Ctrl+c`/`Ctrl+d` work exactly as you'd expect without ever touching the prefix key. This is here for when you want more than one thing going at once.

**More:** [README.md](README.md) for the lab menu, or the official docs at <https://github.com/tmux/tmux/wiki>.
