# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Contribution guide, code of conduct, security policy and this changelog.
- Continuous integration (dependency install, byte-compilation, tests when present, secret scan) and a release workflow.

## [1.0.0] - 2023-09-14

First tagged version: the "V3.1" state of the project. Earlier iterations were a command-line script (January 2023) and a first graphical version (June 2023).

### Added

- Encryption and decryption of files and whole folders with a password, using AES-CBC and a key derived with PBKDF2-HMAC-SHA256 (random salt and IV per file).
- PyQt5 desktop interface (`menu.py`) with its icon and background, ready to be packaged with PyInstaller.

[Unreleased]: https://github.com/LaCobble/Styx/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/LaCobble/Styx/releases/tag/v1.0.0
