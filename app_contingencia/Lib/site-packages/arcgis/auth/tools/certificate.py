"""
Tools to assist users to work with PKI Certificates
"""

from __future__ import annotations
import os
import tempfile
import cryptography
from cryptography import x509
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)

import os
import ssl

import tempfile
import cryptography


try:
    from ssl import PROTOCOL_TLS_CLIENT as default_ssl_protocol
except ImportError:
    from ssl import PROTOCOL_SSLv23 as default_ssl_protocol

_crypto_version = [
    int(i) if i.isdigit() else i for i in cryptography.__version__.split(".")
]


def _handle_cert_context(
    cert: tuple | str, password: str, ssl_protocol=default_ssl_protocol
) -> None | str:
    """handles the certificate logic"""
    if cert is None:
        return None
    elif (
        cert
        and isinstance(cert, str)
        and (cert.lower().endswith(".p12") or cert.lower().endswith(".pfx"))
        and password
    ):
        #  case 2 - p12/pfx with password
        return _handle_cert_context(cert=pfx_to_pem(cert, password), password=password)
    elif (
        cert
        and isinstance(cert, str)
        and (cert.lower().endswith(".p12") or cert.lower().endswith(".pfx"))
        and password is None
    ):
        # case 2 p12/pfx with no password - not allowed, raise error
        raise ValueError("`password` is required.")
    elif isinstance(cert, (tuple, list)):
        # case 3 tuple[str]
        ssl_protocol = ssl_protocol
        ssl_context = ssl.SSLContext(ssl_protocol)
        with tempfile.NamedTemporaryFile(delete=False) as c:
            with open(cert[0], "rb") as reader:
                public_cert = x509.load_pem_x509_certificate(reader.read())
            with open(cert[1], "rb") as reader:
                private_bytes = reader.read()
            cert_bytes = public_cert.public_bytes(Encoding.PEM)

            private_key = load_pem_private_key(
                data=private_bytes, password=None, backend=None
            )
            pk_buf = private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
            c.write(pk_buf)

            c.write(cert_bytes)
            c.flush()
            c.close()

            ssl_context.load_cert_chain(c.name)
        return ssl_context
    else:
        raise ValueError("Invalid `cert` parameter")


# ----------------------------------------------------------------------
def pfx_to_pem(pfx_path, pfx_password, folder=None, use_openssl=False):
    """Decrypts the .pfx file to be used with requests.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    pfx_path            Required string.  File pathname to .pfx file to parse.
    ---------------     --------------------------------------------------------------------
    pfx_password        Required string.  Password to open .pfx file to extract key/cert.
    ---------------     --------------------------------------------------------------------
    folder              Optional String.  The save location of the certificate files.  The
                        default is the tempfile.gettempdir() directory.
    ---------------     --------------------------------------------------------------------
    user_openssl        Optional Boolean. If True, OpenPySSL is used to convert the pfx to pem instead of cryptography.
    ===============     ====================================================================

    :return: Tuple
       File path to key_file located in a tempfile location
       File path to cert_file located in a tempfile location
    """
    if (
        pfx_path.lower().endswith(".pfx") == False
        and pfx_path.lower().endswith(".p12") == False
    ):
        raise ValueError("`pfx_to_pem` only supports `pfx` and `p12` certificates.")
    if folder is None:
        folder = tempfile.gettempdir()
    elif folder and not os.path.isdir(folder):
        raise Exception("Folder location does not exist.")
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False, dir=folder)
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False, dir=folder)
    if use_openssl:
        try:
            import OpenSSL.crypto

            k = open(key_file.name, "wb")
            c = open(cert_file.name, "wb")
            try:
                pfx = open(pfx_path, "rb").read()
                p12 = OpenSSL.crypto.load_pkcs12(pfx, pfx_password)
            except OpenSSL.crypto.Error:
                raise RuntimeError("Invalid PFX password.  Unable to parse file.")
            k.write(
                OpenSSL.crypto.dump_privatekey(
                    OpenSSL.crypto.FILETYPE_PEM, p12.get_privatekey()
                )
            )
            c.write(
                OpenSSL.crypto.dump_certificate(
                    OpenSSL.crypto.FILETYPE_PEM, p12.get_certificate()
                )
            )
            k.close()
            c.close()
        except ImportError as e:
            raise e
        except Exception as ex:
            raise ex
    else:
        _default_backend = None
        if _crypto_version < [3, 0]:
            from cryptography.hazmat.backends import default_backend

            _default_backend = default_backend()
        if isinstance(pfx_password, str):
            pfx_password = str.encode(pfx_password)
        with open(pfx_path, "rb") as f:
            (
                private_key,
                certificate,
                additional_certificates,
            ) = pkcs12.load_key_and_certificates(
                f.read(), pfx_password, backend=_default_backend
            )
        cert_bytes = certificate.public_bytes(Encoding.PEM)
        pk_bytes = private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
        k = open(key_file.name, "wb")
        c = open(cert_file.name, "wb")

        k.write(pk_bytes)
        c.write(cert_bytes)
        k.close()
        c.close()
        del k
        del c
    key_file.close()
    cert_file.close()
    return cert_file.name, key_file.name  # certificate/key
