import os
import json
import base64
import ctypes
import logging
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

logger = logging.getLogger("CryptoVault")


class ZeroKnowledgeCryptoVault:
    """Implements Zero-Knowledge Profile & Credential Encryption using Argon2id KDF & AES-256-GCM."""

    SALT_SIZE = 16
    NONCE_SIZE = 12  # Standard 96-bit nonce for GCM
    KEY_SIZE = 32    # 256-bit key

    _master_key_memory: Optional[bytearray] = None
    _session_pass_memory: Optional[bytearray] = None
    _is_unlocked: bool = False

    @staticmethod
    def _zero_memory(buf: Optional[bytearray]):
        """Securely zeroes out volatile bytearray in memory."""
        if buf is not None and isinstance(buf, bytearray):
            for i in range(len(buf)):
                buf[i] = 0

    @classmethod
    def derive_key(cls, master_password: str, salt: bytes) -> bytes:
        """Derives a 256-bit encryption key using Argon2id (time_cost=3, memory_cost=65536KB, parallelism=4)."""
        kdf = Argon2id(
            salt=salt,
            length=cls.KEY_SIZE,
            iterations=3,
            memory_cost=65536,
            lanes=4,
        )
        pwd_bytes = master_password.encode("utf-8")
        try:
            return kdf.derive(pwd_bytes)
        finally:
            # Best effort memory cleanup
            del pwd_bytes

    @classmethod
    def encrypt_bytes(cls, plaintext: bytes, master_password: str) -> bytes:
        """Encrypts raw bytes with AES-256-GCM using an Argon2id derived key. Returns salt + nonce + ciphertext."""
        salt = os.urandom(cls.SALT_SIZE)
        key = cls.derive_key(master_password, salt)
        try:
            aesgcm = AESGCM(key)
            nonce = os.urandom(cls.NONCE_SIZE)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            return salt + nonce + ciphertext
        finally:
            del key

    @classmethod
    def decrypt_bytes(cls, payload: bytes, master_password: str) -> bytes:
        """Decrypts AES-256-GCM payload (salt + nonce + ciphertext) using master password."""
        if len(payload) < cls.SALT_SIZE + cls.NONCE_SIZE + 16:
            raise ValueError("Invalid encrypted payload size")

        salt = payload[:cls.SALT_SIZE]
        nonce = payload[cls.SALT_SIZE : cls.SALT_SIZE + cls.NONCE_SIZE]
        ciphertext = payload[cls.SALT_SIZE + cls.NONCE_SIZE :]

        key = cls.derive_key(master_password, salt)
        try:
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        finally:
            del key

    @classmethod
    def encrypt_dict(cls, data: Dict[str, Any], master_password: str) -> str:
        """Serializes and encrypts a Python dict into a base64-encoded zero-knowledge payload."""
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            encrypted = cls.encrypt_bytes(json_bytes, master_password)
            return base64.b64encode(encrypted).decode("ascii")
        finally:
            del json_bytes

    @classmethod
    def decrypt_dict(cls, encrypted_b64: str, master_password: str) -> Dict[str, Any]:
        """Decrypts a base64-encoded payload into a Python dict. Throws exception if key/password invalid."""
        payload = base64.b64decode(encrypted_b64.encode("ascii"))
        decrypted_bytes = cls.decrypt_bytes(payload, master_password)
        try:
            return json.loads(decrypted_bytes.decode("utf-8"))
        finally:
            del decrypted_bytes

    @classmethod
    def set_session_master_password(cls, master_password: str) -> bool:
        """Stores the derived master key in volatile memory during active session."""
        try:
            salt = os.urandom(cls.SALT_SIZE)  # [F-13] Random salt for session key
            key_bytes = cls.derive_key(master_password, salt)
            cls._master_key_memory = bytearray(key_bytes)
            cls._session_pass_memory = bytearray(master_password.encode("utf-8"))
            cls._is_unlocked = True
            logger.info("[CryptoVault] Session Vault unlocked with Argon2id Master Key.")
            return True
        except Exception as e:
            logger.error(f"[CryptoVault] Unlock error: {e}")
            return False

    @classmethod
    def get_session_password(cls) -> Optional[str]:
        """Returns session password if vault is currently unlocked."""
        if cls._is_unlocked and cls._session_pass_memory:
            return cls._session_pass_memory.decode("utf-8")
        return None

    @classmethod
    def lock_vault(cls):
        """Locks the vault and securely zeros master key and session password memory."""
        cls._zero_memory(cls._master_key_memory)
        cls._zero_memory(cls._session_pass_memory)
        cls._master_key_memory = None
        cls._session_pass_memory = None
        cls._is_unlocked = False
        logger.info("[CryptoVault] Session Vault locked & key memory purged.")

    @classmethod
    def is_vault_unlocked(cls) -> bool:
        return cls._is_unlocked

