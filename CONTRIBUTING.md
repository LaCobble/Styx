# Contributing

Thanks for your interest! Styx is a personal project. Contributions are welcome, especially bug fixes, tests and reviews of the cryptography. Security issues follow [SECURITY.md](SECURITY.md).

## Prerequisites

- Python 3.9 or newer.
- The packages in the requirements file (`cryptography`, `PyQt5`).

## Check your change

```bash
pip install -r requirement.txt   # requirements.txt once the package refactor is merged
python -m compileall -q .
python -m pytest -q              # when a tests/ folder is present
```

The same checks run in CI on every pull request.

## Workflow

1. Create a branch from `main` named `type/short-topic` (for example `fix/flag-placement`).
2. Write commits following [Conventional Commits](https://www.conventionalcommits.org/) (`fix: …`, `feat: …`, `docs: …`).
3. Open a pull request using the template, and make sure CI is green.
4. Pull requests are merged with **squash and merge**.

## Versioning

The project follows [Semantic Versioning](https://semver.org/). User-visible changes go under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md). A release is cut by tagging `main` with `vX.Y.Z`; the release workflow then publishes the GitHub Release from the changelog.

## Rules

- Never commit secrets, personal data or generated files.
- Be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md).
