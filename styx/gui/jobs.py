"""Encrypt/decrypt jobs run by the GUI, file by file, off the UI thread.

:func:`run_job` is plain Python so it can be tested without Qt;
:class:`JobWorker` wraps it for a ``QThread`` and turns its callbacks into
signals.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from styx import (
    AlreadyEncryptedError,
    InvalidFileError,
    LegacyFormatWarning,
    StyxError,
    collect_files,
    decrypt_file,
    encrypt_file,
)

ENCRYPT = "encrypt"
DECRYPT = "decrypt"

# Outcome of a single file.
DONE = "done"
SKIPPED = "skipped"
FAILED = "failed"
LEGACY = "legacy"  # decrypted, but it was in the old unauthenticated format


@dataclass
class JobSummary:
    mode: str
    done: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)
    legacy: list[Path] = field(default_factory=list)
    cancelled: bool = False
    bad_password: int = 0  # failures caused by a wrong password or altered file

    @property
    def total(self) -> int:
        return len(self.done) + len(self.skipped) + len(self.failed)


def describe_error(exc: BaseException, mode: str) -> str:
    """Turn an exception into a short, actionable sentence."""
    if isinstance(exc, InvalidFileError):
        return "Wrong password, or the file was modified, damaged or never encrypted."
    if isinstance(exc, PermissionError):
        return "Permission denied. Check that the file is not read-only or open elsewhere."
    if isinstance(exc, FileNotFoundError):
        return "The file no longer exists."
    if isinstance(exc, IsADirectoryError):
        return "This is a folder, not a file."
    if isinstance(exc, OSError):
        reason = exc.strerror or str(exc)
        return f"Could not {mode} the file: {reason}."
    return str(exc) or exc.__class__.__name__


def expand(paths: Iterable[str | os.PathLike]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Expand folders into their files. Returns ``(files, skipped)``."""
    files: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_symlink():
            skipped.append((p, "Symbolic link, not followed."))
            continue
        if p.is_dir():
            found, ignored = collect_files(p)
            skipped += [(q, reason[:1].upper() + reason[1:] + ".") for q, reason in ignored]
        elif p.exists():
            found = [p]
        else:
            skipped.append((p, "The file no longer exists."))
            continue
        for f in found:
            key = f.resolve()
            if key not in seen:
                seen.add(key)
                files.append(f)
    return files, skipped


def process_one(path: Path, mode: str, password: str) -> tuple[str, str]:
    """Encrypt or decrypt one file. Returns ``(outcome, detail)``."""
    try:
        if mode == ENCRYPT:
            encrypt_file(path, password)
            return DONE, ""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LegacyFormatWarning)
            version = decrypt_file(path, password)
        return (LEGACY, "Old format without tamper protection.") if version == 0 else (DONE, "")
    except AlreadyEncryptedError:
        return SKIPPED, "Already encrypted."
    except (OSError, StyxError) as exc:
        return FAILED, describe_error(exc, mode)


def run_job(
    mode: str,
    paths: Iterable[str | os.PathLike],
    password: str,
    *,
    on_start: Callable[[int], None] = lambda total: None,
    on_file: Callable[[int, Path], None] = lambda index, path: None,
    on_result: Callable[[int, Path, str, str], None] = lambda index, path, outcome, detail: None,
    should_cancel: Callable[[], bool] = lambda: False,
) -> JobSummary:
    summary = JobSummary(mode)
    files, skipped = expand(paths)
    summary.skipped += skipped
    on_start(len(files))
    for index, path in enumerate(files):
        if should_cancel():
            summary.cancelled = True
            break
        on_file(index, path)
        outcome, detail = process_one(path, mode, password)
        if outcome in (DONE, LEGACY):
            summary.done.append(path)
            if outcome == LEGACY:
                summary.legacy.append(path)
        elif outcome == SKIPPED:
            summary.skipped.append((path, detail))
        else:
            summary.failed.append((path, detail))
            if detail.startswith("Wrong password"):
                summary.bad_password += 1
        on_result(index, path, outcome, detail)
    return summary


class JobWorker(QObject):
    """Runs :func:`run_job` in a worker thread."""

    started = pyqtSignal(int)  # total number of files
    file_started = pyqtSignal(int, str)  # index, path
    file_finished = pyqtSignal(int, str, str, str)  # index, path, outcome, detail
    finished = pyqtSignal(object)  # JobSummary

    def __init__(self, mode: str, paths: list[str], password: str):
        super().__init__()
        self._mode = mode
        self._paths = list(paths)
        self._password = password
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @pyqtSlot()
    def run(self) -> None:
        try:
            summary = run_job(
                self._mode,
                self._paths,
                self._password,
                on_start=self.started.emit,
                on_file=lambda i, p: self.file_started.emit(i, str(p)),
                on_result=lambda i, p, o, d: self.file_finished.emit(i, str(p), o, d),
                should_cancel=lambda: self._cancel,
            )
        except Exception as exc:  # never leave the UI waiting
            summary = JobSummary(self._mode)
            summary.failed.append((Path("."), describe_error(exc, self._mode)))
        finally:
            self._password = ""
        self.finished.emit(summary)
