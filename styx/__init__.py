"""Styx: password-based authenticated encryption for files and folders."""

from .crypto import (
    DEFAULT_KDF_PARAMS,
    InvalidFileError,
    KdfParams,
    LegacyFormatWarning,
    StyxError,
    decrypt_stream,
    encrypt_stream,
)
from .files import (
    AlreadyEncryptedError,
    FolderReport,
    collect_files,
    decrypt_file,
    decrypt_folder,
    encrypt_file,
    encrypt_folder,
)

__version__ = "4.0.0"

__all__ = [
    "AlreadyEncryptedError",
    "DEFAULT_KDF_PARAMS",
    "FolderReport",
    "InvalidFileError",
    "KdfParams",
    "LegacyFormatWarning",
    "StyxError",
    "collect_files",
    "decrypt_file",
    "decrypt_folder",
    "decrypt_stream",
    "encrypt_file",
    "encrypt_folder",
    "encrypt_stream",
]
