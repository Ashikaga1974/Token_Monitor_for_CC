# Contributing to Token Monitor for Claude Code

Thank you for your interest in contributing to **Token Monitor for Claude Code**! This project is open source under the [GNU General Public License v3.0 (GPL-3.0-or-later)](LICENSE).

We welcome bug reports, feature suggestions, documentation improvements, and code contributions.

---

## Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions within this project.

---

## How Can I Contribute?

### Reporting Bugs
Before submitting a new issue, please check existing issues to see if the problem has already been reported.

When creating a bug report, please include:
- A clear and descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment details:
  - KDE Plasma version (`plasmashell --version`)
  - Linux distribution (`uname -a`, `cat /etc/os-release`)
  - Python version (`python3 --version`)
  - Claude Code CLI version (`claude --version`)
- Relevant log output from `journalctl --user -u token-monitor.service -n 50`

### Suggesting Enhancements
Feature requests are welcome! Please open an issue and describe:
- The problem your idea solves
- A clear description of the proposed feature
- Potential alternatives or workarounds considered

### Submitting Pull Requests
1. **Fork** the repository and create a new branch from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. **Make your changes** following the coding standards below.
3. **Run existing tests** and add new unit tests for any new logic or bug fixes.
4. **Compile and test translations** if you touched user-facing strings.
5. **Commit your changes** with descriptive commit messages (Conventional Commits style, e.g. `feat: ...`, `fix: ...`, `docs: ...`).
6. **Push** to your fork and submit a Pull Request against the `main` branch.

---

## Development & Testing Workflow

### Prerequisites
- Python 3.10+ (Standard library only; zero external Python dependencies)
- KDE Plasma 6.0+
- `gettext` tools (`msgfmt`, `xgettext`) for building translations

### Running Unit Tests
All backend tests are located in `tests/` and use Python's built-in `unittest` runner:
```bash
python3 -m unittest discover tests
```
Ensure all tests pass before submitting your PR.

### Building Translations
If you added or modified user-facing strings in QML or Python:
```bash
./build_translations.sh
```

### Packaging & Local Validation
To test packaging as a standalone `.plasmoid`:
```bash
./build_plasmoid.sh
kpackagetool6 --type Plasma/Applet --show ~/Downloads/com.buellsunited.TokenMonitor.plasmoid
```

---

## Coding Standards

- **Language**:
  - Code (variables, functions, classes, commit messages) is written in **English**.
  - Internal explanatory comments explaining the *why* are in **German** (project convention).
- **Style**:
  - Small, focused functions adhering to the Single Responsibility Principle.
  - Zero external Python dependencies: the backend relies strictly on Python's standard library to guarantee frictionless installation across all Linux distributions.
- **Security & Privacy**:
  - Strict local-first architecture: no analytics, no external tracking, no telemetry.
  - File permissions must remain restricted (`0700` for data directories, `0600` for databases and credentials).
  - External origins in HTTP server requests must be rejected (CORS prevention).
