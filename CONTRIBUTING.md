# Contributing to pinterest-downloader

Thank you for your interest in contributing. This document explains how to propose changes cleanly and consistently.

## Code of conduct

Be respectful and constructive. Harassment, personal attacks, or bad-faith contributions will not be tolerated. Maintainers may close issues or PRs that violate this standard.

## Ways to contribute

- Bug reports with clear reproduction steps
- Feature proposals with a concrete use case
- Documentation improvements
- Code fixes and carefully scoped enhancements
- Dependency / packaging updates

## Before you start

1. Search [existing issues](https://github.com/MrHacker-X/pinterest-downloader/issues) and pull requests to avoid duplicates.
2. For larger changes, open an issue first so maintainers can discuss scope.
3. Keep pull requests focused — one concern per PR.

## Development setup

```bash
git clone https://github.com/MrHacker-X/pinterest-downloader.git
cd pinterest-downloader

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Quick sanity check:

```bash
python pinterest_downloader.py -v
python pinterest_downloader.py -h
```

## Coding guidelines

- Target **Python 3.9+**
- Match the existing style: clear names, modest comments, no drive-by refactors
- Prefer small, reviewable diffs over broad rewrites
- Preserve graceful **Ctrl+C** / signal handling and session resume behavior
- Do not add login, cookie-harvesting, or credential-related features
- Do not commit downloaded images, virtualenvs, or session state files
- Keep dependencies minimal; justify any new package in the PR description

## Commit messages

Use short, imperative subjects:

```text
fix: stop worker pool promptly on SIGINT
docs: clarify resume behavior in README
feat: add --version flag
```

## Pull request checklist

Before opening a PR, confirm:

- [ ] The change solves one clear problem
- [ ] `python pinterest_downloader.py -h` and `-v` still work
- [ ] Manual smoke test completed for download / interrupt / resume paths you touched
- [ ] Documentation updated when behavior or CLI options change
- [ ] No secrets, personal downloads, or generated media committed
- [ ] LICENSE and attribution remain intact

### PR description template

```markdown
## Summary
What changed and why.

## Test plan
- [ ] Command(s) you ran
- [ ] Expected vs actual behavior
```

## Reporting bugs

Include:

- OS and Python version
- Exact command used
- Full error output (redact personal paths if needed)
- Whether the issue is reproducible

## Feature requests

Describe:

- The problem you are solving
- Proposed CLI / behavior
- Alternatives you considered
- Why it fits a guest / no-login downloader

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
