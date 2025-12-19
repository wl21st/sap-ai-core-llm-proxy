# Configuration
APP_NAME := sap_ai_proxy
UV := uv
MAIN_SCRIPT := ./proxy_server.py
ICON_FILE := assets/icon.ico
DIST_DIR := dist
BUILD_DIR := build
RELEASE_DIR := releases

# Version management (read from pyproject.toml)
VERSION := $(shell grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
VERSION_FILE := VERSION.txt

# PyInstaller options
PYINSTALLER_OPTS := --onefile \
                    --name $(APP_NAME) \
                    --distpath $(DIST_DIR)

# macOS universal binary options
ifeq ($(shell uname -s),Darwin)
    # Universal binary support is not available due to Python package ecosystem limitations.
    # Most Python packages from PyPI are distributed as architecture-specific wheels,
    # making true universal builds impossible without significant manual work.
    #
    # For multi-architecture distribution, build separately on Intel and ARM64 machines.
    PLATFORM := macos
    BINARY_EXT :=
else ifeq ($(OS),Windows_NT)
    PLATFORM := windows
    BINARY_EXT := .exe
else
    PLATFORM := linux
    BINARY_EXT :=
endif

# Add icon if exists
ifneq ($(wildcard $(ICON_FILE)),)
    PYINSTALLER_OPTS += --icon=$(ICON_FILE)
endif

.PHONY: all build build-debug build-universal clean install test package sync \
        version-show version-bump-patch version-bump-minor version-bump-major \
        tag tag-push release-prepare release-github release-docker release-all \
        workflow-commit-and-tag build-all-platforms

all: build

# ============================================================================
# DEPENDENCY MANAGEMENT
# ============================================================================

# Ensure dependencies are synced
sync:
	$(UV) sync

# Add PyInstaller to project dependencies
install:
	$(UV) add --optional build pyinstaller

# Sync with build dependencies
install-build:
	$(UV) sync --extra build

# ============================================================================
# BUILD TARGETS (Independent of versioning)
# ============================================================================

# Generate version file for PyInstaller
generate-version:
	@echo "Generating version file..."
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	GIT_HASH=$$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
	echo "$$CURRENT_VERSION" > _version.txt; \
	echo "$$GIT_HASH" >> _version.txt; \
	echo "Version file generated: $$CURRENT_VERSION (git: $$GIT_HASH)"

# Standard build
build: install-build generate-version
	@echo "Building $(APP_NAME) for $(PLATFORM)..."
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --add-data "_version.txt:." $(MAIN_SCRIPT)
	@echo "Build complete: $(DIST_DIR)/$(APP_NAME)$(BINARY_EXT)"

# Debug build (console visible)
build-debug: install-build generate-version
	@echo "Building $(APP_NAME) (debug mode) for $(PLATFORM)..."
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --add-data "_version.txt:." --console $(MAIN_SCRIPT)

# GUI build (no console)
build-gui: install-build generate-version
	@echo "Building $(APP_NAME) (GUI mode) for $(PLATFORM)..."
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --add-data "_version.txt:." --windowed $(MAIN_SCRIPT)

# Build with dependencies bundled
build-bundle: install-build generate-version
	@echo "Building $(APP_NAME) with bundled dependencies..."
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --add-data "_version.txt:." --collect-all your_package $(MAIN_SCRIPT)

# Run tests before building
test:
	@echo "Running tests..."
	@if [ -d "tests" ]; then \
		$(UV) sync --extra dev && $(UV) run pytest tests/; \
	else \
		echo "Warning: tests/ directory not found. Skipping tests."; \
	fi

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	$(UV) sync --extra dev && $(UV) run pytest --cov=proxy_server --cov=proxy_helpers --cov-report=html --cov-report=term-missing

# Run tests in verbose mode
test-verbose:
	@echo "Running tests (verbose)..."
	$(UV) sync --extra dev && $(UV) run pytest -v

# Run specific test file
test-file:
	@echo "Running specific test file..."
	@if [ -z "$(FILE)" ]; then \
		echo "Error: Please specify FILE=path/to/test_file.py"; \
		exit 1; \
	fi
	$(UV) sync --extra dev && $(UV) run pytest $(FILE) -v

# Run tests matching a pattern
test-pattern:
	@echo "Running tests matching pattern..."
	@if [ -z "$(PATTERN)" ]; then \
		echo "Error: Please specify PATTERN=your_pattern"; \
		exit 1; \
	fi
	$(UV) sync --extra dev && $(UV) run pytest -k $(PATTERN) -v

# Run integration tests
test-integration:
	@echo "Running integration tests against localhost..."
	$(UV) sync --extra dev && $(UV) run pytest tests/integration/ -m real -v

# Run integration smoke tests
test-integration-smoke:
	@echo "Running integration smoke tests..."
	$(UV) sync --extra dev && $(UV) run pytest tests/integration/ -m "real and smoke" -v

# Run integration streaming tests
test-integration-streaming:
	@echo "Running integration streaming tests..."
	$(UV) sync --extra dev && $(UV) run pytest tests/integration/ -m "real and streaming" -v

# Run integration tests for specific model
test-integration-model:
	@echo "Running integration tests for specific model..."
	@if [ -z "$(MODEL)" ]; then \
		echo "Error: Please specify MODEL=model-name"; \
		echo "Available models: anthropic--claude-4.5-sonnet, sonnet-4.5, gpt-4.1, gpt-5, gemini-2.5-pro"; \
		exit 1; \
	fi
	$(UV) sync --extra dev && $(UV) run pytest tests/integration/ -m real -k "$(MODEL)" -v

# Install test dependencies
install-test-deps:
	@echo "Installing test dependencies..."
	$(UV) sync --extra dev

# Build after testing
build-tested: test build


# ============================================================================
# VERSION MANAGEMENT (Separate from build)
# ============================================================================

# Show current version
version-show:
	@echo "Current version: $(VERSION)"
	@echo "Platform: $(PLATFORM)"

# Bump patch version (0.1.0 -> 0.1.1)
version-bump-patch:
	@echo "Bumping patch version..."
	@NEW_VERSION=$$(echo $(VERSION) | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	sed -i.bak "s/version = \"$(VERSION)\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	$(UV) sync && echo "Version bumped: $(VERSION) -> $$NEW_VERSION"

# Bump minor version (0.1.0 -> 0.2.0)
version-bump-minor:
	@echo "Bumping minor version..."
	@NEW_VERSION=$$(echo $(VERSION) | awk -F. '{print $$1"."$$2+1".0"}'); \
	sed -i.bak "s/version = \"$(VERSION)\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	$(UV) sync && echo "Version bumped: $(VERSION) -> $$NEW_VERSION"

# Bump major version (0.1.0 -> 1.0.0)
version-bump-major:
	@echo "Bumping major version..."
	@NEW_VERSION=$$(echo $(VERSION) | awk -F. '{print $$1+1".0.0"}'); \
	sed -i.bak "s/version = \"$(VERSION)\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	$(UV) sync && echo "Version bumped: $(VERSION) -> $$NEW_VERSION"

# ============================================================================
# GIT TAGGING (Separate from build and version bump)
# ============================================================================

# Create a git tag for current version
tag: generate-version
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Creating git tag v$$CURRENT_VERSION..."; \
	if git rev-parse "v$$CURRENT_VERSION" >/dev/null 2>&1; then \
		echo "Tag v$$CURRENT_VERSION already exists!"; \
		exit 1; \
	fi; \
	git tag -a "v$$CURRENT_VERSION" -m "Release version $$CURRENT_VERSION"; \
	echo "Tag v$$CURRENT_VERSION created successfully"; \
	echo "To push tag, run: make tag-push"

# Push git tag to remote
tag-push:
	@echo "Pushing tag v$(VERSION) to remote..."
	git push origin "v$(VERSION)"
	@echo "Tag v$(VERSION) pushed successfully"

# Complete workflow: commit version changes, push, then tag
workflow-commit-and-tag: generate-version
	@echo "Committing version changes and pushing..."
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	git add pyproject.toml uv.lock && \
	git commit -m "chore: bump version to $$CURRENT_VERSION" && \
	git push origin main && \
	echo "Creating git tag v$$CURRENT_VERSION..." && \
	if git rev-parse "v$$CURRENT_VERSION" >/dev/null 2>&1; then \
		echo "Tag v$$CURRENT_VERSION already exists!"; \
		exit 1; \
	fi; \
	git tag -a "v$$CURRENT_VERSION" -m "Release version $$CURRENT_VERSION" && \
	echo "Tag v$$CURRENT_VERSION created successfully" && \
	echo "Pushing tag to remote..." && \
	git push origin "v$$CURRENT_VERSION" && \
	echo "Tag v$$CURRENT_VERSION pushed successfully"

# ============================================================================
# RELEASE PREPARATION (After build, before upload)
# ============================================================================

# Prepare release artifacts with version
release-prepare: build
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	RELEASE_PATH="$(RELEASE_DIR)/v$$CURRENT_VERSION"; \
	echo "Preparing release artifacts for version $$CURRENT_VERSION..."; \
	mkdir -p "$$RELEASE_PATH" && \
	cp $(DIST_DIR)/$(APP_NAME)$(BINARY_EXT) "$$RELEASE_PATH/$(APP_NAME)-$$CURRENT_VERSION-$(PLATFORM)$(BINARY_EXT)" && \
	(cd "$$RELEASE_PATH" && tar -czf $(APP_NAME)-$$CURRENT_VERSION-$(PLATFORM).tar.gz $(APP_NAME)-$$CURRENT_VERSION-$(PLATFORM)$(BINARY_EXT)) && \
	(cd "$$RELEASE_PATH" && zip -q $(APP_NAME)-$$CURRENT_VERSION-$(PLATFORM).zip $(APP_NAME)-$$CURRENT_VERSION-$(PLATFORM)$(BINARY_EXT)) && \
	echo "Release artifacts prepared in $$RELEASE_PATH/" && \
	ls -lh "$$RELEASE_PATH/"

# ============================================================================
# MULTI-PLATFORM RELEASE TARGETS
# ============================================================================

# Upload to GitHub Releases (requires gh CLI)
release-github:
	@echo "Uploading to GitHub Releases for v$(VERSION)..."
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "Error: GitHub CLI (gh) not found. Install from https://cli.github.com/"; \
		exit 1; \
	fi
	@if ! gh release view "v$(VERSION)" >/dev/null 2>&1; then \
		echo "Creating GitHub release v$(VERSION)..."; \
		gh release create "v$(VERSION)" --title "Release v$(VERSION)" --notes "Release version $(VERSION)"; \
	fi
	@echo "Uploading artifacts..."
	gh release upload "v$(VERSION)" $(RELEASE_DIR)/v$(VERSION)/*.tar.gz $(RELEASE_DIR)/v$(VERSION)/*.zip --clobber
	@echo "Upload to GitHub complete!"

# Build and push Docker image (single platform)
release-docker:
	@echo "Building Docker image for v$(VERSION)..."
	@if [ ! -f Dockerfile ]; then \
		echo "Error: Dockerfile not found"; \
		exit 1; \
	fi
	docker build -t $(APP_NAME):$(VERSION) -t $(APP_NAME):latest .
	@echo "Docker image built. To push to registry:"
	@echo "  docker tag $(APP_NAME):$(VERSION) your-registry/$(APP_NAME):$(VERSION)"
	@echo "  docker push your-registry/$(APP_NAME):$(VERSION)"

# Build multi-platform Docker image (amd64 and arm64)
release-docker-multiplatform:
	@echo "Building multi-platform Docker image for v$(VERSION)..."
	@if [ ! -f Dockerfile ]; then \
		echo "Error: Dockerfile not found"; \
		exit 1; \
	fi
	@echo "Setting up buildx builder..."
	@docker buildx create --name multiplatform-builder --use 2>/dev/null || docker buildx use multiplatform-builder
	@echo "Building for linux/amd64 and linux/arm64..."
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-t $(APP_NAME):$(VERSION) \
		-t $(APP_NAME):latest \
		--load \
		.
	@echo "Multi-platform Docker image built successfully!"
	@echo "To push to registry:"
	@echo "  docker buildx build --platform linux/amd64,linux/arm64 \\"
	@echo "    -t your-registry/$(APP_NAME):$(VERSION) \\"
	@echo "    -t your-registry/$(APP_NAME):latest \\"
	@echo "    --push ."

# Build and push multi-platform Docker image to registry
release-docker-multiplatform-push:
	@echo "Building and pushing multi-platform Docker image for v$(VERSION)..."
	@if [ ! -f Dockerfile ]; then \
		echo "Error: Dockerfile not found"; \
		exit 1; \
	fi
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Error: REGISTRY variable not set"; \
		echo "Usage: make release-docker-multiplatform-push REGISTRY=your-registry"; \
		exit 1; \
	fi
	@echo "Setting up buildx builder..."
	@docker buildx create --name multiplatform-builder --use 2>/dev/null || docker buildx use multiplatform-builder
	@echo "Building and pushing for linux/amd64 and linux/arm64..."
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-t $(REGISTRY)/$(APP_NAME):$(VERSION) \
		-t $(REGISTRY)/$(APP_NAME):latest \
		--push \
		.
	@echo "Multi-platform Docker image pushed to $(REGISTRY)/$(APP_NAME):$(VERSION)"

# Upload to PyPI (if applicable)
release-pypi:
	@echo "Building Python package for PyPI..."
	$(UV) build
	@echo "To upload to PyPI, run:"
	@echo "  uv publish"

# Release to all platforms
release-all: release-prepare release-github release-docker
	@echo "Release $(VERSION) completed for all platforms!"

# ============================================================================
# COMPLETE WORKFLOWS
# ============================================================================

# Complete workflow: bump version, build, commit, push, tag, and prepare release
workflow-patch: version-bump-patch build-tested workflow-commit-and-tag release-prepare
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Patch release workflow complete!"; \
	echo "Next steps:"; \
	echo "  1. Review artifacts in $(RELEASE_DIR)/v$$CURRENT_VERSION/"; \
	echo "  2. Upload to platforms: make release-github"

workflow-minor: version-bump-minor build-tested workflow-commit-and-tag release-prepare
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Minor release workflow complete!"; \
	echo "Next steps:"; \
	echo "  1. Review artifacts in $(RELEASE_DIR)/v$$CURRENT_VERSION/"; \
	echo "  2. Upload to platforms: make release-github"

workflow-major: version-bump-major build-tested workflow-commit-and-tag release-prepare
	@CURRENT_VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Major release workflow complete!"; \
	echo "Next steps:"; \
	echo "  1. Review artifacts in $(RELEASE_DIR)/v$$CURRENT_VERSION/"; \
	echo "  2. Upload to platforms: make release-github"

# ============================================================================
# CLEANUP
# ============================================================================

# Clean build artifacts only
clean:
	rm -rf $(DIST_DIR) $(BUILD_DIR) $(RELEASE_DIR) __pycache__
	rm -f sap_ai_proxy.spec _version.txt
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Clean everything including releases
clean-all: clean
	rm -rf $(RELEASE_DIR)

# ============================================================================
# UTILITIES
# ============================================================================

# Create distribution package (legacy)
package: build
	cd $(DIST_DIR) && tar -czf $(APP_NAME).tar.gz $(APP_NAME)$(BINARY_EXT)

# Show project info
info:
	@echo "Project: $(APP_NAME)"
	@echo "Version: $(VERSION)"
	@echo "Platform: $(PLATFORM)"
	@echo ""
	$(UV) tree
	$(UV) pip list

# Show help
help:
	@echo "SAP AI Core LLM Proxy - Makefile Commands"
	@echo ""
	@echo "BUILD COMMANDS:"
	@echo "  make generate-version   - Generate _version.txt file for builds"
	@echo "  make build              - Build native binary (current architecture)"
	@echo "  make build-debug        - Build with console output"
	@echo "  make build-gui          - Build GUI version (no console)"
	@echo ""
	@echo "MULTI-ARCHITECTURE BUILDING (macOS):"
	@echo "  Universal binary support is not available due to Python package ecosystem limitations."
	@echo "  For multi-architecture distribution, build separately on Intel and ARM64 machines."
	@echo "  Recommended: Build on Intel Mac for x86_64, ARM Mac for arm64"
	@echo ""
	@echo "TESTING:"
	@echo "  make test                      - Run all tests"
	@echo "  make test-cov                  - Run tests with coverage report"
	@echo "  make test-verbose              - Run tests with verbose output"
	@echo "  make test-file FILE=...        - Run specific test file"
	@echo "  make test-pattern PATTERN=...  - Run tests matching pattern"
	@echo "  make test-integration          - Run integration tests against localhost"
	@echo "  make test-integration-smoke    - Run integration smoke tests"
	@echo "  make test-integration-streaming - Run integration streaming tests"
	@echo "  make test-integration-model MODEL=... - Run tests for specific model"
	@echo "  make build-tested              - Run tests then build"
	@echo "  make install-test-deps         - Install test dependencies"
	@echo ""
	@echo "VERSION MANAGEMENT:"
	@echo "  make version-show       - Show current version"
	@echo "  make version-bump-patch - Bump patch version (0.1.0 -> 0.1.1)"
	@echo "  make version-bump-minor - Bump minor version (0.1.0 -> 0.2.0)"
	@echo "  make version-bump-major - Bump major version (0.1.0 -> 1.0.0)"
	@echo ""
	@echo "GIT TAGGING:"
	@echo "  make tag                - Create git tag for current version"
	@echo "  make tag-push           - Push tag to remote"
	@echo "  make tag-and-push       - Create and push tag"
	@echo ""
	@echo "RELEASE PREPARATION:"
	@echo "  make release-prepare    - Prepare release artifacts"
	@echo "  make release-github     - Upload to GitHub Releases"
	@echo "  make release-docker     - Build Docker image (single platform)"
	@echo "  make release-docker-multiplatform - Build multi-platform image (amd64+arm64)"
	@echo "  make release-docker-multiplatform-push REGISTRY=... - Build and push multi-platform"
	@echo "  make release-all        - Release to all platforms"
	@echo ""
	@echo "COMPLETE WORKFLOWS:"
	@echo "  make workflow-patch     - Bump patch, build, tag, prepare"
	@echo "  make workflow-minor     - Bump minor, build, tag, prepare"
	@echo "  make workflow-major     - Bump major, build, tag, prepare"
	@echo ""
	@echo "UTILITIES:"
	@echo "  make test               - Run tests"
	@echo "  make clean              - Clean build artifacts"
	@echo "  make clean-all          - Clean everything including releases"
	@echo "  make info               - Show project information"
	@echo "  make help               - Show this help message"
