from __future__ import annotations
import os
import json
import logging
from enum import Enum
from typing import Any
import requests
from functools import lru_cache
from arcgis.auth.tools import LazyLoader
from arcgis import network
from arcgis._impl.common._utils import _validate_url
from arcgis.geoprocessing import (
    import_toolbox as _import_toolbox,
)

from ..geoprocessing._uploads import Uploads

_log = logging.getLogger()
_arcgis_gis = LazyLoader("arcgis.gis")
_arcgis = LazyLoader("arcgis")
_gp = LazyLoader("arcgis.geoprocessing")
__all__ = [
    "SolverType",
    "publish_routing_services",
    "find_travel_mode",
    "default_travel_mode",
]


class SolverType(Enum):
    CLOSESTFACILITY: str = "ClosestFacility"
    LOCATIONALLOCATION: str = "Location-Allocation"
    ORIGINDESTINATIONCOSTMATRIX: str = "OriginDestinationCostMatrix"
    ROUTE: str = "Route"
    SERVICEAREA: str = "ServiceArea"
    VEHICLEROUTINGPROBLEM: str = "VehicleRoutingProblem"
    ALL: list = [
        "ClosestFacility",
        "Location-Allocation",
        "OriginDestinationCostMatrix",
        "Route",
        "ServiceArea",
        "VehicleRoutingProblem",
    ]


@lru_cache(maxsize=255)
def _get_network_publishing_url(gis: _arcgis_gis.GIS, server_id: str) -> str:
    """gets the network system publishing url"""
    params = {"f": "json"}
    if gis._is_arcgisonline == False:
        url = f"{gis.resturl}portals/self/servers"
    else:
        url = f"{gis.resturl}portals/self/urls"
    resp: requests.Response = gis.session.get(url=url, params=params)
    resp.raise_for_status()
    data: dict = resp.json()
    hosting_server_urls: list[str] = []
    for server in data.get("servers", []):
        if server_id == server.get("id", None):
            return server.get("url") + "/rest/services/System/PublishingTools/GPServer"
        elif server.get("serverRole", "NOPE") == "HOSTING_SERVER":
            hosting_server_urls.append(
                server.get("url") + "/rest/services/System/PublishingTools/GPServer"
            )
    if hosting_server_urls:
        return hosting_server_urls[0]
    else:
        raise Exception("The enterprise does not have a valid hosting server.")


@lru_cache(maxsize=255)
def _get_network_publishing_toolbox(gis: _arcgis_gis.GIS, server_id: str | None = None):
    """gets the network system publishing tool"""
    service: str = _get_network_publishing_url(gis=gis, server_id=server_id)

    return _import_toolbox(
        url_or_item=service,
        gis=gis,
    )


# -------------------------------------------------------------------------
def publish_routing_services(
    datastore: _arcgis_gis.Item,
    path: str,
    server_id: str | None = None,
    folder: str | None = None,
    solver_types: list[SolverType] | SolverType = SolverType.ALL,
    config: str = None,
    gis: _arcgis_gis.GIS | None = None,
) -> _arcgis.geoprocessing._job.GPJob:
    """
    ======================================  ==========================================================================================================================================
    **Parameter**                            **Description**
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    datastore                               Required Item. The registered datastore where the network dataset resides.
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    path                                    Required String. The relative path to the network dataset in the data store.
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    server_id                               Required String. The unique ID of the server to publish the dataset to.
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    folder                                  Optional String. The name for the server folder that will contain all the routing services created by this service. The service returns
                                            an error if the folder contains existing services. The default value is `Routing`
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    solver_types                            Optional :class:`~arcgis.network.SolverType`. The list of Network Analyst solvers
                                            to be included in the services. The default is to include all the solvers.
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    config                                  Optional str. The file containing additional configuration for the services. If no value is specified, the system default configuration
                                            file is used.  For a full list of config values and explanation, please reach out to support@esri.com.
    --------------------------------------  ------------------------------------------------------------------------------------------------------------------------------------------
    gis                                     Optional GIS. The GIS object where the dataset will be hosted at.  If `None` is provided, the datastore's GIS will be used.
    ======================================  ==========================================================================================================================================

    .. code-block:: python

        # Usage Example
        >>> job = publish_routing_services(datastore=gis.content.get("05cb079948f241a799651b3ac0401309"),
                                           path="/streets/NorthAmerica.gdb/Routing/Routing_ND",
                                           config=config_file,
                                           solver_types=[SolverType.ROUTE, SolverType.VEHICLEROUTINGPROBLEM],
                                           server_id=gis.servers['servers'][0]['id'])
        >>> type(job)

        <:class:`~arcgis.geoprocessing._job.GPJob>


    :returns:
        :class:`~arcgis.geoprocessing.GPJob`
    """

    if gis is None:
        gis = datastore._gis
    if gis._is_arcgisonline:
        return None

    network_dataset: dict[str, Any] = {
        "datastoreId": datastore.id,
        "path": path,
    }
    folder = folder or "Routing"
    sts: list = []
    if isinstance(solver_types, list):
        for st in solver_types:
            if isinstance(st, str):
                sts.append(st)
            elif isinstance(st, SolverType):
                sts.append(st.value)
    elif isinstance(solver_types, SolverType):
        if isinstance(solver_types.value, list):
            sts.extend(solver_types.value)
        else:
            sts.append(solver_types.value)
    elif isinstance(solver_types, str):
        sts = ""
    else:
        raise ValueError("Invalid solver_types, please verify the parameter.")
    solver_types: str = json.dumps(list(sts))

    toolbox = _get_network_publishing_toolbox(gis=gis, server_id=server_id)
    if config and os.path.isfile(config) and gis._is_kubernetes:
        um = gis.admin.uploads
        status, data = um.upload(config)
        if status:
            config: dict = {"itemID": data["item"]["itemID"]}
        else:
            config = ""
    elif config and os.path.isfile(config):
        base_url: str = _get_network_publishing_url(gis=gis, server_id=server_id)
        uploads = Uploads(url=f"{base_url}/uploads", gis=gis)
        upload = uploads.upload(config)
        config: dict = {"itemID": upload.properties["itemID"]}
    else:
        config = ""

    job = toolbox.publish_routing_services(
        network_dataset=network_dataset,
        service_folder=folder,
        solver_types=solver_types,
        config_file=config,
        gis=gis,
        future=True,
    )

    return job


# -------------------------------------------------------------------------
def _gp_travel_mode(gis: _arcgis_gis.GIS, travel_mode: str = None) -> str:
    """Calculates the travel mode via the GP Service"""
    output = network.analysis.get_travel_modes(gis=gis)
    if travel_mode is None:
        _log.warning("Travel mode not set, using default travel mode")
        travel_mode = output.default_travel_mode
    matches = [
        feature.attributes["TravelMode"]
        for feature in output.supported_travel_modes.features
        if (
            feature.attributes["TravelModeId"].lower() == travel_mode.lower()
            or feature.attributes["AltName"].lower() == travel_mode.lower()
            or feature.attributes["Name"].lower() == travel_mode.lower()
        )
    ]

    if len(matches) > 0:
        try:
            return json.loads(matches[0])
        except:
            return matches[0]
    else:
        _log.warning(
            f"Cannot find {travel_mode}, using default: {output.default_travel_mode}."
        )
        matches = [
            feature.attributes["TravelMode"]
            for feature in output.supported_travel_modes.features
            if (
                feature.attributes["TravelModeId"].lower()
                == output.default_travel_mode.lower()
                or feature.attributes["AltName"].lower()
                == output.default_travel_mode.lower()
                or feature.attributes["Name"].lower()
                == output.default_travel_mode.lower()
            )
        ]
        return matches[0]


# -------------------------------------------------------------------------
def _route_service_travel_modes(gis, travel_mode: str = None) -> str:
    """gets the default values from the routing service"""
    url = _validate_url(gis.properties.helperServices.route.url, gis)
    route_service = network.RouteLayer(url, gis=gis)
    modes = route_service.retrieve_travel_modes()
    if travel_mode is None:
        travel_mode = modes["defaultTravelMode"]
    fn = lambda tm: travel_mode.lower() in [
        tm["id"].lower(),
        tm["name"].lower(),
    ]
    res = list(filter(fn, modes["supportedTravelModes"]))
    if len(res) > 0:
        return json.dumps(res[0])
    else:
        travel_mode = modes["defaultTravelMode"]
        res = list(filter(fn, modes["supportedTravelModes"]))
        return json.dumps(res[0])


# -------------------------------------------------------------------------
@lru_cache(maxsize=10)
def find_travel_mode(gis: _arcgis_gis.GIS, travel_mode: str = None) -> str:
    """Gets and Validate the Travel Mode for the Network Analyst Tools"""
    try:
        return _gp_travel_mode(gis, travel_mode)
    except:
        return _route_service_travel_modes(gis, travel_mode)


# -------------------------------------------------------------------------
@lru_cache(maxsize=10)
def default_travel_mode(gis: _arcgis_gis.GIS) -> str:
    """Gets the default travel mode for the GIS"""
    try:
        output = network.analysis.get_travel_modes(gis=gis)
        return output.default_travel_mode
    except:
        url = _validate_url(gis.properties.helperServices.route.url, gis)
        route_service = network.RouteLayer(url, gis=gis)
        modes = route_service.retrieve_travel_modes()
        return modes["defaultTravelMode"]
