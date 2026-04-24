# ls-cx-ss

`ls-cx-ss` is a small local tool for Codex CLI users.

It fills the current gaps in `codex resume` by:

- listing sessions for the current working directory
- showing sessions across providers together
- displaying `Provider` and `SessionID`
- supporting a lightweight TUI picker
- resuming directly with `codex resume <SESSION_ID>`

## Single-file entry

The repo now includes a self-contained `ls-cx-ss` Python script in the repo root.
It only uses the standard library, so you can run it directly without installing the package first:

```bash
python3 ./ls-cx-ss list
python3 ./ls-cx-ss tui
python3 ./ls-cx-ss resume <SESSION_ID>
```

If you want a command-like entry on Unix shells:

```bash
chmod +x ./ls-cx-ss
./ls-cx-ss list
```

## GitHub Pages URL usage

The project also supports GitHub Pages distribution, so you can use it directly from a URL:

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 -
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - list
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - tui
```

With no subcommand, it now defaults to the TUI. `-h` / `--help` still shows help.

For URL-based install, use the Python installer script hosted on the same Pages site:

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/install.py | python3 -
~/.local/bin/ls-cx-ss list
```

## Commands

The packaged entry point still works if you prefer to install it:

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
- `Enter`: resume selected session
- `q` or `Esc`: quit
