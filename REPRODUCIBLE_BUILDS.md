# Reproducible and Deterministic Builds

This document describes the reproducible build strategy for **ublue-rebase-helper** (`urh.pyz`), ensuring bitwise-identical artifacts across different build environments and times.

## Overview

The build system produces a deterministic Python zipapp (`dist/urh.pyz`) that is bitwise-identical when built from the same source commit, regardless of:
- When the build is performed
- Where the build is performed (different machines)
- Who performs the build

## Build Output

```
dist/
├── urh.pyz           # Executable Python zipapp
└── urh.pyz.sha256sum # SHA256 checksum for verification
```

## Reproducibility Guarantees

The build system ensures determinism through five key mechanisms:

### 1. Fixed Timestamps (`SOURCE_DATE_EPOCH`)

All file timestamps are normalized to a fixed epoch time to eliminate build-time variability:

- **Default**: `315532800` (January 1, 1980 00:00:00 UTC)
- **Override**: Set via environment variable before building:
  ```bash
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)  # Use commit timestamp
  make build
  ```

Implementation:
```makefile
SOURCE_DATE_EPOCH ?= 315532800
export SOURCE_DATE_EPOCH
find $(BUILD_DIR)/staging -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;
```

### 2. Sorted File Order

Files are added to the archive in a deterministic, locale-independent order:

```bash
find . -type f | LC_ALL=C sort | zip -X -q -@ ../archive.zip
```

This ensures consistent file ordering regardless of filesystem or OS.

### 3. Stripped Metadata

The `zip -X` flag strips extra file attributes (UID/GID, extended attributes) that could vary between systems:

```bash
zip -X -q -@
```

### 4. Staging Directory Isolation

A clean staging directory is created for each build to prevent source tree pollution:

```bash
rm -rf $(BUILD_DIR)/staging
mkdir -p $(BUILD_DIR)/staging
cp -r $(SRC_DIR)/* $(BUILD_DIR)/staging/
```

This ensures no cached `.pyc` files or other artifacts affect the build.

### 5. Pinned Toolchain via Nix

The development environment pins all build tools to specific versions:

- **Python**: 3.13 (explicitly pinned)
- **GNU Make**: From Nix flake
- **zip**: From Nix flake
- **coreutils**: From Nix flake (provides `touch`, `date`)
- **jq**: From Nix flake (for JSON parsing)

## Build Environment Setup

### Using Nix (Recommended)

```bash
nix develop    # Enter reproducible build environment
make build     # Build deterministically
```

### Using direnv (Automatic)

```bash
direnv allow   # Automatically loads .envrc
make build
```

The `.envrc` file automatically:
- Sets up the Nix development shell
- Exports `SOURCE_DATE_EPOCH`
- Configures `PYTHON` environment variable

### Manual Setup (Not Recommended)

If not using Nix, ensure you have:
- Python 3.13
- GNU Make
- zip (with `-X` support)
- coreutils (for `touch -d`)
- jq

And manually set:
```bash
export SOURCE_DATE_EPOCH=315532800
```

## Build Process

### Step-by-Step Breakdown

1. **Clean**: Remove all build artifacts, caches, and `.direnv/`
2. **Version Injection**: Update `__version__` in `src/urh/constants.py` from `pyproject.toml`
3. **Staging**: Copy `src/` contents to isolated staging directory
4. **Entry Point**: Create `__main__.py` for zipapp execution
5. **Timestamp Normalization**: Touch all files to `SOURCE_DATE_EPOCH`
6. **Archive Creation**: Create deterministic zip with sorted file order
7. **Shebang Injection**: Prepend `#!/usr/bin/env python3` to create executable
8. **Checksum Generation**: Create SHA256 checksum file
9. **Cleanup**: Remove staging directory and intermediate files

### Makefile Targets

| Target    | Description                                          |
| --------- | ---------------------------------------------------- |
| `build`   | Create deterministic zipapp (`dist/urh.pyz`)         |
| `install` | Install to `~/.local/bin/urh`                        |
| `all`     | Clean + build + install                              |
| `clean`   | Remove build artifacts and caches                    |
| `test`    | Run pytest with coverage                             |
| `quality` | Run lint and format checks                           |

## Verification

### Verify Build Reproducibility

Build twice and compare checksums:

```bash
# First build
nix develop --command make build
cp dist/urh.pyz.sha256sum dist/urh.first.sha256sum

# Second build
nix develop --command make build

# Compare (should be identical)
diff dist/urh.pyz.sha256sum dist/urh.first.sha256sum
```

### Verify Installed Artifact

```bash
cd ~/.local/bin
sha256sum -c urh.pyz.sha256sum
```

### Inspect Build Contents

```bash
# List contents (timestamps will all be SOURCE_DATE_EPOCH)
unzip -l dist/urh.pyz

# Extract and inspect
mkdir /tmp/urh-inspect
cd /tmp/urh-inspect
unzip dist/urh.pyz
find . -type f -exec stat -c '%y %n' {} \; | head
```

## Continuous Integration

For CI/CD pipelines, ensure:

1. **Use Nix**: Always build within the Nix development shell
2. **Fixed Epoch**: Set `SOURCE_DATE_EPOCH` explicitly (or use git commit timestamp)
3. **Clean Builds**: Run `make clean` before each build
4. **Checksum Verification**: Verify checksums after build completion

Example GitHub Actions snippet:

```yaml
- name: Install Nix
  uses: DeterminateSystems/nix-installer-action@main

- name: Build
  run: |
    nix develop --command make build
    cd dist && sha256sum -c urh.pyz.sha256sum
```

## Troubleshooting

### Non-Deterministic Builds

If builds are not reproducible:

1. **Check SOURCE_DATE_EPOCH**:
   ```bash
   echo $SOURCE_DATE_EPOCH  # Should be set
   date -d "@$SOURCE_DATE_EPOCH" -u
   ```

2. **Verify Clean Build**:
   ```bash
   make clean && make build
   ```

3. **Check File Ordering**:
   ```bash
   cd dist/staging && find . -type f | LC_ALL=C sort
   ```

4. **Ensure Nix Shell**:
   ```bash
   nix develop  # Make sure you're in the reproducible environment
   ```

### Build Failures

Common issues:

- **Missing tools**: Ensure all Nix packages are available (`zip`, `coreutils`, `jq`)
- **Permission errors**: Run within Nix shell for consistent permissions
- **Version mismatch**: Check Python version matches `flake.nix` (3.13)

## Technical Implementation

### Makefile Excerpt (Key Determinism Logic)

```makefile
# Ensure SOURCE_DATE_EPOCH is set
SOURCE_DATE_EPOCH ?= 315532800
export SOURCE_DATE_EPOCH

# Normalize timestamps on ALL files
find $(BUILD_DIR)/staging -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;

# Create deterministic archive
cd $(BUILD_DIR)/staging && \
  find . -type f | LC_ALL=C sort | \
  zip -X -q -@ ../archive.zip
```

### Nix Flake (Toolchain Pinning)

```nix
devShells.default = pkgs.mkShell {
  packages = [
    python        # Pinned to 3.13
    pkgs.gnumake
    pkgs.zip
    pkgs.coreutils
    pkgs.jq
  ];
  shellHook = ''
    export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-315532800}
  '';
};
```

## References

- [Reproducible Builds Specification](https://reproducible-builds.org/specs/source-date-epoch/)
- [SOURCE_DATE_EPOCH](https://reproducible-builds.org/docs/source-date-epoch/)
- [Python Zipapp Documentation](https://docs.python.org/3/library/zipapp.html)
- [Nix Flakes](https://nixos.wiki/wiki/Flakes)
