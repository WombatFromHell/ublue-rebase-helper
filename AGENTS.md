# AGENTS.md

## Development Environment

```bash
nix develop    # or: direnv allow
```

Provides: Python 3.13, zip, coreutils, gnumake, jq + fixed `SOURCE_DATE_EPOCH`

## Quick Reference

| Task         | Command                             |
| ------------ | ----------------------------------- |
| Setup        | `nix develop`                       |
| Test         | `make test` or `uv run pytest -xvs` |
| Quality      | `make quality`                      |
| Build        | `make build`                        |
| Install      | `make install`                      |
| Dependencies | `uv add/remove ...`                 |

## Makefile Targets

| Target    | Description                    |
| --------- | ------------------------------ |
| `build`   | Deterministic zipapp           |
| `install` | Install to `~/.local/bin/urh`  |
| `clean`   | Remove build artifacts         |
| `test`    | Pytest with coverage           |
| `quality` | Lint + format checks           |
| `lint`    | Type check (ty) + ruff         |
| `format`  | Ruff + prettier                |
| `radon`   | Code complexity analysis       |

## Build Output

```
dist/
├── urh.pyz           # Executable zipapp
└── urh.pyz.sha256sum # Checksum
```

## Reproducibility

Builds are bitwise-identical via:
1. Fixed timestamps (`SOURCE_DATE_EPOCH`)
2. Sorted file order (`LC_ALL=C sort`)
3. Stripped metadata (`zip -X`)
4. Staging isolation
5. Pinned toolchain (Nix)

See [REPRODUCIBLE_BUILDS.md](REPRODUCIBLE_BUILDS.md) for details.
