# Quick start

The commands you will use most in the terminal workspace. Type them in the shell pane on the right.

## Open and edit files

| Command | What it does |
|---|---|
| `e notes.txt` | Edit a file in a floating pane. It is created if it does not exist |
| `e -s notes.txt` | The same, in a pane beside your work |
| `show lab1.md` | Read a file in a floating pane (`q` closes it) |
| `show -s lab1.md` | The same, beside your work, to keep a lab open as you type |
| `guide` | List the guides; `guide micro` opens one |

## micro, the editor

`e` opens your file in **micro**. Paste or type, then:

| Key | What it does |
|---|---|
| `Ctrl+S` | Save |
| `Ctrl+Q` | Quit (the floating pane closes with it) |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / cut / paste |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+F` | Find |
| `Ctrl+A` | Select all |

Paste text from your browser with `Ctrl+Shift+V`. The mouse works too. More in `guide micro`.

## Get around

| Command | What it does |
|---|---|
| `pwd` | Show which folder you are in |
| `ls` | List files; `ls -la` shows details and hidden files |
| `cd roster` | Go into a folder; `cd ..` goes up; `cd` alone goes home |
| `z lab` | Jump to a folder you have been in before |
| `mkdir notes` | Make a folder |
| `touch a.txt` | Make an empty file |
| `cp a.txt b.txt` | Copy a file |
| `mv a.txt c.txt` | Move or rename a file |
| `rm a.txt` | Delete a file. There is no undo, and no recycle bin |

The pane on the left always shows the folder you are in.

## Look at files

| Command | What it does |
|---|---|
| `cat file` | Print a file |
| `bat file` | Print it with colours and line numbers |
| `head -n 5 file` / `tail -n 5 file` | The first / last 5 lines |
| `less file` | Page through a long file (`q` quits) |
| `glow -p file.md` | Read Markdown, formatted |
| `wc -l file` | Count lines |
| `diff a.txt b.txt` | Show how two files differ |

## Search

| Command | What it does |
|---|---|
| `rg word` | Search every file here for a word (fast, ignores case) |
| `rg word roster/` | Search only inside one folder |
| `grep word file` | Search one file |
| `find . -name "*.yaml"` | Find files by name |
| `ls \| fzf` | Pick from a list by typing a few letters |

## Shortcuts that save typing

- **Tab** completes file and folder names. **Up arrow** brings back earlier commands.
- `Ctrl+R` searches your command history as you type.
- `Ctrl+C` stops a running command. `clear` (or `Ctrl+L`) tidies the screen.

## Getting help

Every tool explains itself: add `--help`, for example `rg --help`, `bat --help` or `ls --help`. For git, `git commit -h` gives a short summary. The man-page viewer is not installed in this environment, so `--help` is the place to look.
