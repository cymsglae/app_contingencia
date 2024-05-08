from __future__ import annotations
import os
import tempfile
from typing import Any
from io import BytesIO, StringIO
import requests
from arcgis.auth.tools import LazyLoader
from arcgis.auth import EsriSession
from ._utils import (
    _filename_from_headers,
    _filename_from_url,
    calculate_chunksize,
)
import mimetypes
from requests_toolbelt.downloadutils import stream

arcgis = LazyLoader("arcgis")


########################################################################
class Upload:
    """Represents a Single Uploaded Item on a Feature Service"""

    _url: str
    session: EsriSession

    def __init__(self, url: str, session: EsriSession) -> None:
        self._url = url
        self.session = session

    # ----------------------------------------------------------------------
    @property
    def properties(self) -> dict[str, Any]:
        """returns the upload's properties"""
        params: dict[str, Any] = {"f": "json"}
        resp: requests.Response = self.session.get(url=self._url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ----------------------------------------------------------------------
    def upload_by_part(
        self,
        part_number: int,
        part: str | BytesIO | StringIO,
        part_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Uploads a new item to the server. Once the operation is completed
        successfully, the JSON structure of the uploaded item is returned.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        item_id             Required string. Item ID to upload to.
        ---------------     --------------------------------------------------------------------
        part_number         Required int. An integer value associated with the part.
        ---------------     --------------------------------------------------------------------
        part                Required string. File path to the part to upload.
        ---------------     --------------------------------------------------------------------
        part_name           Optional String. When a io.BytesIO or io.StringIO is given, the user
                            must provide a part_name, which represents the file name of the
                            upload part.
        ===============     ====================================================================


        :return: Dictionary indicating 'success' or 'error'

        """
        url: str = f"{self._url}/uploadPart"
        params: dict[str, Any] = {"f": "json", "partNumber": part_number}
        files: dict[str, Any] = {}
        if isinstance(part, str):
            with open(part, "rb") as reader:
                # (fileName,filePath,None,)
                # files["file"] = (os.path.basename(part), reader, None)
                files["file"] = (
                    part_name,
                    reader,
                    mimetypes.guess_type(part_name)[0],
                )
                resp: requests.Response = self.session.post(
                    url=url, data=params, files=files
                )
                # self._con.post(path=url, postdata=params, files=files)
                resp.raise_for_status()
                return resp.json()
        elif isinstance(part, (StringIO, BytesIO)):
            if part_name is None:
                raise ValueError(
                    "part_name is required when uploading using io objects."
                )
            files["file"] = (
                os.path.basename(part_name),
                part,
                mimetypes.guess_type(os.path.basename(part_name))[0],
            )
            resp: requests.Response = self.session.post(
                url=url, data=params, files=files
            )
            resp.raise_for_status()
            return resp.json()
        else:
            raise ValueError(f"Unsupported part type: {type(part)}")

    # ----------------------------------------------------------------------
    def commit(self, parts: list[int] = None) -> bool:
        """
        Use this operation to complete the upload of all the parts that
        make an item. The parts parameter indicates to the server all the
        parts that make up the item.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        parts               Optional list. An optional comma-separated ordered list of all the
                            parts that make the item. If this parameter is not provided, the
                            default order of the parts is used.
        ===============     ====================================================================


        :return: Boolean. True if successful else False.

        """
        params: dict[str, Any] = {"f": "json"}
        url = f"{self._url}/commit"
        if parts:
            params["parts"] = parts
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        res: dict[str, Any] = resp.json()
        if "status" in res:
            return res["status"] == "success"
        elif "success" in res:
            return res["success"]
        return res

    # ----------------------------------------------------------------------
    def delete(self) -> bool:
        """
        Deletes the uploaded item and its configuration.

        :return: Boolean. True if successful else False.

        """
        url: str = f"{self._url}/delete"
        params: dict[str, Any] = {"f": "json"}
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        res: dict[str, Any] = resp.json()
        if "status" in res:
            return res["status"] == "success"
        elif "success" in res:
            return res["success"]
        return res

    # ----------------------------------------------------------------------
    def _download(self, out_path: str | None = None) -> str:
        """
        Downloads the uploaded asset to the local disk drive

        :returns: string
        """
        if out_path is None:
            out_path = tempfile.gettempdir()
        url = f"{self._url}/download"
        resp: requests.Response = self.session.get(url)
        resp.raise_for_status()
        headers: dict[str, Any] = resp.headers
        if headers.get("Content-Disposition", None):
            _ffheader = _filename_from_headers(resp.headers)
            _ffurl = _filename_from_url(url)
            fname: str = _ffheader or _ffurl or None
            file_name: str = os.path.join(out_path, fname)
            stream_size: int = calculate_chunksize(resp.headers)
            if os.path.isfile(file_name):
                os.remove(file_name)
            fp: str = stream.stream_response_to_file(
                response=resp, path=file_name, chunksize=stream_size
            )
            return fp
        else:
            return resp.text

    # ----------------------------------------------------------------------
    @property
    def parts(self) -> list[int]:
        """returns the parts of an upload"""
        url: str = f"{self._url}/parts"
        params: dict[str, Any] = {"f": "json"}
        resp: requests.Response = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("parts", [])


class UploadManager:
    """Manages Feature Service upload items"""

    layer: arcgis.features.FeatureLayer
    parent: arcgis.features.FeatureLayerCollection
    session: arcgis.auth.EsriSession

    def __init__(self, layer: arcgis.features.FeatureLayer) -> None:
        self.layer: arcgis.features.FeatureLayer = layer
        self.session = self.layer._gis._con._session
        self.parent: arcgis.features.FeatureLayerCollection = layer.container
        self._url: str = f"{self.parent._url}/uploads"

    # ----------------------------------------------------------------------
    def register(self, item_name: str, description: str | None = None) -> Upload:
        """
        This operation directs the server to reserve space for a new item
        (to be uploaded) that could be made up of one or more parts. Once
        the operation is completed, you must use the upload part operation
        to upload individual parts. After you have uploaded all the parts,
        you must ask the server to consolidate the upload by committing it.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        item_name           Required string. The name of the item.
        ---------------     --------------------------------------------------------------------
        description         Optional string. Description of the upload.
        ===============     ====================================================================

        :returns: Upload
        """
        url: str = f"{self._url}/register"
        params: dict[str, Any] = {"f": "json", "itemName": item_name}
        if description:
            params["description"] = description
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data.get("status", "failed") == "success" or data.get("success", None):
            item_url = f"{self._url}/{data['item']['itemID']}"
            return Upload(url=item_url, session=self.session)
        else:
            return resp.json()

    # ----------------------------------------------------------------------
    def upload(
        self,
        path: str,
        *,
        description: str | None = None,
        file_name: str | None = None,
    ) -> Upload:
        """
        Uploads a new item to the server.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        path                Required string, BytesIO, StringIO. The data to upload to the server.
        ---------------     --------------------------------------------------------------------
        description         Optional string. Description of the upload.
        ---------------     --------------------------------------------------------------------
        file_name           Optional string. When the path is an IO object, a file name must be
                            given so the server knows how to save the information on the server.
        ===============     ====================================================================


        :return: Upload, on error, a dictionary with the error information is returned.
        """

        url: str = f"{self._url}/upload"
        params: dict[str, Any] = {
            "f": "json",
            "description": description or "",
        }
        files: dict[str, Any] = {}
        if isinstance(path, str):
            with open(path, "rb") as reader:
                correct_path = file_name or path
                files["file"] = (
                    os.path.basename(correct_path),
                    reader,
                    mimetypes.guess_type(os.path.basename(correct_path))[0],
                )
                resp: requests.Response = self.session.post(
                    url=url, data=params, files=files
                )
                resp.raise_for_status()
                res: dict[str, Any] = resp.json()
                if "success" in res and res["success"]:
                    itemid: str = res["item"]["itemID"]
                    upload_url: str = f"{self._url}/{itemid}"
                    return Upload(url=upload_url, session=self.session)
                else:
                    return res
        elif isinstance(path, (BytesIO, StringIO)):
            if hasattr(path, "seek"):
                path.seek(0)
            files["file"] = (
                file_name,
                path,
                mimetypes.guess_type(file_name)[0],
            )
            resp: requests.Response = self.session.post(
                url=url, data=params, files=files
            )
            resp.raise_for_status()
            res: dict[str, Any] = resp.json()
            if "success" in res and res["success"]:
                itemid: str = res["item"]["itemID"]
                upload_url: str = f"{self._url}/{itemid}"
                return Upload(url=upload_url, session=self.session)
            else:
                return res
        else:
            raise ValueError("Invalid path type.")
