import os
import warnings

import pytest
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from styx import (
    AlreadyEncryptedError,
    InvalidFileError,
    KdfParams,
    LegacyFormatWarning,
    decrypt_file,
    decrypt_folder,
    encrypt_file,
    encrypt_folder,
)
from styx import crypto

PASSWORD = "correct horse battery staple"
# Small Argon2id parameters keep the test suite fast; the format records them
# in the header so decryption uses the same values.
FAST = KdfParams(time_cost=1, memory_kib=8 * 1024, parallelism=1)
CHUNK = crypto.MIN_CHUNK_SIZE  # 1 KiB, to get many chunks from small inputs


def write(path, data):
    path.write_bytes(data)
    return path


def roundtrip(path, data, **kwargs):
    write(path, data)
    encrypt_file(path, PASSWORD, kdf_params=FAST, chunk_size=CHUNK, **kwargs)
    enc = path.read_bytes()
    assert enc.startswith(b"STYX\x01")
    if data:
        assert data not in enc
    assert decrypt_file(path, PASSWORD) == 1
    assert path.read_bytes() == data
    return enc


@pytest.mark.parametrize(
    "size",
    [0, 1, CHUNK - 1, CHUNK, CHUNK + 1, 3 * CHUNK, 5 * CHUNK + 123],
    ids=lambda s: f"{s}B",
)
def test_roundtrip_sizes(tmp_path, size):
    data = os.urandom(size)
    enc = roundtrip(tmp_path / "f.bin", data)
    n_chunks = max(1, -(-size // CHUNK))
    assert len(enc) == crypto.HEADER_SIZE + size + n_chunks * crypto.TAG_SIZE


def test_roundtrip_default_params(tmp_path):
    """Real defaults: Argon2id 64 MiB / t=3 / p=4, 64 KiB chunks, multi-chunk."""
    path = write(tmp_path / "big.bin", os.urandom(3 * crypto.DEFAULT_CHUNK_SIZE + 7))
    original = path.read_bytes()
    encrypt_file(path, PASSWORD)
    header = path.read_bytes()[: crypto.HEADER_SIZE]
    params, chunk_size, _, _ = crypto._parse_header(header)
    assert params == crypto.DEFAULT_KDF_PARAMS
    assert chunk_size == 64 * 1024
    decrypt_file(path, PASSWORD)
    assert path.read_bytes() == original


def test_unicode_password_and_mode_preserved(tmp_path):
    path = write(tmp_path / "f.txt", b"hello")
    os.chmod(path, 0o600)
    encrypt_file(path, "pässwörd-日本", kdf_params=FAST)
    assert (os.stat(path).st_mode & 0o777) == 0o600
    decrypt_file(path, "pässwörd-日本")
    assert path.read_bytes() == b"hello"


def test_wrong_password_leaves_file_untouched(tmp_path):
    path = write(tmp_path / "f.bin", os.urandom(2 * CHUNK))
    encrypt_file(path, PASSWORD, kdf_params=FAST, chunk_size=CHUNK)
    enc = path.read_bytes()
    with pytest.raises(InvalidFileError):
        decrypt_file(path, "wrong password")
    assert path.read_bytes() == enc
    assert list(tmp_path.iterdir()) == [path]  # no temp file left behind


def test_empty_password_rejected(tmp_path):
    path = write(tmp_path / "f.bin", b"x")
    with pytest.raises(ValueError):
        encrypt_file(path, "", kdf_params=FAST)
    assert path.read_bytes() == b"x"


def test_double_encryption_refused(tmp_path):
    path = write(tmp_path / "f.bin", b"data")
    encrypt_file(path, PASSWORD, kdf_params=FAST)
    with pytest.raises(AlreadyEncryptedError):
        encrypt_file(path, PASSWORD, kdf_params=FAST)


def _encrypted(tmp_path, size=3 * CHUNK + 10):
    path = write(tmp_path / "f.bin", os.urandom(size))
    encrypt_file(path, PASSWORD, kdf_params=FAST, chunk_size=CHUNK)
    return path, bytearray(path.read_bytes())


@pytest.mark.parametrize(
    "offset",
    [
        5,  # kdf id
        9,  # time_cost (stays within accepted bounds: 1 -> 0 or 1 -> 1^x)
        20,  # chunk_size low byte
        25,  # salt
        40,  # nonce prefix
    ],
)
def test_tampered_header(tmp_path, offset):
    path, enc = _encrypted(tmp_path)
    enc[offset] ^= 0x01
    path.write_bytes(bytes(enc))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)
    assert path.read_bytes() == bytes(enc)


def test_tampered_kdf_memory_within_bounds(tmp_path):
    """Changing a KDF parameter to another *valid* value must still fail (AAD)."""
    path, enc = _encrypted(tmp_path)
    enc[10:14] = (16 * 1024).to_bytes(4, "big")
    path.write_bytes(bytes(enc))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)


@pytest.mark.parametrize("where", ["first", "middle", "last_tag"])
def test_tampered_body(tmp_path, where):
    path, enc = _encrypted(tmp_path)
    offset = {
        "first": crypto.HEADER_SIZE,
        "middle": crypto.HEADER_SIZE + CHUNK + crypto.TAG_SIZE + 100,
        "last_tag": len(enc) - 1,
    }[where]
    enc[offset] ^= 0x80
    path.write_bytes(bytes(enc))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)
    assert path.read_bytes() == bytes(enc)


@pytest.mark.parametrize(
    "cut",
    [
        "chunk_boundary",  # drop the whole final chunk
        "mid_chunk",
        "header_only",
        "partial_header",
        "one_byte",
    ],
)
def test_truncated(tmp_path, cut):
    path, enc = _encrypted(tmp_path, size=3 * CHUNK)  # exactly 3 full chunks
    stored = CHUNK + crypto.TAG_SIZE
    length = {
        "chunk_boundary": crypto.HEADER_SIZE + 2 * stored,
        "mid_chunk": len(enc) - 7,
        "header_only": crypto.HEADER_SIZE,
        "partial_header": 20,
        "one_byte": len(enc) - 1,
    }[cut]
    path.write_bytes(bytes(enc[:length]))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)


def test_appended_data(tmp_path):
    path, enc = _encrypted(tmp_path)
    path.write_bytes(bytes(enc) + b"\x00" * 32)
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)


def test_swapped_chunks(tmp_path):
    path, enc = _encrypted(tmp_path, size=3 * CHUNK)
    stored = CHUNK + crypto.TAG_SIZE
    h = crypto.HEADER_SIZE
    c0, c1 = enc[h : h + stored], enc[h + stored : h + 2 * stored]
    enc[h : h + stored], enc[h + stored : h + 2 * stored] = c1, c0
    path.write_bytes(bytes(enc))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)


def test_absurd_kdf_params_rejected_before_kdf(tmp_path):
    path, enc = _encrypted(tmp_path)
    enc[10:14] = (0xFFFFFFFF).to_bytes(4, "big")  # ~4 TiB of memory
    path.write_bytes(bytes(enc))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)


# --- legacy v0 -------------------------------------------------------------


def encrypt_v0(data: bytes, password: str) -> bytes:
    """Re-implementation of the original Styx.py encrypt() (AES-CBC, PBKDF2)."""
    iv = os.urandom(16)
    salt = os.urandom(16)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000).derive(
        password.encode("utf-8")
    )
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    return salt + iv + encryptor.update(padded) + encryptor.finalize()


@pytest.mark.parametrize("size", [0, 15, 16, 5000])
def test_legacy_v0_decrypt(tmp_path, size):
    data = os.urandom(size)
    path = write(tmp_path / "old.bin", encrypt_v0(data, PASSWORD))
    with pytest.warns(LegacyFormatWarning):
        assert decrypt_file(path, PASSWORD) == 0
    assert path.read_bytes() == data


def test_legacy_v0_then_reencrypt_is_v1(tmp_path):
    path = write(tmp_path / "old.bin", encrypt_v0(b"migrate me", PASSWORD))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LegacyFormatWarning)
        decrypt_file(path, PASSWORD)
    encrypt_file(path, PASSWORD, kdf_params=FAST)
    assert path.read_bytes().startswith(b"STYX\x01")
    assert decrypt_file(path, PASSWORD) == 1
    assert path.read_bytes() == b"migrate me"


def test_legacy_v0_wrong_password(tmp_path):
    # v0 has no MAC: a wrong password is only caught by the padding check,
    # which passes by chance ~1/256 of the time. Try a few passwords so the
    # test is not flaky, and require that most are rejected.
    enc = encrypt_v0(b"secret data", PASSWORD)
    rejected = 0
    for i in range(20):
        path = write(tmp_path / f"old{i}.bin", enc)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", LegacyFormatWarning)
                decrypt_file(path, f"wrong-{i}")
        except InvalidFileError:
            rejected += 1
            assert path.read_bytes() == enc
    assert rejected >= 15


def test_legacy_disabled(tmp_path):
    path = write(tmp_path / "old.bin", encrypt_v0(b"x", PASSWORD))
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD, allow_legacy=False)


def test_not_encrypted_file(tmp_path):
    path = write(tmp_path / "plain.txt", b"just some text, not encrypted")
    with pytest.raises(InvalidFileError):
        decrypt_file(path, PASSWORD)
    assert path.read_bytes() == b"just some text, not encrypted"


# --- folders ---------------------------------------------------------------


def make_tree(root):
    files = {
        "a.txt": b"alpha",
        "empty": b"",
        "sub/b.bin": os.urandom(3000),
        "sub/deeper/c.dat": os.urandom(10),
    }
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return files


def test_folder_roundtrip(tmp_path):
    root = tmp_path / "tree"
    files = make_tree(root)
    report = encrypt_folder(root, PASSWORD, kdf_params=FAST, chunk_size=CHUNK)
    assert report.ok and len(report.processed) == len(files)
    for rel, data in files.items():
        enc = (root / rel).read_bytes()
        assert enc.startswith(b"STYX\x01")

    # Running it again skips already-encrypted files instead of double-encrypting.
    again = encrypt_folder(root, PASSWORD, kdf_params=FAST)
    assert not again.processed and len(again.skipped) == len(files)

    report = decrypt_folder(root, PASSWORD)
    assert report.ok and len(report.processed) == len(files)
    for rel, data in files.items():
        assert (root / rel).read_bytes() == data


def test_folder_wrong_password_reports_failures(tmp_path):
    root = tmp_path / "tree"
    files = make_tree(root)
    encrypt_folder(root, PASSWORD, kdf_params=FAST)
    snapshot = {rel: (root / rel).read_bytes() for rel in files}
    report = decrypt_folder(root, "nope")
    assert not report.ok and len(report.failed) == len(files)
    for rel in files:
        assert (root / rel).read_bytes() == snapshot[rel]


def test_folder_mixed_legacy(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "old.bin").write_bytes(encrypt_v0(b"old", PASSWORD))
    (root / "new.bin").write_bytes(b"new")
    encrypt_file(root / "new.bin", PASSWORD, kdf_params=FAST)
    report = decrypt_folder(root, PASSWORD)
    assert report.ok
    assert report.legacy == [root / "old.bin"]
    assert (root / "old.bin").read_bytes() == b"old"
    assert (root / "new.bin").read_bytes() == b"new"


def test_folder_skips_symlinks(tmp_path):
    outside = write(tmp_path / "outside.txt", b"do not touch")
    root = tmp_path / "tree"
    root.mkdir()
    write(root / "in.txt", b"inside")
    (root / "link.txt").symlink_to(outside)
    (root / "linkdir").symlink_to(tmp_path, target_is_directory=True)
    report = encrypt_folder(root, PASSWORD, kdf_params=FAST)
    assert report.processed == [root / "in.txt"]
    assert outside.read_bytes() == b"do not touch"
