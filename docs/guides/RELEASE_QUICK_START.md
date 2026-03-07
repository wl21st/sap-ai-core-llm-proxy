# Release Quick Start Guide

## TL;DR - Common Workflows

### 1. Build First, Tag Later (Recommended)

```bash
# Build and test thoroughly
make build-tested

# Test the binary
./dist/proxy --help

# When satisfied, version and release
make version-bump-patch
make release-prepare
make tag-and-push
make release-github
```

### 2. Quick Patch Release

```bash
make workflow-patch    # Bumps version, builds, commits, tags, pushes
make release-github    # Upload to GitHub
```

### 3. Build Multiple Times Before Release

```bash
# Iterate on builds
make build
# ... test ...
make build
# ... test more ...
make build

# Finally release
make workflow-minor     # Bumps version, builds, commits, tags, pushes, prepares
make release-github     # Upload to GitHub
```

## Key Commands

| Command | What It Does |
|---------|-------------|
| `make build` | Build binary (no version change) |
| `make version-bump-patch` | 0.1.0 → 0.1.1 |
| `make version-bump-minor` | 0.1.0 → 0.2.0 |
| `make version-bump-major` | 0.1.0 → 1.0.0 |
| `make tag` | Create git tag locally |
| `make tag-push` | Push tag to remote |
| `make workflow-commit-and-tag` | Commit version changes and create/push tag |
| `make release-prepare` | Package artifacts |
| `make release-github` | Upload to GitHub |
| `make help` | Show all commands |

## The Decoupled Process

```
┌─────────────────────────────────────────────────────────┐
│                    DECOUPLED WORKFLOW                    │
└─────────────────────────────────────────────────────────┘

1. BUILD (Independent)
   ├─ make build
   ├─ make build-debug
   └─ make build-tested
   
2. VERSION (Independent)
   ├─ make version-bump-patch
   ├─ make version-bump-minor
   └─ make version-bump-major
   
3. TAG (Independent)
   ├─ make tag
   └─ make tag-push
   
4. PREPARE (Independent)
   └─ make release-prepare
   
5. UPLOAD (Independent, Multiple Platforms)
   ├─ make release-github
   ├─ make release-docker
   └─ make release-pypi
```

## Benefits

✅ **Build anytime** without version changes  
✅ **Test thoroughly** before committing to a version  
✅ **Proper version sync** between files and tags  
✅ **Upload to platforms separately** at your own pace  
✅ **Rebuild without re-tagging** during development  

## Example: Real-World Scenario

```bash
# Monday: Start development
make build
# ... find bugs ...

# Tuesday: Fix and rebuild
make build
# ... more testing ...

# Wednesday: Another iteration
make build
# ... looks good! ...

# Thursday: Ready to release
make workflow-minor         # Bumps version, builds, commits, tags, pushes, prepares
# ... final review of artifacts ...

# Friday: Ship it!
make release-github         # Upload to GitHub
make release-docker         # Build Docker image
```

## Prerequisites

- **GitHub CLI**: `brew install gh` (for `make release-github`)
- **Docker**: For `make release-docker`
- **Git**: For tagging

## Directory Structure

```
project/
├── dist/                    # Build output
│   └── proxy
├── releases/                # Release artifacts
│   └── v0.1.0/
│       ├── proxy-0.1.0-macos
│       ├── proxy-0.1.0-macos.tar.gz
│       └── proxy-0.1.0-macos.zip
└── pyproject.toml          # Version source of truth
```

## Troubleshooting

**Q: Tag already exists?**
```bash
git tag -d v0.1.0              # Delete local
git push origin :refs/tags/v0.1.0  # Delete remote
make tag                       # Recreate
```

**Q: Need to rebuild after tagging?**
```bash
make build                     # Just rebuild, tag stays
```

**Q: Want to change version after tagging?**
```bash
git tag -d v0.1.0              # Delete tag first
make version-bump-patch        # Change version (updates uv.lock too)
make workflow-commit-and-tag   # Commit and create new tag
```

## Full Documentation

See [`RELEASE_WORKFLOW.md`](RELEASE_WORKFLOW.md) for complete details.