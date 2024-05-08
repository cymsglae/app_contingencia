from __future__ import annotations
from functools import lru_cache
from arcgis.auth.tools import LazyLoader

from ._pipelines import DataPipelines, PipelineRun, RunStatus

_arcgis_gis = LazyLoader("arcgis.gis")

__all__ = ["run_data_pipeline"]

_last_run_by_item_id: dict[str, PipelineRun] = {}


@lru_cache(maxsize=254)
def _get_arcgis_pipeline(
    gis: _arcgis_gis.GIS, version: float | int = 1.1
) -> DataPipelines:
    """gets the pipline from the GIS"""
    helper_service = gis.properties["helperServices"]

    if "dataPipelines" in helper_service:
        url: str = (
            f"{helper_service['dataPipelines']['url']}/api/v{version}/{gis.properties['id']}/"
        )
        return DataPipelines(url=url, gis=gis)
    return None


def run_data_pipeline(
    item: _arcgis_gis.Item, gis: _arcgis_gis.GIS | None = None
) -> PipelineRun:
    """
    Runs the data pipeline item. Running data pipelines consumes credits for the time it takes the run to complete.

    NOTE: This method is experimental. All parameters and return types are subject to change.

    =================================================     ========================================================================
    **Parameter**                                         **Description**
    -------------------------------------------------     ------------------------------------------------------------------------
    item                                                  Required Item. The `Data Pipeline` type item to run.
    -------------------------------------------------     ------------------------------------------------------------------------
    gis                                                   Optional GIS. The WebGIS connection class used to run the `run_data_pipeline`
                                                          operation.  If the value is `None`, then the item's GIS object will be
                                                          used.
    =================================================     ========================================================================

    :return: PipelineRun
    :raises: Exception if the user or organization does not have access to Data Pipelines, or if a run is already in progress for the item.
    """
    if gis is None:
        gis = item._gis

    pipeline: DataPipelines = _get_arcgis_pipeline(gis=gis)
    if pipeline is None:
        raise Exception(
            "Your organization or user account does not support Data Pipelines, please contact your Organization's administrator."
        )

    if item.id in _last_run_by_item_id and _last_run_by_item_id[item.id].status in [
        RunStatus.WAITING,
        RunStatus.SUBMITTED,
        RunStatus.RUNNING,
    ]:
        raise Exception("A run is already in progress for this item.")

    new_run = pipeline.runs.create(item=item)
    _last_run_by_item_id[item.id] = new_run
    return new_run
