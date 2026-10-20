"""Command-line interface: ``python -m styx encrypt|decrypt PATH...``.

The password is always read with getpass (never from argv, where it would be
visible in the process list and shell history).
"""

from __future__ import annotations

import argparse
import getpass
import sys
import warnings
from pathlib import Path

from . import __version__
from .crypto import LegacyFormatWarning, StyxError
from .files import FolderReport, decrypt_file, decrypt_folder, encrypt_file, encrypt_folder


def _ask_password(confirm: bool) -> str:
    password = getpass.getpass("Password: ")
    if not password:
        raise SystemExit("error: the password must not be empty")
    if confirm and getpass.getpass("Confirm password: ") != password:
        raise SystemExit("error: passwords do not match")
    return password


def _print_report(path: Path, report: FolderReport, verb: str) -> None:
    print(f"{path}: {len(report.processed)} file(s) {verb}, "
          f"{len(report.skipped)} skipped, {len(report.failed)} failed")
    for p, reason in report.skipped:
        print(f"  skipped {p}: {reason}")
    for p, reason in report.failed:
        print(f"  FAILED  {p}: {reason}", file=sys.stderr)
    for p in report.legacy:
        print(f"  warning: {p} was in the legacy unauthenticated v0 format; "
              "re-encrypt it to upgrade.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="styx",
        description="Encrypt or decrypt files and folders in place with a password.",
    )
    parser.add_argument("--version", action="version", version=f"styx {__version__}")
    parser.add_argument("action", choices=["encrypt", "decrypt"])
    parser.add_argument("paths", nargs="+", type=Path, help="files and/or folders (folders are recursive)")
    args = parser.parse_args(argv)

    missing = [p for p in args.paths if not p.exists()]
    if missing:
        parser.error("not found: " + ", ".join(map(str, missing)))

    encrypting = args.action == "encrypt"
    password = _ask_password(confirm=encrypting)
    ok = True

    for path in args.paths:
        if path.is_dir():
            report = (encrypt_folder if encrypting else decrypt_folder)(path, password)
            _print_report(path, report, "encrypted" if encrypting else "decrypted")
            ok = ok and report.ok
            continue
        try:
            if encrypting:
                encrypt_file(path, password)
                print(f"{path}: encrypted")
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", LegacyFormatWarning)
                    version = decrypt_file(path, password)
                print(f"{path}: decrypted")
                if version == 0:
                    print(f"  warning: {path} was in the legacy unauthenticated v0 format; "
                          "re-encrypt it to upgrade.", file=sys.stderr)
        except (OSError, StyxError, ValueError) as exc:
            print(f"{path}: FAILED: {exc}", file=sys.stderr)
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
