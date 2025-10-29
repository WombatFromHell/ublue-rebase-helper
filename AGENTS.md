# AGENTS Guide for ublue-rebase-helper

This document provides instructions for AI agents and automated tools working with this Python project.

## Project Overview

This is a Python project that uses:

- `uv` for dependency management and execution
- `pytest` for unit testing
- `pytest-mock` for mocking capabilities in tests
- `ruff` for formatting and linting
- `pyright` for type checking

## Testing Commands

When running tests, AI agents should use the following command:

```bash
uv run pytest
```

For more specific test runs, agents can use standard pytest options:

- `uv run pytest tests/test_units.py` - run unit tests
- `uv run pytest tests/test_integrations.py` - run integration tests
- `uv run pytest tests/test_e2e.py` - run end-to-end tests
- `uv run pytest -v` - run with verbose output
- `uv run slipcover -m pytest` - run with code coverage

## Code Formatting and Linting

AI agents should format and lint changes to code using this command: `ruff format .; ruff check . --fix; pyright .`

Formatting and linting should be run before finishing any code changes.

## Recommended Workflow

1. After making code changes, run `ruff format .; ruff check . --fix; pyright .` to format/lint the code
2. Run `ruff check . --fix` to check for linting issues
3. Run `pyright .` to check for type errors
4. Run `uv run pytest -x -v` to ensure all tests pass

## Project Structure

- `urh.py` - Main application entry point
- `pyproject.toml` - Project dependencies and configuration
- `DESIGN.md` - Design document
- `tests/` - Test files (if present)
- `README.md` - Project documentation
- `AGENTS.md` - This file

## Best Practices for AI Agents

- Always run the full test suite with `uv run pytest` after making changes
- Use `pytest-mock` for creating test doubles when writing tests
- Follow existing code style and patterns in the project
- Use `ruff format .` before committing changes
- Verify type correctness with `pyright .` before finalizing changes
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

