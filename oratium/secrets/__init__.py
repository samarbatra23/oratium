"""Secrets handling — symmetric encryption for credentials at rest."""

from oratium.secrets.fernet import FernetCipher

__all__ = ["FernetCipher"]
