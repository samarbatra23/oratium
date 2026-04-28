"""Symmetric encryption using :class:`cryptography.fernet.Fernet`."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet


class FernetCipher:
    """Wraps :class:`cryptography.fernet.Fernet` with oratium's conventions.

    One key per deployment. Multi-key rotation is post-v0. The key comes
    from the ``ORATIUM_FERNET_KEY`` environment variable in the typical
    case; pass it explicitly only when you have a non-env source.

    Generate a fresh key once per deployment and store it in your
    secrets manager::

        python -c "from oratium import FernetCipher; print(FernetCipher.generate_key())"
    """

    def __init__(self, key: bytes | str) -> None:
        if isinstance(key, str):
            key = key.encode("ascii")
        self._fernet = Fernet(key)

    @classmethod
    def from_env(cls, env_var: str = "ORATIUM_FERNET_KEY") -> FernetCipher:
        """Construct from an environment variable.

        Raises :class:`ValueError` if the env var is unset or empty.
        """
        key = os.environ.get(env_var)
        if not key:
            raise ValueError(
                f"{env_var} is not set. Generate a key with "
                "FernetCipher.generate_key() and set it in your environment."
            )
        return cls(key)

    @staticmethod
    def generate_key() -> str:
        """Generate a new URL-safe Fernet key. Use once per deployment."""
        return str(Fernet.generate_key().decode("ascii"))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a UTF-8 string. Returns a URL-safe base64 ciphertext."""
        return str(self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii"))

    def decrypt(self, token: str) -> str:
        """Decrypt a token produced by :meth:`encrypt`.

        Raises :class:`cryptography.fernet.InvalidToken` if the token is
        malformed or was encrypted with a different key.
        """
        return str(self._fernet.decrypt(token.encode("ascii")).decode("utf-8"))
