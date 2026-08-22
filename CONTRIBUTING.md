# Contributing to Void Compass

Thank you for helping improve Void Compass. Bug reports, journal evidence, documentation corrections, accessibility improvements, and focused code changes are all welcome.

## Before opening an issue

- Check the [wiki](https://github.com/insert3coins/VoidCompass/wiki) and existing issues first.
- Reproduce the problem with the newest release when possible.
- Remove commander names, Frontier IDs, API keys, Discord webhooks, and other personal information from screenshots, journals, configuration, and logs.
- Report security problems privately as described in [SECURITY.md](SECURITY.md).

The structured issue forms will ask for the details needed to investigate a bug or evaluate a feature without requiring a complete journal upload.

## Local development

Void Compass 5.3.9 and newer target Windows x64 with Microsoft Edge WebView2. Clone the repository, create a virtual environment, and install the declared dependencies:

```powershell
git clone https://github.com/insert3coins/VoidCompass.git
cd VoidCompass
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python VoidCompass.py
```

The former experimental Linux build has been retired while Void Compass moves to one HTML/WebView2 presentation architecture. Run `python build.py` on Windows to create the executable, public ZIP and SHA-256 checksum.

Create a branch from `master` and keep each change focused. Do not commit generated builds, local databases, commander profiles, configuration, logs, journal files, voice caches, or credentials.

## Journal and UI changes

- Treat Frontier journal, status, route, cargo, market, and locker fields as authoritative only when their published schemas support the interpretation.
- Preserve per-commander isolation and replay safety. Historical journal recovery must not be mistaken for a new live event.
- Keep network integrations optional and never invent unavailable game state.
- Make native UI controls theme-aware, usable after window resizing, and safe for overlay mouse passthrough.
- Include a screenshot or short recording for visible UI changes when practical.

Small, redacted journal excerpts are preferred over full journals. Describe the expected sequence of events around the excerpt.

## Testing

Run the automated test suite before submitting a pull request:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Also launch the application for changes that affect startup, profiles, themes, overlays, journals, audio, or settings. Building the packaged application with `python build.py` is useful for release-sensitive changes but is not required for every contribution.

## Pull requests

A good pull request:

- Explains the player-facing problem and the chosen solution.
- Links the relevant issue when one exists.
- Lists the tests and manual checks performed.
- Calls out migrations, configuration changes, new dependencies, network behaviour, and profile-state implications.
- Avoids unrelated formatting or generated-file changes.
- Updates documentation or release notes when behaviour visible to commanders changes.

By contributing, you agree that your contribution is licensed under the repository's [GNU GPL v3.0-only licence](LICENSE).
