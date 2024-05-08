from __future__ import annotations
from typing import Optional, Union
import uuid
from arcgis.auth.tools import LazyLoader
import re
import copy

arcgis = LazyLoader("arcgis")
Content = LazyLoader("arcgis.apps.storymap.story_content")
storymap = LazyLoader("arcgis.apps.storymap.story")
json = LazyLoader("json")
time = LazyLoader("time")
utils = LazyLoader("arcgis.apps.storymap._utils")


###############################################################################################################
class Briefing(object):
    """
    Synthesize critical information and maintain mission readiness with briefings, a new slide-based presentation
    style now available as a type of ArcGIS StoryMap. Make data-driven decisions and provide meaningful context to
    your audience by infusing your presentations with real-time data and dynamic maps. Briefings also allow you to
    unify images, videos, and other multimedia in your presentation to create a cohesive experience for both you
    and your viewers.

    Example use cases include on-the-ground disaster briefings, budget numbers presented in real-time, and daily
    leadership briefings. After the briefings mobile app launches in September, you'll be able to securely connect
    with your stakeholders wherever they are with a tablet app that works on- and offline.

    Create a StoryMap Briefing object to make edits to a story. Can be created from an item of type 'StoryMap Briefing',
    an item id for that type of item, or if nothing is passed, a new story is created from a generic draft.

    If an Item or item_id is passed in, only published changes or new drafts are taken from the StoryMap Briefing.
    If you have a story with unpublished changes, they will not appear when you construct your story with the API.
    If you start to work on your Briefing that has unpublished changes and save from the Python API, your
    unpublished changes on the GUI will be overwritten with your work from the API.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    item                Optional String or Item. The string for an item id or an item of type
                        'StoryMap Briefing'. If no item is passed, a new story is created and saved to
                        your active portal.
    ---------------     --------------------------------------------------------------------
    gis                 Optional instance of :class:`~arcgis.gis.GIS` . If none provided the active gis is used.
    ===============     ====================================================================
    """

    _properties = None
    _gis = None
    _itemid = None
    _item = None
    _resources = None

    def __init__(
        self,
        item: Optional[Union[arcgis.gis.Item, str]] = None,
        gis: Optional[arcgis.gis.GIS] = None,
    ):
        self._gis = gis or arcgis.env.active_gis
        self._validate_gis()

        # Section: Set up existing story
        if item and isinstance(item, str):
            item = self._get_item_by_id(item)

        if self._is_existing_briefing(item):
            self._validate_item(item)
            self._create_existing_briefing()
        else:
            # If no item was provided create a new story map
            self._create_new_briefing()
        # Get the story url
        self._url = self._get_url()

    # ----------------------------------------------------------------------
    def _validate_gis(self):
        if not self._gis._portal.is_logged_in:
            raise Exception("Must be logged into a Portal Account")

    def _get_item_by_id(self, item_id):
        item = self._gis.content.get(item_id)
        if item is None:
            raise ValueError(
                f"Cannot find storymap briefing associated with item id {item_id} in your portal. Please check it is correct."
            )
        return item

    def _validate_item(self, item):
        if not isinstance(item, arcgis.gis.Item):
            raise ValueError("Invalid item provided")

        type_keywords = set(item.typeKeywords)
        if "StoryMap" not in type_keywords or "storymapbriefing" not in type_keywords:
            raise ValueError("Item is not a StoryMap Briefing")

        self._item = item
        self._itemid = item.itemid
        self._resources = item.resources.list()

    def _is_existing_briefing(self, item):
        return isinstance(item, arcgis.gis.Item)

    # ----------------------------------------------------------------------
    def _create_existing_briefing(self):
        saved_drafts = [
            val
            for resource in self._resources
            for key, val in resource.items()
            if key == "resource"
            and (re.match("draft_[0-9]{13}.json", val) or re.match("draft.json", val))
        ]

        if len(saved_drafts) == 0:
            data = self._item.resources.get("published_data.json", try_json=True)
        else:
            most_recent_draft = max(saved_drafts, key=lambda x: (x[6:19], x))
            data = self._item.resources.get(most_recent_draft, try_json=True)

        self._properties = data

    # ----------------------------------------------------------------------
    def _create_new_briefing(self):
        # Get template from _ref folder
        template = copy.deepcopy(arcgis.apps.storymap._ref.briefing)
        # Add correct by-line and locale
        template["nodes"]["n-3r3mhh"]["data"]["byline"] = self._gis._username

        # Create unique briefing node id
        briefing_node = "n-" + uuid.uuid4().hex[0:6]
        template["root"] = briefing_node
        template["nodes"][briefing_node] = template["nodes"]["n-k23c2p"]
        del template["nodes"]["n-k23c2p"]
        # Set properties for the briefing
        self._properties = template
        # Create text for resource call
        text = json.dumps(template)
        # Create a temporary title
        title = f"Briefing via Python {uuid.uuid4().hex[:10]}"
        # Create a temporary draft name
        draft = f"draft_{int(time.time() * 1000)}.json"
        # Will be posted as a draft
        br_version = self._gis._con.get("https://storymaps.arcgis.com/version")[
            "version"
        ]
        keywords = ",".join(
            [
                "alphabriefing",
                "arcgis-storymaps",
                f"smdraftresourceid:{draft}",
                f"smversiondraft:{br_version}",
                "StoryMap",
                "storymapbriefing",
                "Web Application",
                "smstatusdraft",
            ]
        )
        # Get default thumbnail for a new item
        thumbnail = self._get_thumbnail()
        # Set the item properties dict to add new item to active gis
        item_properties = {
            "title": title,
            "typeKeywords": keywords,
            "type": "StoryMap",
        }
        # Add item to active gis and set properties
        self._item = self._gis.content.add(
            item_properties=item_properties, thumbnail=thumbnail
        )
        # Assign to story properties
        self._itemid = self._item.itemid
        # Make a resource call with the template to create json draft needed
        utils._add_resource(self, resource_name=draft, text=text, access="private")
        # Assign resources to item
        self._resources = self._item.resources.list()

    # ----------------------------------------------------------------------
    def _repr_html_(self):
        """
        HTML Representation for IPython Notebook
        """
        return self._item._repr_html_()

    # ----------------------------------------------------------------------
    def __str__(self):
        """Return the url of the storymap"""
        return self._url

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()

    # ----------------------------------------------------------------------
    def _refresh(self):
        """Load the latest data from the item"""
        if self._item:
            self._properties = json.loads(self._item.get_data())

    # ----------------------------------------------------------------------
    def _get_url(self) -> str:
        """
        Private method to determine what the story url is. This is used to publish
        and have the correct path set.
        """
        if self._gis._is_agol:
            # Online
            self._url = "https://storymaps.arcgis.com/briefings/{briefingid}".format(
                briefingid=self._itemid
            )
        else:
            # Enterprise
            self._url = "{portal}/apps/storymaps/briefings/{briefingid}".format(
                portal=self._gis.url, briefingid=self._itemid
            )
        return self._url

    # ----------------------------------------------------------------------
    def _get_thumbnail(self) -> str:
        """
        Private method to get the default thumbnail path dependent on whether the
        user is Online or on Enterprise.
        """
        return utils._get_thumbnail(self._gis)

    # ----------------------------------------------------------------------
    def show(self, width: Optional[int] = None, height: Optional[int] = None):
        """
        Show a preview of the briefing. The default is a width of 700 and height of 300.

        ===============     ====================================================================
        **Parameter**       **Description**
        ---------------     --------------------------------------------------------------------
        width               Optional integer. The desired width to show the preview.
        ---------------     --------------------------------------------------------------------
        height              Optional integer. The desired height to show the preview.
        ===============     ====================================================================

        :return:
            An Iframe display of the briefing if possible, else the item url is returned to be
            clicked on.
        """
        return utils.show(self._item, width, height)

    # ----------------------------------------------------------------------
    @property
    def slides(self):
        """
        Get a list of all the content instances in order of appearance in the story.
        This returns a list of class instances for the content in the story.
        """
        contents = []
        # get the values from the nodes list and return only these
        nodes = utils._create_node_dict(self)
        for node in nodes:
            content = list(node.values())[0]
            contents.append(content)
        return contents

    # ----------------------------------------------------------------------
    @property
    def actions(self):
        """
        Get list of action nodes. These are nodes that trigger an action to occur, for
        example when text is linked to an image, map, etc.
        """
        actions = []
        if "actions" in self._properties:
            # actions are stored in the briefing properties as a list of dictionaries
            for action in self._properties["actions"]:
                # create a class from the node id
                node = utils._assign_node_class(self, action["origin"])
                actions.append(node)
        return actions

    # ----------------------------------------------------------------------
    def cover(
        self,
        title: Optional[str] = None,
        type: str = None,
        summary: Optional[str] = None,
        by_line: Optional[str] = None,
        media: Optional[Union[Content.Image, Content.Video]] = None,
    ):
        """
        A briefing's cover is the first slide.
        This method allows the cover to be edited by updating the title, byline, media, and more.
        Changing one part of the briefing cover will not change the rest of the cover. If just the
        media is passed in then only the media will change.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Optional string. The title of the Briefing cover.
        ---------------     --------------------------------------------------------------------
        type                Optional string. The type of briefing cover to be used in the story.

                            ``Values: "full" | "sidebyside" | "minimal"``
        ---------------     --------------------------------------------------------------------
        summary             Optional string. The description of the story.
        ---------------     --------------------------------------------------------------------
        by_line             Optional string. Crediting the author(s).
        ---------------     --------------------------------------------------------------------
        media               Optional url or file path or :class:`~arcgis.apps.storymap.story_content.Image` or
                            :class:`~arcgis.apps.storymap.story_content.Video` object.
        ===============     ====================================================================

        :return: True if the cover was updated successfully.

        .. code-block:: python

            briefing = Briefing(<briefing item>)
            briefing.cover(title="My Briefing Title", type="sidebyside", summary="My little summary", by_line="python_dev")
            briefing.save()

        """
        # call method to update cover
        utils.cover(self, title, type, summary, by_line, media)
        return True

    # ----------------------------------------------------------------------
    def theme(self, theme: Union[storymap.Themes, str] = storymap.Themes.SUMMIT):
        """
        Each briefing has a theme node in its resources. This method can be used to change the theme.
        To add a custom theme to your story, pass in the item_id for the item of type Story Map Theme.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        theme               Required Themes Style or custom theme item id.
                            The theme to set on the briefing.

                            Values: `SUMMIT` | `TIDAL` | `MESA` | `RIDGELINE` | `SLATE` | `OBSIDIAN` | `<item_id>`
        ===============     ====================================================================

        .. code-block:: python

            >>> from arcgis.apps.storymap import Themes, Briefing

            >>> briefing = Briefing()
            >>> briefing.theme(Themes.TIDAL)
        """
        # call method to update theme
        utils.theme(self, theme)
        return True

    # ----------------------------------------------------------------------
    def add(
        self,
        layout: str,
        *,
        sublayout: Optional[str] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        section_position: Optional[str] = None,
        position: Optional[int] = None,
    ):
        """
        Use this method to add content to your StoryMap. content can be of various class types and when
        you add this content you can specify a caption, alt_text, display style, and the position
        at which it will be in your story.
        Not passing in any content means a separator will be added.

        ===================     ====================================================================
        **Parameter**           **Description**
        -------------------     --------------------------------------------------------------------
        layout                  Required LayoutType or string, the layout type of the slide.
        -------------------     --------------------------------------------------------------------
        sublayout               Optional SubLayoutType or string, the sublayout type of the slide.
                                Only applicable when the layout is "double" or "titleless-double".
        -------------------     --------------------------------------------------------------------
        title                   Optional string or :class:`~arcgis.apps.storymap.story_content.Text` object, the title of the slide.
                                Text can only be of type heading (h2).
        -------------------     --------------------------------------------------------------------
        subtitle                Optional string or :class:`~arcgis.apps.storymap.story_content.Text` object, the subtitle of the slide.
                                Text can only be of type paragraph.
        -------------------     --------------------------------------------------------------------
        section_position        Optional string, the title panel position of the section slide. Only
                                applicable for "section-double".
                                Values: 'start' | 'end'
        -------------------     --------------------------------------------------------------------
        position                Optional Integer. Indicates the position in which the slide will be
                                added. If no position is provided, the slide will be placed at the end.
        ===================     ====================================================================

        :return: The new slide that was added to the story

        """
        slide = Content.BriefingSlide(
            layout=layout,
            sublayout=sublayout,
            title=title,
            subtitle=subtitle,
            section_position=section_position,
            story=self,
        )

        # Add slide to story
        slide._add_to_story(story=self)

        # Add to story children
        utils._add_child(self, node_id=slide.node, position=position)

        return slide

    # ----------------------------------------------------------------------
    def move(
        self, slide: int, position: Optional[int] = None, delete_current: bool = False
    ):
        """
        Move a slide to another position. The slide currently at that position will
        be moved down one space. The slide at the current position can be deleted
        instead of moved if `delete_current` is set to True.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        slide               Required integer. The slide number to move. The cover is slide 0 and this
                            cannot be moved.
        ---------------     --------------------------------------------------------------------
        position            Optional Integer. Indicates the position in which the slide will be
                            added. If no position is provided, the slide will be placed at the end.
        ---------------     --------------------------------------------------------------------
        delete_current      Optional Boolean. If set to True, the slide at the current position will
                            be deleted instead of moved down one space. Default is False.
        ===============     ====================================================================

        :return: True if the slide was moved successfully.
        """
        # Get list of slide children
        root_id = self._properties["root"]
        ui = self._properties["nodes"][root_id]["children"]
        children = self._properties["nodes"][ui[0]]["children"]

        # Check that slide is not cover
        if slide == 0:
            raise ValueError("Cannot move the cover slide.")

        # Get slide position if none is provided
        if position is None:
            # Move to end
            position = len(children)

        # move the slide to correct position in the list
        self._properties["nodes"][ui[0]]["children"].insert(
            position, children.pop(slide)
        )

        # Delete the slide that was at the position before if specified
        if delete_current:
            # do position+1 since the slide was moved up one space in insert
            self._properties["nodes"].pop(children[position + 1])

        return True

    # ----------------------------------------------------------------------
    def save(
        self,
        title: Optional[str] = None,
        tags: Optional[list] = None,
        access: str = None,
        publish: bool = False,
    ):
        """
        This method will save your Story Map to your active GIS. The story will be saved
        with unpublished changes unless `publish` parameter is specified to True.

        The title only needs to be specified if a change is wanted, otherwise existing title
        is used.

        .. warning::
            Publishing your story through the Python API means it will not go through the Story Map
            issue checker. It is recommended to publish through the Story Maps builder if you
            want your story to go through the issue checker.

        .. warning::
            Changes to the published story may not be visible for up to one hour. You can open
            the story in the story builder to force changes to appear immediately and perform
            other optimizations, such as updating the story's social/SEO metadata.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Optional string. The title of the StoryMap.
        ---------------     --------------------------------------------------------------------
        tags                Optional string. The tags of the StoryMap.
        ---------------     --------------------------------------------------------------------
        access              Optional string. The access of the StoryMap. If none is specified, the
                            current access is kept. This is used when `publish` parameter is set
                            to True.

                            Values: `private` | `org` | `public`
        ---------------     --------------------------------------------------------------------
        publish             Optional boolean. If True, the story is saved and also published.
                            Default is false so story is saved with unpublished changes.
        ===============     ====================================================================


        :return: The Item that was saved to your active GIS.

        """
        # call the save method in common utils module
        return utils.save(self, title, tags, access, publish)

    # ----------------------------------------------------------------------
    def delete_briefing(self):
        """
        Deletes the briefing item.
        """
        # deletes the item
        return utils.delete_item(self)

    # ----------------------------------------------------------------------
    def duplicate(self, title: Optional[str] = None):
        """
        Duplicate the story. All items will be duplicated as they are. This allows you to create
        a briefing template and duplicate it when you want to work with it.

        It is highly recommended that once the duplicate is created, open it in StoryMap Briefing
        builder to ensure the issue checker finds any issues before editing.

        .. note::
            Can be used with ArcGIS Online or with ArcGIS Enterprise starting 10.8.1.

        .. note::
            To duplicate into another organization, use the :func:`~arcgis.gis.contentManager.clone_items` method.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Optional string. The title of the duplicated story. Only available
                            for ArcGIS Online.
        ===============     ====================================================================

        :return:
            The Item that was created.

        .. code-block:: python

            # Example for ArcGIS Online
            >>> briefing = Briefing(<briefing item>)
            >>> briefing.duplicate("A Briefing Copy")
        """
        # call the duplicate (clones the item)
        return utils.duplicate(self, title)

    # ----------------------------------------------------------------------
    def copy_content(self, target_briefing: Briefing, content: list):
        """
        Copy the content from one briefing to another. This will copy the content
        indicated to the target briefing in the order they are provided.

        .. note::
            Do not forget to save the target briefing once you are done copying and making
            any further edits.

        .. note::
            This method can take time depending on the number of resources. Each resource coming
            from a file must be copied over and heavy files, such as videos or audio, can be time
            consuming.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        target_briefing     Required Briefing instance. The target briefing that the content will be
                            copied to.
        ---------------     --------------------------------------------------------------------
        content             Required list of content. The list of content that will be copied to
                            the target briefing.
        ===============     ====================================================================

        :return:
            True if all content has been successfully copied over.

        """
        return utils.copy_content(self, target_briefing, content)
