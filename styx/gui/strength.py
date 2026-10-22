"""A small, dependency-free password strength estimate for the GUI.

This is a guide for the user, not a security guarantee: it estimates the
search space from length and character variety, then penalises obvious
patterns (repeated characters, sequences, very common passwords).
"""

from __future__ import annotations

import math
import string
from dataclasses import dataclass

_COMMON = {
    "password", "passw0rd", "motdepasse", "123456", "12345678", "123456789",
    "1234567890", "qwerty", "azerty", "azertyuiop", "qwertyuiop", "letmein",
    "welcome", "admin", "iloveyou", "monkey", "dragon", "football", "soleil",
    "bonjour", "abc123", "111111", "000000", "styx", "secret", "changeme",
}

_SEQUENCES = (
    string.ascii_lowercase,
    string.digits,
    "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "azertyuiop", "qsdfghjklm", "wxcvbn",
)

LABELS = ("Too weak", "Weak", "Fair", "Strong", "Very strong")
HINTS = (
    "Use at least 12 characters, ideally a few unrelated words.",
    "Make it longer. A passphrase of four or more words works well.",
    "Acceptable. A few more characters would make it much harder to guess.",
    "Keep it somewhere safe: a lost password cannot be recovered.",
    "Keep it somewhere safe: a lost password cannot be recovered.",
)


@dataclass(frozen=True)
class Strength:
    score: int  # 0..4
    bits: float

    @property
    def label(self) -> str:
        return LABELS[self.score]

    @property
    def hint(self) -> str:
        return HINTS[self.score]


def _charset_size(password: str) -> int:
    size = 0
    if any(c in string.ascii_lowercase for c in password):
        size += 26
    if any(c in string.ascii_uppercase for c in password):
        size += 26
    if any(c in string.digits for c in password):
        size += 10
    if any(c in string.punctuation or c == " " for c in password):
        size += 33
    if any(ord(c) > 127 for c in password):
        size += 64
    return max(size, 1)


def _effective_length(password: str) -> float:
    """Length after discounting repeats and keyboard/alphabet sequences."""
    lowered = password.lower()
    length = 0.0
    for i, c in enumerate(lowered):
        if i and c == lowered[i - 1]:
            length += 0.25
            continue
        if i and any(
            lowered[i - 1] + c in seq or (lowered[i - 1] + c)[::-1] in seq for seq in _SEQUENCES
        ):
            length += 0.4
            continue
        length += 1
    return length


def estimate(password: str) -> Strength:
    if not password:
        return Strength(0, 0.0)
    if password.lower() in _COMMON:
        return Strength(0, 1.0)
    bits = _effective_length(password) * math.log2(_charset_size(password))
    if bits < 28:
        score = 0
    elif bits < 45:
        score = 1
    elif bits < 60:
        score = 2
    elif bits < 80:
        score = 3
    else:
        score = 4
    return Strength(score, bits)
