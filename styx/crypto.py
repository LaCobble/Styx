"""Styx file format: password-based authenticated encryption of byte streams.

Format v1 (the only format Styx writes)
---------------------------------------

All integers are unsigned big-endian.

Header (46 bytes)::

    offset size field
    0      4    magic          b"STYX"
    4      1    version        0x01
    5      1    kdf_id         0x01 = Argon2id
    6      4    time_cost      Argon2id iterations
    10     4    memory_kib     Argon2id memory, in KiB
    14     4    parallelism    Argon2id lanes
    18     4    chunk_size     plaintext bytes per chunk
    22     16   salt           random, per file
    38     8    nonce_prefix   random, per file

Body: a sequence of AES-256-GCM chunks. Every chunk except the last holds
exactly ``chunk_size`` plaintext bytes; the last chunk holds 0..chunk_size
bytes (an empty input produces one empty final chunk). Each chunk is stored as
``ciphertext || 16-byte tag``.

* key   = Argon2id(password, salt, time_cost, memory_kib, parallelism), 32 bytes
* nonce = nonce_prefix (8 bytes) || chunk_index (4 bytes)
* AAD   = header (46 bytes) || final_flag (1 byte: 0x01 last chunk, else 0x00)

Binding the whole header as AAD means any change to the KDF parameters, salt,
nonce prefix or chunk size makes every chunk fail authentication. The final
flag prevents truncation at a chunk boundary and appending of data; the chunk
index in the nonce prevents reordering or duplicating chunks.

Legacy format v0 (read-only)
----------------------------

Styx versions before this format wrote ``salt(16) || iv(16) || AES-256-CBC
ciphertext`` with PKCS7 padding and a PBKDF2-HMAC-SHA256 key (100 000
iterations). It has no authentication. It can still be decrypted, for
migration only, and is never written.
"""

from __future__ import annotations

import os
import struct
import warnings
from dataclasses import dataclass
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"STYX"
VERSION = 1
KDF_ARGON2ID = 1

HEADER_STRUCT = struct.Struct(">4sBBIIII16s8s")
HEADER_SIZE = HEADER_STRUCT.size  # 46
TAG_SIZE = 16
SALT_SIZE = 16
NONCE_PREFIX_SIZE = 8
KEY_SIZE = 32

DEFAULT_CHUNK_SIZE = 64 * 1024
MAX_CHUNKS = 2**32  # chunk index is a 32-bit counter

# Bounds accepted when *reading* a header. They stop a crafted file from
# making the KDF allocate absurd amounts of memory or CPU before the
# authentication check can reject it.
MIN_CHUNK_SIZE = 1024
MAX_CHUNK_SIZE = 16 * 1024 * 1024
MAX_TIME_COST = 64
MIN_MEMORY_KIB = 8
MAX_MEMORY_KIB = 4 * 1024 * 1024  # 4 GiB
MAX_PARALLELISM = 64

# Legacy v0 parameters.
V0_SALT_SIZE = 16
V0_IV_SIZE = 16
V0_PBKDF2_ITERATIONS = 100_000


class StyxError(Exception):
    """Base class for Styx errors."""


class InvalidFileError(StyxError):
    """Wrong password, or the file is corrupted / tampered / not a Styx file.

    These cases are deliberately not distinguished: telling them apart would
    give an attacker an oracle.
    """

    def __init__(self, message: str = "Wrong password, or the file is corrupted or was modified."):
        super().__init__(message)


class LegacyFormatWarning(UserWarning):
    """A legacy (v0, unauthenticated) file was decrypted."""


@dataclass(frozen=True)
class KdfParams:
    """Argon2id parameters. Defaults follow RFC 9106's second recommended
    option (64 MiB memory, 3 passes), with 4 lanes."""

    time_cost: int = 3
    memory_kib: int = 64 * 1024
    parallelism: int = 4

    def validate(self) -> None:
        if not 1 <= self.time_cost <= MAX_TIME_COST:
            raise InvalidFileError()
        if not 1 <= self.parallelism <= MAX_PARALLELISM:
            raise InvalidFileError()
        if not max(MIN_MEMORY_KIB, 8 * self.parallelism) <= self.memory_kib <= MAX_MEMORY_KIB:
            raise InvalidFileError()


DEFAULT_KDF_PARAMS = KdfParams()


def _encode_password(password: str | bytes) -> bytes:
    if isinstance(password, str):
        password = password.encode("utf-8")
    if not password:
        raise ValueError("The password must not be empty.")
    return password


def derive_key(password: str | bytes, salt: bytes, params: KdfParams) -> bytes:
    kdf = Argon2id(
        salt=salt,
        length=KEY_SIZE,
        iterations=params.time_cost,
        lanes=params.parallelism,
        memory_cost=params.memory_kib,
    )
    return kdf.derive(_encode_password(password))


def _nonce(prefix: bytes, index: int) -> bytes:
    if index >= MAX_CHUNKS:
        raise StyxError("Input too large for the Styx v1 format.")
    return prefix + index.to_bytes(4, "big")


def _read_exact(src: BinaryIO, size: int) -> bytes:
    """Read up to ``size`` bytes, looping over short reads."""
    parts = []
    remaining = size
    while remaining > 0:
        block = src.read(remaining)
        if not block:
            break
        parts.append(block)
        remaining -= len(block)
    return b"".join(parts)


def encrypt_stream(
    src: BinaryIO,
    dst: BinaryIO,
    password: str | bytes,
    *,
    kdf_params: KdfParams = DEFAULT_KDF_PARAMS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Encrypt everything readable from ``src`` into ``dst`` (format v1)."""
    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError("chunk_size out of range")
    kdf_params.validate()

    salt = os.urandom(SALT_SIZE)
    nonce_prefix = os.urandom(NONCE_PREFIX_SIZE)
    header = HEADER_STRUCT.pack(
        MAGIC,
        VERSION,
        KDF_ARGON2ID,
        kdf_params.time_cost,
        kdf_params.memory_kib,
        kdf_params.parallelism,
        chunk_size,
        salt,
        nonce_prefix,
    )
    aead = AESGCM(derive_key(password, salt, kdf_params))
    dst.write(header)

    index = 0
    current = _read_exact(src, chunk_size)
    while True:
        following = _read_exact(src, chunk_size)
        final = not following
        aad = header + (b"\x01" if final else b"\x00")
        dst.write(aead.encrypt(_nonce(nonce_prefix, index), current, aad))
        if final:
            return
        index += 1
        current = following


def _parse_header(header: bytes) -> tuple[KdfParams, int, bytes, bytes]:
    if len(header) != HEADER_SIZE:
        raise InvalidFileError()
    magic, version, kdf_id, t, m, p, chunk_size, salt, prefix = HEADER_STRUCT.unpack(header)
    if magic != MAGIC or version != VERSION or kdf_id != KDF_ARGON2ID:
        raise InvalidFileError()
    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise InvalidFileError()
    params = KdfParams(time_cost=t, memory_kib=m, parallelism=p)
    params.validate()
    return params, chunk_size, salt, prefix


def _decrypt_v1(src: BinaryIO, dst: BinaryIO, password: str | bytes) -> None:
    header = _read_exact(src, HEADER_SIZE)
    params, chunk_size, salt, prefix = _parse_header(header)
    aead = AESGCM(derive_key(password, salt, params))

    stored_chunk = chunk_size + TAG_SIZE
    index = 0
    current = _read_exact(src, stored_chunk)
    while True:
        if len(current) < TAG_SIZE:
            raise InvalidFileError()
        following = _read_exact(src, stored_chunk)
        final = not following
        aad = header + (b"\x01" if final else b"\x00")
        try:
            plaintext = aead.decrypt(_nonce(prefix, index), current, aad)
        except InvalidTag:
            raise InvalidFileError() from None
        dst.write(plaintext)
        if final:
            return
        index += 1
        current = following


def _decrypt_v0(data: bytes, dst: BinaryIO, password: str | bytes) -> None:
    """Decrypt the legacy unauthenticated AES-CBC format."""
    salt = data[:V0_SALT_SIZE]
    iv = data[V0_SALT_SIZE : V0_SALT_SIZE + V0_IV_SIZE]
    ct = data[V0_SALT_SIZE + V0_IV_SIZE :]
    if len(salt) != V0_SALT_SIZE or len(iv) != V0_IV_SIZE or not ct or len(ct) % 16:
        raise InvalidFileError()
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=V0_PBKDF2_ITERATIONS,
    ).derive(_encode_password(password))
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    try:
        plaintext = unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        raise InvalidFileError() from None
    dst.write(plaintext)


def is_styx_v1(prefix: bytes) -> bool:
    return prefix[:4] == MAGIC


def decrypt_stream(src: BinaryIO, dst: BinaryIO, password: str | bytes, *, allow_legacy: bool = True) -> int:
    """Decrypt ``src`` into ``dst`` and return the format version that was read.

    Raises :class:`InvalidFileError` on a wrong password or any corruption.
    Plaintext written to ``dst`` must be discarded if an exception is raised:
    chunks are verified one by one, so a tampered file can fail part-way.

    A file that does not start with the Styx magic is treated as legacy v0
    (when ``allow_legacy`` is true). v0 has no authentication: a wrong
    password is detected only with high probability, and tampering is not
    reliably detected. A :class:`LegacyFormatWarning` is emitted.
    """
    start = _read_exact(src, len(MAGIC))
    if is_styx_v1(start):
        _decrypt_v1(_Prepend(start, src), dst, password)
        return VERSION
    if not allow_legacy:
        raise InvalidFileError()
    data = start + src.read()
    _decrypt_v0(data, dst, password)
    warnings.warn(
        "Decrypted a legacy (v0) Styx file. That format is NOT authenticated: "
        "tampering cannot be reliably detected. Re-encrypt it to upgrade to v1.",
        LegacyFormatWarning,
        stacklevel=2,
    )
    return 0


class _Prepend:
    """Minimal reader that replays already-consumed bytes before ``src``."""

    def __init__(self, head: bytes, src: BinaryIO):
        self._head = head
        self._src = src

    def read(self, size: int = -1) -> bytes:
        if self._head:
            if size < 0:
                out, self._head = self._head + self._src.read(), b""
                return out
            out, self._head = self._head[:size], self._head[size:]
            return out
        return self._src.read(size)
