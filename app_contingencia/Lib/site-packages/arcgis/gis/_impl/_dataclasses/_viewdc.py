from __future__ import annotations
import os
import json
from arcgis.auth.tools._lazy import LazyLoader
from dataclasses import dataclass, field
from enum import Enum
from arcgis.gis._impl._dataclasses._sfilters import SpatialFilter
from dataclasses import asdict


def _custom_asdict_factory(data):
    def convert_value(obj):
        if isinstance(obj, Enum):
            return obj.value
        return obj

    return dict(
        (k, convert_value(v)) for k, v in data if not k in ["_dict_data", "layer"]
    )


arcgis = LazyLoader("arcgis")

__all__ = [
    "JoinType",
    "StatisticType",
    "PrimaryTableView",
    "RelatedTable",
    "SourceLayerField",
    "ViewLayerDefParameter",
]


###########################################################################
class JoinType(Enum):
    INNER: str = "INNER"
    LEFT: str = "LEFT"
    RIGHT: str = "RIGHT"
    FULL: str = "FULL"


###########################################################################
class StatisticType(Enum):
    """
    The statistic/aggregation function to be applied on the field.
    """

    SUM: str = "SUM"
    AVG: str = "AVG"
    MIN: str = "MIN"
    MAX: str = "MAX"
    STDDEV: str = "STDDEV"


###########################################################################
@dataclass
class SourceLayerField:
    """
    The `SourceLayerField` property defines how view fields reference fields
    from the source layer. It can reference a source field directly, create
    a statistic from it, or can be defined as an expression that uses the
    source layer fields.

    ==================  ===============================================================================
    **Parameter**        **Description**
    ------------------  -------------------------------------------------------------------------------
    name                Required String. The field name in the new view. The name of the field can be different from the source field name.
    ------------------  -------------------------------------------------------------------------------
    alias               Optional String. The field alias in the new view.
    ------------------  -------------------------------------------------------------------------------
    source              Optional String. The source layer field name that is referenced directly or utilized inside the statistic operation.
    ------------------  -------------------------------------------------------------------------------
    statistic_type      Optional StatisticType. The statistic/aggregation function to be applied on the field.
    ==================  ===============================================================================
    """

    name: str
    alias: str | None = None
    source: str | None = None
    statistic_type: StatisticType | None = None
    field_type: str | None = None
    _dict_data: dict | None = field(init=False)

    def __str__(self) -> str:
        return "<SourceLayerField>"

    def __repr__(self) -> str:
        return "<SourceLayerField>"

    def __post_init__(self):
        self._dict_data = self._create_dict()

    def to_json(self) -> str:
        return json.dumps(asdict(self, dict_factory=_custom_asdict_factory))

    def _create_dict(self) -> dict:
        data = {
            "name": self.name,
        }
        if self.alias:
            data["alias"] = self.alias
        if self.source:
            data["source"] = self.source
        if self.statistic_type:
            data["statisticType"] = self.statistic_type.value
        if self.field_type:
            data["type"] = self.field_type

        self._dict_data = data
        return data


###########################################################################
@dataclass
class RelatedTable:
    """
    Related tables define the tables joined to the primary table. Related
    tables are the same in the way they define fields, but differ insofar
    as they contain join information. Related table objects should be
    listed in the relatedTables property of the table.
    """

    name: str
    source_service_name: str
    join_type: JoinType
    parent_key_fields: list[str]
    key_fields: list[str]
    source_layer_id: int | None = None
    filter: str | None = None
    top_filter: str | None = None
    source_fields: list[SourceLayerField] | None = None

    def __str__(self) -> str:
        return "<RelatedTable>"

    def __repr__(self) -> str:
        return "<RelatedTable>"

    def __post_init__(self):
        self._dict_data = self._create_dict()

    def to_json(self) -> str:
        return json.dumps(asdict(self, dict_factory=_custom_asdict_factory))

    def _create_dict(self) -> dict:
        data = {}
        data["name"] = self.name
        data["sourceServiceName"] = self.source_service_name
        data["type"] = self.join_type.value
        data["parentKeyFields"] = self.parent_key_fields
        data["keyFields"] = self.key_fields
        if isinstance(self.source_layer_id, int):
            data["sourceLayerId"] = self.source_layer_id
        if self.filter:
            data["filter"] = self.filter
        if self.top_filter:
            data["topFilter"] = self.top_filter
        if self.source_fields:
            data["sourceLayerFields"] = [
                fld._create_dict()
                for fld in self.source_fields
                if isinstance(fld, SourceLayerField)
            ]
        self._dict_data = data
        return data


###########################################################################
@dataclass
class PrimaryTableView:
    """
    Related tables define the tables joined to the primary table. Related
    tables are the same in the way they define fields, but differ insofar
    as they contain join information.

    =====================  ===============================================================================
    **Parameter**           **Description**
    ---------------------  -------------------------------------------------------------------------------
    source_service_name    Required str. The underlying source service name of the joined service.
    ---------------------  -------------------------------------------------------------------------------
    source_fields          Required list[SourceLayerField]. The list of fields in the newly created view of the joined layer.
    ---------------------  -------------------------------------------------------------------------------
    name                   Optional str. An alias sometimes used to reference this table.
    ---------------------  -------------------------------------------------------------------------------
    source_id              Optional int. The underlying source layer ID of the joined layer. Defaults to the first layer or table.
    ---------------------  -------------------------------------------------------------------------------
    filter                 Optional str. Filters layer data based on non-aggregated fields. The filter needs to reference the source layer field names.
    ---------------------  -------------------------------------------------------------------------------
    top_filter             Optional str. A topFilter on the table results.
    ---------------------  -------------------------------------------------------------------------------
    related_tables         Optional list[RelatedTable]. The definition of the related tables.
    ---------------------  -------------------------------------------------------------------------------
    having_filter          Optional str. Filters data based on aggregated fields. The filter needs to reference field names defined in the view rather than the source field names.
    ---------------------  -------------------------------------------------------------------------------
    group_by               Optional str. Fields for aggregation. Needs to reference field names defined in the view and not the source field names.
    =====================  ===============================================================================
    """

    # table: str
    layer: arcgis.features.FeatureLayer
    source_service_name: str
    source_fields: list[SourceLayerField]
    related_tables: list[RelatedTable]
    name: str | None = None
    source_id: int | None = None
    filter: str | None = None
    top_filter: str | None = None

    having_filter: str | None = None
    group_by: str | None = None
    _dict_data: dict | None = field(init=False)

    def __str__(self) -> str:
        return "<PrimaryTable>"

    def __repr__(self) -> str:
        return "<PrimaryTable>"

    def __post_init__(self):
        self._dict_data = self._create_dict()

    def to_json(self) -> str:
        return json.dumps(asdict(self, dict_factory=_custom_asdict_factory))

    def _create_dict(self) -> dict:
        from arcgis.features import FeatureLayer

        data = {}
        data["name"] = self.name
        data["sourceServiceName"] = self.source_service_name
        if isinstance(self.source_id, int):
            data["sourceLayerId"] = self.source_id
        elif self.layer:
            data["sourceLayerId"] = int(os.path.basename(self.layer._url))
        if self.name:
            data["name"] = self.name
        if self.source_id:
            data["sourceLayerId"] = self.source_id
        if self.filter:
            data["filter"] = self.filter
        if self.top_filter:
            data["topFilter"] = self.top_filter
        if self.related_tables and isinstance(self.related_tables, list):
            data["relatedTables"] = [
                fld._create_dict()
                for fld in self.related_tables
                if isinstance(fld, RelatedTable)
            ]
        if self.having_filter:
            data["havingFilter"] = self.having_filter
        if self.group_by:
            data["groupBy"] = self.group_by
        if self.source_fields:
            data["sourceLayerFields"] = [
                fld._create_dict()
                for fld in self.source_fields
                if isinstance(fld, SourceLayerField)
            ]
        self._dict_data = data
        return data


###########################################################################
@dataclass
class ViewLayerDefParameter:
    """
    When creating views, an optional definition query can be provided to limit what users
    of the view can see with the service view.

    ==================  ===============================================================================
    **Parameter**        **Description**
    ------------------  -------------------------------------------------------------------------------
    layer               Required FeatureLayer.  The layer to apply the layer definition to.
    ------------------  -------------------------------------------------------------------------------
    query_definition    Optional String.  The where clause to limit the layer with.
    ------------------  -------------------------------------------------------------------------------
    spatial_filter      Optional :class:`~arcgis.gis._impl._dataclasses.SpatialFilter`. A spatial
                        filter that can limit the data a user sees.
    ------------------  -------------------------------------------------------------------------------
    fields              Optional list[dict].  An array of field/visible fields that shows or hides a
                        field.  If this parameter is not given, all the fields are shown.

                        .. code-block:: python

                            [
                                {"name":"STATE_CITY","visible":True},
                                {"name":"TYPE","visible":False},
                            ]

    ==================  ===============================================================================

    """

    layer: arcgis.features.FeatureLayer
    query_definition: str | None = None
    spatial_filter: SpatialFilter | None = None
    fields: list[dict] | None = None
    _dict_data: dict | None = field(init=False)

    def __str__(self) -> str:
        return "<ViewLayerDefParameter>"

    def __repr__(self) -> str:
        return "<ViewLayerDefParameter>"

    def __post_init__(self):
        self._dict_data = self._create_dict()

    def _create_dict(self) -> dict:
        data = {}
        if self.query_definition:
            data["viewDefinitionQuery"] = self.query_definition
        if self.spatial_filter:
            data["viewLayerDefinition"] = {"filter": self.spatial_filter.as_json()}
        if self.fields:
            data["fields"] = self.fields
        self._dict_data = data
        return data

    @classmethod
    def fromlayer(
        self,
        layer: (
            arcgis.features.managers.FeatureLayerManager | arcgis.features.FeatureLayer
        ),
    ) -> "ViewLayerDefParameter":
        """Creates a view layer definition parameter object from a layer."""
        from arcgis.features.managers import FeatureLayerManager
        from arcgis.features import FeatureLayer, Table

        if isinstance(layer, (FeatureLayer, Table)):
            fl = layer
            adminlayer = layer.manager
        else:
            adminlayer = layer
            fl = FeatureLayer(
                url=adminlayer.url.replace(r"/admin/", r"/"), gis=layer._gis
            )
        props = dict(adminlayer.properties)
        gfilter = (
            props.get("adminLayerInfo", {})
            .get("viewLayerDefinition", {})
            .get("table", {})
            .get("filter", None)
        )
        if gfilter:
            from arcgis.gis._impl._dataclasses import (
                SpatialRelationship,
                SpatialFilter,
            )

            g = arcgis.geometry.Geometry(gfilter["value"]["geometry"])
            sf = SpatialFilter(
                geometry=g,
                sr=g["spatialReference"],
                spatial_rel=SpatialRelationship._value2member_map_[gfilter["operator"]],
            )
        else:
            sf = None
        fields = [
            {"name": fld["name"], "visible": fld.get("visible", True)}
            for fld in props["fields"]
        ]
        return ViewLayerDefParameter(
            layer=fl,
            query_definition=props.get("viewDefinitionQuery", None),
            spatial_filter=sf,
            fields=fields,
        )

    def as_json(self) -> dict:
        """returns the view as a dictionary"""
        return self._create_dict()
