# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AEGIS Project Guidelines for Claude

## Python Environment Setup
This project uses Python 3.13.2 on macOS with Homebrew. Due to PEP 668, a virtual environment is required.

### Setting up the virtual environment
```bash
# Create virtual environment (one time only)
python3 -m venv venv

# Activate virtual environment (every new terminal session)
source venv/bin/activate

# Install project and development dependencies
pip install -e .
pip install -e ".[dev]"
pip install pylint  # Additional tool not in setup.py
```

## Build Commands
- Install: `pip install -e .`
- Install dev tools: `pip install -e ".[dev]"`
- Install pylint: `pip install pylint`
- Run notebook: `jupyter notebook notebooks/test_notebook.ipynb`

## Linting and Formatting Commands
Always run these from the project root directory with the virtual environment activated:

### Black (Code Formatter)
- Format all code: `python -m black aegis/`
- Check formatting without changing: `python -m black --check aegis/`
- Format specific file: `python -m black aegis/src/chat_model/model.py`

### Pylint (Linter)
- Lint entire codebase: `python -m pylint aegis/`
- Lint specific module: `python -m pylint aegis/src/chat_model/`
- Lint with specific config: `python -m pylint --rcfile=.pylintrc aegis/`
- Disable specific warnings: `python -m pylint --disable=C0103,R0903 aegis/`

### MyPy (Type Checker)
- Type check: `python -m mypy aegis/`
- Type check with config: `python -m mypy --config-file mypy.ini aegis/`

## Testing
- Run tests: `pytest`
- Single test: `pytest path/to/test.py::test_function_name`
- With coverage: `pytest --cov=aegis`

## Code Style

### Imports
- External imports first, then relative imports
- Import specific functions rather than entire modules
- Group related imports together

### Formatting
- 4-space indentation (enforced by Black)
- 88 character line limit (Black default)
- Triple double quotes for docstrings (`"""`)
- Google-style docstrings with Args/Returns/Raises sections

### Naming & Types
- snake_case for functions and variables
- PascalCase for classes
- UPPER_SNAKE_CASE for constants
- Document types in docstrings and use type hints

### Error Handling
- Use custom exception classes when appropriate
- Catch specific exceptions
- Provide detailed error messages
- Log errors at appropriate levels
- Truncate sensitive information in logs

## Quick Reference Commands
```bash
# Activate virtual environment
source venv/bin/activate

# Run all linting and formatting
python -m black aegis/
python -m pylint aegis/
python -m mypy aegis/

# Run tests
pytest

# Deactivate virtual environment when done
deactivate
```

## Important Notes for macOS with Homebrew Python
- Always use `python3` or `python` (when venv is active) instead of system python
- Always activate the virtual environment before running any pip commands
- Use `python -m <tool>` syntax to ensure the correct tool version is used
- If you get "externally-managed-environment" errors, you forgot to activate the venv

## Testing Environment Note
The database refresh scripts (`aegis-database-refresh/`) are tested in an external corporate environment separate from this development machine. When making changes to these scripts:
- Focus on code correctness and proper error handling
- Ensure all dependencies are properly declared in setup.py
- The scripts will be tested with real corporate data and infrastructure that cannot be accessed from this development environment