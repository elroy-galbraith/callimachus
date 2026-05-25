# Demo recordings

## `thematic.cast` — asciinema cast of the thematic pack tour

A ~70-second terminal walkthrough of the shipped `thematic` project:
list the project, peek at a curated excerpt, look at a pending merge
proposal, convert the vault to Turtle, and run competency-question CQ1
against the result.

### Play it

**Browser (no install):** open [`thematic.html`](thematic.html) — a
self-contained HTML page with `asciinema-player` from a CDN and the
cast inlined as JSON. Works on Windows-native, no CLI needed.

```powershell
start docs/demo/thematic.html
```

**WSL CLI:** the Windows-native `asciinema` pip package can't even
import (`fcntl` missing), so use WSL:

```powershell
wsl ~/.local/bin/asciinema play ./docs/demo/thematic.cast
```

First time, install it in WSL: `wsl python3 -m pip install --user
--break-system-packages asciinema`.

**Share:** `asciinema upload <cast>` (from WSL) gives an asciinema.org
URL. The `.cast` file itself is also portable — anyone with the
asciinema CLI or the JS player can replay it.

### How it was assembled

This cast was **hand-built from real outputs**, not recorded
keystroke-by-keystroke. Every command in `STEPS` was executed once
against `projects/thematic/` on the current branch and its real stdout
was pasted into `build_cast.py`. The script then emits a valid
asciinema v2 file (header + JSONL events) with realistic typing
cadence and pauses.

The reason: asciinema needs a Unix PTY, and the original recording
session ran on Windows-native PowerShell. The choice was either spin
up a parallel Linux venv in WSL or synthesise the cast from real
outputs; the second path got something playable without doubling the
dev environment.

If you want a true PTY recording, run `asciinema rec` in WSL after
setting up `.venv` there with `pip install -e .[curator]`.

### Regenerate

```bash
python docs/demo/build_cast.py
```

The script is the source of truth — edit `STEPS` (commands + literal
expected output) and re-run to produce a new `thematic.cast`. Pacing
knobs live at the top of `build_events()`.

### Faithfulness

Every command shown in the cast is replayable on the current branch:

| Cast command | Real backing |
|---|---|
| `ls projects/` | actual directory |
| `cat projects/thematic/vault/...` | actual file |
| `python scripts/to_turtle.py …` | actual CLI shim |
| `python docs/demo/run_cq1.py` | helper added alongside this cast |

`run_cq1.py` is a tiny pyoxigraph wrapper that loads the schema +
vault and prints CQ1's results. It exists so the cast's final command
isn't a stub.
