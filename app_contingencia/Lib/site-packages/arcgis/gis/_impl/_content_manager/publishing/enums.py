from __future__ import annotations
from enum import Enum

__all__ = ["PublishFileTypes", "PublishOutputTypes"]


###########################################################################
class PublishOutputTypes(Enum):
    TILES: str = "tiles"
    VECTOR_TILES: str = "vectorTiles"
    WFS: str = "WFS"
    SCENE_SERVICE: str = "sceneService"
    NONE: str = ""


###########################################################################
class PublishFileTypes(Enum):
    """
    The available file types to publish as services
    """

    COMPACT_TILE_PACKAGE: str = "compactTilePackage"
    CSV: str = "csv"  #
    EXCEL: str = "excel"  #
    FEATURE_SERVICE: str = "featureService"  #
    FEATURE_COLLECTION: str = "featureCollection"  #
    FILE_GEODATABASE: str = "fileGeodatabase"  #
    GEOJSON: str = "geojson"  #
    GEOPACKAGE: str = "geoPackage"
    IMAGE_COLLECTION: str = "imageCollection"
    MAP_SERVICE: str = "mapService"
    SCENE_PACKAGE: str = "scenepackage"  #
    SERVICE_DEFINITION: str = "serviceDefinition"  #
    SQLITE_GEODATABASE: str = "sqliteGeodatabase"
    SHAPEFILE: str = "shapefile"  #
    TILE_PACKAGE: str = "tilePackage"  #
    TILES_3D_PACKAGE: str = "3DTilesPackage"
    VECTOR_TILE_PACKAGE: str = "vectorTilePackage"  #
