"""
The arcgis.network module contains classes and functions for network analysis. Network layers and analysis can be used
for operations such as finding the closest facility, the best route for a vehicle, the best routes for a fleet of
vehicles, locating facilities using location allocation, calculating an OD cost matrix, and generating service areas.
"""

from ._layer import (
    NetworkLayer,
    NetworkDataset,
    NetworkDatasetLayer,
    ClosestFacilityLayer,
    ServiceAreaLayer,
    RouteLayer,
    NAJob,
    ODCostMatrixLayer,
    LocateSettings,
    ToleranceUnits,
)
from ._utils import publish_routing_services, SolverType
from arcgis.auth.tools import LazyLoader

analysis = LazyLoader("arcgis.network.analysis")
