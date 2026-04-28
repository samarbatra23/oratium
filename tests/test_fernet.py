from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from oratium.secrets.fernet import FernetCipher


def test_round_trip() -> None:
    key = FernetCipher.generate_key()
    cipher = FernetCipher(key)
    ct = cipher.encrypt("super secret")
    assert ct != "super secret"
    assert cipher.decrypt(ct) == "super secret"


def test_round_trip_unicode() -> None:
    cipher = FernetCipher(FernetCipher.generate_key())
    plaintext = "héllo 🦊 世界"
    assert cipher.decrypt(cipher.encrypt(plaintext)) == plaintext


def test_round_trip_empty_string() -> None:
    cipher = FernetCipher(FernetCipher.generate_key())
    assert cipher.decrypt(cipher.encrypt("")) == ""


def test_decrypt_with_wrong_key_raises() -> None:
    a = FernetCipher(FernetCipher.generate_key())
    b = FernetCipher(FernetCipher.generate_key())
    token = a.encrypt("secret")
    with pytest.raises(InvalidToken):
        b.decrypt(token)


def test_decrypt_garbage_raises() -> None:
    cipher = FernetCipher(FernetCipher.generate_key())
    with pytest.raises(InvalidToken):
        cipher.decrypt("not-a-real-token")


def test_accepts_str_or_bytes_key() -> None:
    raw = FernetCipher.generate_key()
    str_cipher = FernetCipher(raw)
    bytes_cipher = FernetCipher(raw.encode("ascii"))
    token = str_cipher.encrypt("x")
    assert bytes_cipher.decrypt(token) == "x"


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    key = FernetCipher.generate_key()
    monkeypatch.setenv("ORATIUM_FERNET_KEY", key)
    cipher = FernetCipher.from_env()
    assert cipher.decrypt(cipher.encrypt("hi")) == "hi"


def test_from_env_custom_var(monkeypatch: pytest.MonkeyPatch) -> None:
    key = FernetCipher.generate_key()
    monkeypatch.setenv("MY_KEY", key)
    cipher = FernetCipher.from_env("MY_KEY")
    assert cipher.decrypt(cipher.encrypt("hi")) == "hi"


def test_from_env_missing_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORATIUM_FERNET_KEY", raising=False)
    with pytest.raises(ValueError, match="ORATIUM_FERNET_KEY is not set"):
        FernetCipher.from_env()


def test_from_env_empty_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORATIUM_FERNET_KEY", "")
    with pytest.raises(ValueError, match="ORATIUM_FERNET_KEY is not set"):
        FernetCipher.from_env()


def test_generate_key_is_url_safe() -> None:
    key = FernetCipher.generate_key()
    # 44 chars (32 bytes base64-encoded with padding)
    assert len(key) == 44
    # Constructible
    FernetCipher(key)
