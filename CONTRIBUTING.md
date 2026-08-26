# Contributing to SmartShelf

Thank you for contributing to **SmartShelf** and the **UniLibrary** application.

SmartShelf is a collaborative software development project. To maintain a clean, organized, and reliable codebase, all contributors are expected to follow the development workflow and guidelines outlined below.

## Development Workflow

All development should follow this general workflow:

```text
Create Branch
     ↓
Develop / Make Changes
     ↓
Commit Changes
     ↓
Push Branch
     ↓
Open Pull Request
     ↓
Code Review
     ↓
Merge into main
```

Contributors should avoid making direct changes to the `main` branch unless specifically authorized.

## Branch Naming

Branches should use descriptive names that indicate the purpose of the work.

Recommended prefixes:

* `feature/` — New functionality
* `fix/` — Bug fixes
* `docs/` — Documentation changes
* `refactor/` — Code restructuring
* `test/` — Testing-related changes

Examples:

```text
feature/book-search
feature/recommendation-system
feature/user-authentication
fix/book-availability
docs/database-design
test/recommendation-tests
```

## Commit Messages

Commit messages should clearly describe the change being introduced.

Recommended format:

```text
type: description
```

Common types include:

* `feat` — New functionality
* `fix` — Bug fix
* `docs` — Documentation
* `refactor` — Code restructuring
* `test` — Testing
* `chore` — Maintenance or configuration

Examples:

```text
feat: add book search functionality
fix: correct book availability validation
docs: update database documentation
test: add recommendation system tests
```

## Pull Requests

Changes should be submitted through a Pull Request before being merged into `main`.

A Pull Request should:

1. Clearly describe the changes made.
2. Reference the relevant Issue where applicable.
3. Explain how the changes were tested.
4. Ensure that existing functionality has not been unnecessarily affected.
5. Receive appropriate review before being merged.

## Code Quality

Contributors should aim to produce code that is:

* Readable
* Maintainable
* Consistent with the project's conventions
* Properly documented where necessary
* Tested where appropriate

Avoid committing unnecessary files, generated files, temporary files, or sensitive information such as passwords and API keys.

## Documentation

Changes that significantly affect the system should be accompanied by appropriate documentation.

Technical documentation should be maintained within the `/docs` directory where applicable.

## Questions and Discussions

If you are unsure about an implementation or project decision, discuss it with the team before making significant changes.

The goal of this workflow is not to create unnecessary restrictions, but to keep SmartShelf organized and make collaboration easier for everyone.
