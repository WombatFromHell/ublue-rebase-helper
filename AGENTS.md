# AGENTS Guide for ublue-rebase-helper

This document provides instructions for AI agents and automated tools working with this Python project.

## Project Overview

This is a Python project that uses:

- `uv` for dependency management and execution
- `pytest` for unit testing
- `pytest-mock` for mocking capabilities in tests
- `ruff` for formatting and linting
- `pyright` for type checking
- `prettier` for formatting/linting of markdown files

## Testing Commands

When running tests, AI agents should use the following command `uv run pytest`.

For more specific test runs, agents can use standard pytest options:

- `uv run pytest tests/test_units.py` - run unit tests
- `uv run pytest tests/test_integrations.py` - run integration tests
- `uv run pytest tests/test_e2e.py` - run end-to-end tests
- `uv run pytest -v` - run with verbose output
- `uv run slipcover -m pytest -v` - run with test harness for code coverage report

## Code Formatting and Linting

AI agents should format and lint changes to code using this command: `ruff check --select I --fix; ruff format; pyright`. Likewise, if either our `AGENTS.md` or `DESIGN.md` are changed then `prettier --cache -c -w *.md` should be run afterward to ensure consistent formatting.

Formatting and linting should be run before finishing any code changes.

## Recommended Workflow

1. Read `DESIGN.md` and adhere to our existing design spec before constructing any code changes or action plans
2. After making code changes, run `ruff check --select I --fix; ruff format; pyright` to format/lint the code
3. Run `ruff check --select I --fix; ruff format` to check and correct for linting and/or formatting issues
4. Run `prettier --cache -c -w *.md` from the project root to format markdown files
5. Run `pyright` to check for type errors
6. Run `uv run pytest -vs` to ensure all tests pass

## Project Structure

- `urh.py` - Main application entry point
- `pyproject.toml` - Project dependencies and configuration
- `DESIGN.md` - Design document
- `tests/` - Test files (if present)
- `README.md` - Project documentation
- `AGENTS.md` - This file

## Best Practices for AI Agents

- Before attempting to make any design changes to project files create a comprehensive but concise step-by-step action plan that the user must explicitly approve before changing anything
- Always run the full test suite with `uv run pytest` after making changes
- Use `pytest-mock` fixtures for creating test mocking when writing tests
- Follow existing code style and patterns in the project
- Use `ruff check --select I --fix; ruff format` before committing changes
- Verify type correctness with `pyright` before finalizing changes
- Add appropriate unit tests for new functionality
- Ensure all existing tests continue to pass
- When implementing new features or making significant changes, a planning step must be presented to and approved by the user before any code changes are applied to the codebase
- No destructive changes can be applied to the project without explicit user approval first
- When design changes are made, update the DESIGN.md document to reflect current implementation decisions

## Testing Standards

When writing tests for this project, AI agents must:

- Use `pytest-mock` fixtures (`mocker`, `MockerFixture`, and `monkeypatch`) instead of the `unittest` module
- Organize tests into appropriate categories: unit tests (`test_units.py`), integration tests (`test_integrations.py`), and end-to-end tests (`test_e2e.py`)
- Keep unit tests focused on individual functions with minimal mocking
- Write integration tests that validate how components work together
- Create end-to-end tests that simulate complete user workflows
- Favor pytest's parametrization (`@pytest.mark.parametrize`) for tests that cover similar functionality with different input values, rather than splitting them into multiple discrete tests unless their code concerns are different
- When test functions are similarly named yet test different code concerns, change each test function name to concisely reflect what the test's specific code concern is to prevent tests from shadowing each other
