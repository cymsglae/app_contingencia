from typing import Union, Optional, Any
from datetime import datetime
from arcgis._impl.common._filters import GeometryFilter, StatisticFilter
from arcgis._impl.common._utils import _date_handler
from arcgis.geometry import Geometry
from arcgis.auth.tools import LazyLoader

arcgis_features = LazyLoader("arcgis.features")


def _common_query(
    layer,
    is_layer: bool = False,
    where: str = "1=1",
    text: Optional[str] = None,
    out_fields: Union[str, list[str]] = "*",
    time_filter: Optional[list[datetime]] = None,
    geometry_filter: Optional[GeometryFilter] = None,
    return_geometry: bool = True,
    return_count_only: bool = False,
    return_ids_only: bool = False,
    return_distinct_values: bool = False,
    return_extent_only: bool = False,
    group_by_fields_for_statistics: Optional[str] = None,
    statistic_filter: Optional[StatisticFilter] = None,
    result_offset: Optional[int] = None,
    result_record_count: Optional[int] = None,
    object_ids: Optional[list[str]] = None,
    distance: Optional[int] = None,
    units: Optional[str] = None,
    max_allowable_offset: Optional[int] = None,
    out_sr: Optional[Union[dict[str, int], str]] = None,
    geometry_precision: Optional[int] = None,
    gdb_version: Optional[str] = None,
    order_by_fields: Optional[str] = None,
    out_statistics: Optional[list[dict[str, Any]]] = None,
    return_z: bool = False,
    return_m: bool = False,
    multipatch_option: tuple = None,
    quantization_parameters: Optional[dict[str, Any]] = None,
    return_centroid: bool = False,
    return_all_records: bool = True,
    result_type: Optional[str] = None,
    historic_moment: Optional[Union[int, datetime]] = None,
    sql_format: Optional[str] = None,
    return_true_curves: bool = False,
    return_exceeded_limit_features: Optional[bool] = None,
    as_df: bool = False,
    datum_transformation: Optional[Union[int, dict[str, Any]]] = None,
    range_values: Optional[dict[str, Any]] = None,
    parameter_values: Optional[dict[str, Any]] = None,
    format_3d_objects: Optional[str] = None,
    time_reference_unknown_client: Optional[bool] = None,
    **kwargs,
):
    query_3d = kwargs.pop("query_3d", False)
    raw = False  # default to False
    # get url
    # if raw is True it means it came from query 3D layer
    if query_3d and hasattr(layer, "_is_3d") and layer._is_3d:
        url = layer._url + "/query3D"
        raw = True
    # else query normal
    elif layer._dynamic_layer is None:
        url = layer._url + "/query"
    else:
        url = "%s/query" % layer._url.split("?")[0]

    params = _create_parameters(
        layer=layer,
        is_layer=is_layer,
        where=where,
        text=text,
        out_fields=out_fields,
        time_filter=time_filter,
        geometry_filter=geometry_filter,
        return_geometry=return_geometry,
        return_count_only=return_count_only,
        return_ids_only=return_ids_only,
        return_distinct_values=return_distinct_values,
        return_extent_only=return_extent_only,
        group_by_fields_for_statistics=group_by_fields_for_statistics,
        statistic_filter=statistic_filter,
        result_offset=result_offset,
        result_record_count=result_record_count,
        object_ids=object_ids,
        distance=distance,
        units=units,
        max_allowable_offset=max_allowable_offset,
        out_sr=out_sr,
        geometry_precision=geometry_precision,
        gdb_version=gdb_version,
        order_by_fields=order_by_fields,
        out_statistics=out_statistics,
        return_z=return_z,
        return_m=return_m,
        multipatch_option=multipatch_option,
        quantization_parameters=quantization_parameters,
        return_centroid=return_centroid,
        return_all_records=return_all_records,
        result_type=result_type,
        historic_moment=historic_moment,
        sql_format=sql_format,
        return_true_curves=return_true_curves,
        return_exceeded_limit_features=return_exceeded_limit_features,
        datum_transformation=datum_transformation,
        range_values=range_values,
        parameter_values=parameter_values,
        format_3d_objects=format_3d_objects,
        time_reference_unknown_client=time_reference_unknown_client,
        query_3d=query_3d,
        kwargs=kwargs,
    )

    if not return_all_records or "outStatistics" in params:
        # we cannot assume that because return_all_records is False it means we specified something else
        if return_count_only or return_extent_only or return_ids_only:
            # Remove to avoid missing when wanting counts only
            if "orderByFields" in params:
                del params["orderByFields"]
        if as_df:
            return _query_df(layer, url, params)
        return _query(layer, url, params, raw=as_df)

    # Two workflows: Return as FeatureSet or return as DataFrame
    if as_df:
        return _query_df(layer, url, params)
    else:
        return _query(layer, url, params, raw)


def _create_parameters(
    layer,
    is_layer,
    where,
    text,
    out_fields,
    time_filter,
    geometry_filter,
    return_geometry,
    return_count_only,
    return_ids_only,
    return_distinct_values,
    return_extent_only,
    group_by_fields_for_statistics,
    statistic_filter,
    result_offset,
    result_record_count,
    object_ids,
    distance,
    units,
    max_allowable_offset,
    out_sr,
    geometry_precision,
    gdb_version,
    order_by_fields,
    out_statistics,
    return_z,
    return_m,
    multipatch_option,
    quantization_parameters,
    return_centroid,
    return_all_records,
    result_type,
    historic_moment,
    sql_format,
    return_true_curves,
    return_exceeded_limit_features,
    datum_transformation,
    range_values,
    parameter_values,
    format_3d_objects,
    time_reference_unknown_client,
    query_3d,
    **kwargs,
):
    # create parameters dictionary
    params = {"f": "json"}

    # add optional parameters
    if layer._dynamic_layer is not None:
        params["layer"] = layer._dynamic_layer
    if result_type is not None:
        params["resultType"] = result_type
    if historic_moment is not None:
        params["historicMoment"] = historic_moment
    if sql_format is not None:
        params["sqlFormat"] = sql_format
    if return_true_curves is not None:
        params["returnTrueCurves"] = return_true_curves
    if return_exceeded_limit_features is not None:
        params["returnExceededLimitFeatures"] = return_exceeded_limit_features
    if datum_transformation is not None:
        params["datumTransformation"] = datum_transformation

    # Will only be present for Map Feature Layer
    if text:
        params["text"] = text
    if parameter_values:
        params["parameterValues"] = parameter_values
    if range_values:
        params["rangeValues"] = range_values

    # add required parameters
    params["where"] = where

    # Add parameters for all non 3D querying
    if query_3d is False:
        params["returnDistinctValues"] = return_distinct_values
        params["returnCountOnly"] = return_count_only
        params["returnIdsOnly"] = return_ids_only

    # Add parameters for Layers only
    if is_layer:
        params["returnCentroid"] = return_centroid
        params["returnExtentOnly"] = return_extent_only
        params["returnGeometry"] = return_geometry
        params["returnZ"] = return_z
        params["returnM"] = return_m
        if getattr(layer, "_is_3d", None):
            # for 3D feature query
            if format_3d_objects:
                params["formatOf3DObjects"] = format_3d_objects

    # convert out_fields to a comma separated string
    if isinstance(out_fields, (list, tuple)):
        out_fields = ",".join(out_fields)

    # out_fields and object_ids workflow
    if out_fields != "*" and not return_distinct_values:
        try:
            # Check if object id field is in out_fields.
            # If it isn't, add it
            object_id_field = [
                x.name for x in layer.properties.fields if x.type == "esriFieldTypeOID"
            ][0]
            if object_id_field not in out_fields.split(","):
                out_fields = object_id_field + "," + out_fields
        except (IndexError, AttributeError):
            pass

    # add out_fields parameter
    params["outFields"] = out_fields

    # add parameters based on other parameter values, if doesn't apply to table it will be ignored
    if return_count_only or return_extent_only or return_ids_only:
        return_all_records = False
    if result_record_count and not return_all_records:
        params["resultRecordCount"] = result_record_count
    if result_offset and not return_all_records:
        params["resultOffset"] = result_offset
    if quantization_parameters:
        params["quantizationParameters"] = quantization_parameters
    if multipatch_option:
        params["multipatchOption"] = multipatch_option
    if order_by_fields:
        params["orderByFields"] = order_by_fields
    if group_by_fields_for_statistics:
        params["groupByFieldsForStatistics"] = group_by_fields_for_statistics
    if statistic_filter and isinstance(statistic_filter, StatisticFilter):
        params["outStatistics"] = statistic_filter.filter
    if out_statistics:
        params["outStatistics"] = out_statistics
    if out_sr:
        params["outSR"] = out_sr
    if max_allowable_offset:
        params["maxAllowableOffset"] = max_allowable_offset
    if gdb_version:
        params["gdbVersion"] = gdb_version
    if geometry_precision:
        params["geometryPrecision"] = geometry_precision
    if object_ids:
        params["objectIds"] = object_ids
    if distance:
        params["distance"] = distance
    if units:
        params["units"] = units

    if time_filter is None and layer.time_filter:
        params["time"] = layer.time_filter
    elif time_filter is not None:
        if isinstance(time_filter, list):
            starttime = _date_handler(time_filter[0])
            endtime = _date_handler(time_filter[1])
            if starttime is None:
                starttime = "null"
            if endtime is None:
                endtime = "null"
            params["time"] = "%s,%s" % (starttime, endtime)
        elif isinstance(time_filter, dict):
            for key, val in time_filter.items():
                params[key] = val
        else:
            params["time"] = _date_handler(time_filter)

    if time_reference_unknown_client in [True, False]:
        params["timeReferenceUnknownClient"] = time_reference_unknown_client

    # handle geometry filter parameter
    if geometry_filter and isinstance(geometry_filter, GeometryFilter):
        for key, val in geometry_filter.filter:
            params[key] = val
    elif geometry_filter and isinstance(geometry_filter, dict):
        for key, val in geometry_filter.items():
            params[key] = val

    # handle kwargs
    if len(kwargs) > 0:
        for key, val in kwargs.items():
            if (
                key
                in (
                    "returnCountOnly",
                    "returnExtentOnly",
                    "returnIdsOnly",
                )
                and val
            ):
                # If these keys are passed in as kwargs instead of parameters, set return_all_records
                return_all_records = False
            params[key] = val
            del key, val

    return params


def _query(layer, url, params, raw=False):
    """returns results of query"""
    result = {}
    try:
        # Layer query call
        result = layer._con.post(url, params, token=layer._token)

        # Figure out what to return
        if "error" in result:
            raise ValueError(result)
        elif "returnCountOnly" in params and _is_true(params["returnCountOnly"]):
            # returns an int
            return result["count"]
        elif "returnIdsOnly" in params and _is_true(params["returnIdsOnly"]):
            # returns a dict with keys: 'objectIdFieldName' and 'objectIds'
            return result
        elif "returnExtentOnly" in params and _is_true(params["returnExtentOnly"]):
            # returns extent dictionary with key: 'extent'
            return result
        elif _is_true(raw):
            return result
        elif "resultRecordCount" in params and params["resultRecordCount"] == len(
            result["features"]
        ):
            return arcgis_features.FeatureSet.from_dict(result)
        else:
            # we have features to return
            features = result["features"]

        # If none of the ifs above worked then keep going to find more features
        # Make sure we have all features
        if "exceededTransferLimit" in result:
            while (
                "exceededTransferLimit" in result
                and result["exceededTransferLimit"] == True
            ):
                if "resultRecordCount" not in params:
                    # assign initial value after first query
                    params["resultRecordCount"] = 2000
                if "resultOffset" in params:
                    # add the number we found to the offset so we don't have doubles
                    params["resultOffset"] = params["resultOffset"] + len(
                        result["features"]
                    )
                else:
                    # initial offset after first query (result record count set by user or up above)
                    params["resultOffset"] = params["resultRecordCount"]

                result = layer._con.post(path=url, postdata=params, token=layer._token)
                # add new features to the list
                features = features + result["features"]
        # assign complete list
        result["features"] = features
    except Exception as queryException:
        error_list = [
            "Error performing query operation",
            "HTTP Error 504: GATEWAY_TIMEOUT",
        ]
        if (
            isinstance(queryException.args[0], str)
            and queryException.args[0].lower().find("invalid token") > -1
        ):
            params.pop("token", None)
            return _query(layer, url, params, raw=False)
        elif any(ele in queryException.__str__() for ele in error_list):
            # half the max record count
            max_record = (
                int(params["resultRecordCount"])
                if "resultRecordCount" in params
                else 1000
            )
            offset = int(params["resultOffset"]) if "resultOffset" in params else 0
            # reduce this number to 125 if you still sees 500/504 error
            if max_record < 250:
                # when max_record is lower than 250, but still getting error 500 or 504, just exit with exception
                raise queryException
            else:
                max_rec = int((max_record + 1) / 2)
                i = 0
                result = None
                while max_rec * i < max_record:
                    params["resultRecordCount"] = (
                        max_rec
                        if max_rec * (i + 1) <= max_record
                        else (max_record - max_rec * i)
                    )
                    params["resultOffset"] = offset + max_rec * i
                    try:
                        records = _query(layer, url, params, raw=True)
                        if result:
                            for feature in records["features"]:
                                result["features"].append(feature)
                        else:
                            result = records
                        i += 1
                    except Exception as queryException2:
                        raise queryException2

        else:
            raise queryException

    return arcgis_features.FeatureSet.from_dict(result)


def _is_true(x):
    if isinstance(x, bool) and x:
        return True
    elif isinstance(x, str) and x.lower() == "true":
        return True
    else:
        return False


# ----------------------------------------------------------------------
def _query_df(layer, url, params, **kwargs):
    """returns results of a query as a pd.DataFrame"""
    import pandas as pd
    import numpy as np

    if [float(i) for i in pd.__version__.split(".")] < [1, 0, 0]:
        _fld_lu = {
            "esriFieldTypeSmallInteger": np.int32,
            "esriFieldTypeInteger": np.int32,
            "esriFieldTypeSingle": float,
            "esriFieldTypeDouble": float,
            "esriFieldTypeFloat": float,
            "esriFieldTypeString": str,
            "esriFieldTypeDate": pd.datetime,
            "esriFieldTypeOID": np.int64,
            "esriFieldTypeGeometry": object,
            "esriFieldTypeBlob": object,
            "esriFieldTypeRaster": object,
            "esriFieldTypeGUID": str,
            "esriFieldTypeGlobalID": str,
            "esriFieldTypeXML": object,
            "esriFieldTypeTimeOnly": pd.datetime,
            "esriFieldTypeDateOnly": pd.datetime,
            "esriFieldTypeTimestampOffset": pd.datetime,
        }
    else:
        _fld_lu = {
            "esriFieldTypeSmallInteger": pd.Int32Dtype(),
            "esriFieldTypeInteger": pd.Int32Dtype(),
            "esriFieldTypeSingle": pd.Float64Dtype(),
            "esriFieldTypeDouble": pd.Float64Dtype(),
            "esriFieldTypeFloat": pd.Float64Dtype(),
            "esriFieldTypeString": pd.StringDtype(),
            "esriFieldTypeDate": object,
            "esriFieldTypeOID": pd.Int64Dtype(),
            "esriFieldTypeGeometry": object,
            "esriFieldTypeBlob": object,
            "esriFieldTypeRaster": object,
            "esriFieldTypeGUID": pd.StringDtype(),
            "esriFieldTypeGlobalID": pd.StringDtype(),
            "esriFieldTypeXML": object,
            "esriFieldTypeTimeOnly": pd.StringDtype(),
            "esriFieldTypeDateOnly": object,
            "esriFieldTypeTimestampOffset": object,
            "esriFieldTypeBigInteger": pd.Int64Dtype(),
        }

    def feature_to_row(feature, sr):
        """:return: a feature from a dict"""
        geom = feature["geometry"] if "geometry" in feature else None
        attribs = feature["attributes"] if "attributes" in feature else {}
        if "centroid" in feature:
            if attribs is None:
                attribs = {"centroid": feature["centroid"]}
            elif "centroid" in attribs:
                import uuid

                fld = "centroid_" + uuid.uuid4().hex[:2]
                attribs[fld] = feature["centroid"]
            else:
                attribs["centroid"] = feature["centroid"]
        if geom:
            if "spatialReference" not in geom:
                geom["spatialReference"] = sr
            attribs["SHAPE"] = Geometry(geom)
        return attribs

    try:
        result = layer._con.post(url, params, token=layer._token)
        features = result["features"]
        if "exceededTransferLimit" in result:
            while (
                "exceededTransferLimit" in result
                and result["exceededTransferLimit"] == True
            ):
                if "resultRecordCount" not in params:
                    # assign initial value after first query
                    params["resultRecordCount"] = 2000
                if "resultOffset" in params:
                    params["resultOffset"] = params["resultOffset"] + len(
                        result["features"]
                    )
                else:
                    # initial offset after first query (result record count set by user or up above)
                    params["resultOffset"] = params["resultRecordCount"]

                result = layer._con.post(path=url, postdata=params, token=layer._token)
                # add new features to the list
                features = features + result["features"]
        # assign complete list
        result["features"] = features
    except Exception as queryException:
        error_list = [
            "Error performing query operation",
            "HTTP Error 504: GATEWAY_TIMEOUT",
        ]
        if queryException.args[0].lower().find("invalid token") > -1:
            params.pop("token", None)
            return _query_df(layer, url, params, raw=False)
        if any(ele in queryException.__str__() for ele in error_list):
            # half the max record count
            max_record = (
                int(params["resultRecordCount"])
                if "resultRecordCount" in params
                else 1000
            )
            offset = int(params["resultOffset"]) if "resultOffset" in params else 0
            # reduce this number to 125 if you still sees 500/504 error
            if max_record < 250:
                # when max_record is lower than 250, but still getting error 500 or 504, just exit with exception
                raise queryException
            else:
                max_rec = int((max_record + 1) / 2)
                i = 0
                result = None
                while max_rec * i < max_record:
                    params["resultRecordCount"] = (
                        max_rec
                        if max_rec * (i + 1) <= max_record
                        else (max_record - max_rec * i)
                    )
                    params["resultOffset"] = offset + max_rec * i
                    try:
                        records = _query(layer, url, params, raw=True)
                        if result is not None:
                            for feature in records["features"]:
                                result["features"].append(feature)
                        else:
                            result = records
                        i += 1
                    except Exception as queryException2:
                        raise queryException2

        else:
            raise queryException

    if len(result["features"]) == 0:
        # create columns even if empty dataframe
        columns = {}
        for fld in layer.properties.fields:
            fld = dict(fld)
            columns[fld["name"]] = _fld_lu[fld["type"]]
        if (
            "geometryType" in layer.properties
            and layer.properties.geometryType is not None
        ):
            columns["SHAPE"] = object
        if "return_geometry" in params and params["return_geometry"] == False:
            columns.pop("SHAPE", None)
        df = pd.DataFrame([], columns=columns.keys()).astype(columns, True)
        if "out_fields" in params and params["out_fields"] != "*":
            df = df[params["out_fields"].split(",")].copy()

        if "SHAPE" in df.columns:
            df["SHAPE"] = arcgis_features.geo._array.GeoArray([])
            df.spatial.set_geometry("SHAPE")
            df.spatial.renderer = layer.renderer
            df.spatial._meta.source = layer

        return pd.DataFrame([], columns=columns)
    sr = None
    if "spatialReference" in result:
        sr = result["spatialReference"]

    df = None
    dtypes = None
    names = None
    dfields = []
    rows = [feature_to_row(row, sr) for row in result["features"]]
    if len(rows) == 0:
        return None
    df = pd.DataFrame.from_records(data=rows)
    if "SHAPE" in df.columns:
        df.loc[df.SHAPE.isna(), "SHAPE"] = None
        df.spatial.set_geometry("SHAPE")
    if "fields" in result:
        dtypes = {}
        names = []
        fields = result["fields"]
        for fld in fields:
            if fld["type"] != "esriFieldTypeGeometry":
                dtypes[fld["name"]] = _fld_lu[fld["type"]]
                names.append(fld["name"])
            if fld["type"] in [
                "esriFieldTypeDate",
                #
                "esriFieldTypeDateOnly",
                "esriFieldTypeTimestampOffset",
            ]:
                dfields.append(fld["name"])
    if dtypes:
        df = df.astype(dtypes)

    # set based on layer
    df.spatial.renderer = layer.renderer
    df.spatial._meta.source = layer.url

    if len(dfields) > 0:
        for fld in [fld for fld in dfields if fld in df.columns]:
            try:
                df[fld] = pd.to_datetime(
                    df[fld] / 1000,
                    errors="coerce",
                    unit="s",
                )
            except Exception:
                df[fld] = pd.to_datetime(
                    df[fld],
                    errors="coerce",
                )
    return df
