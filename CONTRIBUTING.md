# Contributing to wilds-wdl-writer

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## Before You Start

This tool is still in its infancy. The architecture, scope, and conventions are still settling, and things may change quickly. Before writing any code, please **[open an issue](https://github.com/getwilds/wilds-wdl-writer/issues/new)** to start a discussion about your idea.

## Making Changes

1. **Fork the repository** on GitHub

2. **Create a branch** from `main` for your work. Use a short, descriptive name:
   ```bash
   git checkout -b my-feature
   ```
3. **Make your changes**, committing in logical increments with clear messages:
   ```bash
   git commit -m "Add support for scatter blocks in WDL generation"
   ```
4. **Keep your branch up to date** with upstream `main`:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

## Opening a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin my-feature
   ```
2. Open a pull request against `getwilds/wilds-wdl-writer`'s `main` branch.
3. Fill out the PR description with:
   - What the change does and why
   - Any relevant context or issue links
4. PRs require approval from a code owner ([@tefirman](https://github.com/tefirman) or [@emjbishop](https://github.com/emjbishop)) before merging.

## Best Practices

- **One concern per PR:** keep pull requests focused. Smaller, targeted PRs are easier to review and less likely to introduce bugs.
- **Write clear commit messages:** describe *what* changed and *why*, not just *how*.
- **Don't force-push to shared branches:** if you need to update a PR, add new commits rather than rewriting history.
- **Link related issues:** if your PR addresses an open issue, reference it in the description (e.g., `Closes #42`).
