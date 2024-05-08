from __future__ import annotations
import time
import logging
import requests
import concurrent.futures
from typing import Any
from arcgis.auth import EsriSession
from arcgis.auth.tools import LazyLoader

_arcgis = LazyLoader("arcgis")
_log = logging.getLogger()


###########################################################################
class PublishJob(object):
    """
    Represents a Single Publishing Job.  The `PublishJo` class allows for the
    asynchronous operation of the `publish` method. This class is not
    intended for users to initialize directly, but is returned by
    :meth:`~arcgis.gis._impl._content_manager.publish`.


    ================  ===============================================================
    **Parameter**      **Description**
    ----------------  ---------------------------------------------------------------
    session           Required EsriSession.  The connection object to use
    ----------------  ---------------------------------------------------------------
    payload           Required dict. The response JSON from the `publish` method.
    ----------------  ---------------------------------------------------------------
    status_url        Required str. The URL of the status endpoint.
    ----------------  ---------------------------------------------------------------
    job_id            Required str.  The unique identifier of the job to watch.
    ----------------  ---------------------------------------------------------------
    gis               Required GIS. The GIS object for the organization doing the work.
    ================  ===============================================================

    """

    _session: EsriSession
    _payload: dict
    _future: concurrent.futures.Future
    _url: str
    _job_id: str
    _serviceItemId: str

    # ----------------------------------------------------------------------
    def __init__(
        self,
        session: EsriSession,
        payload: dict[str, Any],
        status_url: str,
        job_id: str,
        gis: _arcgis.gis.GIS,
    ):
        """
        initializer
        """
        self._session: EsriSession = session
        self._payload: dict = payload
        self._url = status_url
        self._job_id = job_id
        self._gis: _arcgis.gis.GIS = gis
        if job_id is None and payload.get("type", "Map Service") != "Map Service":
            raise ValueError("job_id cannot be NULL")

    def _cache_status(self, manager) -> bool | dict:
        """
        Checks the cache status.
        """
        i: int = 1
        has_error: bool = False
        while True:
            res: list = []
            if i < 5:
                i += 1
            manager._properties = None
            manager._hydrated = False
            time.sleep(i * 1)
            for lod in manager.properties.get("lodInfos", []):
                if lod.get("status", "failed").lower() in [
                    "complete",
                    "completed",
                ]:
                    res.append(True)
                elif lod.get("status", "failed").lower() in [
                    "failed",
                    "failure",
                    "error",
                ]:
                    res.append(True)
                    has_error = True
                    _log.warning(
                        f"The caching process encountered an issue on LOD: {lod}"
                    )
                else:
                    res.append(False)  #  still processing/waiting
            if all(res):
                break
        if all(res) and has_error == False:
            return True
        else:
            _log.warning(
                f"The caching process encountered an issue. Please see the manager's properties to triage the issue."
            )
            return False

    def build_cache(
        self,
    ) -> concurrent.futures.Future:
        item = self.result()
        if isinstance(item, _arcgis.gis.Item):
            if "error" in self._payload:
                raise Exception(self._payload["error"])
            ms_url = item.url
            if ms_url.lower().find("mapserver") > -1:
                ms = _arcgis.mapping._types.MapImageLayer(url=ms_url, gis=self._gis)
                manager = ms.manager
            elif ms_url.lower().find("imageserver") > -1:
                ms = _arcgis.raster._layer.ImageryLayer(url=ms_url, gis=self._gis)
                manager = ms.cache_manager
                if not self._gis._is_arcgisonline:
                    return item

            try:
                # first edit the tile service to set min, max scales
                if not ms.properties.minScale:
                    min_scale = ms.properties.tileInfo.lods[0]["scale"]
                    max_scale = ms.properties.tileInfo.lods[-1]["scale"]
                else:
                    min_scale = ms.properties.minScale
                    max_scale = ms.properties.maxScale

                manager.edit_tile_service(min_scale=min_scale, max_scale=max_scale)

                # Get LoD from Map Image Layer
                full_extent = dict(ms.properties.fullExtent)
                lod_dict = ms.properties.tileInfo["lods"]
                lod = [
                    current_lod["level"]
                    for current_lod in lod_dict
                    if (min_scale <= current_lod["scale"] <= max_scale)
                ]
                manager.update_tiles(levels=lod, extent=full_extent)
                try:
                    tp: concurrent.futures.ThreadPoolExecutor = (
                        concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    )
                    job: concurrent.futures.Future = tp.submit(
                        self._cache_status,
                        **{
                            "manager": manager,
                        },
                    )
                    tp.shutdown(wait=True)
                    return job
                except Exception as ex:
                    raise Exception(str(ex))

            except:
                return item
        return item

    # ----------------------------------------------------------------------
    def __str__(self):
        return "<Publish Service Job>"

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def task(self):
        """Returns the task name.
        :return: string
        """
        return "Publish Service Job"

    # ----------------------------------------------------------------------
    def _status(self) -> dict[str, Any]:
        if self._payload.get("type", "Map Service") != "Map Service":
            params: dict = {
                "f": "json",
            }
            if self._job_id:
                params["jobId"] = self._job_id
            resp: requests.Response = self._session.get(url=self._url, params=params)
            resp.raise_for_status()
            return resp.json()
        else:
            return self._payload

    # ----------------------------------------------------------------------
    @property
    def messages(self):
        """
        returns the GP messages

        :return: List
        """
        return self._status().get("statusMessage", "Message Not Found.")

    # ----------------------------------------------------------------------
    @property
    def status(self):
        """
        returns the Job status

        :return: bool - True means running, False means finished
        """
        return self._status().get("status", "Unknown")

    # ----------------------------------------------------------------------
    def running(self):
        """
        Return True if the call is currently being executed and cannot be cancelled.

        :return: boolean
        """
        return not self.status in ["completed", "failed"]

    # ----------------------------------------------------------------------
    def done(self):
        """
        Return True if the call was successfully cancelled or finished running.

        :return: boolean
        """
        return self.status in ["completed", "failed"]

    # ----------------------------------------------------------------------
    def result(self):
        """
        Return the value returned by the call. If the call hasn't yet completed
        then this method will wait.

        :return: object
        """
        if self._payload.get("type", "Map Service") != "Map Service":
            i: int = 1
            while self.done() == False:
                time.sleep(i)
                if i < 10:
                    i += 1
            data: dict = self._status()
            if data.get("status", "null") in ["failed", "null"]:
                return data
            elif data.get("itemId", None):
                itemid: str = data.get("itemId", None)
                return self._gis.content.get(itemid)

            return data
        else:
            itemid: str = self._payload.get("serviceItemId", None)
            return self._gis.content.get(itemid)
