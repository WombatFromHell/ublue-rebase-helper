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
- `curl` for OCI registry interactions (required dependency)

## Testing Commands

When running tests, AI agents should use the following command `uv run pytest`.

For more specific test runs, agents can use standard pytest options:

- `uv run pytest -v` - run full test suite with verbose output
- `uv run pytest -v --cov=src --cov-report=term-missing` run test suite with `pytest-cov` code coverage report
- Measure Halstead metrics via Radon with the command: `uv run radon hal src/`
- Measure cyclomatic code complexity via Radon using letter grades with the command: `uv run radon cc src/ -a`

## Code Formatting and Linting

AI agents should format and lint changes to code using this command: `ruff check --select I --fix; ruff format; pyright`. Likewise, if either our `AGENTS.md` or `DESIGN.md` are changed then `prettier --cache -c -w *.md` should be run afterward to ensure consistent formatting.

Formatting and linting should be run before finishing any code changes.

## Recommended Workflow

- Read `DESIGN.md` and strictly adhere to listed design spec before constructing any code changes or action plans
- `DESIGN.md` acts as our spec document and single-source-of-truth upon which our implementation and test suite is designed
- Run `ruff check --select I --fix; ruff format; pyright` to check and correct for linting, typing, and formatting issues
- After making code changes, make sure to run our ruff/pyright commands above to format/lint the code
- Run `prettier --cache -c -w *.md` from the project root to format markdown files
- After making changes to markdown files, run our prettier command above to format them
- Run `pyright` to check for type errors
- Run `uv run pytest -vs` to ensure all tests pass
- Run `uv run radon cc src/ -a` to ensure our code complexity stays at A or better

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
- Check for required system dependencies (like `curl`) using utility functions before executing dependent functionality
- Use centralized command registries for managing command definitions and handlers
- Implement proper exit code handling by using `sys.exit()` with appropriate exit codes from underlying commands
- Follow the established pattern of using dataclasses for configuration and command definitions
- Use dedicated exception classes like `MenuExitException` for specific control flow scenarios
- Implement both gum-based and text-based fallback interfaces to ensure functionality across different environments
- Apply proper input validation on numeric arguments to prevent command injection
- Use NamedTuple for structured data representations like DeploymentInfo
- Implement token caching and validation mechanisms for external API interactions

## Testing Standards

When writing tests for this project, AI agents must:

- Use `pytest-mock` fixtures (`mocker`, `MockerFixture`, and `monkeypatch`) instead of the `unittest` module
- Organize tests into appropriate categories: unit tests (`test_units.py`), integration tests (`test_integrations.py`), and end-to-end tests (`test_e2e.py`)
- Keep unit tests focused on individual functions with minimal mocking
- Write integration tests that validate how components work together
- Create end-to-end tests that simulate complete user workflows
- Favor pytest's parametrization (`@pytest.mark.parametrize`) for tests that cover similar functionality with different input values, rather than splitting them into multiple discrete tests unless their code concerns are different
- When test functions are similarly named yet test different code concerns, change each test function name to concisely reflect what the test's specific code concern is to prevent tests from shadowing each other
