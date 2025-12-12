PY = python3
SRC_DIR = src
BUILD_DIR = dist
STAGING = .build
ENTRY = src.entry:main
OUT = $(BUILD_DIR)/urh.pyz

build:
	mkdir -p $(BUILD_DIR)
	rm -rf $(STAGING)
	mkdir -p $(STAGING)
	cp -r $(SRC_DIR) $(STAGING)/
	$(PY) -m zipapp $(STAGING) -o $(OUT) -m $(ENTRY) -p "/usr/bin/env python3"
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
	uv run pytest -xvs --cov=src --cov-report=term-missing --cov-branch

lint:
	ruff check ./src ./tests; \
		pyright ./src ./tests

prettier:
	prettier --cache -c -w *.md

format: prettier
	ruff check --select I ./src ./tests --fix; \
	ruff format ./src ./tests

quality: lint format

radon:
	uv run radon cc ./src/urh/ -a

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +; \
	rm -rf \
		$(STAGING) \
		$(BUILD_DIR) \
		.pytest_cache \
		.ruff_cache \
		.coverage

all: clean build install

.PHONY: all clean install build test lint format radon
