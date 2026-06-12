# Contributing to sparQ

Thank you for your interest in contributing to sparQ!

## Getting Started

1. Check the [README](README.md) for project overview and setup instructions
2. Read through the `blueprint/` directory in `pulse/` for module development patterns
3. Look for issues labeled `good first issue` to find beginner-friendly tasks

## Development Workflow

1. Fork the repository
2. Create a feature branch from `master`
3. Make your changes following the blueprint patterns
4. Run tests: `cd pulse && python -m pytest tests/`
5. Submit a pull request

## Code Style

Follow the patterns in [`pulse/blueprint/patterns/`](pulse/blueprint/patterns/) — they cover MVC structure, database conventions, frontend (HTMX/Alpine.js), security, testing, and more. When in doubt, match what the existing code does.

- All source files must include the copyright header
- Use the sparQ module structure for new features

## Commit Messages

- Keep the subject line under 72 characters
- Use imperative mood ("Add feature" not "Added feature")
- Include a `Signed-off-by` line (DCO sign-off):
  ```
  Signed-off-by: Your Name <your@email.com>
  ```
  Use `git commit -s` to add this automatically.

## Pull Requests

- Fill out the PR template (what, why, testing)
- Keep PRs focused — one concern per PR
- Maintainers typically review within a few business days

## Reporting Issues

Use GitHub Issues with the appropriate template:
- `Feature:` prefix for feature requests
- `Bug:` prefix for bug reports
- `Task:` prefix for tasks

## Maintainers

- [@Aidanu504](https://github.com/Aidanu504)
- [@jwhuettl](https://github.com/jwhuettl)

## License

sparQ is open source under the GNU Affero General Public License v3.0 (AGPL-3.0).
By contributing, you agree that your contributions will be licensed under the same terms.
