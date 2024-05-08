from __future__ import annotations
import io
import os
import requests
import mimetypes
from functools import lru_cache
from typing import Optional, Any, Iterator, Tuple, Union
from arcgis.auth import EsriSession
from arcgis.auth.tools import LazyLoader

_arcgis_gis = LazyLoader("arcgis.gis")
__all__ = [
    "guess_mimetype",
    "create_upload_tuple",
    "close_upload_files",
    "_get_folder_id",
    "_get_folder_name",
    "close_upload_files",
    "calculate_upload_size",
    "chunk_by_file_size",
    "status",
]


# ----------------------------------------------------------------------
def status(
    resturl: str,
    session: EsriSession,
    owner: str,
    itemid: str,
    job_id: Optional[str] = None,
    job_type: Optional[str] = None,
):
    """
    The ``status`` method provides the status of an :class:`~arcgis.gis.Item` in the following situations:
        1. Publishing an :class:`~arcgis.gis.Item`
        2. Adding an :class:`~arcgis.gis.Item` in async mode
        3. Adding with a multipart upload. `Partial` is available for ``Add Item Multipart`` when only a part is
        uploaded and the :class:`~arcgis.gis.Item` object is not committed.


    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    job_id              Optional string. The job ID returned during publish, generateFeatures,
                        export, and createService calls.
    ---------------     --------------------------------------------------------------------
    job_type            Optional string. The type of asynchronous job for which the status
                        has to be checked. Default is none, which checks the item's status.
                        This parameter is optional unless used with the operations listed
                        below. Values: `publish`, `generateFeatures`, `export`, and `createService`
    ===============     ====================================================================

    :return:
       The status of a publishing :class:`~arcgis.gis.Item` object.

    .. code-block:: python

        # Usage Example

        >>> item.status(job_type="generateFeatures")
    """
    params = {"f": "json"}
    data_path = f"{resturl}content/users/{owner}/items/{itemid}/status"
    if job_type is not None:
        params["jobType"] = job_type
    if job_id is not None:
        params["jobId"] = job_id
    resp: requests.Response = session.get(url=data_path, params=params)
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------------------------
def chunk_by_file_size(
    fp: str | io.BytesIO,
    size: int = None,
    parameter_name: str = "file",
    upload_format: bool = False,
) -> Iterator[Union[Tuple[str, io.BytesIO, str], io.BytesIO]]:
    """Splits a File based on a specific bytes size"""
    if size is None:
        size = int(2.5e7)  # 25MB
    i = 1
    if isinstance(fp, str):
        with open(fp, "rb") as reader:
            while True:
                bio = io.BytesIO()
                data = bio.write(reader.read(size))
                bio.seek(0)
                if not data:
                    break
                if upload_format:
                    fpath = f"split{i}.split"
                    yield parameter_name, bio, fpath
                else:
                    yield bio
                i += 1
    elif isinstance(fp, io.StringIO):
        fp.seek(0)
        while True:
            bio = io.StringIO()
            data = bio.write(fp.read(size))
            bio.seek(0)
            if not data:
                break
            if upload_format:
                fpath = f"split{i}.split"
                yield parameter_name, bio, fpath
            else:
                yield bio
            i += 1
    else:
        fp.seek(0)
        while True:
            bio = io.BytesIO()
            data = bio.write(fp.read(size))
            bio.seek(0)
            if not data:
                break
            if upload_format:
                fpath = f"split{i}.split"
                yield parameter_name, bio, fpath
            else:
                yield bio
            i += 1
    return None


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def guess_mimetype(extension: str) -> str:
    """guesses the mimetype for an extension"""
    if extension in ["", None]:
        return None
    return mimetypes.guess_type(f"t{extension}")[0]


# -------------------------------------------------------------------------
def create_upload_tuple(file: str, **kwargs) -> tuple:
    """Creates the tuple used in uploading a file"""
    if isinstance(file, (io.StringIO, io.BytesIO)) and "file_name" in kwargs:
        return (
            kwargs.pop("file_name"),
            file,
            None,
        )
    elif isinstance(file, (io.StringIO, io.BytesIO)) and not "file_name" in kwargs:
        raise ValueError(
            "The `file_name` is required when using io.BytesIO or io.StringIO."
        )
    elif isinstance(file, str):
        _, ext = os.path.splitext(file)
        return (
            os.path.basename(file),
            open(file, "rb"),
            guess_mimetype(ext),
        )
    else:
        raise ValueError(
            "Could not parse the file, ensure it exists and is of type string."
        )


# -------------------------------------------------------------------------
def close_upload_files(upload_tuple: list[tuple]) -> None:
    """Closes the files once the upload is completed."""
    for ut in upload_tuple:
        ut[1].close()
        del ut


# -------------------------------------------------------------------------
def calculate_upload_size(fp: str) -> int:
    """calculates the file MAX upload limit."""
    fd = os.open(fp, os.O_RDONLY)
    size: float = os.fstat(fd).st_size

    if size <= 5 * (1024 * 1024):
        return int(5 * (1024 * 1024))
    elif size > 5 * (1024 * 1024) and size <= 10 * (1024 * 1024):
        return int(7 * (1024 * 1024))
    elif size > 10 * (1024 * 1024) and size <= 15 * (1024 * 1024):
        return int(13 * (1024 * 1024))
    elif size > 15 * (1024 * 1024) and size <= 25 * (1024 * 1024):
        return int(25 * (1024 * 1024))
    elif size > 25 * (1024 * 1024) and size <= 35 * (1024 * 1024):
        return int(30 * (1024 * 1024))
    elif size > 35 * (1024 * 1024) and size <= 40 * (1024 * 1024):
        return int(40 * (1024 * 1024))
    else:
        return int(45 * (1024 * 1024))


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _get_folder_id(
    gis: _arcgis_gis.GIS, owner: str, folder_name: str
) -> dict[str, Any]:
    """Finds the folder for a particular owner and returns its id.

    ================  ========================================================
    **Parameter**      **Description**
    ----------------  --------------------------------------------------------
    owner             required string, the name of the user
    ----------------  --------------------------------------------------------
    folder_name       required string, the name of the folder to search for
    ================  ========================================================

    :return:
        a boolean if succeeded.
    """
    if folder_name in [None, "/", "Root Folder"]:
        return None
    session: EsriSession = gis._con._session
    resp = session.post(
        url=f"{gis._portal.resturl}content/users/{owner}",
        data={
            "f": "json",
        },
    ).json()
    result = [
        f["id"]
        for f in resp.get("folders", [])
        if folder_name.lower() in [f["id"].lower(), f["title"].lower()]
    ]
    if len(result) > 0:
        return result[0]
    return None


# -------------------------------------------------------------------------
def _get_folder_name(
    gis: _arcgis_gis.GIS, owner: str, folder_id: str
) -> dict[str, Any]:
    """Finds the folder for a particular owner and returns its id.

    ================  ========================================================
    **Parameter**      **Description**
    ----------------  --------------------------------------------------------
    owner             required string, the name of the user
    ----------------  --------------------------------------------------------
    folder_name       required string, the name of the folder to search for
    ================  ========================================================

    :return:
        a boolean if succeeded.
    """
    if folder_id is None:
        return "Root Folder"
    session: EsriSession = gis._con._session
    resp = session.post(
        url=f"{gis._portal.resturl}content/users/{owner}",
        data={
            "f": "json",
        },
    )
    data: dict[str, Any] = resp.json()
    result = [
        f["title"]
        for f in data.get("folders", [])
        if folder_id.lower() in [f["id"].lower(), f["title"].lower()]
    ]
    if len(result) > 0:
        return result[0]
    return None
