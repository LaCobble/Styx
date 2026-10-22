"""File and folder operations on top of :mod:`styx.crypto`.

Semantics (unchanged from earlier Styx versions):

* Encryption and decryption happen **in place**: the file keeps its name and
  its content is replaced by the ciphertext (or plaintext). No ``.styx``
  copy is created and no separate original is kept.
* Folders are processed recursively; every regular file inside is handled.

What changed:

* The replacement is atomic: output goes to a temporary file in the same
  directory, is flushed to disk, then renamed over the original. If anything
  fails (wrong password, tampered file, disk full), the original file is left
  untouched and the temporary file is removed.
* Encrypting a file that is already in Styx v1 format is refused (it used to
  silently double-encrypt).
* Symbolic links are skipped when walking folders, so encryption never
  escapes the selected folder.
* Folder operations no longer swallow errors: every failure is reported.

Note: replacing a file does not securely erase the previous bytes from the
disk (neither did the old in-place overwrite, especially on SSDs).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable

from . import crypto
from .crypto import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_KDF_PARAMS,
    InvalidFileError,
    KdfParams,
    LegacyFormatWarning,
    StyxError,
)


class AlreadyEncryptedError(StyxError):
    """The file already starts with the Styx v1 header."""


@dataclass
class FolderReport:
    processed: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)
    legacy: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def _atomic_rewrite(path: Path, transform: Callable[[BinaryIO, BinaryIO], object]) -> object:
    """Run ``transform(src, dst)`` and atomically replace ``path`` with ``dst``."""
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".styx-tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with open(path, "rb") as src, os.fdopen(fd, "wb") as dst:
            result = transform(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return result


def encrypt_file(
    path: str | os.PathLike,
    password: str,
    *,
    kdf_params: KdfParams = DEFAULT_KDF_PARAMS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Encrypt ``path`` in place using the Styx v1 format."""
    path = Path(path)
    with open(path, "rb") as f:
        if crypto.is_styx_v1(f.read(len(crypto.MAGIC))):
            raise AlreadyEncryptedError(f"{path} is already encrypted with Styx.")
    _atomic_rewrite(
        path,
        lambda src, dst: crypto.encrypt_stream(src, dst, password, kdf_params=kdf_params, chunk_size=chunk_size),
    )


def decrypt_file(path: str | os.PathLike, password: str, *, allow_legacy: bool = True) -> int:
    """Decrypt ``path`` in place. Returns the format version read (0 = legacy).

    Raises :class:`InvalidFileError` on a wrong password or a corrupted /
    tampered file; the file is then left unchanged.
    """
    return _atomic_rewrite(
        Path(path),
        lambda src, dst: crypto.decrypt_stream(src, dst, password, allow_legacy=allow_legacy),
    )


def _iter_files(folder: Path, report: FolderReport):
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs.sort()
        for name in sorted(files):
            p = Path(root) / name
            if p.is_symlink():
                report.skipped.append((p, "symbolic link"))
                continue
            if name.endswith(".styx-tmp"):
                report.skipped.append((p, "Styx temporary file"))
                continue
            if p.is_file():
                yield p


def collect_files(folder: str | os.PathLike) -> tuple[list[Path], list[tuple[Path, str]]]:
    """List the files a folder operation would process, without touching them.

    Returns ``(files, skipped)`` where ``skipped`` holds ``(path, reason)``
    pairs for entries that folder operations ignore (symbolic links, Styx
    temporary files). Useful to show progress file by file.
    """
    report = FolderReport()
    files = list(_iter_files(Path(folder), report))
    return files, report.skipped


def encrypt_folder(folder: str | os.PathLike, password: str, **kwargs) -> FolderReport:
    """Encrypt every regular file under ``folder`` in place (recursively).

    Files already in Styx v1 format are skipped. Errors are collected in the
    returned report instead of stopping the walk.
    """
    report = FolderReport()
    for p in _iter_files(Path(folder), report):
        try:
            encrypt_file(p, password, **kwargs)
            report.processed.append(p)
        except AlreadyEncryptedError:
            report.skipped.append((p, "already encrypted"))
        except (OSError, StyxError) as exc:
            report.failed.append((p, str(exc)))
    return report


def decrypt_folder(folder: str | os.PathLike, password: str, *, allow_legacy: bool = True) -> FolderReport:
    """Decrypt every regular file under ``folder`` in place (recursively).

    Files that cannot be decrypted (wrong password, tampered, or simply not
    encrypted) are left unchanged and listed in ``report.failed``.
    """
    report = FolderReport()
    for p in _iter_files(Path(folder), report):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", LegacyFormatWarning)
                version = decrypt_file(p, password, allow_legacy=allow_legacy)
            report.processed.append(p)
            if version == 0:
                report.legacy.append(p)
        except (OSError, StyxError) as exc:  # includes InvalidFileError
            report.failed.append((p, str(exc)))
    return report
