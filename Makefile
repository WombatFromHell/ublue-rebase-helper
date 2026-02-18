PY = python3
SRC_DIR = src
BUILD_DIR = dist
ENTRY = entry:main
OUT = $(BUILD_DIR)/urh.pyz
VERSION_FILE = $(SRC_DIR)/urh/constants.py

# Extract version from pyproject.toml
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
	$(BUILD_DIR) \
	.pytest_cache \
	.ruff_cache \
	.coverage

build: clean
	mkdir -p $(BUILD_DIR)
	# Inject version into constants.py
	sed -i 's/^__version__ = .*/__version__ = "$(VERSION)"/' $(VERSION_FILE)
	$(PY) -m zipapp $(SRC_DIR) -o $(OUT) -m $(ENTRY) -p "/usr/bin/env python3"
	chmod +x $(OUT)

install: $(OUT)
	@if [ -d "$$HOME/.local/bin/scripts/" ]; then \
		INSTALL_DIR="$$HOME/.local/bin/scripts"; \
	else \
		mkdir -p "$$HOME/.local/bin"; \
		INSTALL_DIR="$$HOME/.local/bin"; \
	fi; \
	cp $(OUT) "$$INSTALL_DIR/urh.pyz"; \
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
