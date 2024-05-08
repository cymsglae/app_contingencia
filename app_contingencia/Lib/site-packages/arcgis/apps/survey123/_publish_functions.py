import os
import re
import xml.etree.ElementTree as ET
import arcgis
import uuid
import json
import os
from arcgis.auth import EsriSession
import locale
import unicodedata
import warnings

# =============================================================================================================

""" Map Survey123 question types to default ArcGIS field types """
_field_types = {
    "select1": "esriFieldTypeString",
    "select": "esriFieldTypeString",
    "odk:rank": "esriFieldTypeString",
    "string": "esriFieldTypeString",
    "dateTime": "esriFieldTypeDate",
    "date": "esriFieldTypeDate",
    "time": "esriFieldTypeString",
    "int": "esriFieldTypeInteger",
    "decimal": "esriFieldTypeDouble",
    "barcode": "esriFieldTypeString",
}

# =============================================================================================================


def _get_schema(element):
    """Recursivly loop through the instance node to find schema skeleton"""
    return (
        re.sub("[{][^}]*[}]", "", element.tag),
        dict(map(_get_schema, element)) or element.text,
    )


# =============================================================================================================


def _iter_schema(d, nodeset, layer_name, ns_dict):
    """Traverse schema for multiple geometry questions"""
    geom_count = {}
    for k, v in d.items():
        if isinstance(v, dict):
            geom_count.update(_iter_schema(v, f"{nodeset}/{k}", k, ns_dict))
        else:
            try:
                if (
                    ns_dict[f"/{nodeset}/{k}"] == "geopoint"
                    or ns_dict[f"/{nodeset}/{k}"] == "geotrace"
                    or ns_dict[f"/{nodeset}/{k}"] == "geoshape"
                ):
                    if layer_name not in geom_count:
                        geom_count.update({layer_name: 1})
                    else:
                        geom_count[layer_name] += 1
            except KeyError:
                pass
    return geom_count


# =============================================================================================================


def _duplicate_geometry(xml):
    """Checks if more than 1 geo* question exists in the XLSForm without being in a repeat."""
    root = ET.parse(xml).getroot()
    instance = root.findall(".//{http://www.w3.org/2002/xforms}instance")[0][0]
    model = root.findall(".//{http://www.w3.org/2002/xforms}model")[0]

    name, schema = _get_schema(instance)
    try:
        schema.pop("meta")
    except KeyError:
        pass

    ns_dict = {}
    for x in model:
        if len(x.attrib) > 1 and "nodeset" in x.attrib and "type" in x.attrib:
            if (
                "{http://esri.com/xforms}fieldType" in x.attrib
                and x.attrib["{http://esri.com/xforms}fieldType"] == "null"
            ):
                pass
            else:
                ns_dict.update({x.attrib["nodeset"]: x.attrib["type"]})

    s_geometry = _iter_schema(schema, name, name, ns_dict)
    for layer in s_geometry.keys():
        if s_geometry[layer] > 1:
            return f"Only one geometry field is allowed per layer; {s_geometry[layer]} found in the {layer} layer."

    return None


# =============================================================================================================


def _update_view(schema, relationships, survey, parent, view_service):
    """Update view service definition"""
    form_view_definition = {"layers": [], "tables": []}
    for layer in schema["layers"]:
        form_view_definition["layers"].append(
            {
                "adminLayerInfo": {
                    "viewLayerDefinition": {
                        "sourceServiceName": parent.name,
                        "sourceLayerId": layer["id"],
                        "sourceLayerFields": "*",
                    }
                },
                "name": layer["name"],
            }
        )
    for table in schema["tables"]:
        form_view_definition["tables"].append(
            {
                "adminLayerInfo": {
                    "viewLayerDefinition": {
                        "sourceServiceName": parent.name,
                        "sourceLayerId": table["id"],
                        "sourceLayerFields": "*",
                    }
                },
                "name": table["name"],
            }
        )
    form_view_url = view_service.url.replace("/rest/services", "/rest/admin/services")
    form_view_flcm = arcgis.features.managers.FeatureLayerCollectionManager(
        url=form_view_url, gis=survey._gis, fs=view_service
    )
    try:
        form_view_flcm.add_to_definition(form_view_definition)
    except AttributeError:
        pass
    try:
        form_view_flcm.add_to_definition(relationships)
    except AttributeError:
        pass


# =============================================================================================================


def _add_repeat(
    survey,
    service,
    new_repeat,
    use_non_globalid_relationships,
    view_update,
    view_service,
):
    """On schema update adds new layers/tables to feature service and creates relationship"""
    url = service.url.replace("/rest/services", "/rest/admin/services")
    flcm = arcgis.features.managers.FeatureLayerCollectionManager(
        url=url, gis=survey._gis, fs=service
    )
    add_repeat = {}
    for dict in new_repeat:
        for layer in dict:
            if (
                layer in add_repeat.keys()
                and "rel_only" in list(dict[layer].keys())
                and dict[layer]["relationships"][0]["name"]
                in [x for x in add_repeat[layer]["relationships"]]
            ):
                pass
            elif (
                layer in add_repeat.keys()
                and "rel_only" in list(dict[layer].keys())
                and dict[layer]["relationships"][0]["name"]
                not in [x for x in add_repeat[layer]["relationships"]]
            ):
                add_repeat[layer]["relationships"].extend(dict[layer]["relationships"])
            else:
                add_repeat.update({layer: dict[layer]})

    schema, relationships = _xml2sd(add_repeat, use_non_globalid_relationships)

    try:
        flcm.add_to_definition(schema)
    except AttributeError:
        pass
    try:
        flcm.add_to_definition(relationships)
    except AttributeError:
        pass

    if view_update is True:
        _update_view(schema, relationships, survey, service, view_service)


# =============================================================================================================


def _init_schema(
    survey,
    use_non_globalid_relationships,
    xform,
    table_only,
    create_coded_value_domains,
    enable_sync,
):
    """On initial publish adds schema to empty feature service"""

    # Add to definition (schema)
    url = survey._ssi.url.replace("/rest/services", "/rest/admin/services")
    flcm = arcgis.features.managers.FeatureLayerCollectionManager(
        url=url, gis=survey._gis, fs=survey._ssi
    )
    xml_schema = _xmlschema(
        xform,
        "new",
        survey._gis.properties.isPortal,
        table_only,
        use_non_globalid_relationships,
        create_coded_value_domains,
    )

    if not (isinstance(xml_schema, dict)):
        warnings.warn(*xml_schema, sep="\n")
        exit()

    schema, relationships = _xml2sd(xml_schema, use_non_globalid_relationships)

    try:
        flcm.add_to_definition(schema)
    except AttributeError:
        pass

    try:
        flcm.add_to_definition(relationships)
    except AttributeError:
        pass

    # Update definition (editor tracking)
    try:
        if enable_sync is True:
            capabilities = "Create,Delete,Query,Update,Editing,Extract,Sync"
        else:
            capabilities = "Create,Delete,Query,Update,Editing,Extract"
        flcm.update_definition(
            {
                "hasStaticData": False,
                "editorTrackingInfo": {
                    "enableEditorTracking": True,
                    "enableOwnershipAccessControl": True,
                    "allowOthersToUpdate": True,
                    "allowOthersToDelete": True,
                    "allowAnonymousToQuery": False,
                    "allowAnonymousToUpdate": False,
                    "allowAnonymousToDelete": False,
                },
                "capabilities": capabilities,
            }
        )
    except AttributeError:
        pass

    form_view = survey._gis.content.create_service(
        name=f"survey123_{'a%s' % uuid.uuid4().hex}_form",
        folder=survey._si.ownerFolder,
        is_view=True,
    )
    form_view.update(
        {
            "title": f"{survey._si.title}_form",
            "typeKeywords": f"ArcGIS Server,Data,Feature Access,Feature Service,Service,Singlelayer,Hosted Service,View Service,FieldworkerView,{survey._si.id},Survey123,Survey123 Hub",
        }
    )
    form_view_definition = {"layers": [], "tables": []}
    for layer in survey._ssi.layers:
        form_view_definition["layers"].append(
            {
                "adminLayerInfo": {
                    "viewLayerDefinition": {
                        "sourceServiceName": survey._ssi.name,
                        "sourceLayerId": layer.properties["id"],
                        "sourceLayerFields": "*",
                    }
                },
                "name": layer.properties["name"],
            }
        )
    for table in survey._ssi.tables:
        form_view_definition["tables"].append(
            {
                "adminLayerInfo": {
                    "viewLayerDefinition": {
                        "sourceServiceName": survey._ssi.name,
                        "sourceLayerId": table.properties["id"],
                        "sourceLayerFields": "*",
                    }
                },
                "name": table.properties["name"],
            }
        )
    form_view_url = form_view.url.replace("/rest/services", "/rest/admin/services")
    form_view_flcm = arcgis.features.managers.FeatureLayerCollectionManager(
        url=form_view_url, gis=survey._gis, fs=form_view
    )
    try:
        form_view_flcm.add_to_definition(form_view_definition)
    except AttributeError:
        pass
    try:
        view_def = {
            "serviceDescription": f"Feature service view of form for the survey {survey._si.id}",
            "sourceSchemaChangesAllowed": True,
            "editorTrackingInfo": {
                "enableEditorTracking": True,
                "enableOwnershipAccessControl": True,
                "allowOthersToUpdate": False,
                "allowOthersToDelete": False,
                "allowOthersToQuery": False,
                "allowAnonymousToUpdate": False,
                "allowAnonymousToDelete": False,
            },
            "isUpdatableView": True,
        }
        if survey._gis.properties.isPortal is True:
            # Enterprise
            view_def.update({"capabilities": "Create,Editing"})
        else:
            # Online
            view_def.update({"Capabilities": "Create,Editing"})
        form_view_flcm.update_definition(view_def)
    except AttributeError:
        pass

    survey._si.add_relationship(form_view, "Survey2Service")
    survey._si.delete_relationship(survey._ssi, "Survey2Service")
    survey._si.add_relationship(survey._ssi, "Survey2Data")


# =============================================================================================================


def _modify_schema(
    survey,
    service,
    schema_changes,
    deltas,
    use_non_globalid_relationships,
    update_view=None,
    view_service=None,
):
    """Either applies schema changes to feature service or generates appropriate error message"""
    error_reciept = {"Layer Errors": []}
    error = 0
    layers = deltas.pop("layers")
    if len(layers) > 0:
        if schema_changes is True:
            _add_repeat(
                survey,
                service,
                layers,
                use_non_globalid_relationships,
                update_view,
                view_service,
            )
        else:
            layer = [[y for y in x if "rel_only" not in x[y]] for x in layers]
            [
                error_reciept["Layer Errors"].append(
                    f"Layer not found in feature service: {x[0]}"
                )
                for x in layer
            ]
            error += 1
    else:
        error_reciept.pop("Layer Errors")

    _ssi_layers = service.layers + service.tables
    for layer in deltas:
        error_reciept.update(
            {
                f"{layer} Errors": {
                    "Field Errors": [],
                    "Field Type Errors": [],
                    "Field Length Errors": [],
                    "Geometry Errors": [],
                }
            }
        )
        if schema_changes is True:
            service_layer = [x for x in _ssi_layers if x.properties["name"] == layer][0]
            url = service_layer.url.replace("/rest/services", "/rest/admin/services")
            flm = arcgis.features.managers.FeatureLayerManager(url=url, gis=survey._gis)
        if len(deltas[layer]["fields"]) > 0:
            if schema_changes is True:
                # Covers new field and field name change
                flm.add_to_definition({"fields": deltas[layer]["fields"]})
            else:
                [
                    error_reciept[f"{layer} Errors"]["Field Errors"].append(
                        f"Field not found in the feature service for the {x['name']} question."
                    )
                    for x in deltas[layer]["fields"]
                ]
                error += 1
        else:
            error_reciept[f"{layer} Errors"].pop("Field Errors")
        if len(deltas[layer]["domains"]) > 0:
            if schema_changes is True:
                # Covers all domain deltas
                domains = {
                    "fields": [
                        {"domain": x["schema"]["domain"], "name": x["schema"]["name"]}
                        for x in deltas[layer]["domains"]
                    ]
                }
                flm.update_definition(domains)
            else:
                choices = [
                    [y["name"] for y in x["choices"]] for x in deltas[layer]["domains"]
                ]
                ch = []
                for cl in choices:
                    for choice in cl:
                        ch.append(choice)
                [
                    warnings.warn(
                        f"Warning: Choice {x} not found in the feature service domain."
                    )
                    for x in ch
                ]
        if len(deltas[layer]["fieldalias"]) > 0 and schema_changes is True:
            # Covers all field alias updates
            alias = {
                "fields": [
                    {"alias": x["alias"], "name": x["name"]}
                    for x in deltas[layer]["fieldalias"]
                ]
            }
            flm.update_definition(alias)
        if len(deltas[layer]["fieldtype"]) > 0:
            [
                error_reciept[f"{layer} Errors"]["Field Type Errors"].append(
                    f"Field type {x['xmltype']} for question {x['fieldname']} does not match {x['servicetype']} for field {x['fieldname']} in {x['layer']}."
                )
                for x in deltas[layer]["fieldtype"]
            ]
        else:
            error_reciept[f"{layer} Errors"].pop("Field Type Errors")
        if len(deltas[layer]["fieldlength"]) > 0:
            [
                error_reciept[f"{layer} Errors"]["Field Length Errors"].append(
                    f"Field length {x['xmllength']} for {x['fieldname']} exceeds length {x['fieldlength']} in the {x['layer']} layer."
                )
                for x in deltas[layer]["fieldlength"]
            ]
        else:
            error_reciept[f"{layer} Errors"].pop("Field Length Errors")
        if len(deltas[layer]["geometry"]) > 0:
            [
                error_reciept[f"{layer} Errors"]["Geometry Errors"].append(
                    f"{x['xmlgeom']['geometryType']} requires a feature layer but {x['xmllayer']} is a table."
                )
                for x in deltas[layer]["geometry"]
                if "xmllayer" in list(x.keys())
            ]
            [
                error_reciept[f"{layer} Errors"]["Geometry Errors"].append(
                    f"Incompatible geometry types: {x['xmlgeometry']['geometryType']} set in the survey does not match {x['servicegeometry']['geometryType']} in the {x['xmllayer']} layer."
                )
                for x in deltas[layer]["geometry"]
                if "servicegeometry" in list(x.keys())
            ]
            error += 1
        else:
            error_reciept[f"{layer} Errors"].pop("Geometry Errors")

    if error > 0:
        return json.dumps(error_reciept, indent=2)


# =============================================================================================================


def _get_version():
    """Identifies the current version of Survey123 Connect"""
    url = "https://doc.arcgis.com/en/survey123/versions.json"
    session = EsriSession()
    response = session.get(url=url)
    for version in response.json()["secured"]["windows64_connect"]["versions"]:
        return ".".join(
            ".".join(
                response.json()["secured"]["windows64_connect"]["versions"][version][
                    "url"
                ]
                .split("/")[-1]
                .split("_")[2:5]
            ).split(".")[0:3]
        )


# =============================================================================================================


def _schema_parity(
    survey, service, xform, table_only, use_non_globalid_relationships, parent_layer
):
    """Identify deltas between the XForm and feature service"""
    if use_non_globalid_relationships is None:
        use_non_globalid_relationships = _id_relationships(service, parent_layer)

    service_schema = {}

    for layer in list(service.layers + service.tables):
        service_schema.update(
            {
                layer.properties["name"]: {
                    "fields": layer.properties["fields"],
                    "id": layer.properties["id"],
                }
            }
        )
        if "relationships" in list(layer.properties.keys()):
            service_schema[layer.properties["name"]].update(
                {"relationships": layer.properties["relationships"]}
            )

        if "geometryType" in list(layer.properties.keys()):
            service_schema[layer.properties["name"]].update(
                {"geometryType": layer.properties["geometryType"]}
            )

    xml_schema = _xmlschema(
        xform,
        "submission",
        survey._gis.properties.isPortal,
        table_only,
        use_non_globalid_relationships,
        existing_schema=service_schema,
    )

    deltas = {"layers": []}

    for xml_layer in xml_schema:
        if xml_layer not in list(service_schema.keys()):
            new_layer = {xml_layer: xml_schema[xml_layer]}
            for relationship in xml_schema[xml_layer]["relationships"]:
                parent_layer_relationship = [
                    {
                        x: {
                            "id": xml_schema[x]["id"],
                            "rel_only": True,
                            "relationships": [
                                y
                                for y in xml_schema[x]["relationships"]
                                if y["relatedTableId"] == xml_schema[xml_layer]["id"]
                            ],
                        }
                    }
                    for x in xml_schema
                    if xml_schema[x]["id"] == relationship["relatedTableId"]
                ][0]
                new_layer.update(parent_layer_relationship)

            deltas["layers"].append(new_layer)
        else:
            service_fields = {}
            for field in service_schema[xml_layer]["fields"]:
                service_fields.update(
                    {field["name"]: {"type": field["type"], "alias": field["alias"]}}
                )
                if "domain" in list(field.keys()):
                    service_fields[field["name"]].update({"domain": field["domain"]})
                if "length" in list(field.keys()):
                    service_fields[field["name"]].update({"length": field["length"]})
            deltas.update(
                {
                    xml_layer: {
                        "fields": [],
                        "fieldalias": [],
                        "fieldtype": [],
                        "fieldlength": [],
                        "domains": [],
                        "geometry": [],
                    }
                }
            )

            for field in xml_schema[xml_layer]["fields"]:
                if field["name"] not in list(service_fields.keys()):
                    deltas[xml_layer]["fields"].append(field)
                elif field["alias"] != service_fields[field["name"]]["alias"]:
                    deltas[xml_layer]["fieldalias"].append(
                        {"alias": field["alias"], "name": field["name"]}
                    )
                elif field["type"] != service_fields[field["name"]]["type"]:
                    deltas[xml_layer]["fieldtype"].append(
                        {
                            "layer": xml_layer,
                            "fieldname": field["name"],
                            "xmltype": field["type"],
                            "servicetype": field["type"],
                            "field": field,
                        }
                    )
                elif (
                    "length" in list(field.keys())
                    and field["length"] is not None
                    and field["length"] > service_fields[field["name"]]["length"]
                    and field["type"] == "esriFieldTypeString"
                ):
                    deltas[xml_layer]["fieldlength"].append(
                        {
                            "layer": xml_layer,
                            "fieldname": field["name"],
                            "fieldlength": service_fields[field["name"]]["length"],
                            "xmllength": field["length"],
                            "field": field,
                        }
                    )
                elif (
                    "domain" in list(service_fields[field["name"]].keys())
                    and field["domain"] is not None
                ):
                    domains = {
                        x["code"]: x["name"]
                        for x in service_fields[field["name"]]["domain"]["codedValues"]
                    }
                    domain_deltas = {
                        "choices": [],
                        "schema": {
                            "domain": service_fields[field["name"]]["domain"],
                            "name": field["name"],
                        },
                    }
                    domain_changes = 0
                    for domain in field["domain"]["codedValues"]:
                        if domain["code"] not in list(domains.keys()) and domain[
                            "name"
                        ] not in list(domains.values()):
                            # New choice -> add new
                            domain_changes += 1
                            domain_deltas["choices"].append(
                                {"name": domain["name"], "code": domain["code"]}
                            )
                            domain_deltas["schema"]["domain"]["codedValues"].append(
                                {"name": domain["name"], "code": domain["code"]}
                            )
                        elif domain["code"] not in list(domains.keys()) and domain[
                            "name"
                        ] in list(domains.values()):
                            # Code change -> Add new domain but keep the existing one
                            domain_changes += 1
                            domain_deltas["choices"].append(
                                {"name": domain["name"], "code": domain["code"]}
                            )
                            domain_deltas["schema"]["domain"]["codedValues"].append(
                                {"name": domain["name"], "code": domain["code"]}
                            )
                        elif domain["name"] not in list(domains.values()):
                            domain_changes += 1
                            domain_deltas["choices"].append(
                                {"name": domain["name"], "code": domain["code"]}
                            )
                            for dom in domain_deltas["schema"]["domain"]["codedValues"]:
                                if dom["code"] == domain["code"]:
                                    dom["name"] = domain["name"]
                    if domain_changes > 0:
                        deltas[xml_layer]["domains"].append(domain_deltas)
            if "geometryType" in list(xml_schema[xml_layer].keys()):
                if "geometryType" not in list(service_schema[xml_layer].keys()):
                    deltas[xml_layer]["geometry"].append(
                        {"xmllayer": xml_layer, "xmlgeom": xml_schema[xml_layer]}
                    )
                elif (
                    xml_schema[xml_layer]["geometryType"]
                    != service_schema[xml_layer]["geometryType"]
                ):
                    deltas[xml_layer]["geometry"].append(
                        {
                            "xmlgeometry": xml_schema[xml_layer],
                            "servicegeometry": service_schema[xml_layer],
                        }
                    )

    return (deltas, use_non_globalid_relationships)


# =============================================================================================================


def _id_relationships(service, layer):
    """Determins how relationships are configured in a feature service, GlobalID to GUID or GUID to GUID"""
    layers = service.layers + service.tables
    try:
        parent_layer = [x for x in layers if x.properties["name"] == layer][0]
    except IndexError:
        return False
    if len(parent_layer.properties["relationships"]) > 0:
        keyfield = []
        for relationship in parent_layer.properties["relationships"]:
            if relationship["keyField"] not in keyfield:
                keyfield.append(relationship["keyField"])
        if len(keyfield) > 1:
            return False
        else:
            keyfield_type = [
                x["type"]
                for x in parent_layer.properties["fields"]
                if x["name"] == keyfield[0]
            ][0]
            if keyfield_type == "esriFieldTypeGlobalID":
                return False
            elif keyfield_type == "esriFieldTypeGUID":
                return True

    else:
        return False


# =============================================================================================================


def _xform2webform(xform, portalUrl, connectVersion=None):
    """Converts a XForm XML to Enketo Web form by Enketo Transformer"""
    (dir_path, file_name) = os.path.split(xform)
    xlsx_name = os.path.splitext(file_name)[0]

    with open(xform, "r", encoding="utf-8") as intext:
        xform_string = intext.read()

    url = "https://survey123.arcgis.com/api/xform2webform"
    params = {"xform": xform_string}
    if connectVersion:
        params["connectVersion"] = connectVersion

    session = EsriSession()
    r = session.post(url=url, data=params)
    response_json = r.json()
    r.close()
    with open(
        os.path.join(dir_path, xlsx_name + ".webform"), "w", encoding="utf-8"
    ) as fp:
        # with open(os.path.join(dir_path, xlsx_name + ".webform"), 'w') as fp:
        response_json["surveyFormJson"]["portalUrl"] = portalUrl
        webform = {
            "form": response_json["form"],
            "languageMap": response_json["languageMap"],
            "model": response_json["model"],
            "success": response_json["success"],
            "surveyFormJson": response_json["surveyFormJson"],
            "transformerVersion": response_json["transformerVersion"],
        }

        fp.write(json.dumps(webform, indent=2))
    return os.path.join(dir_path, xlsx_name + ".webform")


# =============================================================================================================


def _xml2sd(xmldict, useGUID):
    """Convert the XML dictionary to a JSON Service Definition"""
    sd = {"layers": [], "tables": []}
    relationships = {"layers": []}

    for layer in xmldict:
        if "rel_only" in xmldict[layer]:
            relationships["layers"].append(
                {
                    "id": xmldict[layer]["id"],
                    "relationships": xmldict[layer]["relationships"],
                }
            )
        elif "geometryType" in xmldict[layer]:
            if xmldict[layer]["geometryType"] == "esriGeometryPoint":
                """point"""
                pointjson = {
                    "allowGeometryUpdates": True,
                    "capabilities": "Create",
                    "defaultVisibility": True,
                    "displayField": "objectid",
                    "drawingInfo": {
                        "labelingInfo": None,
                        "renderer": {
                            "description": "Survey Data Locations",
                            "label": "point",
                            "symbol": {
                                "angle": 0,
                                "color": [255, 0, 0, 255],
                                "outline": {"color": [255, 255, 0, 255], "width": 1},
                                "size": 8,
                                "style": "esriSMSCircle",
                                "type": "esriSMS",
                                "xoffset": 0,
                                "yoffset": 0,
                            },
                            "type": "simple",
                        },
                        "transparency": 0,
                    },
                    "extent": {
                        "spatialReference": {"wkid": 102100},
                        "type": "extent",
                        "xmax": 180,
                        "xmin": -180,
                        "ymax": 90,
                        "ymin": -90,
                    },
                    "fields": [],
                    "geometryType": "esriGeometryPoint",
                    "globalIdField": "globalid",
                    "hasAttachments": False,
                    "hasM": False,
                    "hasStaticData": False,
                    "hasZ": False,
                    "htmlPopupType": "esriServerHTMLPopupTypeAsHTMLText",
                    "id": 0,
                    "isDataVersioned": False,
                    "maxRecordCount": 1000,
                    "maxScale": 0,
                    "minScale": 0,
                    "name": "point",
                    "objectIdField": "objectid",
                    "propagateVisibleFields": True,
                    "relationships": [],
                    "supportedQueryFormats": "JSON",
                    "supportsAdvancedQueries": True,
                    "supportsRollbackOnFailureParameter": True,
                    "supportsStatistics": True,
                    "templates": [
                        {
                            "description": "",
                            "name": "New Feature",
                            "prototype": {"attributes": {}},
                        }
                    ],
                    "type": "Feature Layer",
                    "indexes": [
                        {
                            "name": "GlobalIDIndex",
                            "fields": "globalid",
                            "isAscending": False,
                            "isUnique": True,
                            "description": "GlobalID index",
                        }
                    ],
                }

                pointjson["fields"] = xmldict[layer]["fields"]
                pointjson["id"] = xmldict[layer]["id"]
                pointjson["name"] = layer
                pointjson["drawingInfo"]["renderer"]["label"] = layer
                # pointjson.update({'title': xmldict[layer]['title']})

                if len(xmldict[layer]["relationships"]) > 0:
                    relationships["layers"].append(
                        {
                            "id": xmldict[layer]["id"],
                            "relationships": xmldict[layer]["relationships"],
                        }
                    )

                    if useGUID is True and "uniquerowid" in [
                        x["name"] for x in xmldict[layer]["fields"]
                    ]:
                        pointjson["indexes"].append(
                            {
                                "name": "RowIDIndex",
                                "fields": "uniquerowid",
                                "isAscending": False,
                                "isUnique": True,
                                "description": "Parent Key Field index",
                            }
                        )

                    if xmldict[layer]["id"] > 0:
                        if useGUID is True:
                            pointjson["indexes"].append(
                                {
                                    "name": "ParentRowIDIndex",
                                    "fields": "parentrowid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )
                        else:
                            pointjson["indexes"].append(
                                {
                                    "name": "ParentGlobalIDIndex",
                                    "fields": "parentglobalid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )

                if "hasAttachments" in xmldict[layer]:
                    pointjson["hasAttachments"] = True

                if "hasZ" in xmldict[layer]:
                    pointjson["hasZ"] = True

                sd["layers"].append(pointjson)

            elif xmldict[layer]["geometryType"] == "esriGeometryLine":
                """line"""
                linejson = {
                    "allowGeometryUpdates": True,
                    "capabilities": "Create",
                    "defaultVisibility": True,
                    "displayField": "objectid",
                    "drawingInfo": {
                        "renderer": {
                            "symbol": {
                                "color": [0, 178, 255, 255],
                                "style": "esriSLSSolid",
                                "type": "esriSLS",
                                "width": 2,
                            },
                            "type": "simple",
                            "label": "line",
                        },
                        "transparency": 0,
                    },
                    "extent": {
                        "spatialReference": {"wkid": 102100},
                        "type": "extent",
                        "xmax": 180,
                        "xmin": -180,
                        "ymax": 90,
                        "ymin": -90,
                    },
                    "fields": [
                        {
                            "name": "objectid",
                            "type": "esriFieldTypeOID",
                            "alias": "ObjectID",
                            "nullable": False,
                            "editable": False,
                            "domain": None,
                            "defaultValue": None,
                        },
                        {
                            "name": "globalid",
                            "type": "esriFieldTypeGlobalID",
                            "alias": "GlobalID",
                            "sqlType": "sqlTypeGUID",
                            "length": 38,
                            "nullable": False,
                            "editable": False,
                            "domain": None,
                            "defaultValue": None,
                        },
                    ],
                    "geometryType": "esriGeometryPolyline",
                    "globalIdField": "globalid",
                    "hasAttachments": False,
                    "hasM": False,
                    "hasStaticData": False,
                    "hasZ": False,
                    "htmlPopupType": "esriServerHTMLPopupTypeAsHTMLText",
                    "id": 1,
                    "isDataVersioned": False,
                    "maxRecordCount": 1000,
                    "maxScale": 0,
                    "minScale": 0,
                    "name": "line",
                    "objectIdField": "objectid",
                    "propagateVisibleFields": True,
                    "relationships": [],
                    "supportedQueryFormats": "JSON",
                    "supportsAdvancedQueries": True,
                    "supportsRollbackOnFailureParameter": True,
                    "supportsStatistics": True,
                    "templates": [
                        {
                            "description": "",
                            "name": "New Feature",
                            "prototype": {"attributes": {}},
                        }
                    ],
                    "type": "Feature Layer",
                    "indexes": [
                        {
                            "name": "GlobalIDIndex",
                            "fields": "globalid",
                            "isAscending": False,
                            "isUnique": True,
                            "description": "GlobalID index",
                        }
                    ],
                }

                linejson["fields"] = xmldict[layer]["fields"]
                linejson["id"] = xmldict[layer]["id"]
                linejson["name"] = layer
                linejson["drawingInfo"]["renderer"]["label"] = layer
                # linejson.update({'title': xmldict[layer]['title']})

                if len(xmldict[layer]["relationships"]) > 0:
                    relationships["layers"].append(
                        {
                            "id": xmldict[layer]["id"],
                            "relationships": xmldict[layer]["relationships"],
                        }
                    )

                    if useGUID is True and "uniquerowid" in [
                        x["name"] for x in xmldict[layer]["fields"]
                    ]:
                        linejson["indexes"].append(
                            {
                                "name": "RowIDIndex",
                                "fields": "uniquerowid",
                                "isAscending": False,
                                "isUnique": True,
                                "description": "Parent Key Field index",
                            }
                        )

                    if xmldict[layer]["id"] > 0:
                        if useGUID is True:
                            linejson["indexes"].append(
                                {
                                    "name": "ParentRowIDIndex",
                                    "fields": "parentrowid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )
                        else:
                            linejson["indexes"].append(
                                {
                                    "name": "ParentGlobalIDIndex",
                                    "fields": "parentglobalid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )

                if "hasAttachments" in xmldict[layer]:
                    linejson["hasAttachments"] = True

                sd["layers"].append(linejson)

            elif xmldict[layer]["geometryType"] == "esriGeometryPolygon":
                """polygon"""
                polygonjson = {
                    "allowGeometryUpdates": True,
                    "capabilities": "Create",
                    "defaultVisibility": True,
                    "displayField": "objectid",
                    "drawingInfo": {
                        "renderer": {
                            "symbol": {
                                "color": [0, 178, 255, 48],
                                "outline": {
                                    "color": [0, 178, 255, 255],
                                    "style": "esriSLSSolid",
                                    "type": "esriSLS",
                                    "width": 2,
                                },
                                "style": "esriSFSSolid",
                                "type": "esriSFS",
                            },
                            "type": "simple",
                            "label": "polygon",
                        },
                        "transparency": 0,
                    },
                    "extent": {
                        "spatialReference": {"wkid": 102100},
                        "type": "extent",
                        "xmax": 180,
                        "xmin": -180,
                        "ymax": 90,
                        "ymin": -90,
                    },
                    "fields": [
                        {
                            "name": "objectid",
                            "type": "esriFieldTypeOID",
                            "alias": "ObjectID",
                            "nullable": False,
                            "editable": False,
                            "domain": None,
                            "defaultValue": None,
                        },
                        {
                            "name": "globalid",
                            "type": "esriFieldTypeGlobalID",
                            "alias": "GlobalID",
                            "sqlType": "sqlTypeGUID",
                            "length": 38,
                            "nullable": False,
                            "editable": False,
                            "domain": None,
                            "defaultValue": None,
                        },
                    ],
                    "geometryType": "esriGeometryPolygon",
                    "globalIdField": "globalid",
                    "hasAttachments": False,
                    "hasM": False,
                    "hasStaticData": False,
                    "hasZ": False,
                    "htmlPopupType": "esriServerHTMLPopupTypeAsHTMLText",
                    "id": 2,
                    "isDataVersioned": False,
                    "maxRecordCount": 1000,
                    "maxScale": 0,
                    "minScale": 0,
                    "name": "polygon",
                    "objectIdField": "objectid",
                    "propagateVisibleFields": True,
                    "relationships": [],
                    "supportedQueryFormats": "JSON",
                    "supportsAdvancedQueries": True,
                    "supportsRollbackOnFailureParameter": True,
                    "supportsStatistics": True,
                    "templates": [
                        {
                            "description": "",
                            "name": "New Feature",
                            "prototype": {"attributes": {}},
                        }
                    ],
                    "type": "Feature Layer",
                    "indexes": [
                        {
                            "name": "GlobalIDIndex",
                            "fields": "globalid",
                            "isAscending": False,
                            "isUnique": True,
                            "description": "GlobalID index",
                        }
                    ],
                }

                polygonjson["fields"] = xmldict[layer]["fields"]
                polygonjson["id"] = xmldict[layer]["id"]
                polygonjson["name"] = layer
                polygonjson["drawingInfo"]["renderer"]["label"] = layer
                # polygonjson.update({'title': xmldict[layer]['title']})

                if len(xmldict[layer]["relationships"]) > 0:
                    relationships["layers"].append(
                        {
                            "id": xmldict[layer]["id"],
                            "relationships": xmldict[layer]["relationships"],
                        }
                    )

                    if useGUID is True and "uniquerowid" in [
                        x["name"] for x in xmldict[layer]["fields"]
                    ]:
                        polygonjson["indexes"].append(
                            {
                                "name": "RowIDIndex",
                                "fields": "uniquerowid",
                                "isAscending": False,
                                "isUnique": True,
                                "description": "Parent Key Field index",
                            }
                        )

                    if xmldict[layer]["id"] > 0:
                        if useGUID is True:
                            polygonjson["indexes"].append(
                                {
                                    "name": "ParentRowIDIndex",
                                    "fields": "parentrowid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )
                        else:
                            polygonjson["indexes"].append(
                                {
                                    "name": "ParentGlobalIDIndex",
                                    "fields": "parentglobalid",
                                    "isAscending": False,
                                    "isUnique": False,
                                    "description": "Child Key Field index",
                                }
                            )

                if "hasAttachments" in xmldict[layer]:
                    polygonjson["hasAttachments"] = True

                sd["layers"].append(polygonjson)

        else:
            """table"""
            tablejson = {
                "capabilities": "Create",
                "defaultVisibility": True,
                "displayField": "objectid",
                "editFieldsInfo": None,
                "fields": [],
                "globalIdField": "globalid",
                "hasAttachments": False,
                "htmlPopupType": "esriServerHTMLPopupTypeNone",
                "id": 0,
                "isDataVersioned": False,
                "maxRecordCount": 1000,
                "name": "table",
                "objectIdField": "objectid",
                "ownershipBasedAccessControlForFeatures": None,
                "propagateVisibleFields": True,
                "relationships": [],
                "supportedQueryFormats": "JSON, AMF",
                "supportsAdvancedQueries": True,
                "supportsRollbackOnFailureParameter": True,
                "supportsStatistics": True,
                "syncCanReturnChanges": False,
                "type": "Table",
                "useStandardizedQueries": True,
                "indexes": [
                    {
                        "name": "GlobalIDIndex",
                        "fields": "globalid",
                        "isAscending": False,
                        "isUnique": True,
                        "description": "GlobalID index",
                    }
                ],
            }

            tablejson["fields"] = xmldict[layer]["fields"]
            tablejson["id"] = xmldict[layer]["id"]
            tablejson["name"] = layer
            # tablejson.update({'title': xmldict[layer]['title']})

            if len(xmldict[layer]["relationships"]) > 0:
                relationships["layers"].append(
                    {
                        "id": xmldict[layer]["id"],
                        "relationships": xmldict[layer]["relationships"],
                    }
                )

                if useGUID is True and "uniquerowid" in [
                    x["name"] for x in xmldict[layer]["fields"]
                ]:
                    tablejson["indexes"].append(
                        {
                            "name": "RowIDIndex",
                            "fields": "uniquerowid",
                            "isAscending": False,
                            "isUnique": True,
                            "description": "Parent Key Field index",
                        }
                    )

                if xmldict[layer]["id"] > 0:
                    if useGUID is True:
                        tablejson["indexes"].append(
                            {
                                "name": "ParentRowIDIndex",
                                "fields": "parentrowid",
                                "isAscending": False,
                                "isUnique": False,
                                "description": "Child Key Field index",
                            }
                        )
                    else:
                        tablejson["indexes"].append(
                            {
                                "name": "ParentGlobalIDIndex",
                                "fields": "parentglobalid",
                                "isAscending": False,
                                "isUnique": False,
                                "description": "Child Key Field index",
                            }
                        )

            if "hasAttachments" in xmldict[layer]:
                tablejson["hasAttachments"] = True

            if xmldict[layer]["id"] == 0:
                sd["layers"].append(tablejson)
            else:
                sd["tables"].append(tablejson)

    return (sd, relationships)


# =============================================================================================================


def _append_hidden_questions(ns_dict, f_schema, schema):
    """Appends hidden questions to the schema"""
    for field in ns_dict:
        field_key = field.split("/")
        f_name = field_key.pop(-1)
        if len(field_key) > 0:
            if field_key[-1] in list(f_schema.keys()):
                if f_name not in f_schema[field_key[-1]]:
                    if (
                        isinstance(ns_dict[field], dict)
                        and ns_dict[field]["type"] != "geopoint"
                        and ns_dict[field]["type"] != "geotrace"
                        and ns_dict[field]["type"] != "geoshape"
                        and ns_dict[field]["type"] != "binary"
                    ):
                        if "esriFieldType" in list(ns_dict[field].keys()):
                            type = ns_dict[field]["esriFieldType"]
                        else:
                            type = _field_types[ns_dict[field]["type"]]
                        if "alias" in list(ns_dict[field].keys()):
                            alias = ns_dict[field]["alias"]
                        else:
                            alias = field.split("/")[-1]
                        if type != "esriFieldTypeString":
                            length = None
                        else:
                            length = ns_dict[field]["length"]
                        hidden_field = {
                            "name": field.split("/")[-1],
                            "alias": alias,
                            "type": type,
                            "length": length,
                            "domain": None,
                        }
                        if (
                            "parentglobalid" in f_schema[field_key[-1]]
                            or "parentrowid" in f_schema[field_key[-1]]
                        ):
                            schema[field_key[-1]]["fields"].insert(-1, hidden_field)
                        else:
                            schema[field_key[-1]]["fields"].append(hidden_field)
            else:
                field_key.pop(-1)
                field_key.append(f_name)
                _append_hidden_questions(
                    {"/".join(field_key): ns_dict[field]}, f_schema, schema
                )


# =============================================================================================================


def _find_key(d, key, value):
    for k, v in d.items():
        if isinstance(v, dict):
            p = _find_key(v, key, value)
            if p:
                return d[k].update(value)
        elif v == key:
            return d.update(value)


# =============================================================================================================


def _itext_labels(itext):
    """If multiple language form uses the labels from the default language as field alias'"""
    system_locale = list(locale.getdefaultlocale())[0].split("_")[0]
    itext_labels = {}
    default = None
    for node in itext:
        itext_labels.update({node.attrib["lang"]: {}})
        if "default" in node.attrib:
            default = node.attrib["lang"]
        for label in node:
            itext_labels[node.attrib["lang"]].update(
                {label.attrib["id"]: label[0].text}
            )

    if default is not None:
        return itext_labels[default]
    elif any(system_locale in loc for loc in list(itext_labels.keys())):
        return itext_labels[
            [lang for lang in list(itext_labels.keys()) if system_locale in lang][0]
        ]
    else:
        return itext_labels[list(itext_labels.keys())[-1]]


# =============================================================================================================


def _append_labels(body, ns_dict, itext_labels, model):
    """Update field alias' appropriatly"""
    for x in body:
        if (
            re.sub("[{][^}]*[}]", "", x.tag) == "group"
            or re.sub("[{][^}]*[}]", "", x.tag) == "repeat"
        ):
            if re.sub("[{][^}]*[}]", "", x.tag) == "group":
                if (
                    len(
                        [
                            y
                            for y in list(x)
                            if re.sub("[{][^}]*[}]", "", y.tag) == "repeat"
                        ]
                    )
                    > 0
                ):
                    label = x.find(".//{http://www.w3.org/2002/xforms}label")
                    if itext_labels and "ref" in label.attrib:
                        alias = itext_labels[
                            re.findall("(?<=')[^']+(?=')", label.attrib["ref"])[0]
                        ]
                    else:
                        alias = label.text
                    ns_dict.update({"/".join(x.attrib["ref"].split("/")[-2:]): alias})
            _append_labels(x, ns_dict, itext_labels, model)
        elif re.sub("[{][^}]*[}]", "", x.tag) != "label":
            search_apearance = False
            if (
                "appearance" in list(x.attrib.keys())
                and "search(" in x.attrib["appearance"]
            ):
                search_apearance = True
            q_body = {}
            coded_vals = []
            if (
                len([y for y in list(x) if re.sub("[{][^}]*[}]", "", y.tag) == "label"])
                == 0
            ):
                q_body.update({"alias": x.attrib["ref"].split("/")[-1]})
            for y in x:
                if (
                    re.sub("[{][^}]*[}]", "", y.tag) == "item"
                    and re.sub("[{][^}]*[}]", "", x.tag) == "select1"
                ):
                    choice = {}
                    for i in y:
                        if re.sub("[{][^}]*[}]", "", i.tag) == "label":
                            if itext_labels and "ref" in i.attrib:
                                name = itext_labels[
                                    re.findall("(?<=')[^']+(?=')", i.attrib["ref"])[0]
                                ]
                            else:
                                name = i.text
                            choice.update({"name": name})
                        else:
                            choice.update({"code": i.text})
                    if choice["code"] not in [c["code"] for c in coded_vals]:
                        coded_vals.append(choice)
                elif re.sub("[{][^}]*[}]", "", y.tag) == "label":
                    if (
                        not (
                            "{http://esri.com/xforms}fieldType"
                            in model[x.attrib["ref"]]
                            and model[x.attrib["ref"]][
                                "{http://esri.com/xforms}fieldType"
                            ]
                            == "null"
                        )
                        and "generated_note" not in x.attrib["ref"].split("/")[-1]
                        and "alias" in list(ns_dict[x.attrib["ref"]].keys())
                    ):
                        alias = ns_dict[x.attrib["ref"]]["alias"]
                    elif itext_labels and "ref" in y.attrib:
                        alias = itext_labels[
                            re.findall("(?<=')[^']+(?=')", y.attrib["ref"])[0]
                        ]
                    else:
                        alias = y.text
                    q_body.update({"alias": alias})
            if len(coded_vals) > 0 and search_apearance is False:
                q_body.update(
                    {
                        "domain": {
                            "type": "codedValue",
                            "name": f"cvd_{x.attrib['ref'].split('/')[-1]}",
                            "codedValues": coded_vals,
                        }
                    }
                )

            if (
                not (
                    "{http://esri.com/xforms}fieldType" in model[x.attrib["ref"]]
                    and model[x.attrib["ref"]]["{http://esri.com/xforms}fieldType"]
                    == "null"
                )
                and "generated_note" not in x.attrib["ref"].split("/")[-1]
            ):
                update = {**ns_dict[x.attrib["ref"]], **q_body}
                ns_dict[x.attrib["ref"]] = update


# =============================================================================================================


def _append_fields(node, ns_dict, new_dict, parent, model, create_domain, use_GUID):
    """Recursivly adds fields to the appropriate layer"""
    if (
        re.sub("[{][^}]*[}]", "", node.tag) != "group"
        and re.sub("[{][^}]*[}]", "", node.tag) != "label"
        and not any("generated_note" in y for y in node.attrib["ref"].split("/"))
        and not (
            "{http://esri.com/xforms}fieldType" in model[node.attrib["ref"]]
            and model[node.attrib["ref"]]["{http://esri.com/xforms}fieldType"] == "null"
        )
    ):
        if ns_dict[node.attrib["ref"]]["type"] == "binary":
            new_dict[parent].update({"hasAttachments": True})
        elif ns_dict[node.attrib["ref"]]["type"] == "geopoint":
            if (
                "esriFieldType" in list(ns_dict[node.attrib["ref"]].keys())
                and ns_dict[node.attrib["ref"]]["esriFieldType"]
                == "esriFieldTypePointZ"
            ):
                new_dict[parent].update({"hasZ": True})
            new_dict[parent].update({"geometryType": "esriGeometryPoint"})
        elif ns_dict[node.attrib["ref"]]["type"] == "geotrace":
            new_dict[parent].update({"geometryType": "esriGeometryLine"})
        elif ns_dict[node.attrib["ref"]]["type"] == "geoshape":
            new_dict[parent].update({"geometryType": "esriGeometryPolygon"})
        else:
            if "esriFieldType" in list(ns_dict[node.attrib["ref"]].keys()):
                type = ns_dict[node.attrib["ref"]]["esriFieldType"]
            else:
                type = _field_types[ns_dict[node.attrib["ref"]]["type"]]
            if (
                "domain" in list(ns_dict[node.attrib["ref"]].keys())
                and create_domain is True
            ):
                domain = ns_dict[node.attrib["ref"]]["domain"]
                if (
                    type != "esriFieldTypeString"
                    and len(
                        [
                            x["code"]
                            for x in domain["codedValues"]
                            if isinstance(x["code"], str)
                        ]
                    )
                    > 0
                ):
                    type = "esriFieldTypeString"
            else:
                domain = None

            new_dict[parent]["fields"].append(
                {
                    "name": node.attrib["ref"].split("/")[-1],
                    "alias": ns_dict[node.attrib["ref"]]["alias"],
                    "type": type,
                    "length": ns_dict[node.attrib["ref"]]["length"],
                    "domain": domain,
                }
            )

    elif (
        re.sub("[{][^}]*[}]", "", node.tag) == "group"
        and not len(
            [y for y in list(node) if re.sub("[{][^}]*[}]", "", y.tag) == "repeat"]
        )
        > 0
    ):
        for subnode in node:
            if re.sub("[{][^}]*[}]", "", subnode.tag) not in [
                "repeat",
                "label",
                "item",
                "value",
            ]:
                _append_fields(
                    subnode, ns_dict, new_dict, parent, model, create_domain, use_GUID
                )
            elif re.sub("[{][^}]*[}]", "", subnode.tag) == "repeat":
                new_dict[parent]["relationships"].append(
                    {
                        "name": f"{parent}_{subnode.attrib['nodeset'].split('/')[-1]}",
                        "cardinality": "esriRelCardinalityOneToMany",
                        "role": "esriRelRoleOrigin",
                        "keyField": "globalid",
                        "composite": True,
                        "parent": parent,
                        "child": subnode.attrib["nodeset"].split("/")[-1],
                    }
                )
                new_dict.update(
                    _gen_schema(
                        subnode[0],
                        subnode.attrib["nodeset"].split("/")[-1],
                        ns_dict,
                        model,
                        create_domain,
                        use_GUID,
                        parent,
                    )
                )
    elif (
        len([y for y in list(node) if re.sub("[{][^}]*[}]", "", y.tag) == "repeat"]) > 0
    ):
        new_dict[parent]["relationships"].append(
            {
                "name": f"{parent}_{node.attrib['ref'].split('/')[-1]}",
                "cardinality": "esriRelCardinalityOneToMany",
                "role": "esriRelRoleOrigin",
                "keyField": "globalid",
                "composite": True,
                "parent": parent,
                "child": node.attrib["ref"].split("/")[-1],
            }
        )
        new_dict.update(
            _gen_schema(
                node[1],
                node.attrib["ref"].split("/")[-1],
                ns_dict,
                model,
                create_domain,
                use_GUID,
                parent,
            )
        )


# =============================================================================================================


def _gen_schema(body, parent, ns_dict, model, create_domain, use_GUID, old_parent=None):
    """Generates a dictionary of all layers and fields in the XForm"""
    new_dict = {
        parent: {
            "fields": [
                {
                    "name": "objectid",
                    "type": "esriFieldTypeOID",
                    "alias": "ObjectID",
                    "nullable": False,
                    "editable": False,
                    "domain": None,
                    "defaultValue": None,
                },
                {
                    "name": "globalid",
                    "type": "esriFieldTypeGlobalID",
                    "alias": "GlobalID",
                    "length": 38,
                    "nullable": False,
                    "editable": False,
                    "domain": None,
                    "defaultValue": None,
                },
            ],
            "relationships": [],
        }
    }

    if old_parent is not None:
        if use_GUID is True:
            k_field = "parentrowid"
        else:
            k_field = "parentglobalid"
        new_dict[parent]["relationships"].append(
            {
                "name": f"{old_parent}_{parent}",
                "cardinality": "esriRelCardinalityOneToMany",
                "role": "esriRelRoleDestination",
                "keyField": k_field,
                "composite": True,
                "parent": old_parent,
                "child": parent,
            }
        )
    else:
        if use_GUID is True:
            if "uniquerowid" not in [x["name"] for x in new_dict[parent]["fields"]]:
                new_dict[parent]["fields"].append(
                    {
                        "name": "uniquerowid",
                        "type": "esriFieldTypeGUID",
                        "alias": "RowID",
                        "length": 38,
                        "domain": None,
                    }
                )

    for node in body:
        # Process if not repeat
        if not (
            re.sub("[{][^}]*[}]", "", node.tag) == "group"
            and len(
                [y for y in list(node) if re.sub("[{][^}]*[}]", "", y.tag) == "repeat"]
            )
            > 0
        ):
            _append_fields(
                node, ns_dict, new_dict, parent, model, create_domain, use_GUID
            )
        else:
            if use_GUID is True:
                if "uniquerowid" not in [x["name"] for x in new_dict[parent]["fields"]]:
                    new_dict[parent]["fields"].append(
                        {
                            "name": "uniquerowid",
                            "type": "esriFieldTypeGUID",
                            "alias": "RowID",
                            "length": 38,
                            "domain": None,
                        }
                    )
                key_field = "uniquerowid"
            else:
                key_field = "globalid"
            new_dict[parent]["relationships"].append(
                {
                    "name": f"{parent}_{node.attrib['ref'].split('/')[-1]}",
                    "cardinality": "esriRelCardinalityOneToMany",
                    "role": "esriRelRoleOrigin",
                    "keyField": key_field,
                    "composite": True,
                    "parent": parent,
                    "child": node.attrib["ref"].split("/")[-1],
                }
            )
            new_dict.update(
                _gen_schema(
                    node[1],
                    node.attrib["ref"].split("/")[-1],
                    ns_dict,
                    model,
                    create_domain,
                    use_GUID,
                    parent,
                )
            )
    if old_parent is not None:
        if use_GUID is True:
            guid_name = "parentrowid"
            guid_alias = "ParentRowID"
        else:
            guid_name = "parentglobalid"
            guid_alias = "ParentGlobalID"

        new_dict[parent]["fields"].append(
            {
                "name": guid_name,
                "type": "esriFieldTypeGUID",
                "alias": guid_alias,
                "length": 38,
                "domain": None,
            }
        )

    return new_dict


# =============================================================================================================


def _xmlschema(
    xml, mode, isPortal, create_table, use_GUID, create_domains=True, existing_schema={}
):
    """Generates dict schema from XForm"""
    root = ET.parse(xml).getroot()
    instance = root.findall(".//{http://www.w3.org/2002/xforms}instance")[0]
    parent = re.sub("[{][^}]*[}]", "", instance[0].attrib["id"])
    # parent = re.sub("[{][^}]*[}]", "", instance[0].tag)
    model = root.findall(".//{http://www.w3.org/2002/xforms}model")[0]
    body = root.findall(".//{http://www.w3.org/1999/xhtml}body")[0]
    title = root.find(".//{http://www.w3.org/1999/xhtml}title").text

    multilingual = None
    if "itext" in [re.sub("[{][^}]*[}]", "", x.tag) for x in model]:
        multilingual = _itext_labels(
            model.findall(".//{http://www.w3.org/2002/xforms}itext")[0]
        )

    ns_dict = {}
    for x in model:
        if len(x.attrib) > 1 and "nodeset" in x.attrib and "type" in x.attrib:
            if (
                "{http://esri.com/xforms}fieldType" in x.attrib
                and x.attrib["{http://esri.com/xforms}fieldType"] == "null"
                or x.attrib["nodeset"].split("/")[-1] == "instanceID"
                or x.attrib["nodeset"].split("/")[-1] == "instanceName"
                or "generated_note" in x.attrib["nodeset"].split("/")[-1]
            ):
                pass
            else:
                ns_dict[x.attrib["nodeset"]] = {
                    "type": x.attrib["type"],
                    "nodeset": x.attrib["nodeset"],
                }
                if "{http://esri.com/xforms}fieldType" in x.attrib and x.attrib[
                    "{http://esri.com/xforms}fieldType"
                ] in [
                    "esriFieldTypeString",
                    "esriFieldTypeDate",
                    "esriFieldTypeInteger",
                    "esriFieldTypeSingle",
                    "esriFieldTypeDouble",
                    "esriFieldTypeSmallInteger",
                    "esriFieldTypePointZ",
                    "esriFieldTypeGUID",
                ]:
                    ns_dict[x.attrib["nodeset"]].update(
                        {"esriFieldType": x.attrib["{http://esri.com/xforms}fieldType"]}
                    )

                if "{http://esri.com/xforms}fieldLength" in x.attrib:
                    ns_dict[x.attrib["nodeset"]].update(
                        {"length": int(x.attrib["{http://esri.com/xforms}fieldLength"])}
                    )
                elif (
                    x.attrib["type"]
                    in ["select1", "select", "odk:rank", "string", "time", "barcode"]
                    or "esriFieldType" in list(ns_dict[x.attrib["nodeset"]].keys())
                    and ns_dict[x.attrib["nodeset"]]["esriFieldType"]
                    == "esriFieldTypeString"
                ):
                    ns_dict[x.attrib["nodeset"]].update({"length": 255})
                else:
                    ns_dict[x.attrib["nodeset"]].update({"length": None})

                if "{http://esri.com/xforms}fieldAlias" in x.attrib:
                    ns_dict[x.attrib["nodeset"]].update(
                        {"alias": x.attrib["{http://esri.com/xforms}fieldAlias"]}
                    )

    full_model = {x.attrib["nodeset"]: x.attrib for x in model if "nodeset" in x.attrib}

    _append_labels(body, ns_dict, multilingual, full_model)

    if mode == "new" and isPortal is True:
        field_len_check = {
            x.split("/")[-1]: len(x.split("/")[-1])
            for x in list(ns_dict.keys())
            if len(x.split("/")[-1]) > 31
        }
        if len(field_len_check) > 0:
            return [
                f"This survey cannot be published. The field name {x} in {parent} is too long ({field_len_check[x]}) for Portal, must be less than 32 characters"
                for x in field_len_check
            ]

    schema = _gen_schema(
        body, parent, ns_dict, full_model, create_domains, use_GUID, old_parent=None
    )

    # Append hidden questions
    f_schema = {}
    for layer in schema:
        f_schema.update({layer: []})
        for field in schema[layer]["fields"]:
            f_schema[layer].append(field["name"])
    _append_hidden_questions(ns_dict, f_schema, schema)

    if len(existing_schema) == 0:
        id = 0
        for layer in schema.keys():
            if list(schema.keys()).index(layer) == 0:
                schema[layer].update({"id": id})
                id += 1
            elif "geometryType" in list(schema[layer].keys()):
                schema[layer].update({"id": id})
                id += 1

        for layer in schema.keys():
            if not ("id" in list(schema[layer].keys())):
                schema[layer].update({"id": id})
                id += 1
    else:
        id = max([existing_schema[x]["id"] for x in existing_schema]) + 1
        for layer in schema.keys():
            if layer in list(existing_schema.keys()):
                schema[layer].update({"id": existing_schema[layer]["id"]})
            else:
                schema[layer].update({"id": id})
                id += 1

    layers = list(schema.keys())

    rel_id = 1
    rel_ids_dict = {}

    for layer in layers:
        if len(schema[layer]["relationships"]) > 0:
            for idx in range(len(schema[layer]["relationships"])):
                rel_parent = schema[layer]["relationships"][idx].pop("parent")
                child = schema[layer]["relationships"][idx].pop("child")
                name = f"{rel_parent}_{child}"

                if schema[layer]["relationships"][idx]["role"] == "esriRelRoleOrigin":
                    schema[layer]["relationships"][idx].update(
                        {"relatedTableId": schema[child]["id"]}
                    )
                elif (
                    schema[layer]["relationships"][idx]["role"]
                    == "esriRelRoleDestination"
                ):
                    schema[layer]["relationships"][idx].update(
                        {"relatedTableId": schema[rel_parent]["id"]}
                    )

                if name not in list(rel_ids_dict.keys()):
                    rel_ids_dict.update({name: rel_id})
                    schema[layer]["relationships"][idx].update({"id": rel_id})
                    rel_id += 1
                else:
                    schema[layer]["relationships"][idx].update(
                        {"id": rel_ids_dict[name]}
                    )

    if (
        mode == "new"
        and create_table is False
        and "geometryType" not in list(schema[parent].keys())
    ):
        schema[parent].update({"geometryType": "esriGeometryPoint"})
    elif (
        mode == "new"
        and create_table is True
        and "geometryType" in list(schema[parent].keys())
    ):
        return [
            "Parameter table_only is set to True but a geometry question was detected in the surveys parent layer"
        ]

    return schema


# =============================================================================================================


def _identify_sub_url(xml):
    """Identifies if a submission URL is used"""
    sub = False
    submission_url = None
    root = ET.parse(xml).getroot()
    model = root.findall(".//{http://www.w3.org/2002/xforms}model")[0]
    instance = root.findall(".//{http://www.w3.org/2002/xforms}instance")[0]
    parent_layer_name = instance[0].attrib["id"]
    if "submission" in [re.sub("[{][^}]*[}]", "", x.tag) for x in model]:
        sub = True
        submission_url = [
            x.attrib["action"]
            for x in model
            if re.sub("[{][^}]*[}]", "", x.tag) == "submission"
        ][0]

    return (sub, submission_url, parent_layer_name)


# =============================================================================================================


def _xlsxregex(m):
    """Update special characters to X's"""
    length = len(m.group(0))
    value = "X"
    return value * length


# =============================================================================================================


def _xls2xform(file_path):
    """Convert the XLSForm to XForm"""
    (dir_path, file_name) = os.path.split(file_path)
    xlsx_name = os.path.splitext(file_name)[0]
    # https://www.codegrepper.com/code-examples/python/replace+diacritics+python
    replace_diacritics = (
        unicodedata.normalize("NFD", xlsx_name)
        .encode("ascii", "ignore")
        .decode("utf-8")
    )
    regex_first_pass = re.sub(r"[ .,;:-]", "_", replace_diacritics)
    regex_file_name = re.sub(r"[^A-Za-z0-9_]+", _xlsxregex, regex_first_pass)

    url = "https://survey123.arcgis.com/api/xls2xform"

    file = {
        "xlsform": (
            str(regex_file_name) + ".xlsx",
            open(file_path, "rb"),
            "application/octet-stream",
        )
    }
    session = EsriSession()
    r = session.post(url=url, files=file)
    response_json = r.json()
    r.close()
    # If itemsets in the response update the itemsets.csv file
    if "itemsets" in response_json:
        if not os.path.exists(os.path.join(dir_path, "media")):
            os.mkdir(os.path.join(dir_path, "media"))
        with open(
            os.path.join(dir_path, "media", "itemsets.csv"), "w", newline=""
        ) as itemsets:
            itemsets.write(response_json["itemsets"])
            itemsets.close()
    with open(os.path.join(dir_path, xlsx_name + ".xml"), "w", encoding="utf-8") as fp:
        fp.write(response_json["xform"])
        fp.close()
    if len(response_json["warnings"]) > 0:
        warnings.warn("Warning: ", str(response_json["warnings"]))
    return os.path.join(dir_path, xlsx_name + ".xml")
