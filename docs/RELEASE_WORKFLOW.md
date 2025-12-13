# Release Workflow Guide

This document explains the decoupled build, tag, and release process for the SAP AI Core LLM Proxy project.

## Overview

The release process has been decoupled into independent stages:

1. **Build** - Compile binaries (independent of versioning)
2. **Version Management** - Bump version numbers
3. **Tagging** - Create git tags
4. **Release Preparation** - Package artifacts
5. **Multi-Platform Upload** - Distribute to various platforms

## Quick Start

### Option 1: Manual Step-by-Step (Recommended for first-time releases)

```bash
# 1. Build and test first
make build-tested

# 2. Review the build
./dist/sap_ai_proxy --help

# 3. Bump version (choose one)
make version-bump-patch   # 0.1.0 -> 0.1.1
make version-bump-minor   # 0.1.0 -> 0.2.0
make version-bump-major   # 0.1.0 -> 1.0.0

# 4. Prepare release artifacts
make release-prepare

# 5. Review artifacts
ls -lh releases/v*/

# 6. Create git tag
make tag

# 7. Push tag to remote
make tag-push

# 8. Upload to platforms (choose one or more)
make release-github       # Upload to GitHub Releases
make release-docker       # Build Docker image
make release-all          # Upload to all platforms
```

### Option 2: Automated Workflow

```bash
# Complete workflow for patch release
make workflow-patch

# Then review and upload
make tag-push
make release-github
```

## Detailed Workflow

### 1. Build Stage (Independent of Versioning)

Build binaries without any version changes:

```bash
# Standard build
make build

# Debug build (with console)
make build-debug

# GUI build (no console)
make build-gui

# Build after running tests
make build-tested
```

**Output**: Binary in `dist/sap_ai_proxy` (or `.exe` on Windows)

### 2. Version Management (Separate from Build)

Manage version numbers independently:

```bash
# Check current version
make version-show

# Bump version (modifies pyproject.toml)
make version-bump-patch   # Bug fixes: 0.1.0 -> 0.1.1
make version-bump-minor   # New features: 0.1.0 -> 0.2.0
make version-bump-major   # Breaking changes: 0.1.0 -> 1.0.0
```

**Note**: Version bumping only modifies [`pyproject.toml`](../pyproject.toml:3) - it doesn't build or tag anything.

### 3. Git Tagging (Separate from Build and Version)

Create git tags independently:

```bash
# Create tag locally
make tag

# Push tag to remote
make tag-push

# Or do both at once
make tag-and-push
```

**Note**: Tags are based on the current version in [`pyproject.toml`](../pyproject.toml:3).

### 4. Release Preparation

Package built binaries with version information:

```bash
make release-prepare
```

This creates:

- `releases/v{VERSION}/sap_ai_proxy-{VERSION}-{PLATFORM}` (binary)
- `releases/v{VERSION}/sap_ai_proxy-{VERSION}-{PLATFORM}.tar.gz` (tarball)
- `releases/v{VERSION}/sap_ai_proxy-{VERSION}-{PLATFORM}.zip` (zip archive)

### 5. Multi-Platform Upload

Upload to different platforms independently:

#### GitHub Releases

```bash
make release-github
```

**Requirements**:

- GitHub CLI (`gh`) installed
- Authenticated with `gh auth login`
- Git tag must exist (created with `make tag`)

#### Docker

```bash
make release-docker
```

This builds the Docker image. To push to a registry:

```bash
docker tag sap_ai_proxy:0.1.0 your-registry/sap_ai_proxy:0.1.0
docker push your-registry/sap_ai_proxy:0.1.0
```

#### PyPI (if applicable)

```bash
make release-pypi
```

Then manually publish:

```bash
uv publish
```

#### All Platforms

```bash
make release-all
```

Uploads to GitHub and builds Docker image.

## Common Scenarios

### Scenario 1: Build First, Tag Later

You want to build and test thoroughly before committing to a version:

```bash
# Build and test
make build-tested

# Test the binary extensively
./dist/sap_ai_proxy

# When satisfied, bump version and tag
make version-bump-patch
make tag-and-push

# Prepare and upload
make release-prepare
make release-github
```

### Scenario 2: Build Multiple Times Before Release

You need to rebuild several times during development:

```bash
# Build iteration 1
make build

# Test and find issues...

# Build iteration 2
make build

# Test again...

# Build iteration 3
make build

# Finally satisfied - now version and release
make version-bump-minor
make release-prepare
make tag-and-push
make release-github
```

### Scenario 3: Upload to Multiple Platforms Separately

You want to upload to different platforms at different times:

```bash
# Build and prepare once
make build-tested
make version-bump-patch
make release-prepare
make tag-and-push

# Upload to GitHub first
make release-github

# Later, upload Docker image
make release-docker

# Even later, upload to PyPI
make release-pypi
```

### Scenario 4: Hotfix Release

Quick patch release:

```bash
# Use automated workflow
make workflow-patch

# Review artifacts
ls -lh releases/v*/

# Push and upload
make tag-push
make release-github
```

## Platform Detection

The Makefile automatically detects your platform:

- **macOS**: Builds universal2 binary (Intel + Apple Silicon)
- **Linux**: Builds Linux binary
- **Windows**: Builds `.exe` binary

Platform is included in artifact names: `sap_ai_proxy-0.1.0-macos.tar.gz`

## Version Source

Version is read from [`pyproject.toml`](../pyproject.toml:3):

```toml
[project]
version = "0.1.0"
```

All version-related commands use this as the source of truth.

## Directory Structure

```
project/
├── dist/                          # Build output
│   └── sap_ai_proxy              # Binary
├── releases/                      # Release artifacts
│   └── v0.1.0/                   # Version-specific releases
│       ├── sap_ai_proxy-0.1.0-macos
│       ├── sap_ai_proxy-0.1.0-macos.tar.gz
│       └── sap_ai_proxy-0.1.0-macos.zip
└── build/                         # PyInstaller build cache
```

## Makefile Commands Reference

### Build Commands

- `make build` - Build standard binary
- `make build-debug` - Build with console output
- `make build-gui` - Build GUI version (no console)
- `make build-tested` - Run tests then build

### Version Management

- `make version-show` - Show current version
- `make version-bump-patch` - Bump patch version
- `make version-bump-minor` - Bump minor version
- `make version-bump-major` - Bump major version

### Git Tagging

- `make tag` - Create git tag for current version
- `make tag-push` - Push tag to remote
- `make tag-and-push` - Create and push tag

### Release Preparation

- `make release-prepare` - Prepare release artifacts
- `make release-github` - Upload to GitHub Releases
- `make release-docker` - Build and tag Docker image
- `make release-all` - Release to all platforms

### Complete Workflows

- `make workflow-patch` - Bump patch, build, tag, prepare
- `make workflow-minor` - Bump minor, build, tag, prepare
- `make workflow-major` - Bump major, build, tag, prepare

### Utilities

- `make test` - Run tests
- `make clean` - Clean build artifacts
- `make clean-all` - Clean everything including releases
- `make info` - Show project information
- `make help` - Show help message

## Best Practices

1. **Always test before versioning**: Use `make build-tested` to ensure tests pass
2. **Review artifacts before uploading**: Check `releases/v*/` directory
3. **Use semantic versioning**:
   - Patch: Bug fixes
   - Minor: New features (backward compatible)
   - Major: Breaking changes
4. **Tag after successful builds**: Only create tags when you're confident in the build
5. **Keep releases directory**: Don't delete old releases for historical reference

## Troubleshooting

### "Tag already exists" error

```bash
# Delete local tag
git tag -d v0.1.0

# Delete remote tag
git push origin :refs/tags/v0.1.0

# Recreate tag
make tag
```

### GitHub CLI not found

Install GitHub CLI:

```bash
# macOS
brew install gh

# Linux
# See https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Windows
# See https://github.com/cli/cli/releases
```

Then authenticate:

```bash
gh auth login
```

### Version not updating

The version is cached. Force re-read:

```bash
make clean
make version-show
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Build
        run: make build
      
      - name: Prepare Release
        run: make release-prepare
      
      - name: Upload to GitHub
        run: make release-github
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Summary

The decoupled workflow provides flexibility:

- **Build** anytime without version changes
- **Version** independently of builds
- **Tag** when ready, not forced by build
- **Upload** to multiple platforms separately

This allows for iterative development, thorough testing, and controlled releases.
