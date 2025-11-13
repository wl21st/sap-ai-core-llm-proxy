# Configuration
APP_NAME := sap_ai_proxy_server
UV := uv
MAIN_SCRIPT := ./proxy_server.py
ICON_FILE := assets/icon.ico
DIST_DIR := dist
BUILD_DIR := build

# PyInstaller options
PYINSTALLER_OPTS := --onefile \
                    --name $(APP_NAME) \
                    --distpath $(DIST_DIR)

# Add icon if exists
ifneq ($(wildcard $(ICON_FILE)),)
    PYINSTALLER_OPTS += --icon=$(ICON_FILE)
endif

.PHONY: all build build-debug clean install test package sync

all: build

# Ensure dependencies are synced
sync:
	$(UV) sync

# Standard build
build: sync
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) $(MAIN_SCRIPT)

# Debug build (console visible)
build-debug: sync
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --console $(MAIN_SCRIPT)

# GUI build (no console)
build-gui: sync
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --windowed $(MAIN_SCRIPT)

# Build with dependencies bundled
build-bundle: sync
	$(UV) run pyinstaller $(PYINSTALLER_OPTS) --collect-all your_package $(MAIN_SCRIPT)

# Clean all build artifacts
clean:
	rm -rf $(DIST_DIR) $(BUILD_DIR) *.spec __pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Add PyInstaller to project dependencies
install:
	$(UV) add pyinstaller

# Add PyInstaller as dev dependency
install-dev:
	$(UV) add --dev pyinstaller

# Run tests before building
test: sync
	$(UV) run pytest tests/

# Build after testing
build-tested: test build

# Create distribution package
package: build
	cd $(DIST_DIR) && tar -czf $(APP_NAME).tar.gz $(APP_NAME)

# Show project info
info:
	$(UV) tree
	$(UV) pip list