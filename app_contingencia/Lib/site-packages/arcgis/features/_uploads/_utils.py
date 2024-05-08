from __future__ import annotations
import io
import os
import re
import time
import datetime as _dt
from pathlib import Path
from arcgis.auth.tools._util import parse_url
from urllib.parse import unquote
from typing import Any
from functools import lru_cache

__all__ = [
    "_filename_from_headers",
    "_filename_from_url",
    "calculate_chunksize",
    "local_time_to_online",
    "prepare_file_upload",
]


# ----------------------------------------------------------------------
def prepare_file_upload(
    file: str | io.StringIO | io.BytesIO | io.BufferedReader,
    mimetype: str = None,
    file_name: str = None,
) -> list:
    """This helper creates the tuple/list used to pass into the POST file parameter"""

    if isinstance(file, (io.BytesIO, io.StringIO)):
        if file_name is None:
            raise ValueError(
                "A file_name must be given when an io.BytesIO or io.StringIO is given."
            )
        return [
            file_name,
            file,
            None or mimetype or _get_file_name(file_name),
        ]
    elif isinstance(file, str):
        return [
            file_name,
            open(file, "rb"),
            None or mimetype or _get_file_name(file),
        ]
    elif isinstance(file, io.BufferedReader):
        file_name = os.path.basename(file.name)
        mimetype = mimetype or _get_file_name(file_name)
        return [file_name, file, mimetype]
    else:
        raise ValueError("Cannot process the inputs, please provide a file")
    return None


# ----------------------------------------------------------------------
@lru_cache(maxsize=100)
def local_time_to_online(dt: _dt.datetime | None = None) -> int:
    """
    converts datetime object to a UTC timestamp for AGOL
    Inputs:
       dt - datetime object
    Output:
       int
    """

    if dt is None:
        dt = _dt.datetime.now()

    if sys.version_info.major == 3:
        return int(dt.timestamp() * 1000)
    elif isinstance(dt, _dt.datetime) and dt.tzinfo:
        dt = dt.astimezone()

    return int(time.mktime(dt.timetuple()) * 1000)


# --------------------------------------------------------------------------
def calculate_chunksize(headers: dict[str, Any]) -> int:
    """calculates the chunk size for downloads"""
    stream_size: int = 512 * 2
    if "Content-Length" in headers:
        max_length: int = int(headers["Content-Length"])
        if max_length > stream_size * 2 and max_length < 1024 * 1024:
            stream_size = 1024 * 2
        elif max_length > 5 * (1024 * 1024):
            stream_size = 5 * (1024 * 1024)  # 5 mb
        elif max_length > (1024 * 1024):
            stream_size = 1024 * 1024  # 1 mb
        else:
            stream_size = 512 * 2
    else:
        return 512 * 2


@lru_cache(maxsize=255)
def _filename_from_url(url: str) -> Path:
    """:return: detected filename or None"""
    parsed = parse_url(url)

    return Path(parsed.path).name


# --------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _get_file_name(s: str) -> str:
    """stips the filename from content-disposition using regex"""
    fname = re.findall(r"filename\*=([^;]+)", s, flags=re.IGNORECASE)
    if not fname:
        fname = re.findall(r"filename=([^;]+)", s, flags=re.IGNORECASE)
    if "utf-8''" in fname[0].lower():
        fname = re.sub("utf-8''", "", fname[0], flags=re.IGNORECASE)
        try:
            if type(fname) == str:
                fname = unquote(fname)
            else:
                fname = unquote(fname).decode("utf-8")
        except:
            fname = unquote(fname).encode("utf-8")
    else:
        fname = fname[0]
    # clean space and double quotes
    return fname.strip().strip('"')


# --------------------------------------------------------------------------
def _filename_from_headers(headers: dict[str, Any]) -> str:
    """
    Detect filename from Content-Disposition headers if present.


    :param: headers as dict, list or string
    :return: filename from content-disposition header or None
    """
    if type(headers) == str:
        headers = headers.splitlines()
    if type(headers) == list:
        headers = dict([x.split(":", 1) for x in headers])
    cdisp: str = headers.get("Content-Disposition")
    if not cdisp:
        return None
    return _get_file_name(cdisp)
