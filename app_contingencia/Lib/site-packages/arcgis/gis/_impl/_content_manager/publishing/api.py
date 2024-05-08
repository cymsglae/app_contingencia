from __future__ import annotations

import os
import json
import mimetypes
from functools import lru_cache
from typing import Any
import requests
from arcgis.auth import EsriSession
from arcgis.auth.tools import LazyLoader
from .enums import PublishFileTypes, PublishOutputTypes
from ._job import PublishJob

_arcgis = LazyLoader("arcgis")

__all__ = ["PublishFileTypes", "publish", "PublishJob", "PublishOutputTypes"]


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _guess_mimetype(extension: str) -> str:
    """guesses the mimetype for an extension"""
    return mimetypes.guess_type(f"t{extension}")[0]


# -------------------------------------------------------------------------
@lru_cache(maxsize=255)
def _file_type_look_up(item: _arcgis.gis.Item) -> str:
    """
    looks up the file type from the Item type.
    """
    fileType: str | None = None
    item_type = item.get("type", None)
    if item_type is None:
        raise ValueError("Invalid Item.  Type is missing.")
    if item_type == "GeoPackage":
        fileType = PublishFileTypes.GEOPACKAGE
    elif item_type.lower().find("excel") > -1:
        fileType = PublishFileTypes.EXCEL
    elif item_type == "Compact Tile Package":
        fileType = PublishFileTypes.COMPACT_TILE_PACKAGE
    elif item_type == "Service Definition":
        fileType = PublishFileTypes.SERVICE_DEFINITION
    elif item_type == "Microsoft Excel":
        fileType = PublishFileTypes.EXCEL
    elif item_type == "Feature Collection":
        fileType = PublishFileTypes.FEATURE_COLLECTION
    elif item_type == "CSV":
        fileType = PublishFileTypes.CSV
    elif item_type == "Shapefile":
        fileType = PublishFileTypes.SHAPEFILE
    elif item_type == "File Geodatabase":
        fileType = PublishFileTypes.FILE_GEODATABASE
    elif item_type == "Vector Tile Package":
        fileType = PublishFileTypes.VECTOR_TILE_PACKAGE
    elif item_type == "Scene Package":
        fileType = PublishFileTypes.SCENE_PACKAGE
    elif item_type == "Tile Package":
        fileType = PublishFileTypes.TILE_PACKAGE
    elif item_type == "SQLite Geodatabase":
        fileType = PublishFileTypes.SQLITE_GEODATABASE
    elif item_type in ["GeoJson", "geojson"]:
        fileType = PublishFileTypes.GEOJSON
    elif item_type == "Feature Service" and "Spatiotemporal" in item.get(
        "typeKeywords", []
    ):
        fileType = PublishFileTypes.FEATURE_SERVICE
    else:
        raise ValueError("A file_type must be provide, data format not recognized")
    return fileType


# ----------------------------------------------------------------------
def _analyze(
    gis: _arcgis.gis.GIS,
    url: str | None = None,
    item: str | _arcgis.gis.Item | None = None,
    file_path: str | None = None,
    text: str | None = None,
    file_type: str | None = None,
    source_locale: str = "en",
    geocoding_service: str | None = None,
    location_type: str | None = None,
    source_country: str = "world",
    country_hint: str | None = None,
    enable_global_geocoding: bool | None = None,
) -> dict[str, Any]:
    """
    The ``analyze`` method helps a client analyze a CSV or Excel file (.xlsx, .xls) prior to publishing or
    generating features using the Publish or Generate operation, respectively.

    ``analyze`` returns information about the file including the fields present as well as sample records.
    ``analyze`` attempts to detect the presence of location fields that may be present as either X,Y fields or
    address fields.

    ``analyze`` packages its result so that publishParameters within the JSON response contains information that
    can be passed back to the server in a subsequent call to Publish or Generate. The publishParameters subobject
    contains properties that describe the resulting layer after publishing, including its fields, the desired
    renderer, and so on. ``analyze`` will suggest defaults for the renderer.

    In a typical workflow, the client will present portions of the ``analyze`` results to the user for editing
    before making the call to :attr:`~arcgis.gis.ContentManager.generate` or ``publish``.

    .. note::
        The maximum upload size for shapefiles is now 2 Mb and 10 Mb for all other supported file types.

    .. note::
        If the file to be analyzed currently exists in the portal as an item, callers can pass in its itemId.
        Callers can also directly post the file.
        In this case, the request must be a multipart post request pursuant to IETF RFC1867.
        The third option for text files is to pass the text in as the value of the text parameter.

    =======================    =============================================================
    **Parameter**               **Description**
    -----------------------    -------------------------------------------------------------
    url                        Optional string. The URL of the csv file.
    -----------------------    -------------------------------------------------------------
    item                       Optional string/:class:`~arcgis.gis.Item` . The ID or Item of the item to be
                               analyzed.
    -----------------------    -------------------------------------------------------------
    file_path                  Optional string. The file to be analyzed.
    -----------------------    -------------------------------------------------------------
    text                       Optional string. The text in the file to be analyzed.
    -----------------------    -------------------------------------------------------------
    file_type                  Optional string. The type of the input file: shapefile, csv, excel,
                               or geoPackage (Added ArcGIS API for Python 1.8.3+).
    -----------------------    -------------------------------------------------------------
    source_locale              Optional string. The locale used for the geocoding service source.
    -----------------------    -------------------------------------------------------------
    geocoding_service          Optional string/geocoder. The URL of the service.
    -----------------------    -------------------------------------------------------------
    location_type              Optional string. Indicates the type of spatial information stored in the dataset.

                               Values for CSV: coordinates | address | lookup | none
                               Values for Excel: coordinates | address | none
    -----------------------    -------------------------------------------------------------
    source_country             Optional string. The two character country code associated with the geocoding service, default is "world".
    -----------------------    -------------------------------------------------------------
    country_hint               Optional string. If first time analyzing, the hint is used. If source country is already specified than sourcecountry is used.
    -----------------------    -------------------------------------------------------------
    enable_global_geocoding    Optional boolean. Default is None. When True, the global geocoder is used.
    =======================    =============================================================

    :return: dictionary

    .. code-block:: python

        # Usage Example

        >>> gis.content.analyze(item = "9311d21a9a2047d19c0faaebd6f2cca6", file_type = "csv")

    """
    surl: str = (
        f"{gis.url.replace('/sharing/rest/', '')}/sharing/rest/content/features/analyze"
    )
    params: dict[str, Any] = {"f": "json", "analyzeParameters": {}}
    files: dict[str, str] = None
    if not (text or file_path or item or url):
        return Exception("Must provide an itemid, file_path or text to analyze data.")
    if item:
        if isinstance(item, str):
            params["itemid"] = item
        elif isinstance(item, _arcgis.gis.Item):
            params["itemid"] = item.itemid

    elif text:
        params["text"] = text
    elif url:
        params["sourceUrl"] = url

    params["analyzeParameters"]["sourcelocale"] = source_locale
    if geocoding_service:
        if hasattr(geocoding_service, "url"):
            params["analyzeParameters"]["geocodeServiceUrl"] = getattr(
                geocoding_service, "url"
            )
        else:
            params["analyzeParameters"]["geocodeServiceUrl"] = geocoding_service
    if location_type:
        params["analyzeParameters"]["locationType"] = location_type

    if file_type is None and (url or file_path):
        d = url or file_path
        if d:
            if str(d).lower().endswith(".csv"):
                params["fileType"] = "csv"
            elif str(d).lower().endswith(".xls") or str(d).lower().endswith(".xlsx"):
                params["fileType"] = "excel"
            elif str(d).lower().endswith("gpkg"):
                params["fileType"] = "geoPackage"

    elif str(file_type).lower() in ["excel", "csv"]:
        params["fileType"] = file_type
    elif str(file_type).lower() in ["filegeodatabase", "shapefile"]:
        params["fileType"] = file_type
        params["analyzeParameters"]["enableGlobalGeocoding"] = False
    if source_country:
        params["analyzeParameters"]["sourceCountry"] = source_country
    if country_hint:
        params["analyzeParameters"]["sourcecountryhint"] = country_hint
    if enable_global_geocoding in [True, False]:
        params["analyzeParameters"]["enableGlobalGeocoding"] = enable_global_geocoding
    params["analyzeParameters"] = json.dumps(params["analyzeParameters"])
    if file_path and os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            files: dict[str, Any] = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    _guess_mimetype(os.path.splitext(file_path)[1]),
                )
            }

            resp: requests.Response = gis.session.post(surl, data=params, files=files)
    else:
        resp: requests.Response = gis.session.post(surl, data=params, files=files)
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------------------------
def publish(
    item: _arcgis.gis.Item,
    publish_parameters: dict[str, Any] | None = None,
    file_type: PublishFileTypes | None = None,
    output_type: PublishOutputTypes = PublishOutputTypes.NONE,
    delete_source: bool = False,
    item_id_to_create: str | None = None,
    owner: str | None = None,
    folder: str | None = None,
    build_initial_cache: bool = False,
) -> PublishJob | dict[str, Any]:
    """
    Publishes an Item
    """
    if owner:
        url: str = f"{item._gis.resturl}content/users/{owner}/publish"
    else:
        owner = item.owner
        url: str = f"{item._gis.resturl}content/users/{owner}/publish"
    if file_type is None:
        file_type = _file_type_look_up(item=item)
    if file_type == PublishFileTypes.VECTOR_TILE_PACKAGE and [
        PublishOutputTypes.NONE,
        None,
    ]:
        output_type = PublishOutputTypes.VECTOR_TILES
        build_initial_cache = True
    elif file_type == PublishFileTypes.SCENE_PACKAGE and [
        PublishOutputTypes.NONE,
        None,
    ]:
        output_type = PublishOutputTypes.SCENE_SERVICE
        build_initial_cache = True
    elif file_type in [
        PublishFileTypes.TILE_PACKAGE,
        PublishFileTypes.TILES_3D_PACKAGE,
        PublishFileTypes.COMPACT_TILE_PACKAGE,
    ] and output_type in [PublishOutputTypes.NONE, None]:
        output_type = PublishOutputTypes.TILES
        build_initial_cache = True
    if file_type and isinstance(file_type, PublishFileTypes) == False:
        raise ValueError("`file_type` must be of type PublishFileTypes")
    if (
        publish_parameters is None
        and file_type
        in [
            PublishFileTypes.CSV,
            PublishFileTypes.EXCEL,
            PublishFileTypes.GEOPACKAGE,
            PublishFileTypes.SHAPEFILE,
            PublishFileTypes.FILE_GEODATABASE,
        ]
        and item._gis._is_arcgisonline
    ):
        publish_parameters = _analyze(
            gis=item._gis, item=item, file_type=file_type.value
        ).get("publishParameters")
        publish_parameters["name"] = item.title.strip().replace(" ", "_")
    elif (
        publish_parameters is None and file_type == PublishFileTypes.VECTOR_TILE_PACKAGE
    ):
        publish_parameters = {
            "name": item.title.strip().replace(" ", "_"),
            "maxRecordCount": 2000,
        }
    elif (
        publish_parameters is None
        and file_type
        in [
            PublishFileTypes.CSV,
            PublishFileTypes.EXCEL,
            PublishFileTypes.SHAPEFILE,
        ]
        and item._gis._is_arcgisonline == False
    ):
        publish_parameters = _analyze(
            gis=item._gis, item=item, file_type=file_type.value
        ).get("publishParameters")
        publish_parameters["name"] = item.title.strip().replace(" ", "_")
    elif (
        item._gis._is_arcgisonline == False
        and publish_parameters is None
        and file_type == PublishFileTypes.FILE_GEODATABASE
    ):
        publish_parameters = {
            "name": item.title.replace(" ", "_"),
            "maxRecordCount": 2000,
            "hasStaticData": True,
            "layerInfo": {"capabilities": "Query"},
        }
    elif (
        item._gis._is_arcgisonline == False
        and publish_parameters is None
        and file_type == PublishFileTypes.GEOPACKAGE
    ):
        publish_parameters = {
            "name": item.title.replace(" ", "_"),
            "maxRecordCount": 2000,
        }

    elif publish_parameters is None and file_type in [
        PublishFileTypes.SERVICE_DEFINITION
    ]:
        publish_parameters = None
    elif publish_parameters:
        ...
    else:
        raise ValueError(f"Publish Parameters are required for type: {file_type.value}")
    if output_type and isinstance(output_type, PublishOutputTypes):
        output_type = output_type.value
    if publish_parameters:
        publish_parameters = json.dumps(publish_parameters)
    params: dict[str, Any] = {
        "f": "json",
        "itemID": item.id,
        "fileType": file_type.value.lower(),
        "publishParameters": publish_parameters,
        "outputType": output_type,
        "deleteSourceItemUponCompletion": json.dumps(delete_source),
        "itemIdToCreate": item_id_to_create or "",
    }
    if build_initial_cache:
        params["buildInitialCache"] = json.dumps(build_initial_cache)
    params = {k: v for k, v in params.items() if v}
    session: EsriSession = item._gis.session
    resp: requests.Response = session.post(url=url, data=params)
    data: dict[str, Any] = resp.json()
    if "error" in data:
        return data
    elif "services" in data:
        publish_payload: dict = data["services"][0]
        item_id: str = publish_payload.get("serviceItemId")
        job_id: str = publish_payload.get("jobId", None)

        if folder:
            status_url: str = (
                f"{item._gis.resturl}content/users/{owner}/{folder}/items/{item_id}/status"
            )
        else:
            status_url: str = (
                f"{item._gis.resturl}content/users/{owner}/items/{item_id}/status"
            )

            return PublishJob(
                session=session,
                payload=publish_payload,
                status_url=status_url,
                job_id=job_id,
                gis=item._gis,
            )
    return data
