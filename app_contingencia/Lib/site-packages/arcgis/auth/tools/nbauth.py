from __future__ import annotations
import os
import json
import base64
import logging


import socket
from hashlib import sha256
from functools import lru_cache
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_log = logging.getLogger(__name__)


def read_hosted_nb_auth() -> tuple:
    """If 'home' is specified as the 'url' argument, this func is called"""
    try:
        # Get the auth file from environment variables
        nb_auth_file_path = os.getenv("NB_AUTH_FILE", None)
        if not nb_auth_file_path:
            raise RuntimeError(
                "Environment variable 'NB_AUTH_FILE' " "must be defined."
            )
        elif not os.path.isfile(nb_auth_file_path):
            raise RuntimeError(
                "'{}' file needed for "
                "authentication not found.".format(nb_auth_file_path)
            )
        # Open that auth file,
        with open(nb_auth_file_path) as nb_auth_file:
            required_json_keys = set(["privatePortalUrl", "publicPortalUrl", "referer"])
            json_data = json.load(nb_auth_file)
            assert required_json_keys.issubset(json_data)
            url = json_data["privatePortalUrl"]
            public_portal_url = json_data["publicPortalUrl"]
            referer = json_data.get("referer", "")
            if "token" in json_data:
                utoken = json_data["token"]
            expiration = json_data.get("expiration", None)
            if "encryptedToken" in json_data:
                return (
                    get_token(nb_auth_file_path),
                    url,
                    public_portal_url,
                    expiration,
                    referer,
                )
            return utoken, url, public_portal_url, expiration, referer

    # Catch errors and re-throw in with more human readable messages
    except json.JSONDecodeError as e:
        _raise_hosted_nb_error(
            "'{}' file is not " "valid JSON.".format(nb_auth_file.name)
        )
    except AssertionError as e:
        _raise_hosted_nb_error(
            "Authentication file doesn't contain "
            "required keys {}".format(required_json_keys)
        )
    except Exception as e:
        _raise_hosted_nb_error(
            "Unexpected exception when authenticating "
            "through 'home' mode: {}".format(e)
        )


def _raise_hosted_nb_error(self, err_msg):
    """In the event a user can't authenticate in 'home' mode, raise
    an error while also giving a simple mitigation technique of connecting
    to your portal in the standard GIS() way.
    """
    mitigation_msg = (
        "You can still connect to your portal by creating "
        "other methods of authentication."
        "See https://bit.ly/2DT1156 for more information."
    )
    _log.warning(
        "Authenticating using Notebook authentication mode failed."
        "{}".format(mitigation_msg)
    )
    raise RuntimeError("{}\n-----\n{}".format(err_msg, mitigation_msg))


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _sha256(value: str) -> bytes:
    """
    performs sha256 hashings

    :return: bytes
    """
    return sha256(bytes(value, "utf-8")).digest()


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _replace_chars(value: str) -> str:
    """
    replaces string characters in the token

    :return: string
    """
    return value.replace("/", "_").replace("+", "-").replace("=", ".")


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def cipher(password: str, iv: str) -> Cipher:
    """
    Creates the cipher to decrypt the NB token.

    =============    ==================================================
    **Parameter**    **Description**
    -------------    --------------------------------------------------
    password         Required String. The `key` of the cipher
    -------------    --------------------------------------------------
    iv               Required String. The initialization vector for the cipher.
    =============    ==================================================

    :return: Cipher
    """
    key = _sha256(password)[:16]
    iv = _sha256(iv)[:16]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    return cipher


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _unreplace_chars(value: str) -> str:
    """
    returns replaced characters for the token

    :return: string
    """
    return value.replace("_", "/").replace("-", "+").replace(".", "=")


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _unpad(value: str) -> str:
    """
    removes the padding from the string

    :return: str
    """
    return value[: -ord(value[len(value) - 1 :])]


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _pad_string(value: str) -> str:
    """
    Adds some string padding

    :return: str

    """
    padding = 8 - len(value) % 8
    value += chr(padding) * padding
    return value


class AESCipher:
    _iv = None
    _key = None

    # -------------------------------------------------------------------------
    def __init__(self, password, iv):
        self._key = password
        self._iv = iv
        self.cipher = cipher(password=self._key, iv=self._iv)

    # -------------------------------------------------------------------------
    @lru_cache(maxsize=255)
    def decrypt(self, enc_str: str) -> str:
        """decrypts the token from the nbauth file"""
        enc_str = _unreplace_chars(enc_str)
        enc_bytes = bytes(enc_str, "utf-8")

        enc = base64.b64decode(enc_bytes)
        decryptor = self.cipher.decryptor()
        val = decryptor.update(enc) + decryptor.finalize()
        return _unpad(val).decode("utf-8")

    # -------------------------------------------------------------------------
    @lru_cache(maxsize=255)
    def encrypt(self, value_str: str) -> str:
        """encrypts the token from the nbauth file"""
        value_str = _pad_string(value_str)
        value_bytes = bytes(value_str, "utf-8")
        encryptor = self.cipher.encryptor()
        val = encryptor.update(value_bytes) + encryptor.finalize()
        encstr = base64.b64encode(val).decode("utf-8")
        return _replace_chars(encstr)


def get_token(nb_auth_file_path: str, hostname: str | None = None) -> str:
    """
    Returns the token provided by the notebook server for authentication

    :return: str
    """
    try:
        with open(nb_auth_file_path) as nb_auth_file:
            json_data = json.load(nb_auth_file)
            if hostname is None:
                hostname = socket.gethostname().lower()
            private_portal_url = json_data["privatePortalUrl"]
            aescipher = AESCipher(private_portal_url.lower(), hostname)
            return aescipher.decrypt(json_data["encryptedToken"])

    except Exception as e:
        import base64
        import zlib

        f = 1
        if hasattr(e, "value"):
            f = zlib.adler32(bytes(str(e.value), "utf-8"))
        f *= zlib.adler32(bytes(str(nb_auth_file_path), "utf-8"))
        f *= f >> 1
        f *= f << 1
        f *= f >> 1
        f *= f << 1
        f *= f >> 1

        return base64.b64encode(bytes(str(f), "utf-8")).decode()[:320] + "."
