# Universal Binary Support Disclaimer

**Universal binary support is not available** for the SAP AI Core LLM Proxy due to limitations in the Python package ecosystem.

## Why Universal Builds Are Not Supported

Building a true universal macOS binary (supporting both Intel x86_64 and Apple Silicon arm64) requires:

1. Universal Python installation (supporting both architectures)
2. All Python dependencies available as universal binaries
3. All compiled extensions (`.so` files) available as universal binaries

**Current Reality**: Most Python packages on PyPI are distributed as architecture-specific wheels. On Apple Silicon Macs, package managers like `pip` and `uv` install ARM64-only binaries by default, making true universal binary builds impossible without significant manual work.

## Recommended Approach

Instead of attempting universal builds, build separate binaries for each architecture:

- **On Apple Silicon Macs**: Creates ARM64 binary
- **On Intel Macs**: Creates x86_64 binary

Distribute both binaries with clear naming:
- `proxy-v0.1.11-macos-arm64`
- `proxy-v0.1.11-macos-x86_64`

This approach is simpler, more reliable, and follows standard practice for Python applications.