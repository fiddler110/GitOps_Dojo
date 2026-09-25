# tmux Guide

Your terminal runs inside `tmux`, whether you open it with **Open Terminal** or from the terminal panel inside
**Open VS Code**. tmux lets you split one terminal into several panes, keep commands running, and pick up exactly
where you left off after a reload or a dropped connection. You don't need it for the labs, but it helps when you
want two things going at once.

---

## ⌨️ The one key to learn: `Ctrl+b`

> **Every tmux shortcut starts with `Ctrl+b`.** It's two steps, not one chord:
>
> 1. **Hold `Ctrl` and press `b`.**
> 2. **Let go of both keys.**
> 3. **Then press the command key**, such as `%` (which is `Shift+5`).
>
> Nothing appears on screen after step 2. tmux is quietly waiting for the command key.

This guide writes a shortcut like this: **`Ctrl+b` → `Shift+5`**. Read it as "press `Ctrl+b`, release, then press
`Shift+5`".

**Symbols need `Shift`.** Several commands are symbols on the top row of the keyboard, so the command key itself is
a `Shift` combination. The keys below are for a **US keyboard**; on a UK keyboard `"` is `Shift+2`.

| Command key | What you actually press |
| --- | --- |
| `%` | `Shift+5` |
| `"` | `Shift+'` (the quote key, left of `Enter`) |
| `[` | `[` (no Shift) |
| `,` | `,` (no Shift) |

**If nothing happens:** you probably pressed the command key while still holding `Ctrl`. Let go and try again. If
you pressed `Ctrl+b` by mistake, press `Esc` and carry on.

---

## Splitting panes

| To do this | Press `Ctrl+b`, release, then |
| --- | --- |
| Split **side by side** (a new pane on the right) | `Shift+5` (the `%` key) |
| Split **top and bottom** (a new pane below) | `Shift+'` (the `"` key) |
| Move to the pane **left / right / up / down** | an arrow key |
| Move to the **next** pane | `o` |
| **Zoom** the current pane to full size (press again to shrink back) | `z` |
| **Resize** the current pane | hold `Ctrl` and press an arrow key |

**Close a pane:** type `exit` (or press `Ctrl+d`) in it, the same as closing any shell.

**The mouse works too.** Click a pane to switch to it, and drag the line between two panes to resize them.

---

## Windows

A *window* is a full-screen tab inside tmux. A *pane* is a split inside one window. The status bar at the bottom
lists your windows; the one marked `*` is the current one.

| To do this | Press `Ctrl+b`, release, then |
| --- | --- |
| **Create** a new window | `c` |
| **Next** window | `n` |
| **Previous** window | `p` |
| Jump to window **0-9** | the number |
| **List** all windows and pick one | `w`, then arrow keys and `Enter` |
| **Rename** the current window | `,`, type a name, `Enter` |

---

## Scrolling back and copying

Output that has scrolled off the top lives in tmux, not in the browser, so the browser's own scrollbar won't reach
it.

- **With the mouse:** scroll the wheel over the terminal.
- **With the keyboard:** press `Ctrl+b`, release, then `[`. Now the arrow keys and `Page Up` / `Page Down` scroll,
  and `?` searches upward (type a word, `Enter`, then `n` for the next match). Press `q` to go back to typing.

**Copying text.** Dragging with the mouse copies into tmux's own clipboard, not your computer's. Paste it in the
terminal with `Ctrl+b`, release, then `]`. To copy into your computer's clipboard instead (to paste into another
app), **hold `Shift` while you drag**, then copy as usual.

While you're scrolled back, your typing doesn't reach the shell: press `q` first.

---

## Detaching and reattaching

| To do this | Press `Ctrl+b`, release, then |
| --- | --- |
| **Detach**: leave everything running and step out of tmux | `d` |

You rarely need this here. Reloading the browser tab reattaches you to the same session automatically, and closing
the tab doesn't stop anything that's running.

To see what's still running, or reattach by hand from a fresh terminal:

```sh
tmux ls                    # list your sessions
tmux attach -t <name>      # reattach to one by its name
```

---

## Quick reference

Every row starts with **`Ctrl+b`, release**, then the key shown.

| Then press | What it does |
| --- | --- |
| `Shift+5` (`%`) | Split side by side |
| `Shift+'` (`"`) | Split top and bottom |
| arrow key | Move to another pane |
| `o` | Next pane |
| `z` | Zoom / unzoom the current pane |
| `c` | New window |
| `n` / `p` | Next / previous window |
| `w` | List windows |
| `d` | Detach (the session keeps running) |
| `[` … `q` | Scroll back … back to typing |
| `]` | Paste what you dragged to copy |

Without the prefix: `exit` or `Ctrl+d` closes a pane, `Ctrl+c` stops a running command, and `tmux ls` lists
sessions.

---

Your facilitator can open a read-only view of your terminal from their dashboard, to help you troubleshoot. They
can watch, but they can't type into your session.

**More:** [README.md](README.md) for the lab menu, or the official docs at <https://github.com/tmux/tmux/wiki>.
