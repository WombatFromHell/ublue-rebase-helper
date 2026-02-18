#!/usr/bin/env make
# Deterministic build system for ublue-rebase-helper
# Uses staging-directory approach with fixed timestamps for bitwise reproducibility

PY ?= $(PYTHON)
SRC_DIR = src
BUILD_DIR = dist
ENTRY = entry:main
ARTIFACT = urh.pyz
OUT = $(BUILD_DIR)/$(ARTIFACT)
VERSION_FILE = $(SRC_DIR)/urh/constants.py

# Ensure SOURCE_DATE_EPOCH is set for deterministic timestamps
# Default to Jan 1, 1980 00:00:00 UTC (315532800) if not set
SOURCE_DATE_EPOCH ?= 315532800
export SOURCE_DATE_EPOCH

# Extract version from pyproject.toml
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)

# Human-readable timestamp for logging
TIMESTAMP := $(shell date -d "@$(SOURCE_DATE_EPOCH)" -u +%Y-%m-%dT%H:%M:%SZ)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
	$(BUILD_DIR) \
	.pytest_cache \
	.ruff_cache \
	.coverage \
	.direnv

build: clean
	@echo "Building $(ARTIFACT) (version $(VERSION))"
	@echo "SOURCE_DATE_EPOCH: $(SOURCE_DATE_EPOCH) ($(TIMESTAMP))"
	mkdir -p $(BUILD_DIR)

	# Inject version into constants.py
	sed -i 's/^__version__ = .*/__version__ = "$(VERSION)"/' $(VERSION_FILE)

	# Create staging directory for deterministic build
	# Copy contents of src/ directly into staging (not src/ itself)
	rm -rf $(BUILD_DIR)/staging
	mkdir -p $(BUILD_DIR)/staging
	cp -r $(SRC_DIR)/* $(BUILD_DIR)/staging/

	# Create __main__.py for zipapp entry point (overwrite if exists)
	echo "from entry import main; main()" > $(BUILD_DIR)/staging/__main__.py

	# Normalize timestamps on ALL files in staging directory
	# This is crucial for bitwise determinism
	find $(BUILD_DIR)/staging -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;

	# Create the zip archive deterministically
	# -X: strip extra file attributes
	# -q: quiet mode
	# Using 'find | LC_ALL=C sort' ensures consistent file ordering across systems
	cd $(BUILD_DIR)/staging && \
		find . -type f | LC_ALL=C sort | \
		zip -X -q -@ ../archive.zip

	# Prepend shebang to create executable pyz
	echo '#!/usr/bin/env python3' > $(OUT)
	cat $(BUILD_DIR)/archive.zip >> $(OUT)
	chmod +x $(OUT)

	# Generate SHA256 checksum file for verification (basename only for portability)
	cd $(BUILD_DIR) && sha256sum $(ARTIFACT) > $(ARTIFACT).sha256sum

	# Cleanup staging and intermediate files
	rm -rf $(BUILD_DIR)/staging $(BUILD_DIR)/archive.zip

	@echo "Built: $(OUT)"
	@echo "SHA256: $$(cat $(OUT).sha256sum | cut -d' ' -f1)"

install: $(OUT)
	@if [ -d "$$HOME/.local/bin/scripts/" ]; then \
		INSTALL_DIR="$$HOME/.local/bin/scripts"; \
	else \
		mkdir -p "$$HOME/.local/bin"; \
		INSTALL_DIR="$$HOME/.local/bin"; \
	fi; \
	cp $(OUT) $(OUT).sha256sum "$$INSTALL_DIR/"; \
	chmod +x "$$INSTALL_DIR/urh.pyz"; \
	ln -sf "$$INSTALL_DIR/urh.pyz" "$$HOME/.local/bin/urh"; \
	echo "Installed to $$INSTALL_DIR/urh.pyz"

test:
	uv run pytest --tb=short --cov=src --cov-report=term-missing --cov-branch

lint:
	uv run ty check ./src ./tests; \
	uv run ruff check ./src ./tests --fix

prettier:
	uv run prettier -c -w *.md

format: prettier
	uv run ruff check --select I ./src ./tests --fix; \
	uv run ruff format ./src ./tests

quality: lint format

radon:
	uv run radon cc ./src/urh/ -a

all: clean build install

.PHONY: all clean install build test lint prettier format radon
.SILENT: all clean install build test lint prettier format radon
