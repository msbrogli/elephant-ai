# Elephant - Project Guidelines

## Package Manager
Always use `uv` to run commands. Never use raw `pip`, `python -m pytest`, etc.
- Run tests: `uv run pytest tests/`
- Run linter: `uv run ruff check src/ tests/`
- Run type checker: `uv run mypy src/`
- Run a single test file: `uv run pytest tests/test_foo.py -v`

## Project Structure
- Source code: `src/elephant/`
- Tests: `tests/`
- Config: `pyproject.toml` (ruff, mypy, pytest all configured there)
- Python >=3.12, async-first (aiohttp), Pydantic models, YAML data store

## Code Style
- Ruff for linting (line-length 100, target py312)
- mypy strict mode
- pytest with asyncio_mode=auto (no need for @pytest.mark.asyncio)
- Use `from __future__ import annotations` in source files
