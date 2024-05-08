from __future__ import annotations
import os
import ssl
import requests
import tempfile
import cryptography
import datetime as _dt

try:
    from ssl import PROTOCOL_TLS_CLIENT as default_ssl_protocol
except ImportError:
    from ssl import PROTOCOL_SSLv23 as default_ssl_protocol


from .certificate import _handle_cert_context

__all__ = ["PKIAdapter"]


###########################################################################
class PKIAdapter(requests.adapters.HTTPAdapter):
    # ---------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        pki_data = kwargs.pop("pki_data", None)

        password = kwargs.pop("pki_password", None)
        ssl_protocol_or_none = kwargs.pop("ssl_protocol", None)
        if pki_data is None:
            raise ValueError('"pki_data" is missing')

        if password is None:
            password_bytes = None
        elif isinstance(password, bytes):
            password_bytes = password
        elif isinstance(password, str):
            password_bytes = password.encode("utf8")
        else:
            raise TypeError("Password must be a None, string or bytes.")
        if ssl_protocol_or_none is None:
            ssl_protocol = default_ssl_protocol
        else:
            ssl_protocol = ssl_protocol_or_none
        self.ssl_context = _handle_cert_context(
            cert=pki_data, password=password_bytes, ssl_protocol=ssl_protocol
        )
        super(PKIAdapter, self).__init__(*args, **kwargs)

    # ---------------------------------------------------------------------
    def init_poolmanager(self, *args, **kwargs):
        if self.ssl_context:
            kwargs["ssl_context"] = self.ssl_context
        return super(PKIAdapter, self).init_poolmanager(*args, **kwargs)

    # ---------------------------------------------------------------------
    def proxy_manager_for(self, *args, **kwargs):
        if self.ssl_context:
            kwargs["ssl_context"] = self.ssl_context
        return super(PKIAdapter, self).proxy_manager_for(*args, **kwargs)

    # ---------------------------------------------------------------------
    def cert_verify(self, conn, url, verify, cert):
        check_hostname = self.ssl_context.check_hostname
        try:
            if verify is False:
                self.ssl_context.check_hostname = False
            return super(PKIAdapter, self).cert_verify(conn, url, verify, cert)
        finally:
            self.ssl_context.check_hostname = check_hostname

    # ---------------------------------------------------------------------
    def send(
        self,
        request,
        stream=False,
        timeout=None,
        verify=True,
        cert=None,
        proxies=None,
    ):
        check_hostname = self.ssl_context.check_hostname
        try:
            if verify is False:
                self.ssl_context.check_hostname = False
            return super(PKIAdapter, self).send(
                request, stream, timeout, verify, cert, proxies
            )
        finally:
            self.ssl_context.check_hostname = check_hostname
