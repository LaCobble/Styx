# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Authenticated, streaming v1 file format: AES-256-GCM in 64 KiB chunks with a versioned header, Argon2id key derivation and atomic in-place rewrites (#1).
- Command-line interface: `python -m styx encrypt|decrypt PATH...`, password read only through a prompt (#1).
- Test suite for the core and the CLI (#1), and for the main GUI flows with pytest-qt (#3).
- Redesigned desktop interface: single window with a mode switch, drop zone for files and folders, password confirmation and strength indicator, per-file progress with cancel, and a summary of skipped or failed files; follows the system light/dark appearance and is usable from the keyboard (#3).
- Contribution guide, code of conduct, security policy and this changelog.
- Continuous integration (dependency install, byte-compilation, tests when present, secret scan) and a release workflow.

### Changed

- Files from the original format (v0, AES-CBC without authentication) can still be decrypted, read-only, with a warning; they are never written again (#1).
- The GUI reports per-file failures instead of silently swallowing errors, so a wrong password is no longer reported as a success (#1).
- Long operations run off the UI thread, so the window no longer freezes on large folders (#3).

### Removed

- The duplicate `Styx.py` / `styx.py` modules, replaced by the `styx` package (#1).

## [1.0.0] - 2023-09-14

First tagged version: the "V3.1" state of the project. Earlier iterations were a command-line script (January 2023) and a first graphical version (June 2023).

### Added

- Encryption and decryption of files and whole folders with a password, using AES-CBC and a key derived with PBKDF2-HMAC-SHA256 (random salt and IV per file).
- PyQt5 desktop interface (`menu.py`) with its icon and background, ready to be packaged with PyInstaller.

[Unreleased]: https://github.com/LaCobble/Styx/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/LaCobble/Styx/releases/tag/v1.0.0
