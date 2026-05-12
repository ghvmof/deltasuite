# Contributing to DeltaSuite

Thank you for your interest in contributing! DeltaSuite is a community project and we welcome bug reports, feature requests, documentation improvements and code contributions of all sizes.

## Code of Conduct

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

| Type | How |
|---|---|
| Bug reports | Open an [issue](https://github.com/ghvmof/deltasuite/issues) describing what happened, what you expected and how to reproduce it |
| Feature requests | Open an issue tagged `enhancement` describing the use case |
| Documentation | Edit files under `docs/` and submit a pull request |
| Code | Fork the repo, create a branch, submit a pull request following the guidelines below |
| Translations | We use Qt Linguist `.ts` files in `src/deltasuite/resources/i18n/` |

## Development setup

```bash
git clone https://github.com/ghvmof/deltasuite.git
cd deltasuite

python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # Linux / Mac

pip install -e .[dev,viz,science,delft3d,docs]
pre-commit install
```

## Coding standards

- **Python style:** enforced by Ruff with the configuration in `pyproject.toml`. Run `ruff format .` before committing.
- **Type hints:** all new code should include type annotations and pass `mypy src` in strict mode.
- **Docstrings:** Google or NumPy style for all public functions, classes and modules.
- **Naming:**
  - Modules / packages: `snake_case`
  - Classes: `PascalCase`
  - Functions / variables: `snake_case`
  - Qt slots: `on_<widget>_<signal>` convention
- **Imports:** sorted automatically by Ruff (isort-compatible).
- **Line length:** 100 characters max.

## Tests

- All new features must include unit tests under `tests/`.
- Use `pytest-qt` fixtures (`qtbot`, `qapp`) for GUI tests.
- Mark slow or integration tests with `@pytest.mark.slow` or `@pytest.mark.integration`.

```bash
pytest                    # Fast tests
pytest -m "not slow"      # Skip slow ones
pytest --cov              # With coverage report
```

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(mesh): add curvilinear grid generator
fix(runner): resolve deadlock when killing process on Windows
docs(readme): clarify installation instructions
test(io): cover edge case in .mdf parser
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

## Pull request process

1. Fork the repository and create a topic branch from `main`.
2. Make your changes following the coding standards.
3. Add or update tests as needed.
4. Update `CHANGELOG.md` under the `[Unreleased]` section.
5. Ensure all CI checks pass (`ruff check`, `mypy src`, `pytest`).
6. Open a pull request describing the change and linking related issues.
7. A maintainer will review, request changes if needed, and merge.

## License of contributions

By submitting a contribution you agree that it will be released under the same GPL-3.0-or-later license as the rest of DeltaSuite.

## Questions

Open a thread under [GitHub Discussions](https://github.com/ghvmof/deltasuite/discussions). Thank you for helping make DeltaSuite better!
