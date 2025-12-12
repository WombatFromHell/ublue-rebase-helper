# AGENTS.md - Tool Usage Guide for Agentic Tools

## Development Environment Tools

### Testing Tools

- `make test` - Full test suite with coverage reporting

### Code Quality Tools

- `make quality` - Code linting/formatting checks
- `make radon` - Code complexity analysis

## Agent Workflow

1. **Testing**: Use `uv run pytest -xvs` for test execution
2. **Quality Checks**: Run `make quality` before commits to validate linting/formatting
3. **Complexity Analysis**: Use `make radon` for refactoring code complexity validation
4. Building and Deployment: Use `make all` to clean, build, and install locally to `~/.local/bin/urh`
5. **Dependency Management**: Use `uv` for package operations
