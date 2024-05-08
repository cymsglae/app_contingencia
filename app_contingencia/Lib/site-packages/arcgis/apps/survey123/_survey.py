from __future__ import annotations
import os
import json
import time
import uuid
import tempfile
from urllib.parse import urlparse
from typing import Optional, Union, Any
import pandas as pd
from arcgis.gis import GIS, Item
from requests.utils import quote
import xml.etree.ElementTree as ET
from .exceptions import ServerError
from arcgis.auth import EsriSession
import arcgis
import shutil
from arcgis.gis import ItemTypeEnum, ItemProperties
from ._publish_functions import (
    _get_version,
    _xform2webform,
    _xls2xform,
    _identify_sub_url,
    _duplicate_geometry,
    _schema_parity,
    _init_schema,
    _modify_schema,
)

########################################################################


class SurveyManager:
    """
    Survey Manager allows users and administrators of ArcGIS Survey123 to
    analyze, report on, and access the data for surveys.

    """

    _baseurl = None
    _gis = None
    _portal = None
    _url = None
    _properties = None
    # ----------------------------------------------------------------------

    def __init__(self, gis, baseurl=None):
        """Constructor"""
        if baseurl is None:
            baseurl = "survey123.arcgis.com"
        self._baseurl = baseurl
        self._gis = gis

    # ----------------------------------------------------------------------
    def __str__(self):
        return "< SurveyManager @ {iid} >".format(iid=self._gis._url)

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def surveys(self) -> list:
        """returns a list of existing Survey"""
        query = (
            'type:"Form" AND NOT tags:"noxlsform"'
            'AND NOT tags:"draft" AND NOT typekeyw'
            "ords:draft AND owner:{owner}"
        ).format(owner=self._gis.users.me.username)
        content = self._gis.content
        items = content.search(
            query=query,
            item_type=None,
            sort_field="avgRating",
            sort_order="desc",
            max_items=10000,
            outside_org=False,
            categories=None,
            category_filters=None,
        )
        return [Survey(item=i, sm=self) for i in items]

    # ----------------------------------------------------------------------
    def get(self, survey_id: Union[Item, str]):
        """returns a single :class:`~arcgis.apps.survey123.Survey` object from and Item ID or Item"""
        if isinstance(survey_id, Item):
            survey_id = survey_id.id
        item = self._gis.content.get(survey_id)
        return Survey(item=item, sm=self)

    # ----------------------------------------------------------------------
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
        r = session.post(url, params)
        response_json = r.json()
        r.close()

        with open(
            os.path.join(dir_path, xlsx_name + ".webform"), "w", encoding="utf-8"
        ) as fp:
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

    # ----------------------------------------------------------------------
    def _xls2xform(self, file_path: str):
        """
        Converts a XLSForm spreadsheet to XForm XML. The spreadsheet must be in Excel XLS(X) format

        ============   ================================================
        *Inputs*       *Description*
        ------------   ------------------------------------------------
        file_path      Required String. Path to the XLS(X) file.
        ============   ================================================

        :returns: dict

        """

        url = "https://{base}/api/xls2xform".format(base=self._baseurl)
        params = {"f": "json"}
        file = {"xlsform": file_path}
        isinstance(self._gis, GIS)
        return self._gis._con.post(
            path=url, postdata=params, files=file, verify_cert=False
        )

    # ----------------------------------------------------------------------
    def create(
        self,
        title: str,
        folder: str = None,
        tags: str = None,
        summary: str = None,
        description: str = None,
        thumbnail: str = None,
    ) -> Survey:
        """
        The `create()` method creates an empty form item and hosted feature service in the folder supplied to the method or a new folder created with the survey.

        The output of the `create()` method is a single :class:`~arcgis.apps.survey123.Survey` object.

        ============   ================================================
        *Inputs*       *Description*
        ------------   ------------------------------------------------
        title          Required string. Title for the form item.
        ------------   ------------------------------------------------
        folder         Optional string. The name of the folder to store the survey form item in your ArcGIS content.
        ------------   ------------------------------------------------
        tags           Optional string. Comma-separated tags for the form item.
        ------------   ------------------------------------------------
        summary        Optional string. Summary of the survey purpose (limit to a maximum of 250 characters).
        ------------   ------------------------------------------------
        description    Optional string. Description of the form item.
        ------------   ------------------------------------------------
        thumbnail      Optional string. Path for the thumbnail image file.
        ============   ================================================

        :returns: :class:`~arcgis.apps.survey123.Survey`

        """

        if folder is None:
            existing_folder = self._gis.content.folders.get(
                folder=f"Survey-{title}", owner=self._gis.users.me.username
            )
            if existing_folder is None:
                folder_obj = self._gis.content.folders.create(f"Survey-{title}")
                folder = folder_obj.properties["id"]
            else:
                folder_obj = existing_folder
                folder = folder_obj.properties["id"]
        else:
            folder_obj = self._gis.content.folders.get(
                folder=str(folder), owner=self._gis.users.me.username
            )
            if folder_obj is None:
                raise RuntimeError("Folder name not found")
            folder = folder_obj.properties["id"]

        form_properties = ItemProperties(
            title=title,
            item_type=ItemTypeEnum.FORM.value,
            type_keywords=["Form, Survey123, Survey123 Hub, Draft"],
            tags=tags,
            snippet=summary,
            description=description,
            thumbnail=thumbnail,
        )
        form_item = folder_obj.add(item_properties=form_properties, text="{}").result()

        uid = "%s" % uuid.uuid4().hex
        service = self._gis.content.create_service(
            name=f"survey123_{uid}",
            folder=folder,
            create_params={
                "name": f"survey123_{uid}",
                "serviceDescription": f"Feature Service for survey {form_item.id}",
                "hasStaticData": False,
                "maxRecordCount": 2000,
                "sourceSchemaChangesAllowed": True,
                "capabilities": "Create,Delete,Query,Update,Editing,Extract,Sync",
                "description": "",
                "copyrightText": "",
                "spatialReference": {"wkid": 4326, "latestWkid": 4326},
                "fullExtent": {
                    "xmin": -180,
                    "ymin": -90,
                    "xmax": 180,
                    "ymax": 90,
                    "spatialReference": {"wkid": 4326, "latestWkid": 4326},
                },
                "allowGeometryUpdates": True,
                "units": "esriDecimalDegrees",
                "supportsApplyEditsWithGlobalIds": True,
                "editorTrackingInfo": {
                    "enableEditorTracking": True,
                    "enableOwnershipAccessControl": True,
                    "allowOthersToUpdate": True,
                    "allowOthersToDelete": True,
                    "allowOthersToQuery": True,
                    "allowAnonymousToUpdate": False,
                    "allowAnonymousToDelete": False,
                },
            },
        )
        # Update service with title and thumbnail
        service.update(
            {
                "title": title,
                "typeKeywords": f"Survey123,Survey123 Hub,OwnerView,Source,{uid}",
            },
            thumbnail=thumbnail,
        )

        form_item.add_relationship(service, "Survey2Service")
        return Survey(item=form_item, sm=self)


########################################################################
class Survey:
    """
    A `Survey` is a single instance of a survey project. This class contains
    the :class:`~arcgis.gis.Item` information and properties to access the underlying dataset
    that was generated by the `Survey` form.

    Data can be exported to `Pandas DataFrames`, `shapefiles`, `CSV`, and
    `File Geodatabases`.

    In addition to exporting data to various formats, a `Survey's` data can
    be exported as reports.

    """

    _gis = None
    _sm = None
    _si = None
    _ssi = None
    _baseurl = None
    # ----------------------------------------------------------------------

    def __init__(self, item, sm, baseurl: Optional[str] = None):
        """Constructor"""
        if baseurl is None:
            baseurl = "survey123.arcgis.com"
        self._si = item
        self._gis = item._gis
        self._sm = sm
        try:
            self.layer_name = self._find_layer_name()
        except:
            self.layer_name = None
        self._baseurl = baseurl

        sd = self._si.related_items("Survey2Data", direction="forward")
        if len(sd) > 0:
            for item in sd:
                if "StakeholderView" in item.typeKeywords:
                    self._stk = item
                    _stk_layers = self._stk.layers + self._stk.tables
                    _idx = 0
                    if self.layer_name:
                        for layer in _stk_layers:
                            if layer.properties["name"] == self.layer_name:
                                _idx = layer.properties["id"]
                    self._stk_url = self._stk.url + f"/{str(_idx)}"

        related = self._si.related_items("Survey2Service", direction="forward")
        if len(related) > 0:
            self._ssi = related[0]
            self._ssi_view = False
            self._ssi_layers = self._ssi.layers + self._ssi.tables

            ssi_layer = None
            if self.layer_name:
                for layer in self._ssi_layers:
                    if layer.properties["name"] == self.layer_name:
                        _idx = layer.properties["id"]
                        ssi_layer = layer
                        break
            if not ssi_layer and len(self._ssi_layers) > 0:
                ssi_layer = self._ssi_layers[0]
                _idx = ssi_layer.properties["id"]
            try:
                self._ssi_url = ssi_layer._url
            except AttributeError:
                pass
            try:
                if self._ssi_layers[0].properties["isView"] == True:
                    self._ssi_view = True
                    view_url = self._ssi.url  # [:-1]
                    parent_info = self._find_parent(view_url)
                    self.parent_fl_url = parent_info[0] + f"/{str(_idx)}"
                    self._ssi_parent = arcgis.gis.Item(self._gis, parent_info[1])
                    self._ssi_parent_layers = self._ssi.layers + self._ssi.tables
            except KeyError:
                if ssi_layer is not None:
                    self.parent_fl_url = ssi_layer._url
            except IndexError:
                pass

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """returns the properties of the survey"""
        return dict(self._si)

    # ----------------------------------------------------------------------
    def __str__(self):
        return "<Survey @ {iid}>".format(iid=self._si.title)

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()

    # ----------------------------------------------------------------------
    def download(
        self, export_format: str, save_folder: Optional[str] = None
    ) -> Union[str, pd.Dataframe]:
        """
        Exports the Survey's data to other format

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        export_format     Required string. This is the acceptable export format that a
                          user can export the survey data to. The following formats are
                          acceptable: File Geodatabase, Shapefile, CSV, and DF.
        ----------------  ---------------------------------------------------------------
        save_folder       Optional string. Specify the folder location where the output file should be stored.
        ================  ===============================================================

        :Returns: String or DataFrame
        """

        title = "a%s" % uuid.uuid4().hex
        if export_format.lower() == "df":
            return self._ssi.layers[0].query().sdf
        if save_folder is None:
            save_folder = tempfile.gettempdir()
        isinstance(self._ssi, Item)
        eitem = self._ssi.export(
            title=title,
            export_format=export_format,
        )
        save_file = eitem.download(save_path=save_folder)
        eitem.delete(force=True)
        return save_file

    # ----------------------------------------------------------------------
    def generate_report(
        self,
        report_template: Item,
        where: str = "1=1",
        utc_offset: str = "+00:00",
        report_title: Optional[str] = None,
        package_name: Optional[str] = None,
        output_format: str = "docx",
        folder_id: Optional[str] = None,
        merge_files: Optional[str] = None,
        survey_item: Optional[Item] = None,
        webmap_item: Optional[Item] = None,
        map_scale: Optional[float] = None,
        locale: str = "en",
        save_folder: Optional[str] = None,
    ) -> str:
        """
        The `generate_report` method allows users to create Microsoft Word and PDF reports
        for survey results based on a reporting template. Reports are saved as an :class:`~arcgis.gis.Item`
        in an ArcGIS content folder or saved locally on disk. For additional information on parameters,
        see `Create Report <https://developers.arcgis.com/survey123/api-reference/rest/report/#create-report>`.

        .. note::
            The Survey123 report service may output one or more `.docx` or `.pdf` files, or a zipped
            package of these files. Whether the output is contained in a `.zip` file depends
            on the number of files generated and their size. For more information, see the
            `packageFiles` parameter in the `Create Report <https://developers.arcgis.com/survey123/api-reference/rest/report/#request-parameters-3>`_ documentation.

        .. note::
            To save to disk, do not specify a `folder_id` argument.

        See `Get Started with Survey123 Reports <https://www.esri.com/arcgis-blog/products/survey123/sharing-collaboration/get-started-with-survey123-reports/>`_
        for further information.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        report_template   Required :class:`~arcgis.gis.Item`. The report template.
        ----------------  ---------------------------------------------------------------
        where             Optional string. The select statement issued on survey
                          :class:`~arcgis.features.FeatureLayer` to report on
                          all survey records or a subset.

                          Query the `parent_fl_url` property of the
                          :class:`~arcgis.apps.survey123.Survey` object to get the
                          feature layer URL and retrieve a list of fields.

                          .. code-block:: python

                              >>> gis = GIS(profile="your_profile")
                              >>> smgr = SurveyManager(gis)

                              >>> survey_item = gis.content.get("<survey form id>")
                              >>> survey_obj = smgr.get(survey_item.id)

                              >>> survey_fl = FeatureLayer(survey_obj.parent_fl_url, gis)

                              >>> print([f["name"] for f in survey_fl.properties.fields])
        ----------------  ---------------------------------------------------------------
        utc_offset        Optional string.  Time offset from UTC. This offset is applied to
                          all `date`, `time`, and `dateTime` questions that appear in the report output.
                          Example: EST - "+04:00"
        ----------------  ---------------------------------------------------------------
        report_title      Optional string. If `folder_id` is provided, the result is an
                          :class:`~arcgis.gis.Item` with this argument as the title. If
                          `save_folder` argument is provided, this argument will be the
                          name of the output file, or the base name for files
                          in the output zipped package if the server-side component
                          chose to zip up the output (depends upon the size and number
                          of files that would result).


                          .. note::
                              If `merge_files` is either `nextPage` or `continuous`,
                              `report_title` is the output file name.
        ----------------  ---------------------------------------------------------------
        package_name      Optional string. Specify the file name (without extension) of the
                          packaged `.zip` file. If multiple files are packaged, the `report_title`
                          argument will be used to name individual files in the package.


                          .. note::
                            The Survey123 report service automatically decides whether to package
                            generated reports as a `.zip` file, depending on the output file count.
                            See the `packageFiles` parameter description in the `Create Report Request parameters <https://developers.arcgis.com/survey123/api-reference/rest/report/#request-parameters-3>`_
                            documentation for details.
        ----------------  ---------------------------------------------------------------
        save_folder       Optional string. Specify the folder location where the output
                          file or zipped file should be stored. If `folder_id` argument
                          is provided, this argument is ignored.
        ----------------  ---------------------------------------------------------------
        output_format     Optional string. Accepts `docx` or `pdf`.
        ----------------  ---------------------------------------------------------------
        folder_id         Optional string. If a file :class:`~arcgis.gis.Item` is the
                          desired output, specify the `id` value of the ArcGIS content
                          folder.
        ----------------  ---------------------------------------------------------------
        merge_files       Optional string. Specify if output is a single file containing individual
                          records on multiple pages (`nextPage` or `continuous`) or
                          multiple files (`none`).

                          + `none` - Print multiple records in split mode. Each record
                            is a separate file. This is the default value.
                          + `nextPage` - Print multiple records in a single document.
                            Each record starts on a new page.
                          + `continuous` - Print multiple records in a single document.
                            EAch records starts on the same page of the previous record.

                          .. note::
                              A merged file larger than 500 MB will be split into multiple
                              files.
        ----------------  ---------------------------------------------------------------
        survey_item       Optional survey :class:`~arcgis.gis.Item` to provide
                          additional information on survey structure.
        ----------------  ---------------------------------------------------------------
        webmap_item       Optional web map :class:`~arcgis.gis.Item`. Specify the basemap for all
                          map questions in the report. This takes precedence over the map set for
                          each question in the report template.
        ----------------  ---------------------------------------------------------------
        map_scale         Optional float. Specify the map scale for all map questions in the report.
                          The map will center on the feature geometry. This takes precedence over the
                          scale set for each question in the report template.
        ----------------  ---------------------------------------------------------------
        locale            Optional string. Specify the locale to format number
                          and date values.
        ================  ===============================================================

        :Returns:
            An :class:`~arcgis.gis.Item` or string upon completion of the reporting
            `job <https://developers.arcgis.com/survey123/api-reference/rest/report/#jobs>`_.
            For details on the returned value, see `Response Parameters <https://developers.arcgis.com/survey123/api-reference/rest/report/#response-parameters>`_
            for the :func:`~arcgis.apps.survey123.Survey.generate_report` job.

        .. code-block:: python

            # Usage example #1: output a PDF file item:
            >>> from arcgis.gis import GIS
            >>> from arcgis.apps.survey123 import SurveyManager

            >>> gis = GIS(profile="your_profile_name")

            >>> # Get report template and survey items
            >>> report_templ = gis.content.get("<template item id>")
            >>> svy_item = gis.content.get("<survey item id>")

            >>> svy_mgr = SurveyManager(gis)
            >>> svy_obj = svy_mgr.get(svy_item.id)

            >>> user_folder_id = [f["id"]
                                 for f in gis.users.me.folders
                                 if f["title"] == "folder_title"][0]

            >>> report_item = svy_obj.generate_report(report_template=report_templ,
                                                      report_title="Title of Report item",
                                                      output_format="pdf",
                                                      folder_id=user_folder_id,
                                                      merge_files="continuous")

           # Usage example #2: output a Microsoft Word document named `LessThan20_Report.docx`

           >>> report_file = svy_obj.generate_report(report_template=report_templ,
                                                     where="objectid < 20",
                                                     report_title="LessThan20_Report",
                                                     output_format="docx",
                                                     save_folder="file\system\directory\",
                                                     merge_files="nextPage")

           # Usage example #3: output a zip file named `api_gen_report_pkg.zip` of individual
           #                   pdf files with a base name of `SpecimensOver30`

           >>> report_file = svy_obj.generate_report(report_template=report_templ,
                                                     where="number_specimens>30",
                                                     report_title="SpecimensOver30",
                                                     output_format="pdf",
                                                     save_folder="file\system\directory",
                                                     package_name="api_gen_report_pkg")

        """
        if isinstance(where, str):
            where = {"where": where}

        url = "https://{base}/api/featureReport/createReport/submitJob".format(
            base=self._baseurl
        )

        try:
            if (
                self._si._gis.users.me.username == self._si.owner
                and self._ssi_layers[0].properties["isView"] == True
            ):
                fl_url = self.parent_fl_url
            elif self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
        except KeyError:
            if self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
            else:
                fl_url = self._ssi_url

        params = {
            "outputFormat": output_format,
            "queryParameters": where,
            "portalUrl": self._si._gis._url,
            "templateItemId": report_template.id,
            "outputReportName": report_title,
            "outputPackageName": package_name,
            "surveyItemId": self._si.id,
            "featureLayerUrl": fl_url,
            "utcOffset": utc_offset,
            "uploadInfo": json.dumps(None),
            "f": "json",
            "username": self._si._gis.users.me.username,
            "locale": locale,
        }
        if merge_files:
            params["mergeFiles"] = merge_files
        if map_scale and isinstance(map_scale, (int, float)):
            params["mapScale"] = map_scale
        if webmap_item and isinstance(webmap_item, Item):
            params["webmapItemId"] = webmap_item.itemid
        if survey_item and isinstance(survey_item, Item):
            params["surveyItemId"] = survey_item.itemid
        if merge_files == "nextPage" or merge_files == "continuous":
            params["package_name"] = ""
        if folder_id:
            params["uploadInfo"] = json.dumps(
                {
                    "type": "arcgis",
                    "packageFiles": True,
                    "parameters": {"folderId": folder_id},
                }
            )
        # 1). Submit the request.
        submit = self._si._gis._con.post(
            url, params, add_headers={"X-Survey123-Request-Source": "API/Python"}
        )
        return self._check_status(
            res=submit, status_type="generate_report", save_folder=save_folder
        )

    # ----------------------------------------------------------------------
    @property
    def report_templates(self) -> list:
        """
        Returns a list of saved report :class:`Items <arcgis.gis.Item>`.

        :returns: list of :class:`Items <arcgis.gis.Item>`
        """
        related_items = self._si.related_items(
            direction="forward", rel_type="Survey2Data"
        )
        report_templates = [t for t in related_items if t.type == "Microsoft Word"]

        return report_templates

    @property
    def reports(self) -> list:
        """returns a list of generated reports"""
        return self._si._gis.content.search(
            'owner: %s AND type:"Microsoft Word" AND tags:"Survey 123"'
            % self._ssi._gis.users.me.username,
            max_items=10000,
            outside_org=False,
        )

    # ----------------------------------------------------------------------
    def create_report_template(
        self,
        template_type: Optional[str] = "individual",
        template_name: Optional[str] = None,
        save_folder: Optional[str] = None,
    ):
        """
        The `create_report_template` creates a simple default template that
        can be downloaded locally, edited and uploaded back up as a report
        template.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        template_type     Optional string. Specify which sections to include in the template.
                          Acceptable types are `individual`, `summary`, and `summaryIndividual`.
                          Default is `individual`.
        ----------------  ---------------------------------------------------------------
        template_name     Optional string. Specify the name of the output template file without file extension.
        ----------------  ---------------------------------------------------------------
        save_folder       Optional string. Specify the folder location where the output file should be stored.
        ================  ===============================================================

        :returns: String
        """
        if self._si._gis.users.me.username != self._si.owner:
            raise TypeError("Stakeholders cannot create report templates")
        try:
            if self._ssi_layers[0].properties["isView"] == True:
                fl_url = self.parent_fl_url
        except KeyError:
            fl_url = self._ssi_url

        if template_name:
            file_name = f"{template_name}.docx"
        else:
            if template_type == "individual":
                type = "Individual"
            elif template_type == "summary":
                type = "Summary"
            elif template_type == "summaryIndividual":
                type = "SummaryIndividual"
            file_name = f"{self._si.title}_sampleTemplate{type}.docx"

        url = "https://{base}/api/featureReport/createSampleTemplate".format(
            base=self._baseurl
        )
        gis = self._si._gis
        params = {
            "featureLayerUrl": fl_url,
            "surveyItemId": self._si.id,
            "portalUrl": gis._url,
            "contentType": template_type,
            "username": gis.users.me.username,
            "f": "json",
        }

        res = gis._con.post(
            url,
            params,
            try_json=False,
            out_folder=save_folder,
            file_name=file_name,
            add_headers={"X-Survey123-Request-Source": "API/Python"},
        )
        return res

    # ----------------------------------------------------------------------

    def check_template_syntax(self, template_file: Optional[str] = None):
        """
        A sync operation to check any syntax which will lead to a failure
        when generating reports in the given feature.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        template_file     Required string. The report template file for which syntax is to be checked.
        ================  ===============================================================

        :returns: dictionary {Success or Failure}
        """

        if self._si._gis.users.me.username != self._si.owner:
            raise TypeError("Stakeholders cannot create report templates")

        try:
            if self._ssi_layers[0].properties["isView"] == True:
                fl_url = self.parent_fl_url
        except KeyError:
            fl_url = self._ssi_url

        url = "https://{base}/api/featureReport/checkTemplateSyntax".format(
            base=self._baseurl
        )
        file = {
            "templateFile": (os.path.basename(template_file), open(template_file, "rb"))
        }
        gis = self._si._gis
        params = {
            "featureLayerUrl": fl_url,
            "surveyItemId": self._si.id,
            "portalUrl": self._si._gis._url,
            "f": "json",
        }

        check = gis._con.post(
            url,
            params,
            files=file,
            add_headers={"X-Survey123-Request-Source": "API/Python"},
        )
        return check

    # ----------------------------------------------------------------------

    def upload_report_template(
        self, template_file: Optional[str] = None, template_name: Optional[str] = None
    ):
        """
        Check report template syntax to identify any syntax which will lead to a failure
        when generating reports in the given feature. Uploads the report to the organization
        and associates it with the survey.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        template_file     Required string. The report template file which syntax to be checked, and uploaded.
        ----------------  ---------------------------------------------------------------
        template_name     Optional string. If provided the resulting item will use the provided name, otherwise
                          the name of the docx file will be used.
        ================  ===============================================================

        :returns: :class:`~arcgis.gis.Item` {Success) or string (Failure}
        """

        check = self.check_template_syntax(template_file)

        if check["success"] == True:
            if template_name:
                file_name = template_name
            else:
                file_name = os.path.splitext(os.path.basename(template_file))[0]

            properties = {
                "title": file_name,
                "type": "Microsoft Word",
                "tags": "Survey123,Print Template,Feature Report Template",
                "typeKeywords": "Survey123,Survey123 Hub,Print Template,Feature Report Template",
                "snippet": "Report template",
            }
            survey_folder_id = self._si.ownerFolder
            gis = self._si._gis
            user = gis.users.get(gis.properties.user.username)
            user_folders = user.folders
            survey_folder = next(
                (f for f in user_folders if f["id"] == survey_folder_id), 0
            )
            folder = survey_folder["title"]
            # folder = "Survey-" + self._si.title
            template_item = gis.content.add(
                item_properties=properties, data=template_file, folder=folder
            )
            add_relationship = self._si.add_relationship(template_item, "Survey2Data")
        else:
            return check["details"][0]["description"]

        return template_item

    # ----------------------------------------------------------------------

    def update_report_template(self, template_file: Optional[str] = None):
        """
        Check report template syntax to identify any syntax which will lead to a failure
        when generating reports in the given feature and updates existing report template organizational item.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        template_file     Required string. The report template file which syntax to be checked, and uploaded.
                          The updated template name must match the name of the existing template item.
        ================  ===============================================================

        :returns: :class:`~arcgis.gis.Item` {Success) or string (Failure}
        """

        check = self.check_template_syntax(template_file)

        if check["success"] == True:
            file_name = os.path.splitext(os.path.basename(template_file))[0]
            gis = self._si._gis
            template_item = gis.content.search(
                query="title:" + file_name, item_type="Microsoft Word"
            )
            update = template_item[0].update(item_properties={}, data=template_file)
        else:
            return check["details"][0]["description"]

        return template_item

    # ----------------------------------------------------------------------

    def estimate(self, report_template: Item, where: str = "1=1"):
        """
        An operation to estimate how many credits are required for a task
        with the given parameters.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        report_template   Required :class:`~arcgis.gis.Item`. The report template item.
        ----------------  ---------------------------------------------------------------
        where             Optional string. This is the select statement used to export
                          part or whole of the dataset. If the filtered result has more
                          than one feature/record, the request will be considered as a
                          batch printing. Currently, one individual report will be
                          generated for each feature/record.
        ================  ===============================================================

        :returns: dictionary {totalRecords, cost(in credits)}
        """
        try:
            if (
                self._si._gis.users.me.username == self._si.owner
                and self._ssi_layers[0].properties["isView"] == True
            ):
                fl_url = self.parent_fl_url
            elif self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
        except KeyError:
            if self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
            else:
                fl_url = self._ssi_url

        gis = self._si._gis
        if isinstance(where, str):
            where = {"where": where}

        url = "https://{base}/api/featureReport/estimateCredits".format(
            base=self._baseurl
        )
        params = {
            "featureLayerUrl": fl_url,
            "queryParameters": where,
            "templateItemId": report_template.id,
            "surveyItemId": self._si.id,
            "portalUrl": self._si._gis._url,
            "f": "json",
        }

        estimate = gis._con.get(
            url, params, add_headers={"X-Survey123-Request-Source": "API/Python"}
        )
        return estimate

    # ----------------------------------------------------------------------

    def create_sample_report(
        self,
        report_template: Item,
        where: str = "1=1",
        utc_offset: str = "+00:00",
        report_title: Optional[str] = None,
        merge_files: Optional[str] = None,
        survey_item: Optional[Item] = None,
        webmap_item: Optional[Item] = None,
        map_scale: Optional[float] = None,
        locale: str = "en",
        save_folder: Optional[str] = None,
    ) -> str:
        """
        Task for creating a test sample report (similar to generate_report) and refining a report template before generating any formal report.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        report_template   Required :class:`~arcgis.gis.Item`. The report template :class:`~arcgis.gis.Item`.
        ----------------  ---------------------------------------------------------------
        where             Optional string. This is the select statement used to export
                          part or whole of the dataset.  If the record count is > 1, then
                          the item must be saved to your organization.
        ----------------  ---------------------------------------------------------------
        utc_offset        Optional string.  This is the time offset from UTC to match the
                          users timezone. Example: EST - "+04:00"
        ----------------  ---------------------------------------------------------------
        report_title      Optional string. An :class:`~arcgis.gis.Item` with this argument
                          as the title if no `save_folder` argument. If `save_folder`
                          argument is provided, this argument will be the name of the
                          output file, or the base name for files in the output zipped
                          package if the server-side component chose to zip up the output
                          (depends upon the size and number of files that would result).

                          .. note::
                              If `merge_files` is either `nextPage` or `continuous`,
                              `report_title` is the output file name.
        ----------------  ---------------------------------------------------------------
        merge_files       Optional string. Specify if output is a single file containing individual
                          records on multiple pages (`nextPage` or `continuous`) or
                          multiple files (`none`).

                          + `none` - Print multiple records in split mode. Each record
                            is a separate file. This is the default value.
                          + `nextPage` - Print multiple records in a single document.
                            Each record starts on a new page.
                          + `continuous` - Print multiple records in a single document.
                            EAch records starts on the same page of the previous record.

                          .. note::
                              A merged file larger than 500 MB will be split into multiple
                              files.
        ----------------  ---------------------------------------------------------------
        save_folder       Optional string. Specify the folder location where the output
                          file should be stored.
        ----------------  ---------------------------------------------------------------
        survey_item       Optional survey :class:`~arcgis.gis.Item` to provide additional
                          information on the survey structure.
        ----------------  ---------------------------------------------------------------
        webmap_item       Optional :class:`~arcgis.gis.Item` . Specify the basemap for printing task when printing
                          a point/polyline/polygon. This takes precedence over the map set for
                          each question inside a survey.
        ----------------  ---------------------------------------------------------------
        map_scale         Optional float. Specify the map scale when printing, the map will center on the feature geometry.
        ----------------  ---------------------------------------------------------------
        locale            Optional string. Specify the locale setting to format number and date values.
        ================  ===============================================================

        :Returns: String

        """
        try:
            if (
                self._si._gis.users.me.username == self._si.owner
                and self._ssi_layers[0].properties["isView"] == True
            ):
                fl_url = self.parent_fl_url
            elif self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
        except KeyError:
            if self._si._gis.users.me.username != self._si.owner:
                fl_url = self._stk_url
            else:
                fl_url = self._ssi_url

        if isinstance(where, str):
            where = {"where": where}

        url = "https://{base}/api/featureReport/createSampleReport/submitJob".format(
            base=self._baseurl
        )

        params = {
            "queryParameters": where,
            "portalUrl": self._si._gis._url,
            "templateItemId": report_template.id,
            "surveyItemId": self._si.id,
            "featureLayerUrl": fl_url,
            "utcOffset": utc_offset,
            "f": "json",
            "locale": locale,
        }
        if merge_files:
            params["mergeFiles"] = merge_files
        if map_scale and isinstance(map_scale, (int, float)):
            params["mapScale"] = map_scale
        if webmap_item and isinstance(webmap_item, Item):
            params["webmapItemId"] = webmap_item.itemid
        if survey_item and isinstance(survey_item, Item):
            params["surveyItemId"] = survey_item.itemid
        if merge_files == "nextPage" or merge_files == "continuous":
            params["package_name"] = ""
        if report_title:
            params["outputReportName"] = report_title

        # 1). Submit the request.
        submit = self._si._gis._con.post(
            url, params, add_headers={"X-Survey123-Request-Source": "API/Python"}
        )
        return self._check_status(
            res=submit, status_type="generate_report", save_folder=save_folder
        )

    # ----------------------------------------------------------------------

    def _check_status(self, res, status_type, save_folder):
        """checks the status of a Survey123 operation"""
        jid = res["jobId"]
        gis = self._si._gis
        params = {
            "f": "json",
            "username": self._si._gis.users.me.username,
            "portalUrl": self._si._gis._url,
        }
        status_url = "https://{base}/api/featureReport/jobs/{jid}/status".format(
            base=self._baseurl, jid=jid
        )
        # 3). Start Checking the status
        res = gis._con.get(
            status_url,
            params=params,
            add_headers={"X-Survey123-Request-Source": "API/Python"},
        )
        while res["jobStatus"] == "esriJobExecuting":
            res = self._si._gis._con.get(
                status_url,
                params=params,
                add_headers={"X-Survey123-Request-Source": "API/Python"},
            )
            time.sleep(1)
        if status_type == "default_report_template":
            if (
                "results" in res
                and "details" in res["results"]
                and "resultFile" in res["results"]["details"]
                and "url" in res["results"]["details"]["resultFile"]
            ):
                url = res["results"]["details"]["resultFile"]["url"]
                file_name = os.path.basename(url)
                return gis._con.get(url, file_name=file_name, out_folder=save_folder)
            return res
        elif status_type == "generate_report":
            urls = []
            files = []
            items = []
            if res["jobStatus"] == "esriJobSucceeded":
                if "resultFiles" in res["resultInfo"]:
                    for sub in res["resultInfo"]["resultFiles"]:
                        if "id" in sub:
                            items.append(sub["id"])
                        elif "url" in sub:
                            urls.append(sub["url"])
                    files = [
                        self._si._gis._con.get(
                            url,
                            file_name=os.path.basename(urlparse(url).path),
                            add_token=False,
                            try_json=False,
                            out_folder=save_folder,
                        )
                        for url in urls
                    ] + [gis.content.get(i) for i in items]
                    if len(files) == 1:
                        return files[0]
                    return files
                elif "details" in res["resultInfo"]:
                    for res in res["resultInfo"]["details"]:
                        if "resultFile" in res:
                            fr = res["resultFile"]
                            if "id" in fr:
                                items.append(fr["id"])
                            else:
                                urls.append(fr["url"])
                        del res

                    files = [
                        self._si._gis._con.get(
                            url, file_name=os.path.basename(url), out_folder=save_folder
                        )
                        for url in urls
                    ] + [gis.content.get(i) for i in items]
                    if len(files) == 1:
                        return files[0]
                    else:
                        return files
            elif (
                res["jobStatus"] == "esriJobPartialSucceeded"
                or res["jobStatus"] == "esriJobFailed"
            ):
                raise ServerError(res["messages"][0])
            # return

    # ----------------------------------------------------------------------
    def _find_parent(self, view_url):
        """Finds the parent feature layer for a feature layer view"""
        url = view_url + "/sources"
        response = self._si._gis._con.get(url)
        return (
            response["services"][0]["url"],
            response["services"][0]["serviceItemId"],
        )

    # ----------------------------------------------------------------------
    def _find_layer_name(self):
        """Finds the name of the layer the survey is submitting to, used to find the appropriate layer index"""
        tmpdir = tempfile.TemporaryDirectory()
        tmp_name = tmpdir.name
        name = self._si._gis._con.get(
            f"{self._gis._url}/sharing/rest/content/items/{self._si.id}/info/forminfo.json"
        )["name"]
        title = quote(name, safe="()!-_.'~")
        url = f"{self._gis._url}/sharing/rest/content/items/{self._si.id}/info/{title}.xml"
        response = self._si._gis._con.get(url, out_folder=tmp_name)
        tree = ET.parse(response)
        shutil.rmtree(tmp_name, ignore_errors=True)
        root = tree.getroot()
        for elem in root[0][1].iter():
            for key, value in zip(elem.attrib.keys(), elem.attrib.values()):
                if key == "id":
                    return value

    # ----------------------------------------------------------------------
    def publish(
        self,
        xlsform: Optional[str] = None,
        info: Optional[dict] = None,
        media: Optional[str] = None,
        scripts: Optional[str] = None,
        create_web_form: Optional[bool] = True,
        enable_delete_protection: Optional[bool] = False,
        table_only: Optional[bool] = False,
        create_coded_value_domains: Optional[bool] = True,
        enable_sync: Optional[bool] = False,
        use_non_globalid_relationships: Optional[bool] = None,
        create_web_map: Optional[bool] = True,
        thumbnail: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        schema_changes: Optional[bool] = False,
    ) -> Survey:
        """
        Publishes surveys created by the `create()` method or an existing survey published to your ArcGIS organization.
        It can also be an unpublished blank survey created with the Survey123 Web Designer (any designs will be overwritten by the `publish()` method's required XLSForm.).

        If `schema_changes` is set to False, any differences between the schema of the XLSForm and the submission endpoint will generate an error
        that lets you know what the differences are. If `schema_changes` is set to True, the following logic is applied:

         - When using a submission_url that references an ArcGIS Server feature service, schema changes are not applied. The publish() method returns an error about any differences found between the design and schema.
         - When the survey has an associated hosted feature service and view service, with or without a submission_url set, schema changes are applied to the parent service and propagated to the view.
         - When the survey has an associated hosted feature service but no view service, with or without a submission_url set, schema changes are applied to the submission endpoint.

        ==============================  ===============================================================
        **Argument**                    **Description**
        ------------------------------  ---------------------------------------------------------------
        xlsform                         Optional string. Path for the XLSForm file.
        ------------------------------  ---------------------------------------------------------------
        info                            Optional dictionary. Represents the contents of the .info file (settings); See the table below for the keys and values. Keys are case sensitive.

                                        .. code-block:: python

                                            # Example: Enable the Inbox:

                                            info={
                                                "queryInfo": {
                                                    "mode": "manual",
                                                    "editEnabled": True,
                                                    "copyEnabled": True
                                                }
                                            }
        ------------------------------  ---------------------------------------------------------------
        media                           Optional string. Path for the media folder or the ZIP file that contains it.
        ------------------------------  ---------------------------------------------------------------
        scripts                         Optional string. Path for the scripts folder or the ZIP file that contains it.
        ------------------------------  ---------------------------------------------------------------
        create_web_form                 Optional boolean. Enabled by default. When this parameter is off, publishing a survey does not create a matching web form that allows users to complete the survey in the web app, so the survey only works in the field app.
        ------------------------------  ---------------------------------------------------------------
        enable_delete_protection        Optional boolean. Disabled by default. Enables delete protection on the form item and all related content (feature service, web maps, report templates).
        ------------------------------  ---------------------------------------------------------------
        table_only                      Optional boolean. Disabled by default. Creates a hosted table instead of a feature service if no geometry is present in the parent layer.
        ------------------------------  ---------------------------------------------------------------
        create_coded_value_domains      Optional boolean. Enabled by default. Choice lists in the choices worksheet will be used to create coded value domains in the feature layer. For more information, see `Multiple choice questions <https://doc.arcgis.com/en/survey123/desktop/create-surveys/xlsformessentials.htm#ESRI_SECTION1_63B0F9AA1A05458BB4B86F2A1A05AA78>`_.
        ------------------------------  ---------------------------------------------------------------
        enable_sync                     Optional boolean. Disabled by default. When this parameter is on, the sync capability is enabled on the feature layer when the survey is published.
                                        The sync capability is a requirement if a survey uses offline map areas that have been configured for a web map.
                                        Alternatively, you can enable sync after publishing by using the Settings tab on the feature layer's item page in your ArcGIS organization.
        ------------------------------  ---------------------------------------------------------------
        use_non_globalid_relationships   Optional boolean. Enabled by default when publishing to ArcGIS Online and disabled by default when publishing to ArcGIS Enterprise.
                                         If your work involves copying survey data between databases, it is recommended that you do not use global ID parent keys in repeat relationships.
        ------------------------------  ---------------------------------------------------------------
        create_web_map                  Optional boolean. Enabled by default. Creates a web map that includes the survey's feature layer with default symbology and uses your organization's default basemap.
                                        This web map is automatically added to the Linked Content tab in Survey123 Connect and is available in the Survey123 field app.
        ------------------------------  ---------------------------------------------------------------
        thumbnail                       Optional string. Path for the thumbnail image file.
        ------------------------------  ---------------------------------------------------------------
        summary                         Optional string. Short summary about the survey  (limit to a maximum of 250 characters).
        ------------------------------  ---------------------------------------------------------------
        description                     Optional string. Description of the form item.
        ------------------------------  ---------------------------------------------------------------
        tags                            Optional string. Tags listed as comma-separated values or a list of strings. Used for searches on items.
        ------------------------------  ---------------------------------------------------------------
        schema_changes                  Optional boolean. Disabled by default. Specifies if schema changes should be made to the feature service or not.
        ==============================  ===============================================================

        *Key:Value options for the `info` argument*


        ==========================  =====================================================================
        **Key**                     **Value**
        --------------------------  ---------------------------------------------------------------------
        collectInfo                 Optional dictionary. Displays the distance and direction from the device's location for each response in the list view in the Inbox, Drafts, Outbox, Sent, and Overview folders in the Survey123 field app and also enables the map view in each of these folders.
                                    Setting `showMap` to True enables location indicators, and False disables location indicators.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "foldersInfo":{
                                                "showMap": True|False
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        displayInfo                 Optional dictionary. Defines the appearance of the survey with style options and specifies its map and coordinate information.

                                    `map`—Optional dictionary. Provides access to a number of default settings for maps used in a survey, including the coordinate format, zoom level, and home location.
                                    You can also set a default basemap for all map questions in a survey by clicking the Basemap button on the lower map.

                                        - `coordinateFormat`—Optional string. Displays a location value in the specified format, including the following coordinate types: Degrees Minutes, Degrees Decimal Minutes, Decimal Degrees, MGRS, USNG, and UTM/UPS. This setting doesn't affect manually entered values (which only accepts decimal minutes) nor the value recorded in a survey (which is recorded in decimal degrees).
                                        - `defaultType`—Optional dictionary. Control the name of the default basemap by setting the `name` in the `defaultType` dictionary.
                                        - `home`—Optional dictionary. The home location provided for a survey is returned if the device's location cannot be found. In the `home` dictionary, set `latitude`, `longitude`, and `zoomLevel` to define the home location. The Survey123 website uses the home zoom level as a default when viewing or printing individual survey results.
                                        - `preview`—Optional dictionary. Control the preview map by using the `preview` dictionary. Setting `coordinateFormat` controls the display format of the coordinates. Setting `zoomLevel` controls the tile level of detail to display.
                                        - `mapTypes`—Optional dictionary. Use the `mapTypes` dictionary to manually associate a map to a survey. This workflow won't link the map to the survey. You can add the default basemap list to any `mapSources` by setting `append` to True. By setting `includeLibrary` to True, all maps associated with the survey will be added to the ArcGIS/My Surveys/Maps folder to make them available to any survey.

                                    `mapSources`—Optional list. List of dictionaries for which each contains a map to include. Parameters in the dictionary include: `url` for the the map's item page URL, `name` sets the display name of the map, `description` sets the description of the map, and `storeInLibrary` is a boolean that controls if the map gets added to the ArcGIS/My Surveys/Maps folder making it available to any survey.

                                    `style`—Optional dictionary. Controls the colors of various elements in the survey.
                                    You can customize `toolbarTextColor` and `toolbarBackgroundColor` colors for the survey header, body (`textColor`/`backgroundColor`/`backgroundImage`), input fields (`inputTextColor`/`inputBackgroundColor`), and footer (`footerTextColor`/`footerBackgroundColor`). Provide the hexadecimal color code or HTML color name for the respective parameter. For readability, the contrast ratio between text and background colors should not be below 4.5.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "displayInfo": {
                                                "map": {
                                                    "coordinateFormat" : "<dm | ddm | d | mgrs | usng | utmups>",
                                                    "defaultType": {
                                                        "name": "Basemap name"
                                                    },
                                                    "home": {
                                                        "latitude": 34.0568,
                                                        "longitude": -117.1961,
                                                        "zoomLevel": 20
                                                    },
                                                    "preview": {
                                                        "coordinateFormat": "<dm | ddm | d | mgrs | usng | utmups>",
                                                        "zoomLevel": 0
                                                    },
                                                    "mapTypes": {
                                                        "append": True|False,
                                                        "includeLibrary": True|False,
                                                        "mapSources": [{
                                                            "url": "https://www.arcgis.com/home/item.html?id=ABC1234...",
                                                            "name": "Redlands Basemap",
                                                            "description": "Basemap for the City of Redlands, CA",
                                                            "storyInLibrary": True|False
                                                        }]
                                                    },
                                                },
                                                "style": {
                                                    "backgroundColor": "#00338D",
                                                    "backgroundImage": "media/backgroundImage.jpeg",
                                                    "inputBackgroundColor": "#C60C30",
                                                    "inputTextColor": "#00338D",
                                                    "textColor": "#C60C30",
                                                    "toolbarBackgroundColor": "#00338D",
                                                    "toolbarTextColor": "#C60C30",
                                                    "footerTextColor": "#00338D",
                                                    "footerBackgroundColor": "#C60C30"
                                                }
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        foldersInfo                 Optional dictionary. Displays the distance and direction from the device's location for each response in the list view in the Inbox, Drafts, Outbox, Sent, and Overview folders in the Survey123 field app and also enables the map view in each of these folders. Setting `showMap` to True enables location indicators, and False disables location indicators.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "foldersInfo":{
                                                "showMap": True|False
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        imagesInfo                  Optional dictionary. Controls the maximum dimensions for images submitted to the survey. A photo taken in Survey123 is saved as a .jpg file, with a quality level dependent on the device's camera. The image size, measured by pixels on the longest edge, can be set using the `captureResolution` property. This size is applied to all image questions in the survey. The default size is 1280. To allow any size photo, set a value of 0.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "imagesInfo": {
                                                "captureResolution": <320 | 640 | 1280 | 1920 | 0>
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        locationSharingInfo         Optional dictionary. Ignored if location sharing is not enabled in the organization; a survey setting cannot override the organization setting. To require location sharing for an individual survey, set both `enabled` and `required` to True. To allow users to enable location sharing, set `enabled` to True and `required` to False.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "locationSharingInfo": {
                                                "enabled": True|False,
                                                "required": True|False
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        overviewInfo                Optional dictionary. Setting `enabled` to True provides access to the Overview folder in the Survey123 field app. This folder contains every survey record currently stored on the device, color-coded by the folder in which they are located.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "overviewInfo": {
                                                "enabled": True|False
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        queryInfo                   Optional dictionary. Setting `mode` to `"manual"` provides access to the inbox, which allows viewing (`viewEnabled`: True), editing (`editEnabled`: True), and copying (`copyEnabled`: True) existing survey responses stored in the feature layer.

                                    The query expression specified by the `where` parameter determines which surveys in the Survey123 field app are available for editing in the inbox.

                                    In the inbox, selecting Refresh updates the list of surveys shown on the List tab. The refresh action generally returns all surveys that satisfy the query expression in the `where` parameter (if set) and that are not already stored in other folders on the device. If you set `applySpatialFilter` to True, selecting Refresh on the Map tab applies a spatial filter that updates the list to show only surveys that are within the current map extent.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "queryInfo": {
                                                "mode": ""|"manual",
                                                "where": "status='for_review'",
                                                "applySpatialFilter": True|False,
                                                "editEnabled": True|False,
                                                "viewEnabled": True|False,
                                                "copyEnabled": True|False
                                            }
                                        }
        --------------------------  ---------------------------------------------------------------------
        sentInfo                    Optional dictionary. Controls access to the sent folder, which allows access to surveys that were previously sent from the device. Setting `enabled` to True provides access to the sent folder, which allows editing (`editEnabled`: True) and copying (`copyEnabled`: True) existing survey responses that were previously submitted from the device.

                                    .. code-block:: python

                                        # Syntax:

                                        {
                                            "sentInfo": {
                                                "enabled": True|False,
                                                "editEnabled": True|False,
                                                "copyEnabled": True|False
                                            }
                                        }
        ==========================  =====================================================================

        :returns: :class:`~arcgis.apps.survey123.Survey`

        """

        tmpdir = tempfile.TemporaryDirectory()
        tmp_name = tmpdir.name
        # Identify if publishing a new survey or re-publishing an existing survey.
        if "Draft" in self._si.typeKeywords:
            if xlsform is None:
                raise ValueError(
                    "An XLSForm is required when publishing a survey for the first time."
                )
            initial_publish = True
            directory = os.path.join(tmp_name, self._si.id, "esriinfo")
            os.makedirs(directory)
            # Survey123 Connect has an option to use GUID to GUID relationships instead of GlobalId to GUID. This is the default configuration if the user does not specify.
            if (
                use_non_globalid_relationships is None
                and self._gis.properties.isPortal is True
            ):
                use_non_globalid_relationships = True
            elif use_non_globalid_relationships is None:
                use_non_globalid_relationships = False

            # Create forminfo.json
            with open(os.path.join(directory, "forminfo.json"), "w") as forminfo:
                forminfo.write(
                    json.dumps({"name": self._si.title, "type": "xform"}, indent=4)
                )
        else:
            # Since this is a re-publish of an existing survey we work with the current state of the form item.
            initial_publish = False
            form_zip = self._si.download(save_path=tmp_name)
            shutil.unpack_archive(form_zip, os.path.join(tmp_name, self._si.id), "zip")
            os.remove(form_zip)
            directory = os.path.join(tmp_name, self._si.id, "esriinfo")

        connect_version = _get_version()
        # Copy all files from a user supplied media folder
        if media:
            clear_media = False
            if os.path.isfile(media):
                tmpmedia = tempfile.TemporaryDirectory()
                tmp_media = tmpmedia.name
                shutil.unpack_archive(media, os.path.join(tmp_media, "media"), "zip")
                media = os.path.join(tmp_media, "media")
                clear_media = True
            if not os.path.exists(os.path.join(directory, "media")):
                os.mkdir(os.path.join(directory, "media"))
            [
                shutil.copy2(
                    os.path.join(media, x), os.path.join(directory, "media", x)
                )
                for x in os.listdir(media)
                if not (os.path.isdir(os.path.join(media, x)))
            ]
            if clear_media is True:
                shutil.rmtree(tmp_media, ignore_errors=True)
        # Copy all files from a user supplied scripts folder
        if scripts:
            clear_scripts = False
            if os.path.isfile(scripts):
                tmpscripts = tempfile.TemporaryDirectory()
                tmp_scripts = tmpscripts.name
                shutil.unpack_archive(
                    scripts, os.path.join(tmp_scripts, "scripts"), "zip"
                )
                scripts = os.path.join(tmp_scripts, "scripts")
                clear_scripts = True
            if not os.path.exists(os.path.join(directory, "scripts")):
                os.mkdir(os.path.join(directory, "scripts"))
            [
                shutil.copy2(
                    os.path.join(scripts, x), os.path.join(directory, "scripts", x)
                )
                for x in os.listdir(scripts)
                if not (os.path.isdir(os.path.join(scripts, x)))
            ]
            if clear_scripts is True:
                shutil.rmtree(tmp_scripts, ignore_errors=True)

        # Create .info file
        full_info = {
            "collectInfo": {"enabled": True},
            "displayInfo": {
                "map": {
                    "defaultType": {},
                    "home": {},
                    "includeDefaultMaps": True,
                    "preview": {},
                },
                "style": {},
            },
            "foldersInfo": {"showMap": True},
            "imagesInfo": {"captureResolution": 1280},
            "locationSharingInfo": {"enabled": True, "required": False},
            "overviewInfo": {"enabled": False},
            "queryInfo": {
                "applySpatialFilter": True,
                "copyEnabled": False,
                "editEnabled": True,
                "mode": "",
                "viewEnabled": False,
                "where": "",
            },
            "sentInfo": {"copyEnabled": True, "editEnabled": False, "enabled": True},
        }
        if info is None and initial_publish is True:
            # No info supplied new publish, use default .info config
            with open(
                os.path.join(directory, f"{self._si.title}.info"), "w"
            ) as infofile:
                infofile.write(json.dumps(full_info))
        elif info is not None and initial_publish is True:
            # User supplied info on new publish, use the default and update what the user supplied
            for property in info.keys():
                for setting in info[property]:
                    if not (isinstance(info[property][setting], dict)):
                        full_info[property][setting] = info[property][setting]
                    else:
                        for m_setting in info[property][setting]:
                            full_info[property][setting][m_setting] = info[property][
                                setting
                            ][m_setting]
            with open(
                os.path.join(directory, f"{self._si.title}.info"), "w"
            ) as infofile:
                infofile.write(json.dumps(full_info))
        elif info is None and initial_publish is False:
            # No info republish, do nothing keep .info as is
            pass
        else:
            # User supplied .info on re-publish, update what the user supplied
            with open(
                os.path.join(directory, f"{self._si.title}.info"), "r"
            ) as infojson:
                user_full_info = json.load(infojson)
            for property in info.keys():
                for setting in info[property]:
                    if not (isinstance(info[property][setting], dict)):
                        user_full_info[property][setting] = info[property][setting]
                    else:
                        for m_setting in info[property][setting]:
                            user_full_info[property][setting][m_setting] = info[
                                property
                            ][setting][m_setting]
            with open(
                os.path.join(directory, f"{self._si.title}.info"), "w"
            ) as infofile:
                infofile.write(json.dumps(user_full_info))

        if xlsform:
            # Convert XLSForm to XForm (XML)
            xlsform = shutil.copy2(
                xlsform, os.path.join(directory, f"{self._si.title}.xlsx")
            )
            xform = _xls2xform(xlsform)

            # Check for duplicate geometry in the same layer, can only have one geometry per layer.
            duplicate = _duplicate_geometry(xform)
            if duplicate is not None:
                print(duplicate)
                exit()

            # Generate webform file if desired
            if create_web_form is True:
                _xform2webform(
                    xform=xform, portalUrl=self._gis.url, connectVersion=connect_version
                )

            # sub is a boolean true if it is a submission_url survey and false if it is not. Also returns the URL for the submission URL feature service.
            # If view also returns the parent layer
            sub, submission_url, parent_layer = _identify_sub_url(xform)
            use_parent = False

            if sub is True:
                # User defined submission_url
                try:
                    use_non_globalid_relationships = None
                    service = arcgis.gis.Item(self._gis, submission_url.split("/")[-1])
                    service_layers = service.layers + service.tables
                    if "Hosted Service" in service.typeKeywords:
                        hosted = True
                    else:
                        hosted = False
                    if (
                        "isView" in list(service_layers[0].properties.keys())
                        and service_layers[0].properties["isView"] is True
                    ):
                        use_parent = True
                        parent_info = self._find_parent(service.url)
                        parent_item = arcgis.gis.Item(self._gis, parent_info[1])
                        parent_deltas = _schema_parity(
                            self,
                            parent_item,
                            xform,
                            table_only,
                            use_non_globalid_relationships,
                            parent_layer,
                        )[0]
                except Exception:
                    raise RuntimeError(
                        "The feature service set in the submission_url does not exist or is inaccessible."
                    )
            else:
                # Publish method needs to manage the feature service
                service = self._ssi
                if (
                    initial_publish is False
                    and "isView" in list(self._ssi_layers[0].properties.keys())
                    and self._ssi_layers[0].properties["isView"] is True
                ):
                    use_parent = True
                    parent_info = self._find_parent(service.url)
                    parent_item = arcgis.gis.Item(self._gis, parent_info[1])
                    parent_deltas = _schema_parity(
                        self,
                        parent_item,
                        xform,
                        table_only,
                        use_non_globalid_relationships,
                        parent_layer,
                    )[0]

            # Identify deltas between feature service and XForm
            deltas, guid = _schema_parity(
                self,
                service,
                xform,
                table_only,
                use_non_globalid_relationships,
                parent_layer,
            )

            if (
                use_parent is True
                and schema_changes is True
                and deltas != parent_deltas
            ):
                if sub is True:
                    raise RuntimeError(
                        "The schema of the source layer and its view do not match. Review content and update accordingly."
                    )
                else:
                    parent_layers = parent_item.layers + parent_item.tables
                    for lyr in parent_layers:
                        if "propagateVisibleFields" not in lyr.properties:
                            lyr_url = lyr.url.replace(
                                "/rest/services", "/rest/admin/services"
                            )
                            flcm = (
                                arcgis.features.managers.FeatureLayerCollectionManager(
                                    url=lyr_url, gis=self._gis, fs=parent_item
                                )
                            )
                            flcm.update_definition({"propagateVisibleFields": True})

                    parent_deltas = _schema_parity(
                        self,
                        parent_item,
                        xform,
                        table_only,
                        use_non_globalid_relationships,
                        parent_layer,
                    )[0]
                    deltas, guid = _schema_parity(
                        self,
                        service,
                        xform,
                        table_only,
                        use_non_globalid_relationships,
                        parent_layer,
                    )
                    if parent_deltas != deltas:
                        raise RuntimeError(
                            "The schema of the source layer and its view do not match. Review content and update accordingly."
                        )

            # - When using a submission_url that references an ArcGIS Server feature service, schema changes are not applied. If there are differences between the XLSForm design and the schema of the submission_url, the `publish()` method returns an error that lets you know what the difference is.
            # - When the survey has an associated hosted feature service and view service, with or without a submission_url set, schema changes are applied to the parent service and propagated to the view.
            # - When the survey has an associated hosted feature service but no view service, with or without a submission_url set, schema changes are applied to the submission endpoint.

            if initial_publish is True:
                if sub is False:
                    _init_schema(
                        self,
                        use_non_globalid_relationships,
                        xform,
                        table_only,
                        create_coded_value_domains,
                        enable_sync,
                    )
                else:
                    if hosted is False:
                        mod_schema = _modify_schema(
                            self, service, False, deltas, use_non_globalid_relationships
                        )
                        if mod_schema is not None:
                            raise RuntimeError(mod_schema)
                        self._si.delete_relationship(self._ssi, "Survey2Service")
                        self._ssi.delete()
                        self._si.add_relationship(service, "Survey2Service")
                        self._ssi = service
                    else:
                        if use_parent is False:
                            mod_schema = _modify_schema(
                                self,
                                service,
                                schema_changes,
                                deltas,
                                use_non_globalid_relationships,
                            )
                            if mod_schema is not None:
                                raise RuntimeError(mod_schema)
                            self._si.delete_relationship(self._ssi, "Survey2Service")
                            self._ssi.delete()
                            self._si.add_relationship(service, "Survey2Service")
                            self._ssi = service
                        else:
                            mod_schema = _modify_schema(
                                self,
                                parent_item,
                                schema_changes,
                                deltas,
                                use_non_globalid_relationships,
                                True,
                                service,
                            )
                            if mod_schema is not None:
                                raise RuntimeError(mod_schema)
                            self._si.delete_relationship(self._ssi, "Survey2Service")
                            self._ssi.delete()
                            self._si.add_relationship(service, "Survey2Service")
                            self._ssi = service
            else:
                if sub is True:
                    if hosted is True:
                        if use_parent is True:
                            mod_schema = _modify_schema(
                                self,
                                parent_item,
                                schema_changes,
                                deltas,
                                use_non_globalid_relationships,
                                True,
                                service,
                            )
                            if mod_schema is not None:
                                raise RuntimeError(mod_schema)
                        else:
                            mod_schema = _modify_schema(
                                self,
                                service,
                                schema_changes,
                                deltas,
                                use_non_globalid_relationships,
                            )
                            if mod_schema is not None:
                                raise RuntimeError(mod_schema)
                    else:
                        mod_schema = _modify_schema(
                            self, service, False, deltas, use_non_globalid_relationships
                        )
                        if mod_schema is not None:
                            raise RuntimeError(mod_schema)
                else:
                    if use_parent is True:
                        mod_schema = _modify_schema(
                            self,
                            parent_item,
                            schema_changes,
                            deltas,
                            use_non_globalid_relationships,
                            True,
                            service,
                        )
                        if mod_schema is not None:
                            raise RuntimeError(mod_schema)
                    else:
                        mod_schema = _modify_schema(
                            self,
                            service,
                            schema_changes,
                            deltas,
                            use_non_globalid_relationships,
                        )
                        if mod_schema is not None:
                            raise RuntimeError(mod_schema)

        # Update form item
        form_zip = shutil.move(
            shutil.make_archive(
                self._si.id, "zip", os.path.join(tmp_name, self._si.id)
            ),
            tmp_name,
        )
        properties = {
            "connectVersion": connect_version,
            "typeKeywords": "xForm, Form, Survey123, Survey123 Connect",
        }
        if tags:
            properties["tags"] = tags
        if summary:
            properties["snippet"] = summary
        if description:
            properties["description"] = description
        self._si.update(properties, data=form_zip, thumbnail=thumbnail)

        # Create web map
        if create_web_map is True and initial_publish is True:
            wm = arcgis.mapping.WebMap()
            for lyr in list(self._ssi.layers + self._ssi.tables):
                wm.add_layer(
                    lyr, {"title": f"{self._si.title} - {lyr.properties.name}"}
                )
            wm_properties = {
                "title": self._si.title,
                "snippet": "",
                "tags": [],
                "typeKeywords": "ArcGIS Online,Data Editing,Explorer Web Map,Map,Offline,Online Map,Survey123Python,useOnly,Web Map",
            }
            web_map = wm.save(
                wm_properties, thumbnail=thumbnail, folder=self._si.ownerFolder
            )
            self._si.add_relationship(web_map, "Survey2Data")

        # Enable delete protection
        if enable_delete_protection is True:
            self._si.protect(enable=True)
            [
                x.protect(enable=True)
                for x in self._si.related_items("Survey2Service", direction="forward")
                + self._si.related_items("Survey2Data", direction="forward")
            ]
        shutil.rmtree(tmp_name, ignore_errors=True)
        return Survey(item=self._gis.content.get(self._si.id), sm=self._sm)

    # ----------------------------------------------------------------------
    @property
    def webhooks(self) -> list:
        """Returns a list of existing :class:`~arcgis.apps.survey123.Survey` webhooks"""
        url = f"{self._gis._url}/sharing/rest/content/items/{self._si.id}/info/{self._si.title}.info"
        params = {"f": "json"}
        submit = self._si._gis._con.get(url, params)
        try:
            webhook = submit["notificationsInfo"]["webhooks"]
        except KeyError:
            webhook = []
        return webhook

    # ----------------------------------------------------------------------
    def add_webhook(
        self,
        name: str,
        payload_url: str,
        trigger_events: Optional[list] = ["addData"],
        portal_info: Optional[bool] = False,
        submitted_record: Optional[bool] = False,
        user_info: Optional[bool] = False,
        server_response: Optional[bool] = False,
        survey_info: Optional[bool] = False,
        active: Optional[bool] = True,
    ) -> dict:
        """
        Add a webhook to your survey.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        name              Required string. The name for your webhook.
        ----------------  ---------------------------------------------------------------
        payload_url       Required string. The payload URL is where the survey information will be sent. This needs to be provided by an external webhook service.
        ----------------  ---------------------------------------------------------------
        trigger_events    Optional list. The trigger events describe the specific actions that will call the webhook. Options are "addData" and "editData". Set to "addData" by default.
        ----------------  ---------------------------------------------------------------
        portal_info       Optional boolean. Information about the ArcGIS organization where the survey is hosted. It contains the following properties:

                          + `url`
                          + `token`

        ----------------  ---------------------------------------------------------------
        submitted_record  Optional boolean. The survey record that was submitted. It contains the following properties:

                          + `attributes`
                          + `geometry`
                          + `layerInfo`
                          + `result`
                          + `repeats`
                          .. note::
                              Each object within the repeats array is a feature that has attributes, geometry, layerInfo, result, repeats, and attachments.
                          + `attachments`
                            + `id`
                            + `globalId`
                            + `name`
                            + `contentType`
                            + `size`
                            + `keywords`
                            + `url`
                            + `parentObjectId`

        ----------------  ---------------------------------------------------------------
        user_info         Optional boolean. Information about the ArcGIS organizational account for the user who submitted the survey. It contains the following properties:

                          + `username`
                          + `firstName`
                          + `lastName`
                          + `fullName`
                          + `email`

        ----------------  ---------------------------------------------------------------
        server_response   Optional boolean. The response from the applyEdits operation.
                          It includes the global IDs for the features created by the operation and whether the operation was successful.
        ----------------  ---------------------------------------------------------------
        survey_info       Optional boolean. Information about the survey that generated the webhook. It contains the following properties:

                          + `formItemId`
                          + `formTitle`
                          + `serviceItemId`
                          + `serviceUrl`

        ----------------  ---------------------------------------------------------------
        active            Optional boolean. Determines whether the webhook will be active when saved. Set to True by default.
        ================  ===============================================================

        :Returns: Dictionary {success, webhookId}

        """
        url = f"https://{self._baseurl}/api/survey/{self._si.id}/webhook/add"
        params = {
            "f": "json",
            "webhook": {
                "active": active,
                "name": name,
                "url": payload_url,
                "includePortalInfo": portal_info,
                "includeServiceRequest": submitted_record,
                "includeUserInfo": user_info,
                "includeServiceResponse": server_response,
                "includeSurveyInfo": survey_info,
                "events": trigger_events,
            },
            "portalUrl": self._gis._url,
        }
        submit = self._si._gis._con.post(url, params)
        return submit

    # ----------------------------------------------------------------------
    def update_webhook(
        self,
        webhook_id: str,
        name: Optional[str] = None,
        payload_url: Optional[str] = None,
        trigger_events: Optional[list] = None,
        portal_info: Optional[bool] = None,
        submitted_record: Optional[bool] = None,
        user_info: Optional[bool] = None,
        server_response: Optional[bool] = None,
        survey_info: Optional[bool] = None,
        active: Optional[bool] = None,
    ) -> dict:
        """
        Update a webhook with your survey.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        webhook_id        Required string. The ID for the webhook to update.
        ----------------  ---------------------------------------------------------------
        name              Optional string. The name for your webhook.
        ----------------  ---------------------------------------------------------------
        payload_url       Optional string. The payload URL is where the survey information will be sent. This needs to be provided by an external webhook service.
        ----------------  ---------------------------------------------------------------
        trigger_events    Optional list. The trigger events describe the specific actions that will call the webhook. Options are "addData" and "editData".
        ----------------  ---------------------------------------------------------------
        portal_info       Optional boolean. Information about the ArcGIS organization where the survey is hosted. It contains the following properties:

                          + `url`
                          + `token`

        ----------------  ---------------------------------------------------------------
        submitted_record  Optional boolean. The survey record that was submitted. It contains the following properties:

                          + `attributes`
                          + `geometry`
                          + `layerInfo`
                          + `result`
                          + `repeats`
                          .. note::
                              Each object within the repeats array is a feature that has attributes, geometry, layerInfo, result, repeats, and attachments.
                          + `attachments`
                            + `id`
                            + `globalId`
                            + `name`
                            + `contentType`
                            + `size`
                            + `keywords`
                            + `url`
                            + `parentObjectId`

        ----------------  ---------------------------------------------------------------
        user_info         Optional boolean. Information about the ArcGIS organizational account for the user who submitted the survey. It contains the following properties:

                          + `username`
                          + `firstName`
                          + `lastName`
                          + `fullName`
                          + `email`

        ----------------  ---------------------------------------------------------------
        server_response   Optional boolean. The response from the applyEdits operation.
                          It includes the global IDs for the features created by the operation and whether the operation was successful.
        ----------------  ---------------------------------------------------------------
        survey_info       Optional boolean. Information about the survey that generated the webhook. It contains the following properties:

                          + `formItemId`
                          + `formTitle`
                          + `serviceItemId`
                          + `serviceUrl`

        ----------------  ---------------------------------------------------------------
        active            Optional boolean. Determines whether the webhook will be active when saved.
        ================  ===============================================================

        :Returns: Dictionary {success, webhookId}

        """

        url = f"https://{self._baseurl}/api/survey/{self._si.id}/webhook/{webhook_id}/update"
        existing_webhook = [x for x in self.webhooks if x["id"] == webhook_id][0]

        params = {
            "f": "json",
            "webhook": {
                "active": active if active is not None else existing_webhook["active"],
                "name": name if name is not None else existing_webhook["name"],
                "url": (
                    payload_url if payload_url is not None else existing_webhook["url"]
                ),
                "includePortalInfo": (
                    portal_info
                    if portal_info is not None
                    else existing_webhook["includePortalInfo"]
                ),
                "includeServiceRequest": (
                    submitted_record
                    if submitted_record is not None
                    else existing_webhook["includeServiceRequest"]
                ),
                "includeUserInfo": (
                    user_info
                    if user_info is not None
                    else existing_webhook["includeUserInfo"]
                ),
                "includeServiceResponse": (
                    server_response
                    if server_response is not None
                    else existing_webhook["includeServiceResponse"]
                ),
                "includeSurveyInfo": (
                    survey_info
                    if survey_info is not None
                    else existing_webhook["includeSurveyInfo"]
                ),
                "events": (
                    trigger_events
                    if trigger_events is not None
                    else existing_webhook["events"]
                ),
            },
            "portalUrl": self._gis._url,
        }
        submit = self._si._gis._con.post(url, params)
        return submit

    # ----------------------------------------------------------------------
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Deletes a webhook from a survey

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        webhook_id        Required string. The ID for the webhook to delete.
        ================  ===============================================================

        :Returns: String

        """

        url = f"https://{self._baseurl}/api/survey/{self._si.id}/webhook/{webhook_id}/delete"
        params = {"portalUrl": self._gis._url}
        submit = self._si._gis._con.post(url, params)
        return submit["success"]
