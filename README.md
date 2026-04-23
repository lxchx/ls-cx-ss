# ls-cx-ss

`ls-cx-ss` is a small local tool for Codex CLI users.

It fills the current gaps in `codex resume` by:

- listing sessions for the current working directory
- showing sessions across providers together
- displaying `Provider` and `SessionID`
- supporting a lightweight TUI picker
- resuming directly with `codex resume <SESSION_ID>`

## Commands

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
