# ls-cx-ss

English | [中文](./README_CN.md)

`ls-cx-ss` is a small local tool for Codex CLI users.

It fills the current gaps in `codex resume` by:

- listing sessions for the current working directory
- showing sessions across providers together
- displaying `Provider` and `SessionID`
- supporting a lightweight TUI picker
- resuming directly with `codex resume <SESSION_ID>`

## Local development

```bash
python3 -m ls_cx_ss list
python3 -m ls_cx_ss tui
python3 -m ls_cx_ss resume <SESSION_ID>
```

The package entry point and GitHub Pages single-file entry are intended to run on Python 3.6+.

## Development

The source of truth now lives under `ls_cx_ss/`.

- `ls_cx_ss/`: package-style source modules used during development
- `docs/ls-cx-ss.py`: generated single-file entry published through GitHub Pages

The Pages single-file output is generated from the package sources by:

```bash
python3 scripts/build_single_file.py
```

The current generator uses a small loader approach:

- it reads each module under `ls_cx_ss/`
- embeds those module sources into one file as strings
- bootstraps them into `sys.modules`
- then calls `ls_cx_ss.cli.main()`

So if you want to change behavior, edit `ls_cx_ss/` first, then regenerate
`docs/ls-cx-ss.py`. Do not hand-edit `docs/ls-cx-ss.py` unless you are debugging
the generator itself.

## GitHub Pages URL usage

The project also supports GitHub Pages distribution, so you can use it directly from a URL:

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 -
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - list
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - tui
```

With no subcommand, it now defaults to the TUI. `-h` / `--help` still shows help.
Inside the TUI:

- `s`: cycle sort column
- `r`: toggle ascending / descending
- `i`: install the latest Pages build to `~/.local/bin/ls-cx-ss`
- `u`: check whether a newer Pages build is available

For URL-based install, use the Python installer script hosted on the same Pages site:

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/install.py | python3 -
~/.local/bin/ls-cx-ss list
```

## Installed command

If you install it locally, the command still works as:

```bash
ls-cx-ss list
ls-cx-ss tui
ls-cx-ss resume <SESSION_ID>
```

## TUI keys

- `Up/Down` or `j/k`: move
- `PageUp/PageDown`: page
- `Home/End`: jump
- `/`: search
- `s`: cycle sort key
- `r`: toggle reverse
- `i`: install to local `~/.local/bin/ls-cx-ss`
- `u`: check for updates from GitHub Pages
- `Enter`: resume selected session
- `q` or `Esc`: quit
