from __future__ import annotations
import time
import logging
from typing import Any, Iterator
from arcgis.auth.tools import LazyLoader
from arcgis.auth import EsriSession
import requests
from ._enums import RunStatus
from cachetools import cached, TTLCache

_arcgis_gis = LazyLoader("arcgis.gis")

_log = logging.getLogger()


###########################################################################
class PipelineRun:
    """
    Represents a **single** run of a `Data Pipeline` process.

    NOTE: This class is experimental. All properties, methods, and responses are subject to change.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    url                 Required String. The `url` of the data pipeline endpoint.
    ---------------     --------------------------------------------------------------------
    session             Required EsriSession. The connection object.
    ===============     ====================================================================


    """

    url: str
    session: EsriSession
    _properties: dict[str, Any] | None = None
    _result: dict[str, Any] | None = None

    # ---------------------------------------------------------------------
    def __init__(self, url: str, session: EsriSession) -> None:
        """initializer"""
        self.url: str = url
        self.session: EsriSession = session

    # ---------------------------------------------------------------------
    @property
    def properties(self) -> dict[str, Any]:
        """
        Returns the properties of the run


        :returns: dict[str,Any]
        """
        if self._properties is None:
            resp: requests.Response = self.session.get(
                url=self.url,
                params={
                    "f": "json",
                },
            )
            resp.raise_for_status()
            res: dict[str, Any] = resp.json()
            self._properties = res

        return self._parse_properties(self._properties)

    # ---------------------------------------------------------------------
    def result(self) -> dict[str, Any]:
        """
        Gets the run results. This operation will pause the thread when called
        until the data pipeline run finishes.

        :returns: dict[str,Any]
        """
        if self._result is not None:
            return self._parse_result(self._result)

        i: int = 1
        status: RunStatus = self.status
        while isinstance(status, RunStatus) and status in [
            RunStatus.WAITING,
            RunStatus.SUBMITTED,
            RunStatus.CANCELLING,
            RunStatus.RUNNING,
        ]:
            _log.warning(
                f"Waiting for the run to complete. Current status: `{self.status.value}`."
            )
            time.sleep(i * 2)
            if i <= 5:
                i += 1
            status: RunStatus = self.status
        url: str = f"{self.url}/result"
        params: dict[str, Any] = {"f": "json"}
        resp: requests.Response = self.session.get(url=url, params=params)
        resp.raise_for_status()

        self._result = resp.json()
        return self._parse_result(self._result)

    # ---------------------------------------------------------------------
    def cancel(self) -> bool:
        """
        Terminates the current run.

        :returns:bool
        """
        url: str = f"{self.url}/cancel"
        params: dict[str, Any] = {
            "f": "json",
        }
        resp: requests.Response = self.session.post(url=url, data=params)
        if resp.status_code == 412:
            return False  # The run already completed
        resp.raise_for_status()
        return True

    # ---------------------------------------------------------------------
    @property
    @cached(cache=TTLCache(maxsize=1024, ttl=5))
    def status(self) -> RunStatus | dict[str, Any]:
        """
        Checks the Job's status

        :returns: RunStatus | dict[str, Any]

        """
        url: str = f"{self.url}/status"
        params: dict[str, Any] = {"f": "json"}
        resp: requests.Response = self.session.get(url=url, params=params)
        resp.raise_for_status()
        res: dict[str, Any] = resp.json()
        if "status" in res:
            return RunStatus(res.get("status"))
        elif "error" in res:
            return RunStatus.FAILED
        return resp.json()

    # ---------------------------------------------------------------------
    def _parse_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Parses the Data Pipeline run properties."""
        keep_properties = {
            "id",
            "itemId",
            "status",
            "createdAt",
            "runningAt",
            "terminatedAt",
            "startedAt",
            "endedAt",
        }
        return {k: v for k, v in properties.items() if k in keep_properties}

    def _parse_result(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parses the Data Pipeline result object."""
        parsed = {
            "id": response.get("id", None),
            "status": response.get("status", None),
        }

        if "failure" in response:
            parsed["failure"] = self._parse_failure(response["failure"])
        if "results" in response:
            outputs = response["results"].get("outputs", None)
            if isinstance(outputs, list):
                parsed["outputs"] = [{"itemId": o.get("itemId", None)} for o in outputs]
            else:
                # Unknown results, return the whole object
                parsed["results"] = response["results"]

        parsed["messages"] = [
            self._parse_message(m) for m in response.get("messages", [])
        ]

        return parsed

    def _parse_failure(self, failure: dict[str, Any]) -> dict[str, Any]:
        """Parses a failure message into a dictionary."""
        parsed = self._parse_message(failure)
        parsed["details"] = failure.get("details", [])
        parsed["detailProperties"] = [
            self._parse_message(d) for d in failure.get("detailProperties", [])
        ]
        return parsed

    def _parse_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Parses a message into (Node ID, Parameter Path) properties."""
        # Note, the REST API properties may change. This implementation uses fallbacks
        # and is generally defensive to try and maintain forwards compatibility.
        parsed = {
            "message": message.get("message", None),
            "messageCode": message.get("messageCode", None),
            "type": message.get("type", None) or message.get("level", None),
        }

        # Parse the message `nodeId` and `parameter`
        if "nodeId" in message:
            parsed["nodeId"] = message["nodeId"]
            parsed["parameter"] = message.get("parameter", None)
            parsed["path"] = message.get("path", None)
        elif "path" in message:
            node_id, parameter, path = self._parse_message_path(message["path"])
            parsed["nodeId"] = node_id
            parsed["parameter"] = parameter
            parsed["path"] = path

        return {k: v for k, v in parsed.items() if v is not None}

    def _parse_message_path(
        self, path: str
    ) -> tuple[str | None, str | None, str | None]:
        """Parses a message path into (Node ID, Parameter Path) properties."""
        # If the message path starts with a pipeline property, then the message is for the
        # data pipeline itself, not a specific node.
        pipeline_properties = {"inputs", "tools", "outputs", "version", "meta"}

        segments = path.split(".")
        root_parameter = segments[0].split("[")[0]
        if root_parameter in pipeline_properties:
            node_id = None
            parameter = None
            pipeline_path = path
        else:
            node_id = segments[0]
            parameter = ".".join(segments[1:])
            pipeline_path = None

        return (node_id, parameter or None, pipeline_path or None)


###########################################################################
class PipelineRuns:
    """
    Manager class used to work with data pipeline runs.

    NOTE: This class is experimental. All properties, methods, and responses are subject to change.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    url                 Required String. The `url` of the data pipeline endpoint.
    ---------------     --------------------------------------------------------------------
    session             Required EsriSession. The connection object.
    ===============     ====================================================================

    """

    session: EsriSession
    url: str

    # ---------------------------------------------------------------------
    def __init__(self, url: str, session: EsriSession) -> None:
        """initializer"""
        self.url: str = url
        self.session: EsriSession = session

    # ---------------------------------------------------------------------
    def create(self, item: _arcgis_gis.Item) -> PipelineRun:
        """
        Creates a new `Run` of a data pipeline

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        item                Required Item. The `Data Pipeline` type item to run.
        ===============     ====================================================================

        :returns: `PipelineRun`

        """
        if item.type != "Data Pipeline":
            raise ValueError("The `item` must be a `Data Pipeline` item.")
        url: str = f"{self.url}"
        params: dict[str, Any] = {"f": "json", "itemId": item.id}
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data.get("id", None):
            run_url: str = f"{self.url}/{data.get('id')}"
            return PipelineRun(url=run_url, session=self.session)
        return data

    # ---------------------------------------------------------------------
    def query(self, item: _arcgis_gis.Item) -> Iterator[PipelineRun]:
        """
        Returns all the `PipelineRun` objects on a given Data Pipeline item.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        item                Required Item. The `Data Pipeline` type item to run.
        ===============     ====================================================================

        :returns: Iterator[PipelineRun]
        """
        if item.type != "Data Pipeline":
            raise ValueError("The `item` must be a `Data Pipeline` item.")
        url: str = f"{self.url}"
        params: dict[str, Any] = {"f": "json", "itemId": item.id}
        resp: requests.Response = self.session.get(url=url, params=params)
        resp.raise_for_status()
        has_more: str = resp.headers.get("X-Esri-Continuation", None)

        for run in resp.json().get("results", []):
            task_id: str = run.get("id", None)
            if task_id:
                run_url: str = f"{self.url}/{task_id}"
                yield PipelineRun(url=run_url, session=self.session)
        while has_more:
            resp: requests.Response = self.session.get(
                url=url,
                data=params,
                headers={"X-Esri-Continuation": has_more},
            )
            resp.raise_for_status()
            has_more: str = resp.headers.get("X-Esri-Continuation", None)
            data: dict[str, Any] = resp.json()
            for run in data.get("results", []):
                task_id: str = run.get("id", None)
                if task_id:
                    run_url: str = f"{self.url}/{task_id}"
                    yield PipelineRun(url=run_url, session=self.session)
            if len(data.get("results", [])) == 0:
                break


###########################################################################
class DataPipelines:
    """
    The Python API for the ArcGIS Data Pipeline.

    NOTE: This class is experimental. All properties, methods, and responses are subject to change.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    url                 Required String. The `url` of the data pipeline endpoint.
    ---------------     --------------------------------------------------------------------
    gis                 Required GIS. The `GIS` object that represents the current organization.
    ===============     ====================================================================

    """

    _gis: _arcgis_gis.GIS
    url: str
    session: EsriSession | None = None
    _runs: PipelineRuns | None = None

    def __init__(self, url: str, gis: _arcgis_gis.GIS):
        """initializer"""
        self.url = url
        self._gis = gis
        self.session = self._gis.session

    # ---------------------------------------------------------------------
    @property
    def runs(self) -> PipelineRuns:
        """
        Returns the `Runs` manager

        :returns: PipelineRuns
        """
        if self._runs is None:
            url: str = f"{self.url}runs"
            self._runs = PipelineRuns(url=url, session=self.session)
        return self._runs
