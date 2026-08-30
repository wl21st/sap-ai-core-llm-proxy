# Release Quick Start & Packaging Guide

This guide covers building standalone binaries, version management, and release procedures for the SAP AI Core LLM Proxy.

---

## 1. Common Release Workflows

### Recommended: Build First, Tag Later
```bash
# 1. Build and test binary thoroughly
make build-tested

# 2. Verify the built binary
./dist/proxy --help

# 3. Bump version, prepare release, and push
make version-bump-patch    # or make version-bump-minor
make release-prepare
make tag-and-push
make release-github
```

### Quick Automated Patch Release
```bash
make workflow-patch    # Bumps version, builds, commits, tags, and pushes
make release-github    # Creates GitHub release with packaged artifacts
```

---

## 2. Make Command Reference

| Command | Description |
|---|---|
| `make build` | Build standalone binary with PyInstaller (no version change) |
| `make build-tested` | Run tests first, then build binary |
| `make version-bump-patch` | Bump patch version (e.g. `0.1.0` → `0.1.1`) |
| `make version-bump-minor` | Bump minor version (e.g. `0.1.0` → `0.2.0`) |
| `make version-bump-major` | Bump major version (e.g. `0.1.0` → `1.0.0`) |
| `make tag` | Create git tag locally matching `pyproject.toml` version |
| `make tag-push` | Push git tag to remote repository |
| `make release-prepare` | Package binary artifacts into `.tar.gz` and `.zip` archives |
| `make release-github` | Publish release to GitHub via `gh release create` |
| `make release-docker` | Build and tag Docker container image |

---

## 3. Binary Packaging & Architecture Note

When building standalone binaries via PyInstaller, builds target the host machine's architecture:
- **Apple Silicon (macOS arm64)**: Builds native `arm64` binary.
- **Intel (macOS x86_64 / Linux x86_64)**: Builds native `x86_64` binary.

> [!NOTE]
> Python wheels and C-extensions are architecture-specific. To distribute binaries for multiple architectures, build on the respective target machines or CI runners (e.g. GitHub Actions matrix).

---

## 4. Release Directory Structure

```
dist/
└── proxy                       # Compiled binary executable

releases/
└── v0.1.0/
    ├── proxy-0.1.0-macos       # Standalone executable
    ├── proxy-0.1.0-macos.tar.gz
    └── proxy-0.1.0-macos.zip
```
