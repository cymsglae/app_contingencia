from __future__ import annotations
import json
import logging
import datetime

from arcgis.gis import Layer, _GISResource

# Supported Data Types
from typing import Any, Optional, Union
from arcgis.geometry import Point, Polygon, Polyline
from arcgis.features import Feature, FeatureSet
from arcgis.features import FeatureLayer, Table
from arcgis.network import _utils
from arcgis._impl.common._utils import _validate_url
from dataclasses import dataclass
from enum import Enum

try:
    import pandas as pd
    from arcgis.features.geo import _is_geoenabled

    HASPANDAS = True
except ImportError:
    HASPANDAS = False

    def _is_geoenabled(df):
        return False


from arcgis.gis import Item

_log = logging.getLogger(__name__)


###########################################################################
def _handle_spatial_inputs(data, do_not_locate=True, has_z=False, where=None):
    """
    Handles the various supported inputs types
    """
    template = {
        "type": "features",
        "doNotLocateOnRestrictedElements": do_not_locate,
        "hasZ": has_z,
    }
    if isinstance(data, Item) and data.type in ["Feature Layer", "Feature Service"]:
        return _handle_spatial_inputs(data.layers[0])
    if HASPANDAS and isinstance(data, pd.DataFrame) and _is_geoenabled(df=data):
        return data.spatial.__feature_set__
    elif isinstance(data, FeatureSet):
        return data.sdf.spatial.__feature_set__
    elif isinstance(data, list):
        stops_dict = []
        for stop in data:
            if isinstance(stop, Feature):
                stops_dict.append(stop.as_dict)
            else:
                stops_dict.append(stop)
        template["features"] = stops_dict
        return template
    elif isinstance(data, (FeatureLayer, Table)):
        from urllib.parse import quote

        query = data.filter
        url = data._url
        if query and len(str(query)) > 0:
            query = quote(query)
            url += "/query?where=%s&outFields=*&f=json" % query
            if data._gis._con.token:
                url += "&token=%s" % data._gis._con.token
        else:
            query = quote("1=1")
            url += "/query?where=%s&outFields=*&f=json" % query
            if data._gis._con.token:
                url += "&token=%s" % data._gis._con.token
        template["url"] = url
        return template
    else:
        return data


###########################################################################
class NAJob(object):
    """Represents a Future Job for Network Analyst Jobs"""

    _future = None
    _gis = None
    _start_time = None
    _end_time = None

    # ----------------------------------------------------------------------
    def __init__(self, future, task=None, notify=False):
        """
        initializer
        """
        if task is None:
            self._task = "Network Task"
        else:
            self._task = task
        self._future = future
        self._start_time = datetime.datetime.now()
        if notify:
            self._future.add_done_callback(self._notify)
        self._future.add_done_callback(self._set_end_time)

    # ----------------------------------------------------------------------
    @property
    def ellapse_time(self):
        """
        Returns the Ellapse Time for the Job
        """
        if self._end_time:
            return self._end_time - self._start_time
        else:
            return datetime.datetime.now() - self._start_time

    # ----------------------------------------------------------------------
    def _set_end_time(self, future):
        """sets the finish time"""
        self._end_time = datetime.datetime.now()

    # ----------------------------------------------------------------------
    def _notify(self, future):
        """prints finished method"""
        jobid = str(self).replace("<", "").replace(">", "")
        try:
            future.result()
            infomsg = "{jobid} finished successfully.".format(jobid=jobid)
            _log.info(infomsg)
            print(infomsg)
        except Exception as e:
            msg = str(e)
            msg = "{jobid} failed: {msg}".format(jobid=jobid, msg=msg)
            _log.info(msg)
            print(msg)

    # ----------------------------------------------------------------------
    def __str__(self):
        task = self._task
        return f"<{task} Job>"

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def status(self):
        """
        returns the GP status

        :return: String
        """
        return self._future.done()

    # ----------------------------------------------------------------------
    def cancel(self):
        """
        Attempt to cancel the call. If the call is currently being executed
        or finished running and cannot be cancelled then the method will
        return False, otherwise the call will be cancelled and the method
        will return True.

        :return: boolean
        """

        if self.done():
            return False
        if self.cancelled():
            return False
        return True

    # ----------------------------------------------------------------------
    def cancelled(self):
        """
        Return True if the call was successfully cancelled.

        :return: boolean
        """
        return self._future.cancelled()

    # ----------------------------------------------------------------------
    def running(self):
        """
        Return True if the call is currently being executed and cannot be cancelled.

        :return: boolean
        """
        return self._future.running()

    # ----------------------------------------------------------------------
    def done(self):
        """
        Return True if the call was successfully cancelled or finished running.

        :return: boolean
        """
        return self._future.done()

    # ----------------------------------------------------------------------
    def result(self):
        """
        Return the value returned by the call. If the call hasn't yet completed
        then this method will wait.

        :return: object
        """
        if self.cancelled():
            return None
        return self._future.result()


###########################################################################
class NetworkLayer(Layer):
    """
    NetworkLayer represents a single network layer. It provides basic
    information about the network layer such as its name, type, and network
    classes. Additionally, depending on the layer type, it provides different
    pieces of information.

    It is a base class for RouteLayer, ServiceAreaLayer, and
    ClosestFacilityLayer.
    """

    # ----------------------------------------------------------------------
    def _run_async(self, fn, **inputs):
        """runs the inputs asynchronously"""
        import concurrent.futures

        tp = concurrent.futures.ThreadPoolExecutor(1)
        try:
            future = tp.submit(fn=fn, **inputs)
        except Exception:
            future = tp.submit(fn, **inputs)
        tp.shutdown(False)
        return future

    # ----------------------------------------------------------------------
    def retrieve_travel_modes(self):
        """identify all the valid travel modes that have been defined on the
        network dataset or in the portal if the GIS server is federated"""
        url = self._url + "/retrieveTravelModes"
        params = {"f": "json"}
        return self._con.get(
            path=url,
            params=params,
        )


###########################################################################
class ToleranceUnits(Enum):
    centimeters = "esriCentimeters"
    decimaldegrees = "esriDecimalDegrees"
    decimeters = "esriDecimeters"
    feet = "esriFeet"
    inches = "esriInches"
    intFeet = "esriIntFeet"
    intInches = "esriIntInches"
    intMiles = "esriIntMiles"
    intNauticalMiles = "esriIntNauticalMiles"
    intYards = "esriIntYards"
    kilometers = "esriKilometers"
    meters = "esriMeters"
    miles = "esriMiles"
    millimeters = "esriMillimeters"
    nauticalMiles = "esriNauticalMiles"
    yards = "esriYards"


@dataclass
class LocateSettings:
    """
    Parameters available for locate settings that can be
    passed to the solve operation. See
    `locateSettings <https://developers.arcgis.com/rest/services-reference/enterprise/locate-service.htm#ESRI_SECTION2_71A6EDCD15B64DCE84CCAE459FE03865>`_
    for full descriptions.

    ========================     ===============================================
    **Parameter**                **Description**
    ------------------------     -----------------------------------------------
    tolerance                    Allows you to control the maximum search
                                 distance when locating inputs. If no valid network
                                 location is found within this distance, the input
                                 features will be considered unlocated. A small
                                 search tolerance decreases the likelihood of locating
                                 on the wrong street but increases the likelihood of not
                                 finding any valid network location.
    ------------------------     -----------------------------------------------
    tolerance_units              Argument should be specified as one of
                                 :class:`~arcgis.network.ToleranceUnits`
    ------------------------     -----------------------------------------------
    allow_auto_relocate          Allows you to control whether inputs with existing
                                 network location fields can be automatically
                                 relocated to ensure valid, routable location fields
                                 for the analysis.
    ------------------------     -----------------------------------------------
    sources                      Allows you to control which network source can
                                 be used for locating. For example, you can configure
                                 the analysis to locate inputs on streets but not
                                 on sidewalks. The list of possible sources on
                                 which to locate is specific to the network dataset
                                 this service references.
    ========================     ===============================================

    .. code-block:: python

        # Usage Example:
        >>> locate_settings = LocateSettings(
                                        tolerance=5000,
                                        tolerance_units=ToleranceUnits.meters,
                                        allow_auto_relocate=True,
                                        sources=[
                                                {"name": "Routing_Streets"}
                                            ]
                                        )
    """

    tolerance: float
    tolerance_units: str | ToleranceUnits
    allow_auto_relocate: bool
    sources: list[dict[str, Any]] | None

    def to_dict(self):
        return {
            "tolerance": self.tolerance,
            "toleranceUnits": (
                self.tolerance_units.value
                if isinstance(self.tolerance_units, ToleranceUnits)
                else self.tolerance_units
            ),
            "allowAutoRelocate": self.allow_auto_relocate,
            "sources": self.sources,
        }


###########################################################################
class RouteLayer(NetworkLayer):
    """
    The Route Layer which has common properties of Network Layer
    as well as some attributes unique to Route Network Layer only.
    """

    def solve(
        self,
        stops: Union[list[Point], list[FeatureSet], FeatureSet],
        barriers: Optional[Union[Point, FeatureSet, dict[str, Any]]] = None,
        polyline_barriers: Optional[Union[Polyline, FeatureSet, dict[str, Any]]] = None,
        polygon_barriers: Optional[Union[Polygon, FeatureSet, dict[str, Any]]] = None,
        travel_mode: Optional[str] = None,
        attribute_parameter_values: Optional[Union[str, list[str]]] = None,
        return_directions: bool = True,
        return_routes: bool = True,
        return_stops: bool = False,
        return_barriers: bool = False,
        return_polyline_barriers: bool = False,
        return_polygon_barriers: bool = False,
        out_sr: Optional[int] = None,
        ignore_invalid_locations: bool = True,
        output_lines: Optional[str] = None,
        find_best_sequence: bool = False,
        preserve_first_stop: bool = True,
        preserve_last_stop: bool = True,
        use_time_windows: bool = False,
        start_time: Optional[str] = None,
        start_time_is_utc: bool = False,
        accumulate_attribute_names: Optional[str] = None,
        impedance_attribute_name: Optional[str] = None,
        restriction_attribute_names: Optional[str] = None,
        restrict_u_turns: Optional[bool] = None,
        use_hierarchy: bool = True,
        directions_language: Optional[str] = None,
        directions_output_type: Optional[str] = None,
        directions_style_name: Optional[str] = None,
        directions_length_units: Optional[str] = None,
        directions_time_attribute_name: Optional[str] = None,
        output_geometry_precision: Optional[float] = None,
        output_geometry_precision_units: Optional[str] = None,
        return_z: bool = False,
        overrides: Optional[dict[str, Any]] = None,
        preserve_objectid: bool = False,
        future: bool = False,
        time_windows_are_utc: bool = False,
        return_traversed_edges: Optional[bool] = None,
        return_traversed_junctions: Optional[bool] = None,
        return_traversed_turns: Optional[bool] = None,
        geometry_precision: Optional[int] = None,
        geometry_precision_z: Optional[int] = None,
        geometry_precision_m: Optional[int] = None,
        locate_settings: Optional[dict] = None,
        return_empty_results: Optional[bool] = False,
    ):
        """
        The solve operation is performed on a network layer resource.
        The solve operation is supported on a network layer whose layerType
        is esriNAServerRouteLayer. You can provide arguments to the solve
        route operation as query parameters.


        ===================================     ====================================================================
        **Parameter**                            **Description**
        -----------------------------------     --------------------------------------------------------------------
        stops                                   Required Points/FeatureSet/a list of Features. The set of stops
                                                loaded as network locations during analysis. Stops can be specified
                                                using a simple comma / semi-colon based syntax or as a JSON
                                                structure. If stops are not specified, preloaded stops from the map
                                                document are used in the analysis.
        -----------------------------------     --------------------------------------------------------------------
        barriers                                Optional Point/FeatureSet. The set of barriers loaded as network
                                                locations during analysis. Barriers can be specified using a simple
                                                comma/semi-colon based syntax or as a JSON structure. If barriers
                                                are not specified, preloaded barriers from the map document are used
                                                in the analysis. If an empty json object is passed ('{}') preloaded
                                                barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        polyline_barriers                       Optional Polyline/FeatureSet. The set of polyline barriers loaded
                                                as network locations during analysis. If polyline barriers are not
                                                specified, preloaded polyline barriers from the map document are
                                                used in the analysis. If an empty json object is passed ('{}')
                                                preloaded polyline barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        polygon_barriers                        Optional Polygon/FeatureSet. The set of polygon barriers loaded as
                                                network locations during analysis. If polygon barriers are not
                                                specified, preloaded polygon barriers from the map document are used
                                                in the analysis. If an empty json object is passed ('{}') preloaded
                                                polygon barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        travel_mode                             Optional string. Travel modes provide override values that help you
                                                quickly and consistently model a vehicle or mode of transportation.
                                                The chosen travel mode must be preconfigured on the network dataset
                                                that the routing service references.
        -----------------------------------     --------------------------------------------------------------------
        attribute_parameter_values              Optional string/list.  A set of attribute parameter values that can be
                                                parameterized to determine which network elements can be used by a
                                                vehicle.
        -----------------------------------     --------------------------------------------------------------------
        return_directions                       Optional boolean. If true, directions will be generated and returned
                                                with the analysis results. Default is true.
        -----------------------------------     --------------------------------------------------------------------
        return_routes                           Optional boolean. If true, routes will be returned with the analysis
                                                results. Default is true.
        -----------------------------------     --------------------------------------------------------------------
        return_stops                            Optional boolean.  If true, stops will be returned with the analysis
                                                results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_barriers                         Optional boolean.  If true, barriers will be returned with the
                                                analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_polyline_barriers                Optional boolean. If true, polyline barriers will be returned with
                                                the analysis results. Default is False.
        -----------------------------------     --------------------------------------------------------------------
        return_polygon_barriers                 Optional boolean. If true, polygon barriers will be returned with
                                                the analysis results. Default is False.
        -----------------------------------     --------------------------------------------------------------------
        out_sr                                  Optional Integer. The spatial reference of the geometries returned
                                                with the analysis results.
        -----------------------------------     --------------------------------------------------------------------
        ignore_invalid_locations                Optional boolean. - If true, the solver will ignore invalid
                                                locations. Otherwise, it will raise an error. Default is true.
        -----------------------------------     --------------------------------------------------------------------
        output_lines                            The type of output lines to be generated in the result. The default
                                                is as defined in the network layer.
                                                Values: esriNAOutputLineTrueShape |
                                                        esriNAOutputLineTrueShapeWithMeasure |
                                                        esriNAOutputLineStraight | esriNAOutputLineNone
        -----------------------------------     --------------------------------------------------------------------
        find_best_sequence                      Optional boolean. If true, the solver should re-sequence the route in
                                                the optimal order. The default is as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        preserve_first_stop                     Optional boolean. If true, the solver should keep the first stop
                                                fixed in the sequence. The default is as defined in the network
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        preserve_last_stop                      Optional boolean. If true, the solver should keep the last stop fixed
                                                in the sequence. The default is as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        use_time_window                         Optional boolean. If true, the solver should consider time windows.
                                                The default is as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        start_time                              Optional string. The time the route begins. If not specified, the
                                                solver will use the default as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        start_time_is_utc                       Optional boolean. The time zone of the startTime parameter.
        -----------------------------------     --------------------------------------------------------------------
        accumulate_attribute_names              Optional string. A list of network attribute names to be accumulated
                                                with the analysis. The default is as defined in the network layer.
                                                The value should be specified as a comma separated list of attribute
                                                names. You can also specify a value of none to indicate that no
                                                network attributes should be accumulated.
        -----------------------------------     --------------------------------------------------------------------
        impedance_attribute_name                Optional string. The network attribute name to be used as the impedance
                                                attribute in analysis. The default is as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        restriction_attribute_names             Optional string. -The list of network attribute names to be
                                                used as restrictions with the analysis. The default is as defined in
                                                the network layer. The value should be specified as a comma
                                                separated list of attribute names. You can also specify a value of
                                                none to indicate that no network attributes should be used as
                                                restrictions.
        -----------------------------------     --------------------------------------------------------------------
        restrict_u_turns                        Optional boolean. Specifies how U-Turns should be restricted in the
                                                analysis. The default is as defined in the network layer.
                                                Values: esriNFSBAllowBacktrack | esriNFSBAtDeadEndsOnly |
                                                        esriNFSBNoBacktrack | esriNFSBAtDeadEndsAndIntersections
        -----------------------------------     --------------------------------------------------------------------
        use_hierarchy                           Optional boolean.  If true, the hierarchy attribute for the network
                                                should be used in analysis. The default is as defined in the network
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        directions_language                     Optional string. The language to be used when computing directions.
                                                The default is the language of the server's operating system. The list
                                                of supported languages can be found in REST layer description.
        -----------------------------------     --------------------------------------------------------------------
        directions_output_type                  Optional string.  Defines content, verbosity of returned directions.
                                                The default is esriDOTInstructionsOnly.
                                                Values: esriDOTComplete | esriDOTCompleteNoEvents
                                                        | esriDOTInstructionsOnly | esriDOTStandard |
                                                        esriDOTSummaryOnly
        -----------------------------------     --------------------------------------------------------------------
        directions_style_name                   Optional string. The style to be used when returning the directions.
                                                The default is as defined in the network layer. The list of
                                                supported styles can be found in REST layer description.
        -----------------------------------     --------------------------------------------------------------------
        directions_length_units                 Optional string. The length units to use when computing directions.
                                                The default is as defined in the network layer.
                                                Values: esriNAUFeet | esriNAUKilometers | esriNAUMeters |
                                                        esriNAUMiles | esriNAUNauticalMiles | esriNAUYards |
                                                        esriNAUUnknown
        -----------------------------------     --------------------------------------------------------------------
        directions_time_attribute_name          Optional string. The name of network attribute to use for the drive
                                                time when computing directions. The default is as defined in the network
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision               Optional float.  The precision of the output geometry after
                                                generalization. If 0, no generalization of output geometry is
                                                performed. The default is as defined in the network service
                                                configuration.
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision_units         Optional string. The units of the output geometry precision. The
                                                default value is esriUnknownUnits.
                                                Values: esriUnknownUnits | esriCentimeters | esriDecimalDegrees |
                                                        esriDecimeters | esriFeet | esriInches | esriKilometers |
                                                        esriMeters | esriMiles | esriMillimeters |
                                                        esriNauticalMiles | esriPoints | esriYards
        -----------------------------------     --------------------------------------------------------------------
        return_z                                Optional boolean. If true, Z values will be included in the returned
                                                routes and compressed geometry if the network dataset is Z-aware.
                                                The default is false.
        -----------------------------------     --------------------------------------------------------------------
        overrides                               Optional dictionary. Specify additional settings that can influence
                                                the behavior of the solver.  A list of supported override settings
                                                for each solver and their acceptable values can be obtained by
                                                contacting Esri Technical Support.
        -----------------------------------     --------------------------------------------------------------------
        preserve_objectid                       Optional Boolean.  If True, all objectid values are maintained.  The
                                                default is False.
        -----------------------------------     --------------------------------------------------------------------
        future                                  Optional boolean. If True, a future object will be returned and the process
                                                will not wait for the task to complete. The default is False, which means wait for results.
        -----------------------------------     --------------------------------------------------------------------
        time_windows_are_utc                    Optional boolean. Specify whether the TimeWindowStart and TimeWindowEnd
                                                attribute values on stops are specified in coordinated universal time (UTC)
                                                or geographically local time.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_edges                  Optional boolean. Specify whether traversed edges will be returned
                                                by the service.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_junctions              Optional boolean. Specify whether traversed junctions will be returned
                                                by the service.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_turns                  Optional boolean. Specify whether traversed turns will be returned
                                                by the service.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision                      Optional Integer. Use this parameter to specify the number of decimal
                                                places in the response geometries returned by solve operation. This
                                                applies to x/y values only (not m- or z-values).
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_z                    Optional Integer. Use this parameter specify the number of decimal places
                                                in the response geometries returned by solve operation. This applies to
                                                z-value only.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_m                    Optional Integer. Use this parameter to specify the number of decimal
                                                places in the response geometries returned by solve operation.
                                                This applies to m-value only.
        -----------------------------------     --------------------------------------------------------------------
        locate_settings                         Optional dictionary containing additional input location settings.
                                                Use this parameter to specify settings that affect how inputs are located,
                                                such as the maximum search distance to use when locating the inputs on the
                                                network or the network sources being used for locating. To restrict locating
                                                on a portion of the source, you can specify a where clause for a source.

                                                The dictionary of parameters can be assigned to the 'default', or to the
                                                'overrides' key which holds the dictionary of parameters for each override, types of override are
                                                'stops', 'barriers', 'polylineBarriers', 'polygonBarriers'.
                                                Use the :py:class:`~arcgis.network.LocateSettings` class to create the dictionary for each override or
                                                for the default.

                                                .. note::
                                                    'default' has to be present if you want to pass in any locate_settings to the
                                                    service. In addition, locate settings for default have to be complete, meaning
                                                    all properties need to be present.
                                                    For each override, the keys do not have to be complete.

                                                .. note::
                                                    for 'polylineBarriers' and 'polygonBarriers', tolerance and tolerance_units are
                                                    not supported.

                                                .. code-block:: python

                                                    from arcgis.network import LocateSettings
                                                    locate_settings = LocateSettings(
                                                        tolerance=5000,
                                                        tolerance_units=ToleranceUnits.meters,
                                                        allow_auto_relocate=True,
                                                        sources=[{"name": "Routing_Streets"}]
                                                    )
                                                    result = route_layer.solve(stops=stops, locate_settings={"default": locate_settings.to_dict()})
        -----------------------------------     --------------------------------------------------------------------
        return_empty_results                    Optional boolean. If True, the service will return empty results
                                                instead of the error property when the request fails. The default
                                                is False.
        ===================================     ====================================================================


        :return: dict

        .. code-block:: python

            # USAGE EXAMPLE: Solving the routing problem by passing in a FeatureSet

            # get a FeatureSet through query
            fl = sample_cities.layers[0]
            cities_to_visit = fl.query(where="ST = 'CA' AND POP2010 > 300000",
                                       out_fields='NAME', out_sr=4326)

            type(cities_to_visit)
            >> arcgis.features.feature.FeatureSet

            # pass in the FeatureSet
            result = route_layer.solve(stops=cities_to_visit, preserve_first_stop=True,
                                       preserve_last_stop=True, find_best_sequence=True, return_directions=False,
                                       return_stops=True, return_barriers=False, return_polygon_barriers=False,
                                       return_polyline_barriers=False, return_routes=True,
                                       output_lines='esriNAOutputLineStraight')

        """

        if not self.properties.layerType == "esriNAServerRouteLayer":
            raise ValueError(
                "The solve operation is supported on a network "
                "layer of Route type only"
            )

        url = self._url + "/solve"

        params = {
            "f": "json",
        }
        if travel_mode:
            if isinstance(travel_mode, str):
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=travel_mode
                )
                params["travel_mode"] = travel_mode
            elif isinstance(travel_mode, dict):
                travel_mode = json.dumps(travel_mode)
                params["travel_mode"] = travel_mode
            else:
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=_utils.default_travel_mode(gis=self._gis)
                )
                params["travel_mode"] = travel_mode

        stops = _handle_spatial_inputs(data=stops)
        params["stops"] = stops
        if directions_output_type is None:
            directions_output_type = "esriDOTInstructionsOnly"
        if barriers is not None:
            params["barriers"] = _handle_spatial_inputs(data=barriers)
        if polyline_barriers is not None:
            params["polylineBarriers"] = _handle_spatial_inputs(data=polyline_barriers)
        if polygon_barriers is not None:
            params["polygonBarriers"] = _handle_spatial_inputs(data=polygon_barriers)
        if travel_mode is not None:
            params["travelMode"] = travel_mode
        if attribute_parameter_values is not None:
            params["attributeParameterValues"] = attribute_parameter_values
        if return_directions is not None:
            params["returnDirections"] = return_directions
        if return_routes is not None:
            params["returnRoutes"] = return_routes
        if return_stops is not None:
            params["returnStops"] = return_stops
        if return_barriers is not None:
            params["returnBarriers"] = return_barriers
        if return_polyline_barriers is not None:
            params["returnPolylineBarriers"] = return_polyline_barriers
        if return_polygon_barriers is not None:
            params["returnPolygonBarriers"] = return_polygon_barriers
        if out_sr is not None:
            params["outSR"] = out_sr
        if ignore_invalid_locations is not None:
            params["ignoreInvalidLocations"] = ignore_invalid_locations
        if output_lines is not None:
            params["outputLines"] = output_lines
        if find_best_sequence is not None:
            params["findBestSequence"] = find_best_sequence
        if preserve_first_stop is not None:
            params["preserveFirstStop"] = preserve_first_stop
        if preserve_last_stop is not None:
            params["preserveLastStop"] = preserve_last_stop
        if use_time_windows is not None:
            params["useTimeWindows"] = use_time_windows
        if time_windows_are_utc is not None:
            params["timeWindowsAreUTC"] = time_windows_are_utc
        if start_time is not None:
            if isinstance(start_time, datetime.datetime):
                start_time = f"{start_time.timestamp() * 1000}"
            params["startTime"] = start_time
        if start_time_is_utc is not None:
            params["startTimeIsUTC"] = start_time_is_utc
        if accumulate_attribute_names is not None:
            params["accumulateAttributeNames"] = accumulate_attribute_names
        if impedance_attribute_name is not None:
            params["impedanceAttributeName"] = impedance_attribute_name
        if restriction_attribute_names is not None:
            params["restrictionAttributeNames"] = restriction_attribute_names
        if restrict_u_turns is not None:
            params["restrictUTurns"] = restrict_u_turns
        if use_hierarchy is not None:
            params["useHierarchy"] = use_hierarchy
        if directions_language is not None:
            params["directionsLanguage"] = directions_language
        if directions_output_type is not None:
            params["directionsOutputType"] = directions_output_type
        if directions_style_name is not None:
            params["directionsStyleName"] = directions_style_name
        if directions_length_units is not None:
            params["directionsLengthUnits"] = directions_length_units
        if directions_time_attribute_name is not None:
            params["directionsTimeAttributeName"] = directions_time_attribute_name
        if output_geometry_precision is not None:
            params["outputGeometryPrecision"] = output_geometry_precision
        if output_geometry_precision_units is not None:
            params["outputGeometryPrecisionUnits"] = output_geometry_precision_units
        if return_z is not None:
            params["returnZ"] = return_z
        if overrides is not None:
            params["overrides"] = overrides
        if preserve_objectid is not None:
            params["preserveObjectID"] = preserve_objectid
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        if geometry_precision_z is not None:
            params["geometryPrecisionZ"] = geometry_precision_z
        if geometry_precision_m is not None:
            params["geometryPrecisionM"] = geometry_precision_m
        if return_traversed_edges is not None:
            params["returnTraversedEdges"] = return_traversed_edges
        if return_traversed_junctions is not None:
            params["returnTraversedJunctions"] = return_traversed_junctions
        if return_traversed_turns is not None:
            params["returnTraversedTurns"] = return_traversed_turns
        if locate_settings is not None:
            params["locateSettings"] = locate_settings
        if return_empty_results is not None:
            params["returnEmptyResults"] = return_empty_results

        if future:
            f = self._run_async(
                self._con.post,
                **{"path": url, "postdata": params},
            )
            return NAJob(future=f, task="RouteLayer Solve")
        return self._con.post(path=url, postdata=params)  # ,


###########################################################################
class ServiceAreaLayer(NetworkLayer):
    """
    The Service Area Layer which has common properties of Network
    Layer as well as some attributes unique to Service Area Layer
    only.
    """

    def solve_service_area(
        self,
        facilities: Union[FeatureSet, Point, list, dict],
        barriers: Optional[Union[Point, FeatureSet, dict[str, Any]]] = None,
        polyline_barriers: Optional[Union[Polyline, FeatureSet, dict[str, Any]]] = None,
        polygon_barriers: Optional[Union[Polygon, FeatureSet, dict[str, Any]]] = None,
        travel_mode: Optional[str] = None,
        attribute_parameter_values: Optional[Union[str, list]] = None,
        default_breaks: Optional[list[float]] = None,
        exclude_sources_from_polygons: Optional[list[str]] = None,
        merge_similar_polygon_ranges: Optional[bool] = None,
        output_lines: Optional[str] = None,
        output_polygons: Optional[str] = None,
        overlap_lines: Optional[str] = None,
        overlap_polygons: Optional[str] = None,
        split_lines_at_breaks: Optional[bool] = None,
        split_polygons_at_breaks: Optional[bool] = None,
        trim_outer_polygon: Optional[bool] = None,
        trim_polygon_distance: Optional[Union[str, int]] = None,
        trim_polygon_distance_units: Optional[str] = None,
        return_facilities: bool = False,
        return_barriers: bool = False,
        return_polyline_barriers: bool = False,
        return_polygon_barriers: bool = False,
        out_sr: Optional[int] = None,
        accumulate_attribute_names: Optional[list[str]] = None,
        impedance_attribute_name: Optional[str] = None,
        restriction_attribute_names: Optional[list[str]] = None,
        restrict_u_turns: Optional[str] = None,
        output_geometry_precision: Optional[int] = None,
        output_geometry_precision_units: str = "esriUnknownUnits",
        use_hierarchy: Optional[bool] = None,
        time_of_day: Optional[datetime.datetime] = None,
        time_of_day_is_utc: Optional[bool] = None,
        travel_direction: Optional[str] = None,
        return_z: bool = False,
        overrides: Optional[dict[str, Any]] = None,
        preserve_objectid: bool = False,
        future: bool = False,
        ignore_invalid_locations: bool = True,
        geometry_precision: Optional[int] = None,
        geometry_precision_z: Optional[int] = None,
        geometry_precision_m: Optional[int] = None,
        locate_settings: Optional[dict[str, Any]] = None,
        return_empty_results: Optional[bool] = False,
        include_source_information_on_lines: Optional[bool] = True,
    ):
        """The solve service area operation is performed on a network layer
        resource of type service area (layerType is esriNAServerServiceArea).
        You can provide arguments to the solve service area operation as
        query parameters.

        ===================================     ====================================================================
        **Parameter**                            **Description**
        -----------------------------------     --------------------------------------------------------------------
        facilities                              The set of facilities loaded as network locations
                                                during analysis. Facilities can be specified using
                                                a simple comma / semi-colon based syntax or as a
                                                JSON structure. If facilities are not specified,
                                                preloaded facilities from the map document are used
                                                in the analysis. If an empty json object is passed
                                                ('{}') preloaded facilities are ignored.
        -----------------------------------     --------------------------------------------------------------------
        barriers                                The set of barriers loaded as network locations during
                                                analysis. Barriers can be specified using a simple
                                                comma/semicolon-based syntax or as a JSON structure.
                                                If barriers are not specified, preloaded barriers from
                                                the map document are used in the analysis. If an empty
                                                json object is passed ('{}'), preloaded barriers are
                                                ignored.
        -----------------------------------     --------------------------------------------------------------------
        polyline_barriers                       The set of polyline barriers loaded as network
                                                locations during analysis. If polyline barriers
                                                are not specified, preloaded polyline barriers
                                                from the map document are used in the analysis.
                                                If an empty json object is passed ('{}'),
                                                preloaded polyline barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        polygon_barriers                        The set of polygon barriers loaded as network
                                                locations during analysis. If polygon barriers
                                                are not specified, preloaded polygon barriers
                                                from the map document are used in the analysis.
                                                If an empty json object is passed ('{}'),
                                                preloaded polygon barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        travel_mode                             Travel modes provide override values that help you
                                                quickly and consistently model a vehicle or mode of
                                                transportation. The chosen travel mode must be
                                                preconfigured on the network dataset that the
                                                service area service references.
        -----------------------------------     --------------------------------------------------------------------
        attribute_parameter_values              A set of attribute parameter values that
                                                can be parameterized to determine which
                                                network elements can be used by a vehicle.
        -----------------------------------     --------------------------------------------------------------------
        default_breaks                          A comma-separated list of doubles. The default is
                                                defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        exclude_sources_from_polygons           A comma-separated list of string names.
                                                The default is defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        merge_similar_polygon_ranges            If true, similar ranges will be merged in the result polygons.
                                                The default is defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        output_lines                            The type of lines(s) generated. The default is as
                                                defined in the network analysis layer.
                                                Values: esriNAOutputLineNone | esriNAOutputLineTrueShape |
                                                esriNAOutputLineTrueShapeWithMeasure
        -----------------------------------     --------------------------------------------------------------------
        output_polygons                         The type of polygon(s) generated. The default is
                                                as defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        overlap_lines                           Indicates if the lines should overlap from multiple
                                                facilities. The default is defined in the network
                                                analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        overlap_polygons                        Indicates if the polygons for all facilities
                                                should overlap. The default is defined in the
                                                network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        splitLines_at_breaks                    If true, lines will be split at breaks. The
                                                default is defined in the network analysis
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        split_polygons_at_breaks                If true, polygons will be split at breaks.
                                                The default is defined in the network
                                                analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        trim_outer_polygon                      If true, the outermost polygon (at the maximum
                                                break value) will be trimmed. The default is
                                                defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        trim_polygon_distance                   If polygons are being trimmed, provides the
                                                distance to trim. The default is defined in
                                                the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        trim_polygon_distance_units             If polygons are being trimmed, specifies
                                                the units of the trimPolygonDistance. The
                                                default is defined in the network analysis
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        return_facilities                       If true, facilities will be returned with the
                                                analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_barriers                         If true, barriers will be returned with the analysis
                                                results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_polyline_barriers                If true, polyline barriers will be returned
                                                with the analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_polygon_barriers                 If true, polygon barriers will be returned
                                                with the analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        out_sr                                  The well-known ID of the spatial reference for the geometries
                                                returned with the analysis results. If outSR is not specified,
                                                the geometries are returned in the spatial reference of the map.
        -----------------------------------     --------------------------------------------------------------------
        accumulate_attribute_names              The list of network attribute names to be
                                                accumulated with the analysis. The default
                                                is as defined in the network analysis layer.
                                                The value should be specified as a comma
                                                separated list of attribute names. You can
                                                also specify a value of none to indicate that
                                                no network attributes should be accumulated.
        -----------------------------------     --------------------------------------------------------------------
        impedance_attribute_name                The network attribute name to be used as the
                                                impedance attribute in analysis. The default
                                                is as defined in the network analysis layer.
        -----------------------------------     --------------------------------------------------------------------
        restriction_attribute_names             The list of network attribute names to be
                                                used as restrictions with the analysis. The
                                                default is as defined in the network analysis
                                                layer. The value should be specified as a
                                                comma separated list of attribute names.
                                                You can also specify a value of none to
                                                indicate that no network attributes should
                                                be used as restrictions.
        -----------------------------------     --------------------------------------------------------------------
        restrict_u_turns                        Specifies how U-Turns should be restricted in the
                                                analysis. The default is as defined in the network
                                                analysis layer. Values: esriNFSBAllowBacktrack |
                                                esriNFSBAtDeadEndsOnly | esriNFSBNoBacktrack |
                                                esriNFSBAtDeadEndsAndIntersections
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision               The precision of the output geometry after
                                                generalization. If 0, no generalization of
                                                output geometry is performed. The default is
                                                as defined in the network service configuration.
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision_units         The units of the output geometry precision.
                                                The default value is esriUnknownUnits.
                                                Values: esriUnknownUnits | esriCentimeters |
                                                esriDecimalDegrees | esriDecimeters |
                                                esriFeet | esriInches | esriKilometers |
                                                esriMeters | esriMiles | esriMillimeters |
                                                esriNauticalMiles | esriPoints | esriYards
        -----------------------------------     --------------------------------------------------------------------
        use_hierarchy                           If true, the hierarchy attribute for the network should be
                                                used in analysis. The default is as defined in the network
                                                layer. This cannot be used in conjunction with outputLines.
        -----------------------------------     --------------------------------------------------------------------
        time_of_day                             The date and time at the facility. If travelDirection is set
                                                to esriNATravelDirectionToFacility, the timeOfDay value
                                                specifies the arrival time at the facility. if travelDirection
                                                is set to esriNATravelDirectionFromFacility, the timeOfDay
                                                value is the departure time from the facility. The time zone
                                                for timeOfDay is specified by timeOfDayIsUTC.
        -----------------------------------     --------------------------------------------------------------------
        time_of_day_is_utc                      The time zone or zones of the timeOfDay parameter. When
                                                set to false, which is the default value, the timeOfDay
                                                parameter refers to the time zone or zones in which the
                                                facilities are located. Therefore, the start or end times
                                                of the service areas are staggered by time zone.
        -----------------------------------     --------------------------------------------------------------------
        travel_direction                        Options for traveling to or from the facility. The
                                                default is defined in the network analysis layer.
                                                Values: esriNATravelDirectionFromFacility |
                                                        esriNATravelDirectionToFacility
        -----------------------------------     --------------------------------------------------------------------
        return_z                                If true, Z values will be included in saPolygons and saPolylines
                                                geometry if the network dataset is Z-aware. The default is false.
        -----------------------------------     --------------------------------------------------------------------
        overrides                               Optional dictionary. Specify additional settings that can
                                                influence the behavior of the solver.  A list of supported
                                                override settings for each solver and their acceptable values
                                                can be obtained by contacting Esri Technical Support.
        -----------------------------------     --------------------------------------------------------------------
        preserve_objectid                       Optional Boolean.  If True, all objectid values are
                                                maintained.  The default is False.
        -----------------------------------     --------------------------------------------------------------------
        future                                  Optional boolean. If True, a future object will be returned and the process
                                                will not wait for the task to complete. The default is False, which means wait for results.
        -----------------------------------     --------------------------------------------------------------------
        ignore_invalid_locations                If true, the solver will ignore invalid
                                                locations. Otherwise, it will raise an error.
                                                Default is true.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision                      Optional Integer. Use this parameter to specify the number of decimal
                                                places in the response geometries returned by solve operation.
                                                This applies to x/y values only (not m- or z-values).
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_z                    Optional Integer. Use this parameter to specify the number of
                                                decimal places in the response geometries returned by solve operation.
                                                This applies to z values only.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_m                    Optional Integer. Use this parameter to specify the number of
                                                decimal places in the response geometries returned by solve operation.
                                                This applies to m values only.
        -----------------------------------     --------------------------------------------------------------------
        locate_settings                         Optional dictionary containing additional input location settings.
                                                Use this parameter to specify settings that affect how inputs are located,
                                                such as the maximum search distance to use when locating the inputs on the
                                                network or the network sources being used for locating. To restrict locating
                                                on a portion of the source, you can specify a where clause for a source.

                                                The dictionary of parameters can be assigned to the 'default', or to the
                                                'overrides' key which holds the dictionary of parameters for each override, types of override are
                                                'facilities', 'barriers', 'polylineBarriers', 'polygonBarriers'.
                                                Use the :py:class:`~arcgis.network.LocateSettings` class to create the dictionary for each override or
                                                for the default.

                                                .. note::
                                                    'default' has to be present if you want to pass in any locate_settings to the
                                                    service. In addition, locate settings for default have to be complete, meaning
                                                    all properties need to be present.
                                                    For each override, the keys do not have to be complete.

                                                .. note::
                                                    for 'polylineBarriers' and 'polygonBarriers', tolerance and tolerance_units are
                                                    not supported.

                                                .. code-block:: python

                                                    from arcgis.network import LocateSettings
                                                    locate_settings = LocateSettings(tolerance=5000, tolerance_units=ToleranceUnits.meters, allow_auto_relocate=True, sources=[{"name": "Routing_Streets"}])
                                                    result = route_layer.solve(stops=stops, locate_settings={"default": locate_settings.to_dict()})

        -----------------------------------     --------------------------------------------------------------------
        return_empty_results                    Optional boolean. If True, the service will return empty results instead
                                                of the error property when the request fails. The default is False.
        -----------------------------------     --------------------------------------------------------------------
        include_source_information_on_lines     Optional boolean. Specify whether the service will include network source
                                                fields on the output `saPolylines`. Source fields on `saPolylines` are `SourceID`,
                                                `SourceOID`, `FromPosition` and `ToPosition`.

                                                * true—The `saPolylines` property in the JSON response will include network source fields.
                                                * false—The `saPolylines` property in the JSON response will not include network source fields.
                                                The default value is true.

                                                Setting this parameter has no effect if `output_lines` is set to `esriNAOutputLineNone`.
                                                You can set this to false if you don't need network source fields on `saPolylines`
                                                and this will reduce the response size.
        ===================================     ====================================================================


        """
        if not self.properties.layerType == "esriNAServerServiceAreaLayer":
            raise TypeError(
                "The solveServiceArea operation is supported on a network "
                "layer of Service Area type only"
            )

        url = self._url + "/solveServiceArea"
        params = {"f": "json", "facilities": _handle_spatial_inputs(facilities)}

        if travel_mode:
            if isinstance(travel_mode, str):
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=travel_mode
                )
                params["travel_mode"] = travel_mode
            elif isinstance(travel_mode, dict):
                travel_mode = json.dumps(travel_mode)
                params["travel_mode"] = travel_mode
            else:
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=_utils.default_travel_mode(gis=self._gis)
                )
                params["travel_mode"] = travel_mode

        if barriers is not None:
            params["barriers"] = _handle_spatial_inputs(barriers)
        if polyline_barriers is not None:
            params["polylineBarriers"] = _handle_spatial_inputs(polyline_barriers)
        if polygon_barriers is not None:
            params["polygonBarriers"] = _handle_spatial_inputs(polygon_barriers)
        if travel_mode is not None:
            params["travelMode"] = travel_mode
        if attribute_parameter_values is not None:
            params["attributeParameterValues"] = attribute_parameter_values
        if default_breaks is not None:
            params["defaultBreaks"] = default_breaks
        if exclude_sources_from_polygons is not None:
            params["excludeSourcesFromPolygons"] = exclude_sources_from_polygons
        if merge_similar_polygon_ranges is not None:
            params["mergeSimilarPolygonRanges"] = merge_similar_polygon_ranges
        if output_lines is not None:
            params["outputLines"] = output_lines
        if output_polygons is not None:
            params["outputPolygons"] = output_polygons
        if overlap_lines is not None:
            params["overlapLines"] = overlap_lines
        if overlap_polygons is not None:
            params["overlapPolygons"] = overlap_polygons
        if split_lines_at_breaks is not None:
            params["splitLinesAtBreaks"] = split_lines_at_breaks
        if split_polygons_at_breaks is not None:
            params["splitPolygonsAtBreaks"] = split_polygons_at_breaks
        if trim_outer_polygon is not None:
            params["trimOuterPolygon"] = trim_outer_polygon
        if trim_polygon_distance is not None:
            params["trimPolygonDistance"] = trim_polygon_distance
        if trim_polygon_distance_units is not None:
            params["trimPolygonDistanceUnits"] = trim_polygon_distance_units
        if return_facilities is not None:
            params["returnFacilities"] = return_facilities
        if return_barriers is not None:
            params["returnBarriers"] = return_barriers
        if return_polyline_barriers is not None:
            params["returnPolylineBarriers"] = return_polyline_barriers
        if return_polygon_barriers is not None:
            params["returnPolygonBarriers"] = return_polygon_barriers
        if out_sr is not None:
            params["outSR"] = out_sr
        if ignore_invalid_locations is not None:
            params["ignoreInvalidLocations"] = ignore_invalid_locations
        if accumulate_attribute_names is not None:
            params["accumulateAttributeNames"] = accumulate_attribute_names
        if impedance_attribute_name is not None:
            params["impedanceAttributeName"] = impedance_attribute_name
        if restriction_attribute_names is not None:
            params["restrictionAttributeNames"] = restriction_attribute_names
        if restrict_u_turns is not None:
            params["restrictUTurns"] = restrict_u_turns
        if output_geometry_precision is not None:
            params["outputGeometryPrecision"] = output_geometry_precision
        if output_geometry_precision_units is not None:
            params["outputGeometryPrecisionUnits"] = output_geometry_precision_units
        if use_hierarchy is not None:
            params["useHierarchy"] = use_hierarchy
        if time_of_day is not None:
            if isinstance(time_of_day, datetime.datetime):
                time_of_day = f"{time_of_day.timestamp() * 1000}"
            params["timeOfDay"] = time_of_day
        if time_of_day_is_utc is not None:
            params["timeOfDayIsUTC"] = time_of_day_is_utc
        if travel_direction is not None:
            params["travelDirection"] = travel_direction
        if return_z is not None:
            params["returnZ"] = return_z
        if overrides is not None:
            params["overrides"] = overrides
        if preserve_objectid is not None:
            params["preserveObjectID"] = preserve_objectid
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        if geometry_precision_z is not None:
            params["geometryPrecisionZ"] = geometry_precision_z
        if geometry_precision_m is not None:
            params["geometryPrecisionM"] = geometry_precision_m
        if locate_settings is not None:
            params["locateSettings"] = locate_settings
        if return_empty_results is not None:
            params["returnEmptyResults"] = return_empty_results
        if include_source_information_on_lines is not None:
            params["includeSourceInformationOnLines"] = (
                include_source_information_on_lines
            )
        if future:
            f = self._run_async(
                self._con.post,
                **{"path": url, "postdata": params},
            )
            return NAJob(future=f, task="Solve Service Area")
        return self._con.post(path=url, postdata=params)


###########################################################################
class ClosestFacilityLayer(NetworkLayer):
    """
    The Closest Facility Network Layer which has common properties of Network
    Layer as well as some attributes unique to Closest Facility Layer
    only.
    """

    def solve_closest_facility(
        self,
        incidents,
        facilities: Union[FeatureSet, Point, list, dict],
        barriers: Optional[Union[Point, FeatureSet, dict[str, Any]]] = None,
        polyline_barriers: Optional[Union[Polyline, FeatureSet, dict[str, Any]]] = None,
        polygon_barriers: Optional[Union[Polygon, FeatureSet, dict[str, Any]]] = None,
        travel_mode: Optional[str] = None,
        attribute_parameter_values: Optional[Union[str, list]] = None,
        return_directions: bool = False,
        directions_language: Optional[str] = None,
        directions_style_name: Optional[str] = None,
        directions_length_units: Optional[str] = None,
        directions_time_attribute_name: Optional[str] = None,
        return_cf_routes: bool = True,
        return_facilities: bool = False,
        return_incidents: bool = False,
        return_barriers: bool = False,
        return_polyline_barriers: bool = False,
        return_polygon_barriers: bool = False,
        output_lines: Optional[str] = None,
        default_cutoff: Optional[float] = None,
        default_target_facility_count: Optional[int] = None,
        travel_direction: Optional[str] = None,
        out_sr: Optional[int] = None,
        accumulate_attribute_names: Optional[str] = None,
        impedance_attribute_name: Optional[str] = None,
        restriction_attribute_names: Optional[str] = None,
        restrict_u_turns: Optional[str] = None,
        use_hierarchy: bool = True,
        output_geometry_precision: Optional[str] = None,
        output_geometry_precision_units: Optional[str] = None,
        time_of_day: Optional[datetime.datetime] = None,
        time_of_day_is_utc: Optional[str] = None,
        time_of_day_usage: Optional[str] = None,
        return_z: bool = False,
        overrides: Optional[dict[str, Any]] = None,
        preserve_objectid: bool = False,
        future: bool = False,
        ignore_invalid_locations: bool = True,
        directions_output_type: Optional[str] = None,
        return_traversed_edges: Optional[bool] = None,
        return_traversed_junctions: Optional[bool] = None,
        return_traversed_turns: Optional[bool] = None,
        geometry_precision: Optional[int] = None,
        geometry_precision_z: Optional[int] = None,
        geometry_precision_m: Optional[int] = None,
        locate_settings: Optional[dict] = None,
        return_empty_results: Optional[bool] = False,
    ):
        """The solve operation is performed on a network layer resource of
        type closest facility (layerType is esriNAServerClosestFacilityLayer).
        You can provide arguments to the solve route operation as query
        parameters.

        ===================================     ====================================================================
        **Parameter**                            **Description**
        -----------------------------------     --------------------------------------------------------------------
        facilities                              The set of facilities loaded as network locations
                                                during analysis. Facilities can be specified using
                                                a simple comma / semi-colon based syntax or as a
                                                JSON structure. If facilities are not specified,
                                                preloaded facilities from the map document are used
                                                in the analysis. If an empty json object is passed
                                                ('{}') preloaded facilities are ignored.
        -----------------------------------     --------------------------------------------------------------------
        incidents                               The set of incidents loaded as network locations
                                                during analysis. Incidents can be specified using
                                                a simple comma / semi-colon based syntax or as a
                                                JSON structure. If incidents are not specified,
                                                preloaded incidents from the map document are used
                                                in the analysis.
        -----------------------------------     --------------------------------------------------------------------
        barriers                                The set of barriers loaded as network locations during
                                                analysis. Barriers can be specified using a simple comma
                                                / semi-colon based syntax or as a JSON structure. If
                                                barriers are not specified, preloaded barriers from the
                                                map document are used in the analysis. If an empty json
                                                object is passed ('{}') preloaded barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        polyline_barriers                       The set of polyline barriers loaded as network
                                                locations during analysis. If polyline barriers
                                                are not specified, preloaded polyline barriers
                                                from the map document are used in the analysis.
                                                If an empty json object is passed ('{}')
                                                preloaded polyline barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        polygonBarriers                         The set of polygon barriers loaded as network
                                                locations during analysis. If polygon barriers
                                                are not specified, preloaded polygon barriers
                                                from the map document are used in the analysis.
                                                If an empty json object is passed ('{}') preloaded
                                                polygon barriers are ignored.
        -----------------------------------     --------------------------------------------------------------------
        travel_mode                             Travel modes provide override values that help you
                                                quickly and consistently model a vehicle or mode of
                                                transportation. The chosen travel mode must be
                                                preconfigured on the network dataset that the routing
                                                service references.
        -----------------------------------     --------------------------------------------------------------------
        attribute_parameter_values              A set of attribute parameter values that
                                                can be parameterized to determine which
                                                network elements can be used by a vehicle.
        -----------------------------------     --------------------------------------------------------------------
        return_directions                       If true, directions will be generated and returned
                                                with the analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        directions_language                     The language to be used when computing directions.
                                                The default is the language of the server's operating
                                                system. The list of supported languages can be found
                                                in REST layer description.
        -----------------------------------     --------------------------------------------------------------------
        directions_output_type                  Defines content, verbosity of returned
                                                directions. The default is esriDOTStandard.
                                                Values: esriDOTComplete | esriDOTCompleteNoEvents
                                                | esriDOTInstructionsOnly | esriDOTStandard |
                                                esriDOTSummaryOnly
        -----------------------------------     --------------------------------------------------------------------
        directions_style_name                   The style to be used when returning the directions.
                                                The default is as defined in the network layer. The
                                                list of supported styles can be found in REST
                                                layer description.
        -----------------------------------     --------------------------------------------------------------------
        directions_length_units                 The length units to use when computing directions.
                                                The default is as defined in the network layer.
                                                Values: esriNAUFeet | esriNAUKilometers |
                                                esriNAUMeters | esriNAUMiles |
                                                esriNAUNauticalMiles | esriNAUYards |
                                                esriNAUUnknown
        -----------------------------------     --------------------------------------------------------------------
        directions_time_attribute_name          The name of network attribute to use for
                                                the drive time when computing directions.
                                                The default is as defined in the network
                                                layer.
        -----------------------------------     --------------------------------------------------------------------
        return_cf_routes                        If true, closest facilities routes will be returned
                                                with the analysis results. Default is true.
        -----------------------------------     --------------------------------------------------------------------
        return_facilities                       If true, facilities  will be returned with the
                                                analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_incidents                        If true, incidents will be returned with the
                                                analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_barriers                         If true, barriers will be returned with the analysis
                                                results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_polyline_barriers                If true, polyline barriers will be returned
                                                with the analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        return_polygon_barriers                 If true, polygon barriers will be returned with
                                                the analysis results. Default is false.
        -----------------------------------     --------------------------------------------------------------------
        output_lines                            The type of output lines to be generated in the result.
                                                The default is as defined in the network layer.
                                                Values: esriNAOutputLineTrueShape |
                                                esriNAOutputLineTrueShapeWithMeasure |
                                                esriNAOutputLineStraight | esriNAOutputLineNone
        -----------------------------------     --------------------------------------------------------------------
        default_cutoff                          The default cutoff value to stop traversing.
        -----------------------------------     --------------------------------------------------------------------
        default_target_facility_count           The default number of facilities to find.
        -----------------------------------     --------------------------------------------------------------------
        travel_direction                        Options for traveling to or from the facility.
                                                The default is defined in the network layer.
                                                Values: esriNATravelDirectionFromFacility |
                                                esriNATravelDirectionToFacility
        -----------------------------------     --------------------------------------------------------------------
        out_sr                                  The spatial reference of the geometries returned with the
                                                analysis results.
        -----------------------------------     --------------------------------------------------------------------
        accumulate_attribute_names              The list of network attribute names to be
                                                accumulated with the analysis. The default is
                                                as defined in the network layer. The value
                                                should be specified as a comma separated list
                                                of attribute names. You can also specify a
                                                value of none to indicate that no network
                                                attributes should be accumulated.
        -----------------------------------     --------------------------------------------------------------------
        impedance_attribute_name                The network attribute name to be used as the
                                                impedance attribute in analysis. The default is
                                                as defined in the network layer.
        -----------------------------------     --------------------------------------------------------------------
        restriction_attribute_names             The list of network attribute names to be
                                                used as restrictions with the analysis. The
                                                default is as defined in the network layer.
                                                The value should be specified as a comma
                                                separated list of attribute names. You can
                                                also specify a value of none to indicate that
                                                no network attributes should be used as
                                                restrictions.
        -----------------------------------     --------------------------------------------------------------------
        restrict_u_turns                        Specifies how U-Turns should be restricted in the
                                                analysis. The default is as defined in the network
                                                layer. Values: esriNFSBAllowBacktrack |
                                                esriNFSBAtDeadEndsOnly | esriNFSBNoBacktrack |
                                                esriNFSBAtDeadEndsAndIntersections
        -----------------------------------     --------------------------------------------------------------------
        use_hierarchy                           If true, the hierarchy attribute for the network should
                                                be used in analysis. The default is as defined in the
                                                network layer.
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision               The precision of the output geometry after
                                                generalization. If 0, no generalization of
                                                output geometry is performed. The default is
                                                as defined in the network service
                                                configuration.
        -----------------------------------     --------------------------------------------------------------------
        output_geometry_precision_units         The units of the output geometry
                                                precision. The default value is
                                                esriUnknownUnits. Values: esriUnknownUnits
                                                | esriCentimeters | esriDecimalDegrees |
                                                esriDecimeters | esriFeet | esriInches |
                                                esriKilometers | esriMeters | esriMiles |
                                                esriMillimeters | esriNauticalMiles |
                                                esriPoints | esriYards
        -----------------------------------     --------------------------------------------------------------------
        time_of_day                             Arrival or departure date and time. Values: specified by
                                                number of milliseconds since midnight Jan 1st, 1970, UTC.
        -----------------------------------     --------------------------------------------------------------------
        time_of_day_is_utc                      The time zone of the timeOfDay parameter. By setting
                                                timeOfDayIsUTC to true, the timeOfDay parameter refers
                                                to Coordinated Universal Time (UTC). Choose this option
                                                if you want to find what's nearest for a specific time,
                                                such as now, but aren't certain in which time zone the
                                                facilities or incidents will be located.
        -----------------------------------     --------------------------------------------------------------------
        time_of_day_usage                       Defines the way timeOfDay value is used. The default
                                                is as defined in the network layer.
                                                Values: esriNATimeOfDayUseAsStartTime |
                                                esriNATimeOfDayUseAsEndTime
        -----------------------------------     --------------------------------------------------------------------
        return_z                                If true, Z values will be included in the returned routes and
                                                compressed geometry if the network dataset is Z-aware.
                                                The default is false.
        -----------------------------------     --------------------------------------------------------------------
        overrides                               Optional dictionary. Specify additional settings that can influence
                                                the behavior of the solver.  A list of supported override settings
                                                for each solver and their acceptable values can be obtained by
                                                contacting Esri Technical Support.
        -----------------------------------     --------------------------------------------------------------------
        preserve_objectid                       Optional Boolean.  If True, all objectid values are
                                                maintained. The default is False.
        -----------------------------------     --------------------------------------------------------------------
        future                                  Optional boolean. If True, a future object will be returned and the process
                                                will not wait for the task to complete. The default is False,
                                                which means wait for results.
        -----------------------------------     --------------------------------------------------------------------
        ignore_invalid_locations                If true, the solver will ignore invalid
                                                locations. Otherwise, it will raise an error.
                                                Default is true.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_edges                  Optional boolean. Specify whether traversed edges will be returned
                                                by the service.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_junctions              Optional boolean. Specify whether traversed junctions will be
                                                returned by the service.
        -----------------------------------     --------------------------------------------------------------------
        return_traversed_turns                  Optional boolean. Specify whether traversed turns will be returned
                                                by the service.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision                      Optional Integer. Use this parameter to specify the number
                                                of decimal places in the response geometries returned by solve operation.
                                                This applies to x/y values only (not m- or z-values).
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_z                    Optional Integer. Use this parameter specify the number of decimal
                                                places in the response geometries returned by solve operation.
                                                This applies to z-value only.
        -----------------------------------     --------------------------------------------------------------------
        geometry_precision_m                    Optional Integer. Use this parameter to specify the number of decimal
                                                places in the response geometries returned by solve operation.
                                                This applies to m-value only.
        -----------------------------------     --------------------------------------------------------------------
        locate_settings                         Optional dictionary containing additional input location settings.
                                                Use this parameter to specify settings that affect how inputs are located,
                                                such as the maximum search distance to use when locating the inputs on the
                                                network or the network sources being used for locating. To restrict locating
                                                on a portion of the source, you can specify a where clause for a source.

                                                The dictionary of parameters can be assigned to the 'default', or to the
                                                'overrides' key which holds the dictionary of parameters for each override, types of override are
                                                'incidents', 'facilities', 'barriers', 'polylineBarriers', 'polygonBarriers'.
                                                Use the :py:class:`~arcgis.network.LocateSettings` class to create the dictionary for each override or
                                                for the default.

                                                .. note::
                                                    'default' has to be present if you want to pass in any locate_settings to the
                                                    service. In addition, locate settings for default have to be complete, meaning
                                                    all properties need to be present.
                                                    For each override, the keys do not have to be complete.

                                                .. note::
                                                    for 'polylineBarriers' and 'polygonBarriers', tolerance and tolerance_units are
                                                    not supported.

                                                .. code-block:: python

                                                    from arcgis.network import LocateSettings
                                                    locate_settings = LocateSettings(tolerance=5000, tolerance_units=ToleranceUnits.meters, allow_auto_relocate=True, sources=[{"name": "Routing_Streets"}])
                                                    result = route_layer.solve(stops=stops, locate_settings={"default": locate_settings.to_dict()})
        -----------------------------------     --------------------------------------------------------------------
        return_empty_results                    Optional boolean. If True, the service will return empty results instead
                                                of the error property when the request fails. The default is False.
        ===================================     ====================================================================


        """

        if not self.properties.layerType == "esriNAServerClosestFacilityLayer":
            raise TypeError(
                "The solveClosestFacility operation is supported on a network "
                "layer of Closest Facility type only"
            )

        url = self._url + "/solveClosestFacility"
        params = {
            "f": "json",
            "facilities": _handle_spatial_inputs(facilities),
            "incidents": _handle_spatial_inputs(incidents),
        }

        if travel_mode:
            if isinstance(travel_mode, str):
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=travel_mode
                )
                params["travel_mode"] = travel_mode
            elif isinstance(travel_mode, dict):
                travel_mode = json.dumps(travel_mode)
                params["travel_mode"] = travel_mode
            else:
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=_utils.default_travel_mode(gis=self._gis)
                )
                params["travel_mode"] = travel_mode

        if barriers is not None:
            params["barriers"] = _handle_spatial_inputs(barriers)
        if polyline_barriers is not None:
            params["polylineBarriers"] = _handle_spatial_inputs(polyline_barriers)
        if polygon_barriers is not None:
            params["polygonBarriers"] = _handle_spatial_inputs(polygon_barriers)
        if travel_mode is not None:
            params["travelMode"] = travel_mode
        if attribute_parameter_values is not None:
            params["attributeParameterValues"] = attribute_parameter_values
        if return_directions is not None:
            params["returnDirections"] = return_directions
        if directions_language is not None:
            params["directionsLanguage"] = directions_language
        if directions_style_name is not None:
            params["directionsStyleName"] = directions_style_name
        if directions_length_units is not None:
            params["directionsLengthUnits"] = directions_length_units
        if directions_time_attribute_name is not None:
            params["directionsTimeAttributeName"] = directions_time_attribute_name
        if directions_output_type is not None:
            params["directionsOutputType"] = directions_output_type
        if return_cf_routes is not None:
            params["returnCFRoutes"] = return_cf_routes
        if return_facilities is not None:
            params["returnFacilities"] = return_facilities
        if return_incidents is not None:
            params["returnIncidents"] = return_incidents
        if return_barriers is not None:
            params["returnBarriers"] = return_barriers
        if return_polyline_barriers is not None:
            params["returnPolylineBarriers"] = return_polyline_barriers
        if return_polygon_barriers is not None:
            params["returnPolygonBarriers"] = return_polygon_barriers
        if output_lines is not None:
            params["outputLines"] = output_lines
        if default_cutoff is not None:
            params["defaultCutoff"] = default_cutoff
        if default_target_facility_count is not None:
            params["defaultTargetFacilityCount"] = default_target_facility_count
        if travel_direction is not None:
            params["travelDirection"] = travel_direction
        if out_sr is not None:
            params["outSR"] = out_sr
        if ignore_invalid_locations is not None:
            params["ignoreInvalidLocations"] = ignore_invalid_locations
        if accumulate_attribute_names is not None:
            params["accumulateAttributeNames"] = accumulate_attribute_names
        if impedance_attribute_name is not None:
            params["impedanceAttributeName"] = impedance_attribute_name
        if restriction_attribute_names is not None:
            params["restrictionAttributeNames"] = restriction_attribute_names
        if restrict_u_turns is not None:
            params["restrictUTurns"] = restrict_u_turns
        if use_hierarchy is not None:
            params["useHierarchy"] = use_hierarchy
        if output_geometry_precision is not None:
            params["outputGeometryPrecision"] = output_geometry_precision
        if output_geometry_precision_units is not None:
            params["outputGeometryPrecisionUnits"] = output_geometry_precision_units
        if time_of_day is not None:
            if isinstance(time_of_day, datetime.datetime):
                time_of_day = f"{time_of_day.timestamp() * 1000}"
            params["timeOfDay"] = time_of_day
        if time_of_day_is_utc is not None:
            params["timeOfDayIsUTC"] = time_of_day_is_utc
        if time_of_day_usage is not None:
            params["timeOfDayUsage"] = time_of_day_usage
        if return_z is not None:
            params["returnZ"] = return_z
        if overrides is not None:
            params["overrides"] = overrides
        if preserve_objectid is not None:
            params["preserveObjectID"] = preserve_objectid
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        if geometry_precision_z is not None:
            params["geometryPrecisionZ"] = geometry_precision_z
        if geometry_precision_m is not None:
            params["geometryPrecisionM"] = geometry_precision_m
        if return_traversed_edges is not None:
            params["returnTraversedEdges"] = return_traversed_edges
        if return_traversed_junctions is not None:
            params["returnTraversedJunctions"] = return_traversed_junctions
        if return_traversed_turns is not None:
            params["returnTraversedTurns"] = return_traversed_turns
        if locate_settings is not None:
            params["locateSettings"] = locate_settings
        if return_empty_results is not None:
            params["returnEmptyResults"] = return_empty_results
        if future:
            f = self._run_async(self._con.post, **{"path": url, "postdata": params})
            return NAJob(future=f, task="Solve Closest Facility")
        return self._con.post(path=url, postdata=params)


###########################################################################
class ODCostMatrixLayer(NetworkLayer):
    """
    OD Cost Matrix Layer is part of the Network Layer services.  It allows users
    to generate cost matrix data for a given set of input.
    """

    def solve_od_cost_matrix(
        self,
        origins,
        destinations,
        default_cutoff: Optional[float] = None,
        default_target_destination_count: Optional[int] = None,
        travel_mode: Optional[str] = None,
        output_type: str = "Sparse Matrix",
        time_of_day: Optional[datetime.datetime] = None,
        time_of_day_is_utc: Optional[str] = None,
        barriers: Optional[Union[Point, FeatureSet, dict[str, Any]]] = None,
        polyline_barriers: Optional[Union[Polyline, FeatureSet, dict[str, Any]]] = None,
        polygon_barriers: Optional[Union[Polygon, FeatureSet, dict[str, Any]]] = None,
        impedance_attribute_name: Optional[str] = None,
        accumulate_attribute_names: Optional[str] = None,
        restriction_attribute_names: Optional[str] = None,
        attribute_parameter_values: Optional[str] = None,
        restrict_u_turns: Optional[str] = None,
        use_hierarchy: bool = True,
        return_origins: bool = False,
        return_destinations: bool = False,
        return_barriers: bool = False,
        return_polyline_barriers: bool = False,
        return_polygon_barriers: bool = False,
        out_sr: Optional[int] = None,
        ignore_invalid_locations: bool = True,
        return_z: bool = False,
        overrides: Optional[dict[str, Any]] = None,
        future: bool = False,
        geometry_precision: Optional[int] = None,
        geometry_precision_z: Optional[int] = None,
        locate_settings: Optional[dict] = None,
        return_empty_results: Optional[bool] = False,
    ):
        """

        The Origin Destination Cost Matrix service helps you to create an
        origin-destination (OD) cost matrix from multiple origins to
        multiple destinations. An Origin Destination Cost Matrix is a table
        that contains the cost, such as the travel time or travel distance,
        from every origin to every destination. Additionally, it ranks the
        destinations that each origin connects to in ascending order based
        on the minimum cost required to travel from that origin to each
        destination. When generating an OD Cost Matrix, you can optionally
        specify the maximum number of destinations to find for each origin
        and the maximum time or distance to travel when searching for
        destinations.

        The results from the Origin Destination Cost Matrix service often
        become input for other spatial analyses where the cost to travel on
        the street network is more appropriate than straight-line cost.

        The travel time and/or distance for each origin-destination pair is
        stored in the output matrix (default) or as part of the attributes
        of the output lines, which can have no shapes or a straight line
        shape. Even though the lines are straight, they always store the
        travel time and/or travel distance based on the street network, not
        based on Euclidean distance.

        ====================================        ====================================================================
        **Parameter**                               **Description**
        ------------------------------------        --------------------------------------------------------------------
        origins                                     Required FeatureLayer/SeDF/FeatureSet.
                                                    Specifies the starting points from which to travel to the destinations.
        ------------------------------------        --------------------------------------------------------------------
        destinations                                Required FeatureLayer/SeDF/FeatureSet.
                                                    Specifies the ending point locations to travel to from the origins.
        ------------------------------------        --------------------------------------------------------------------
        default_cutoff                              Optional Float. Specify the travel time or travel distance value at
                                                    which to stop searching for destinations. The default value is
                                                    `None` which means to search until all destinations are found for
                                                    every origin. The units are the same as the impedance attribute
                                                    units.
        ------------------------------------        --------------------------------------------------------------------
        default_target_destination_count            Optional Integer. Specify the number of destinations to find per
                                                    origin. The default value is `None` which means to search until all
                                                    destinations are found for every origin.
        ------------------------------------        --------------------------------------------------------------------
        travel_mode                                 Optional String. Choose the mode of transportation for the analysis.
        ------------------------------------        --------------------------------------------------------------------
        output_type                                 Optional String. Specify the type of output returned by the service.
                                                    Allowed value: `Sparse Matrix` (default), `Straight Lines`, or
                                                    `No Lines`.
        ------------------------------------        --------------------------------------------------------------------
        time_of_day                                 Optional Datetime. The `time_of_day` value represents the time at which
                                                    the travel begins from the input origins.
                                                    If a value of `now` is passed, the travel begins at current time.
        ------------------------------------        --------------------------------------------------------------------
        time_of_day_is_utc                          Optional Boolean. Specify the time zone or zones of the
                                                    `time_of_day` parameter. The default is as defined
                                                    in the network layer.
        ------------------------------------        --------------------------------------------------------------------
        barriers                                    Optional FeatureLayer/SeDF/FeatureSet. Specify one or more points that act as
                                                    temporary restrictions or represent additional time or distance that
                                                    may be required to travel on the underlying streets.
        ------------------------------------        --------------------------------------------------------------------
        polyline_barriers                           Optional FeatureLayer/SeDF/FeatureSet. Specify one or more lines that prohibit
                                                    travel anywhere the lines intersect the streets.
        ------------------------------------        --------------------------------------------------------------------
        polygon_barriers                            Optional FeatureLayer/SeDF/FeatureSet. Specify polygons that either prohibit
                                                    travel or proportionately scale the time or distance required to
                                                    travel on the streets intersected by the polygons.
        ------------------------------------        --------------------------------------------------------------------
        impedance_attribute_name                    Optional String. Specify the impedance. The default is as defined
                                                    in the network layer.
        ------------------------------------        --------------------------------------------------------------------
        accumulate_attribute_names                  Optional String. Specify whether the service should accumulate
                                                    values other than the value specified for `impedance_attribute_names`.

                                                    The default is as defined in the network layer. The parameter value
                                                    should be specified as a comma-separated list of names.
        ------------------------------------        --------------------------------------------------------------------
        restriction_attribute_names                 Optional String. Specify which restrictions should be honored by the service.
        ------------------------------------        --------------------------------------------------------------------
        attribute_parameter_values                  Optional String. Specify additional values required by an attribute or restriction.
        ------------------------------------        --------------------------------------------------------------------
        restrict_u_turns                            Optional String. Restrict or permit the route from making U-turns at
                                                    junctions. The default is as defined in the network layer.

                                                    Values:

                                                    * *esriNFSBAllowBacktrack*
                                                    * *esriNFSBAtDeadEndsOnly*
                                                    * *esriNFSBNoBacktrack*
                                                    * *esriNFSBAtDeadEndsAndIntersections*
        ------------------------------------        --------------------------------------------------------------------
        use_hierarchy                               Optional Boolean. Specify whether hierarchy should be used when
                                                    finding the shortest paths. The default value is true.
        ------------------------------------        --------------------------------------------------------------------
        return_origins                              Optional Boolean. Specify whether origins will be returned by the service.
                                                    The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        return_destinations                         Optional Boolean. Specify whether origins will be returned by the service.
                                                    The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        return_barriers                             Optional Boolean. Specify whether barriers will be returned by the service.
                                                    The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        return_polyline_barriers                    Optional Boolean. Specify whether polyline barriers will be returned
                                                    by the service. The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        return_polygon_barriers                     Optional Boolean. Specify whether polygon barriers will be returned
                                                    by the service. The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        out_sr                                      Optional Integer. Specify the spatial reference of the geometries.
        ------------------------------------        --------------------------------------------------------------------
        ignore_invalid_locations                    Optional Boolean. Specify whether invalid input locations should be
                                                    ignored when finding the best solution. The default is True.
        ------------------------------------        --------------------------------------------------------------------
        return_z                                    Optional Boolean. Include z values for the returned geometries if supported
                                                    by the underlying network. The default value is false.
        ------------------------------------        --------------------------------------------------------------------
        overrides                                   Optional Dict. Specify additional settings that can influence the behavior
                                                    of the solver.
        ------------------------------------        --------------------------------------------------------------------
        future                                      Optional boolean. If True, a future object will be returned and the process
                                                    will not wait for the task to complete. The default is False,
                                                    which means wait for results.
        ------------------------------------        --------------------------------------------------------------------
        geometry_precision                          Optional Integer. Use this parameter to specify the number of decimal
                                                    places in the response geometries returned by solve operation. This
                                                    applies to x/y values only (not m- or z-values).
        ------------------------------------        --------------------------------------------------------------------
        geometry_precision_z                        Optional Integer. Use this parameter specify the number of decimal
                                                    places in the response geometries returned by solve operation. This
                                                    applies to z-value only.
        ------------------------------------        --------------------------------------------------------------------
        locate_settings                             Optional dictionary containing additional input location settings.
                                                    Use this parameter to specify settings that affect how inputs are located,
                                                    such as the maximum search distance to use when locating the inputs on the
                                                    network or the network sources being used for locating. To restrict locating
                                                    on a portion of the source, you can specify a where clause for a source.

                                                    The dictionary of parameters can be assigned to the 'default', or to the
                                                    'overrides' key which holds the dictionary of parameters for each override, types of override are
                                                    'origins', 'destinations', 'barriers', 'polylineBarriers', 'polygonBarriers'.
                                                    Use the :py:class:`~arcgis.network.LocateSettings` class to create the dictionary for each override or
                                                    for the default.

                                                    .. note::
                                                        'default' has to be present if you want to pass in any locate_settings to the
                                                        service. In addition, locate settings for default have to be complete, meaning
                                                        all properties need to be present.
                                                        For each override, the keys do not have to be complete.

                                                    .. note::
                                                        for 'polylineBarriers' and 'polygonBarriers', tolerance and tolerance_units are
                                                        not supported.

                                                    .. code-block:: python

                                                        # Usage example:
                                                        >>> from arcgis.network import LocateSettings
                                                        >>> locate_settings = LocateSettings(
                                                                                    tolerance=5000,
                                                                                    tolerance_units=ToleranceUnits.meters,
                                                                                    allow_auto_relocate=True,
                                                                                    sources=[
                                                                                        {"name": "Routing_Streets"}
                                                                                    ]
                                                                                )
                                                        >>> result = route_layer.solve(
                                                                            stops=stops,
                                                                            locate_settings={
                                                                                    "default": locate_settings.to_dict()
                                                                                }
                                                                            )
        ------------------------------------        --------------------------------------------------------------------
        return_empty_results                        Optional boolean. If True, the service will return empty results instead
                                                    of the error property when the request fails. The default is False.
        ====================================        ====================================================================

        :return: Dictionary or `NAJob` when `future=True`

        """
        if not self.properties.layerType == "esriNAServerODCostMatrixLayer":
            raise TypeError(
                "The solveODCostMatrix operation is supported on a network "
                "layer of OD Cost Matrix type only"
            )
        url = f"{self._url}/solveODCostMatrix"
        params = {
            "f": "json",
            "origins": _handle_spatial_inputs(origins),
            "destinations": _handle_spatial_inputs(destinations),
        }
        if travel_mode:
            if isinstance(travel_mode, str):
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=travel_mode
                )
                params["travel_mode"] = travel_mode
            elif isinstance(travel_mode, dict):
                travel_mode = json.dumps(travel_mode)
                params["travel_mode"] = travel_mode
            else:
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=_utils.default_travel_mode(gis=self._gis)
                )
                params["travel_mode"] = travel_mode
        allowed_output_types = {
            "esriNAODOutputSparseMatrix": "esriNAODOutputSparseMatrix",
            "Sparse Matrix": "esriNAODOutputSparseMatrix",
            "esriNAODOutputStraightLines": "esriNAODOutputStraightLines",
            "Straight Lines": "esriNAODOutputStraightLines",
            "esriNAODOutputNoLines": "esriNAODOutputNoLines",
            "No Lines": "esriNAODOutputNoLines",
        }
        if default_cutoff is not None:
            params["defaultCutoff"] = default_cutoff
        if default_target_destination_count is not None:
            params["defaultTargetDestinationCount"] = default_target_destination_count
        if travel_mode is not None:
            params["travelMode"] = travel_mode
        if output_type is not None:
            assert output_type in allowed_output_types
            params["outputType"] = allowed_output_types[output_type]
        if time_of_day is not None:
            if isinstance(time_of_day, datetime.datetime):
                time_of_day = f"{time_of_day.timestamp() * 1000}"
            params["timeOfDay"] = time_of_day
        if time_of_day_is_utc is not None:
            params["timeOfDayIsUTC"] = time_of_day_is_utc
        if barriers is not None:
            params["barriers"] = _handle_spatial_inputs(barriers)
        if polyline_barriers is not None:
            params["polylineBarriers"] = _handle_spatial_inputs(polyline_barriers)
        if polygon_barriers is not None:
            params["polygonBarriers"] = _handle_spatial_inputs(polygon_barriers)
        if impedance_attribute_name is not None:
            params["impedanceAttributeName"] = impedance_attribute_name
        if accumulate_attribute_names is not None:
            params["accumulateAttributeNames"] = accumulate_attribute_names
        if restriction_attribute_names is not None:
            params["restrictionAttributeNames"] = restriction_attribute_names
        if attribute_parameter_values is not None:
            params["attributeParameterValues"] = attribute_parameter_values
        if restrict_u_turns is not None:
            params["restrictUTurns"] = restrict_u_turns
        if use_hierarchy is not None:
            params["useHierarchy"] = use_hierarchy
        if return_origins is not None:
            params["returnOrigins"] = return_origins
        if return_destinations is not None:
            params["returnDestinations"] = return_destinations
        if return_barriers is not None:
            params["returnBarriers"] = return_barriers
        if return_polyline_barriers is not None:
            params["returnPolylineBarriers"] = return_polyline_barriers
        if return_polygon_barriers is not None:
            params["returnPolygonBarriers"] = return_polygon_barriers
        if out_sr is not None:
            params["outSR"] = out_sr
        if ignore_invalid_locations is not None:
            params["ignoreInvalidLocations"] = ignore_invalid_locations
        if return_z is not None:
            params["returnZ"] = return_z
        if overrides is not None:
            params["overrides"] = overrides
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        if geometry_precision_z is not None:
            params["geometryPrecisionZ"] = geometry_precision_z
        if locate_settings is not None:
            params["locateSettings"] = locate_settings
        if return_empty_results is not None:
            params["returnEmptyResults"] = return_empty_results

        if future:
            f = self._run_async(self._con.post, **{"path": url, "postdata": params})
            return NAJob(future=f, task="Solve OD Cost Matrix")
        return self._con.post(path=url, postdata=params)

    # ----------------------------------------------------------------------
    def retrieve_travel_modes(self):
        """
        Identify all the valid travel modes that have been defined on the
        network dataset or in the portal if the GIS server is federated

        :return: Dictionary

        """
        from arcgis._impl.common._isd import InsensitiveDict

        url = self._url + "/retrieveTravelModes"
        params = {"f": "json"}
        return InsensitiveDict(self._con.get(path=url, params=params))


###########################################################################
class NetworkDataset(_GISResource):
    """
    A network dataset containing a collection of network layers including route layers,
    service area layers and closest facility layers.
    """

    def __init__(self, url, gis=None):
        if gis is None:
            from arcgis.env import active_gis

            gis = active_gis
        if gis:
            url = _validate_url(url, gis)
        super(NetworkDataset, self).__init__(url, gis)

        try:
            from ..gis.server._service._adminfactory import AdminServiceGen

            self.service = AdminServiceGen(service=self, gis=gis)
        except Exception:
            pass
        self._closestFacilityLayers = []
        self._routeLayers = []
        self._serviceAreaLayers = []
        self._odCostMatrix = []
        self._load_layers()

    @classmethod
    def fromitem(cls, item):
        """Creates a network dataset from a 'Network Analysis Service' Item in the GIS"""
        if not item.type == "Network Analysis Service":
            raise TypeError(
                "item must be a type of Network Analysis Service, not " + item.type
            )
        url = _validate_url(item.url, item._gis)
        return cls(url, item._gis)

    # ----------------------------------------------------------------------
    def _load_layers(self):
        """loads the various layer types"""
        self._closestFacilityLayers = []
        self._routeLayers = []
        self._serviceAreaLayers = []
        self._odCostMatrix = []
        params = {
            "f": "json",
        }
        json_dict = self._con.get(path=self._url, params=params)
        for k, v in json_dict.items():
            if k == "routeLayers" and json_dict[k]:
                self._routeLayers = []
                for rl in v:
                    self._routeLayers.append(
                        RouteLayer(url=self._url + "/%s" % rl, gis=self._gis)
                    )
            elif k == "serviceAreaLayers" and json_dict[k]:
                self._serviceAreaLayers = []
                for sal in v:
                    self._serviceAreaLayers.append(
                        ServiceAreaLayer(url=self._url + "/%s" % sal, gis=self._gis)
                    )
            elif k == "closestFacilityLayers" and json_dict[k]:
                self._closestFacilityLayers = []
                for cf in v:
                    self._closestFacilityLayers.append(
                        ClosestFacilityLayer(url=self._url + "/%s" % cf, gis=self._gis)
                    )
            elif k == "odCostMatrixLayers" and json_dict[k]:
                self._odCostMatrix = []
                for cf in v:
                    self._odCostMatrix.append(
                        ODCostMatrixLayer(url=self._url + "/%s" % cf, gis=self._gis)
                    )

    # ----------------------------------------------------------------------
    @property
    def route_layers(self):
        """List of route layers in this network dataset"""
        if self._routeLayers is None:
            self._load_layers()
        return self._routeLayers

    # ----------------------------------------------------------------------
    @property
    def service_area_layers(self):
        """List of service area layers in this network dataset"""
        if self._serviceAreaLayers is None:
            self._load_layers()
        return self._serviceAreaLayers

    # ----------------------------------------------------------------------
    @property
    def closest_facility_layers(self):
        """List of closest facility layers in this network dataset"""
        if self._closestFacilityLayers is None:
            self._load_layers()
        return self._closestFacilityLayers

    @property
    def od_cost_matrix_layers(self):
        """
        List of OD Cost Matrix Layers

        :return: List
        """
        if self._odCostMatrix is None:
            self._load_layers()
        return self._odCostMatrix


###########################################################################
class NetworkDatasetLayer(NetworkLayer):
    """
    The network dataset layer resource represents a single network dataset layer
    in routing services published by ArcGIS Server. It provides basic information
    about the network dataset layer, such as its name, type, locate settings,
    travel modes, and other information as in the JSON syntax below. It also provides
    information about the network dataset, such as name build time, build state,
    network attributes and, network sources.

    .. note::
        This is only available for ArcGIS Enterprise 11.1+
    """

    # -----------------------------------------------------------------------
    def locate(
        self,
        input_locations: Union[FeatureSet, list[Point], str],
        travel_mode: Optional[str] = None,
        locate_settings: Optional[dict] = None,
        barriers: Optional[Union[Point, FeatureSet, dict[str, Any]]] = None,
        polyline_barriers: Optional[Union[Polyline, FeatureSet, dict[str, Any]]] = None,
        polygon_barriers: Optional[Union[Polygon, FeatureSet, dict[str, Any]]] = None,
        return_barriers: bool = False,
        return_polyline_barriers: bool = False,
        return_polygon_barriers: bool = False,
        output_source_field_names: Optional[str] = None,
        out_sr: Optional[int] = None,
        future: bool = False,
    ):
        """
        When performing analysis using routing services, the inputs to an analysis
        rarely fall exactly on top of the edges or junctions of the network dataset
        the service is using. For example, you may be using a network dataset constructed
        from street centerline to power your routing services, and the input points
        you want to analyze are the centroids of parcels in your city. These parcel
        centroids do not fall on top of the street centerline; rather, they are offset
        some distance from the streets. To successfully perform a network analysis
        using your routing services, the routing services must identify the location
        on the network dataset where each analysis input lies. This network location,
        rather than the input's original location, is used in the analysis.
        Typically, the longitude and latitude of the inputs are passed in and the
        routing services compute the location on the network during the solve operation.
        With the locate service, you can compute the locations on the network
        before calling the solve operation.

        The locate service is performed on a network dataset layer resource.
        You can provide arguments to the locate service as query parameters defined
        in the parameters table below. The locate service can be used in scenarios
        such as the following:

        * Reuse location fields during the solve operation - You have a set of regularly serviced customers.
          You can use the locate service to calculate location fields, and use the located inputs in the routing services.
          This helps to speed up routing services since the service doesn't need to locate inputs again and
          you can reuse the locations in multiple places.

        .. note::
            The settings and barriers you use to locate inputs should match the eventual analysis
            settings when you perform routing service; otherwise, the routing services may still
            relocate because the locations are not valid for a different travel mode or with barriers.

        * Compute serviceability - Before you perform a routing request, you can call locate
          to determine serviceability. For example, the mode of travel may only allow service
          inputs that are 500 meters off the streets. You can perform a locate service with
          500 meters as the search tolerance and determine which inputs cannot be serviced
          before you perform a more advanced routing service.

        * Use DistanceToNetworkInMeters to calculate service time - You can gain information from the
          locate service response to fine-tune your routing service settings. For example, if you want to
          know how far each input is off network to perform delivery analysis, and it takes time to go
          from the parked vehicle location to the delivery location, you can use the DistanceToNetworkInMeters
          field for each record in the response. Once you know how far away the actual location is from the
          network, you can use a speed factor to calculate a service time for each input based
          on its distance off the network.

        * Query fields from the underlying source features -The locate service also supports returning additional
          field values from the source features where the inputs are located. For example, you can set different
          curb approaches on the inputs depending on the type of road on which they're located. If the input is
          located on a major road, you can set it to right or left side of the vehicle, depending on the driving
          side of the country where it's located. If the input is located on a local road, either side of curb
          approach will work since a vehicle can cross a local road for a delivery.

        ====================================    ====================================================================
        **Parameter**                           **Description**
        ------------------------------------    --------------------------------------------------------------------
        input_locations                         Required FeatureSet, list of Point geometries, or a comma separated string.
                                                To see the fields that can be included in your Feature Set refer to the
                                                `Locate Service <https://developers.arcgis.com/rest/services-reference/enterprise/locate-service.htm>`_
                                                doc.
        ------------------------------------    --------------------------------------------------------------------
        travel_mode                             Optional string. Travel modes provide override values that help you
                                                quickly and consistently model a vehicle or mode of transportation.
                                                The chosen travel mode must be pre-configured on the network dataset
                                                that the routing service references.
        ------------------------------------    --------------------------------------------------------------------
        locate_settings                         Optional dictionary containing additional input location settings.
                                                Use this parameter to specify settings that affect how inputs are located,
                                                such as the maximum search distance to use when locating the inputs on the
                                                network or the network sources being used for locating. To restrict locating
                                                on a portion of the source, you can specify a where clause for a source.

                                                The dictionary of parameters can be assigned to the 'default', or to the
                                                'overrides' key which holds the dictionary of parameters for each override, types of override are
                                                'inputLocations', 'barriers', 'polylineBarriers', 'polygonBarriers'.
                                                Use the :py:class:`~arcgis.network.LocateSettings` class to create the dictionary for each override or
                                                for the default.

                                                .. note::
                                                    'default' has to be present if you want to pass in any locate_settings to the
                                                    service. In addition, locate settings for default have to be complete, meaning
                                                    all properties need to be present.
                                                    For each override, the keys do not have to be complete.

                                                .. note::
                                                    for 'polyline_barriers' and 'polygon_barriers', tolerance and tolerance_units are
                                                    not supported.

                                                .. code-block:: python

                                                    # Usage Example:

                                                    >>> from arcgis.network import LocateSettings
                                                    >>> locate_settings = LocateSettings(
                                                                tolerance=5000,
                                                                tolerance_units=ToleranceUnits.meters,
                                                                allow_auto_relocate=True,
                                                                sources=[
                                                                    {"name": "Routing_Streets"}
                                                                ]
                                                            )
                                                    >>> result = route_layer.solve(
                                                                        stops=stops,
                                                                        locate_settings={
                                                                            "default": locate_settings.to_dict()
                                                                        }
                                                            )
        ------------------------------------    --------------------------------------------------------------------
        barriers                                Optional Point/FeatureSet. The set of barriers loaded as network
                                                locations during analysis. Barriers can be specified using a simple
                                                comma/semi-colon based syntax or as a JSON structure. If barriers
                                                are not specified, preloaded barriers from the map document are used
                                                in the analysis. If an empty json object is passed ('{}') preloaded
                                                barriers are ignored.
        ------------------------------------    --------------------------------------------------------------------
        polyline_barriers                       Optional Polyline/FeatureSet. The set of polyline barriers loaded
                                                as network locations during analysis. If polyline barriers are not
                                                specified, preloaded polyline barriers from the map document are
                                                used in the analysis. If an empty json object is passed ('{}')
                                                preloaded polyline barriers are ignored.
        ------------------------------------    --------------------------------------------------------------------
        polygon_barriers                        Optional Polygon/FeatureSet. The set of polygon barriers loaded as
                                                network locations during analysis. If polygon barriers are not
                                                specified, preloaded polygon barriers from the map document are used
                                                in the analysis. If an empty json object is passed ('{}') preloaded
                                                polygon barriers are ignored.
        ------------------------------------    --------------------------------------------------------------------
        return_barriers                         Optional boolean. If true, barriers will be returned with the analysis
                                                results. Default is False.
        ------------------------------------    --------------------------------------------------------------------
        return_polyline_barriers                Optional boolean. If true, polyline barriers will be returned with
                                                the analysis results. Default is False.
        ------------------------------------    --------------------------------------------------------------------
        return_polygon_barriers                 Optional boolean. If true, polygon barriers will be returned with
                                                the analysis results. Default is False.
        ------------------------------------    --------------------------------------------------------------------
        output_source_field_names               Optional string.The fields from which the located source feature values
                                                will be retrieved. This parameter is specified as a comma-separated
                                                list of names. The values can be specified as in the example below:

                                                * *outputSourceFieldNames=ROAD_CLASS,FULL_STREET_NAME*

                                                .. note::
                                                    These value are specific to the services published with the ArcGIS
                                                    StreetMap Premium data. The values will be different if you are
                                                    using other data for the analysis.
        ------------------------------------    --------------------------------------------------------------------
        out_sr                                  Optional Integer. Specify the spatial reference of the geometries.
        ------------------------------------    --------------------------------------------------------------------
        future                                  Optional boolean. If True, a future object will be returned and the process
                                                will not wait for the task to complete. The default is False, which means wait for results.
        ====================================    ====================================================================

        :return: Dictionary

        """
        url = self._url + "/locate"
        params = {
            "f": "json",
            "inputLocations": _handle_spatial_inputs(input_locations),
        }

        if travel_mode:
            if isinstance(travel_mode, str):
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=travel_mode
                )
                params["travelMode"] = travel_mode
            elif isinstance(travel_mode, dict):
                # travel_mode = json.dumps(travel_mode)
                params["travelMode"] = travel_mode
            else:
                travel_mode = _utils.find_travel_mode(
                    gis=self._gis, travel_mode=_utils.default_travel_mode(gis=self._gis)
                )
                params["travelMode"] = travel_mode

        if barriers is not None:
            params["barriers"] = _handle_spatial_inputs(barriers)
        if polyline_barriers is not None:
            params["polylineBarriers"] = _handle_spatial_inputs(polyline_barriers)
        if polygon_barriers is not None:
            params["polygonBarriers"] = _handle_spatial_inputs(polygon_barriers)
        if return_polyline_barriers:
            params["returnPolylineBarriers"] = return_polyline_barriers
        if return_polygon_barriers:
            params["returnPolygonBarriers"] = return_polygon_barriers
        if output_source_field_names:
            params["outputSourceFieldNames"] = output_source_field_names
        if out_sr:
            params["outSR"] = out_sr
        if locate_settings:
            params["locateSettings"] = locate_settings
        if return_barriers:
            params["returnBarriers"] = return_barriers

        if future:
            f = self._run_async(self._con.post, **{"path": url, "postdata": params})
            return NAJob(future=f, task="Locate")
        return self._con.post(path=url, params=params)
