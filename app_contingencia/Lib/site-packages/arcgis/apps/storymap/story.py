from __future__ import annotations
from typing import Optional, Union
import uuid
from enum import Enum
from arcgis._impl.common._deprecate import deprecated
from arcgis.auth.tools import LazyLoader
import re
import copy

arcgis = LazyLoader("arcgis")
Content = LazyLoader("arcgis.apps.storymap.story_content")
json = LazyLoader("json")
time = LazyLoader("time")
utils = LazyLoader("arcgis.apps.storymap._utils")


class Themes(Enum):
    """
    Represents the Supported Theme Type Enumerations.
    Example: story_map.theme(Theme.Slate)
    """

    SUMMIT = "summit"
    OBSIDIAN = "obsidian"
    RIDGELINE = "ridgeline"
    MESA = "mesa"
    TIDAL = "tidal"
    SLATE = "slate"


###############################################################################################################
class StoryMap(object):
    """
    A Story Map is a web map that has been thoughtfully created, given context, and provided
    with supporting information so it becomes a stand-alone resource. It integrates maps, legends,
    text, photos, and video and provides functionality, such as swipe, pop-ups, and time sliders,
    that helps users explore this content.

    ArcGIS StoryMaps is the next-generation storytelling tool in ArcGIS, and story authors are
    encouraged to use this tool to create stories. The Python API can help you create and edit
    your stories.

    Create a Story Map object to make edits to a story. Can be created from an item of type 'Story Map',
    an item id for that type of item, or if .nothing is passed, a new story is created from a generic draft.

    If an Item or item_id is passed in, only published changes or new drafts are taken from the Story Map.
    If you have a story with unpublished changes, they will not appear when you construct your story with the API.
    If you start to work on your Story that has unpublished changes and save from the Python API, your
    unpublished changes on the GUI will be overwritten with your work from the API.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    item                Optional String or Item. The string for an item id or an item of type
                        'Story Map'. If no item is passed, a new story is created and saved to
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
        # Section: Set up gis
        self._setup_gis(gis)
        self._setup_storymap(item)

    def _setup_gis(self, gis):
        if gis is None:
            # If no gis, find active env
            gis = arcgis.env.active_gis
            self._gis = gis

        if not (gis and gis._portal.is_logged_in):
            raise ValueError("Must be logged into a Portal Account")

    def _setup_storymap(self, item):
        if item and isinstance(item, str):
            # Get item using the item id
            item = self._gis.content.get(item)
            if item is None:
                # Error with storymap in current gis
                raise ValueError("Cannot find storymap associated with this item id.")
        if item and isinstance(item, arcgis.gis.Item) and item.type == "StoryMap":
            self._setup_existing_storymap(item)
        elif (
            item
            and isinstance(item, arcgis.gis.Item)
            and "StoryMap" not in item.typeKeywords
        ):
            # Throw error if item is not of type Story Map
            raise ValueError("Item is not a Story Map")
        else:
            # If no item was provided create a new story map
            self._create_new_storymap()
        # Get the story url
        self._url = self._get_url()

        #  Assign resources to item
        self._resources = self._item.resources.list()

    # ----------------------------------------------------------------------
    def _setup_existing_storymap(self, item):
        saved_drafts = [
            resource["resource"]
            for resource in item.resources.list()
            if self._is_draft(resource["resource"])
        ]

        if saved_drafts:
            current_draft = self._get_most_recent_draft(saved_drafts)
            self._properties = item.resources.get(current_draft, try_json=True)
        else:
            self._properties = item.resources.get("published_data.json", try_json=True)
        self._item = item
        self._itemid = item.itemid

    @staticmethod
    def _is_draft(resource):
        return re.match(r"draft_[0-9]{13}\.json|draft\.json", resource)

    def _get_most_recent_draft(self, drafts):
        drafts.remove("draft.json") if "draft.json" in drafts else None
        return max(drafts, key=lambda x: x[6:19]) if drafts else None

    # ----------------------------------------------------------------------
    def _create_new_storymap(self):
        # Step 1: Get template from _ref folder
        template = self._get_storymap_template()

        # Step 2: Customize template
        self._customize_template(template)

        # Step 3: Create a unique story node id
        self._create_unique_story_node(template)

        # Step 4: Set properties for the story
        self._properties = template

        # Step 5: Create a temporary title
        title = f"StoryMap via Python {uuid.uuid4().hex[:10]}"

        # Step 6: Create draft resource name
        draft = f"draft_{int(time.time() * 1000)}.json"

        # Step 7: Set keywords
        keywords = self._get_keywords(draft)

        # Step 8: Get default thumbnail for a new item
        thumbnail = self._get_thumbnail()

        # Step 9: Set the item properties
        item_properties = {
            "title": title,
            "typeKeywords": keywords,
            "type": "StoryMap",
        }

        # Step 10: Add item to active GIS and set properties
        self._item = self._gis.content.add(
            item_properties=item_properties, thumbnail=thumbnail
        )
        self._itemid = self._item.itemid

        # Step 11: Make a resource call with the template to create json draft needed
        utils._add_resource(
            self, resource_name=draft, text=json.dumps(template), access="private"
        )

    def _get_storymap_template(self):
        return copy.deepcopy(arcgis.apps.storymap._ref.storymap_2)

    def _customize_template(self, template):
        template["nodes"]["n-aTn8ak"]["data"]["byline"] = self._gis._username
        template["nodes"]["n-4xkUEe"]["config"]["storyLocale"] = (
            self._gis.users.me.culture or "en-US"
        )

    def _create_unique_story_node(self, template):
        story_node = "n-" + uuid.uuid4().hex[:6]
        template["root"] = story_node
        template["nodes"][story_node] = template["nodes"]["n-4xkUEe"]
        del template["nodes"]["n-4xkUEe"]

    def _get_keywords(self, draft):
        sm_version = self._gis._con.get("https://storymaps.arcgis.com/version")[
            "version"
        ]
        return ",".join(
            [
                "arcgis-storymaps",
                "StoryMap",
                "Web Application",
                "smstatusdraft",
                f"smversiondraft:{sm_version}",
                "python-api",
                f"smeditorapp:python-api-{arcgis.__version__}",
                f"smdraftresourceid:{draft}",
            ]
        )

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
            self._url = "https://storymaps.arcgis.com/stories/{storyid}".format(
                storyid=self._itemid
            )
        else:
            # Enterprise
            self._url = "{portal}/apps/storymaps/stories/{storyid}".format(
                portal=self._gis.url, storyid=self._itemid
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
        Show a preview of the story. The default is a width of 700 and height of 300.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        width               Optional integer. The desired width to show the preview.
        ---------------     --------------------------------------------------------------------
        height              Optional integer. The desired height to show the preview.
        ===============     ====================================================================

        :return:
            An Iframe display of the story map if possible, else the item url is returned to be
            clicked on.
        """
        return utils.show(self._item, width, height)

    # ----------------------------------------------------------------------
    @property
    def cover_date(self):
        """
        Get/Set the date type shown on the story cover.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        date_type           Optional String. Set the desired date type for the story cover.

                            ``Values: "first-published" | "last-published" | "none"``
        ===============     ====================================================================

        """
        root = self._properties["root"]
        return self._properties["nodes"][root]["config"]["coverDate"]

    # ----------------------------------------------------------------------
    @cover_date.setter
    def cover_date(self, date_type):
        """
        See cover_date property doc
        """
        # cover date is found in story node (i.e. root node id)
        root = self._properties["root"]
        self._properties["nodes"][root]["config"]["coverDate"] = date_type
        return self.cover_date

    # ----------------------------------------------------------------------
    @property
    def story_locale(self):
        """
        Get/Set the locale and language of the story.

        If your story was created with the Python API then the default is "en-US"
        """
        # story_locale is found in story node (i.e. root node id)
        root = self._properties["root"]
        return (
            self._properties["nodes"][root]["config"]["storyLocale"]
            if "storyLocale" in self._properties["nodes"][root]["config"]
            else "en-US"
        )

    # ----------------------------------------------------------------------
    @story_locale.setter
    def story_locale(self, locale):
        """
        See story_locale property above
        """
        # cover date is found in story node (i.e. root node id)
        root = self._properties["root"]
        self._properties["nodes"][root]["config"]["storyLocale"] = locale
        return self.story_locale

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """This property returns the storymap's JSON."""
        return self._properties

    # ----------------------------------------------------------------------
    @deprecated(
        deprecated_in="2.2.0",
        removed_in="3.0.0",
        current_version="2.3.0",
        details="`nodes` property has been deprecated, use `content_list` property instead.",
    )
    @property
    def nodes(self):
        """
        Get main nodes in order of appearance in the story. This will return a list
        of dictionaries specifying the node ids and the class content they correspond to.
        If there is no class for the content, a string is returned with the content type.
        """
        # node_dict contains key-value pairs where the value is the class instance
        node_dict = self._create_node_dict()
        # make the value the string representation of the class
        nodes = []
        for node in node_dict:
            nodes.append({k: node[k] for k in node})
        return nodes

    # ----------------------------------------------------------------------
    @property
    def content_list(self):
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
        Get list of action nodes.
        """
        actions = []
        if "actions" in self._properties:
            for action in self._properties["actions"]:
                node = utils._assign_node_class(self, action["origin"])
                actions.append(node)
        return actions

    # ----------------------------------------------------------------------
    @property
    def navigation_list(self):
        """
        Get a list of the nodes that are linked in the navigation.
        """
        # navigation item has list of links corresponding to the text nodes in the navigation
        nav = self.get(type="navigation")[0]
        for key, value in nav.items():
            node_id = key
        try:
            links = self._properties["nodes"][node_id]["data"]["links"]
            node_ids = []
            for link in links:
                for key, value in link.items():
                    # Only return list of node_ids this way easier for navigation method
                    if key == "nodeId":
                        node_ids.append(value)
            return node_ids
        except Exception:
            return None

    # ----------------------------------------------------------------------
    @deprecated(
        deprecated_in="2.2.0",
        removed_in="3.0.0",
        current_version="2.3.0",
        details="`get` method has been deprecated, use `content_list` property instead.",
    )
    def get(self, node: Optional[str] = None, type: Optional[str] = None):
        """
        Get node(s) by type or by their id. Using this function will help grab a specific node
        from the story if a node id is provided. Set this to a variable and this way edits can be
        made on the node in the story.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        node                Optional string. The node id for the node that should be returned.
                            This will return the class of the node if of type story content.
        ---------------     --------------------------------------------------------------------
        type                Optional string. The type of nodes that user wants returned.
                            If none specified, list of all nodes returned.


                            Values: `image` | `video` | `audio` | `embed` | `webmap` | `text` |
                            `button` | `separator` | `expressmap` | `webscene` | `immersive` | `code`
        ===============     ====================================================================

        :return:
            If type specified: List of node ids and their types in order of appearance in the story map.

            If node_id specified: The node itself.


        .. code-block:: python

            >>> story = StoryMap(<story item>)

            # Example get by type
            >>> story.get(type = "text")
            Returns a list of all nodes of type text

            # Example by id
            >>> text = story.get(node= "<id for text node>")
            >>> text.properties
            Returns a specific node of type text

        """
        return utils.get(self, node, type)

    # ----------------------------------------------------------------------
    def cover(
        self,
        title: Optional[str] = None,
        type: str = None,
        summary: Optional[str] = None,
        by_line: Optional[str] = None,
        image: Optional[Content.Image] = None,
    ):
        """
        A story's cover is at the top of the story and always the first node.
        This method allows the cover to be edited by updating the title, byline, image, and more.
        Changing one part of the story cover will not change the rest of the story cover. If just the
        image is passed in then only the image will change.

        .. note::
            To change the date seen on the story cover, use the ``cover_date`` property.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Optional string. The title of the StoryMap cover.
        ---------------     --------------------------------------------------------------------
        type                Optional string. The type of story cover to be used in the story.

                            ``Values: "full" | "sidebyside" | "minimal"``
        ---------------     --------------------------------------------------------------------
        summary             Optional string. The description of the story.
        ---------------     --------------------------------------------------------------------
        by_line             Optional string. Crediting the author(s).
        ---------------     --------------------------------------------------------------------
        image               Optional url or file path or :class:`~arcgis.apps.storymap.story_content.Image`
                            object. The cover image for the story cover.
        ===============     ====================================================================

        :return: Dictionary representation of the story cover node.

        .. code-block:: python

            story = StoryMap(<story item>)
            story.cover(title="My Story Title", type="minimal", summary="My little summary", by_line="python_dev")
            story.save()

        """
        # call method to update cover
        utils.cover(self, title, type, summary, by_line, image)
        return True

    # ----------------------------------------------------------------------
    def navigation(
        self, nodes: Optional[list[str]] = None, hidden: Optional[bool] = None
    ):
        """
        Story navigation is a way for authors to add headings as
        links to allow readers to navigate between different sections
        of a story. The story navigation node takes ``TextStyle.HEADING`` text styles
        as its only allowed children.
        You can only have 30 :class:`~arcgis.apps.storymap.story_content.Text` child nodes
        as visible and act as links within a story.

        The text nodes must already exist in the story. Pass the list of node ids for the heading
        text nodes to assign them to the navigation.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        nodes               Optional list of nodes to include in the navigation. These nodes can
                            only be of style heading ("h2").
                            Include in order. This will override current list and order.

                            To see current list use ``navigation_list`` property.
        ---------------     --------------------------------------------------------------------
        hidden              Optional boolean. If True, the navigation is hidden.
        ===============     ====================================================================

        :return:
            List of nodes in the navigation.

        .. code-block:: python

            #Example
            >>> story = StoryMap("<existing story id>")
            >>> story.navigation_list

            >>> story.navigation(["<header node id>", "<header node id>"], False)
        """

        # Check if navigation node already exists
        for node, node_info in self._properties["nodes"].items():
            for key, val in node_info.items():
                if key == "type" and val == "navigation":
                    node_id = node

        links = []
        # If none is provided, set to what is already there
        if nodes is not None:
            # check nodes are correct and add in order with linkType
            for node in nodes:
                if self._properties["nodes"][node]["data"]["type"] == "h2":
                    links.append({"nodeId": node, "linkType": "story-heading"})
                elif self._properties["nodes"][node]["data"]["type"] == "h4":
                    links.append({"nodeId": node, "linkType": "credits-heading"})
        else:
            links = self._properties["nodes"][node_id]["data"]["links"]
        if hidden is None:
            hidden = self._properties["nodes"][node_id]["config"]["isHidden"]

        # Update navigation
        self._properties["nodes"][node_id] = {
            "type": "navigation",
            "data": {"links": links},
            "config": {"isHidden": hidden},
        }

        return self.navigation_list

    # ----------------------------------------------------------------------
    def theme(self, theme: Union[Themes, str] = Themes.SUMMIT):
        """
        Each story has a theme node in its resources. This method can be used to change the theme.
        To add a custom theme to your story, pass in the item_id for the item of type Story Map Theme.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        theme               Required Themes Style or custom theme item id.
                            The theme to set the story to.

                            Values: `SUMMIT` | `TIDAL` | `MESA` | `RIDGELINE` | `SLATE` | `OBSIDIAN` | `<item_id>`
        ===============     ====================================================================

        .. code-block:: python

            >>> from arcgis.apps.storymap import Themes

            >>> story = StoryMap()
            >>> story.theme(Themes.TIDAL)
        """
        # call method to update theme
        utils.theme(self, theme)
        return True

    # ----------------------------------------------------------------------
    def credits(
        self,
        content: Optional[str] = None,
        attribution: Optional[str] = None,
        heading: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Credits are found at the end of the story and thus are always the last node.

        To create a credit, add the text that should be shown on each side of the divider.
        content represents the text seen on the left side and attribution is in line with content
        on the right side of the divider. (i.e. 'content' | 'attribution')

        Adding ``content`` and ``attribution`` will add a new line to the credits and will not change previous
        credits.

        Adding ``heading`` and ``description`` will change what is currently in place.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Optional String. The content to be added. (Seen on the left side of
                            the credits.)

                            Make sure text has '<strong> </strong>' tags.
                            Adds to the existing credits.
        ---------------     --------------------------------------------------------------------
        attribution         Optional String. The attribution to be added. (Seen on right side of
                            the credits.)
                            Adds to the existing credits.
        ---------------     --------------------------------------------------------------------
        heading             Optional String. Replace current heading for credits.
        ---------------     --------------------------------------------------------------------
        description         Optional String. Replace current description for credits.
        ===============     ====================================================================

        :return:
            A list of strings that are the node ids for the text nodes that belong to credits.

        .. code-block:: python

            #Example
            >>> story = StoryMap()
            >>> story.credits("Python Dev" , "Python API Team", "Thank You", "A big thank you to those who contributed")
        """
        # Validate parameters
        if (heading is None and description is not None) or (
            heading is not None and description is None
        ):
            raise ValueError(
                "Both heading and description should be provided if one is provided."
            )

        # Find credit node
        credits_node_id = self._get_credits_node_id()

        # Get existing children or initialize an empty list
        children = self._properties["nodes"][credits_node_id].get("children", [])

        # Add content and attribution if provided
        children.extend(self._add_content_and_attribution(content, attribution))

        # Update or add heading
        if heading:
            children = self._update_or_add_heading(heading, children)

        # Update or add description
        if description:
            children = self._update_or_add_description(description, children)

        self._properties["nodes"][credits_node_id]["children"] = children
        return self._properties["nodes"][credits_node_id]["children"]

    def _get_credits_node_id(self):
        # Find credit node
        dict_node = self.get(type="credits")[0]
        # Get credit node id
        for key, value in dict_node.items():
            return key

    def _generate_unique_node_id(self):
        return "n-" + uuid.uuid4().hex[:6]

    def _add_content_and_attribution(self, content, attribution):
        nodes = []
        if content or attribution:
            # Create new content node
            node_id = self._generate_unique_node_id()
            self._properties["nodes"][node_id] = {
                "type": "attribution",
                "data": {"content": content, "attribution": attribution},
            }
            nodes.append(node_id)
        return nodes

    def _update_or_add_heading(self, heading, children):
        # Create new content node
        # Create new heading node
        node_id = self._generate_unique_node_id()
        self._properties["nodes"][node_id] = {
            "type": "text",
            "data": {"text": heading, "type": "h4"},
        }
        children = self._update_node(children, "text", "h4")
        children.append(node_id)
        return children

    def _update_or_add_description(self, description, children):
        node_id = self._generate_unique_node_id()
        self._properties["nodes"][node_id] = {
            "type": "text",
            "data": {"text": description, "type": "paragraph"},
        }
        children = self._update_node(children, "text", "paragraph")
        children.append(node_id)
        return children

    def _update_node(self, children, node_type, data_type):
        # remove the old node if it exists
        for child in children:
            if (
                self._properties["nodes"][child]["type"] == node_type
                and self._properties["nodes"][child]["data"]["type"] == data_type
            ):
                del self._properties["nodes"][child]
                children.remove(child)
        return children

    # ----------------------------------------------------------------------
    def add(
        self,
        content: Optional[
            Union[
                Content.Image,
                Content.Video,
                Content.Audio,
                Content.Embed,
                Content.Map,
                Content.Button,
                Content.Text,
                Content.Gallery,
                Content.Timeline,
                Content.Sidecar,
                Content.Code,
                Content.Table,
            ]
        ] = None,
        caption: Optional[str] = None,
        alt_text: Optional[str] = None,
        display: str = None,
        position: Optional[int] = None,
    ):
        """
        Use this method to add content to your StoryMap. content can be of various class types and when
        you add this content you can specify a caption, alt_text, display style, and the position
        at which it will be in your story.
        Not passing in any content means a separator will be added.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Optional content of type:
                            :class:`~arcgis.apps.storymap.story_content.Image`,
                            :class:`~arcgis.apps.storymap.story_content.Gallery`,
                            :class:`~arcgis.apps.storymap.story_content.Video`,
                            :class:`~arcgis.apps.storymap.story_content.Audio`,
                            :class:`~arcgis.apps.storymap.story_content.Embed`,
                            :class:`~arcgis.apps.storymap.story_content.Map`,
                            :class:`~arcgis.apps.storymap.story_content.Text`,
                            :class:`~arcgis.apps.storymap.story_content.Button`,
                            :class:`~arcgis.apps.storymap.story_content.Timeline`,
                            :class:`~arcgis.apps.storymap.story_content.Sidecar`
                            :class:`~arcgis.apps.storymap.story_content.Swipe`,
                            :class:`~arcgis.apps.storymap.story_content.Separator`,
                            :class:`~arcgis.apps.storymap.story_content.Code`,
                            :class:`~arcgis.apps.storymap.story_content.Table`
        ---------------     --------------------------------------------------------------------
        caption             Optional String. Custom text to caption the webmap.
        ---------------     --------------------------------------------------------------------
        alt_text            Optional String. Custom text to be used for screen readers.
        ---------------     --------------------------------------------------------------------
        display             Optional String. How the item will be displayed in the story map.

                            For Image, Video, Audio, or Map object.
                            Values: "standard" | "wide" | "full" | "float"

                            For Gallery:
                            Values: "jigsaw" | "square-dynamic"

                            For Embed:
                            Values: "card" | "inline"

                            For Swipe:
                            Values: "small" | "medium" | "large"
        ---------------     --------------------------------------------------------------------
        position            Optional Integer. Indicates the position in which the content will be
                            added. To see all node positions use the ``node`` property.
        ===============     ====================================================================

        :return: A String depicting the node id for the content that was added.

        .. code-block:: python

            new_story = StoryMap()

            # Example with Image
            >>> image1 = Image("<image-path>.jpg/jpeg/png/gif ")
            >>> new_node = new_story.add(image1, position = 2)

            # Example with Map
            >>> my_map = Map(<item-id of type webmap>)
            >>> new_node = new_story.add(my_map, "A map caption", "A new map alt-text")

            # Example to add a Separator
            >>> new_node = new_story.add()

            >>> print(new_story.nodes)

        """
        if content and content.node in self._properties["nodes"]:
            content.node = "n-" + uuid.uuid4().hex[0:6]

        # Node id included in all content except separator so create node id for that
        node_id = content.node if content is not None else "n-" + uuid.uuid4().hex[0:6]

        # Find instance of content and call correct method
        if content:
            content._add_to_story(
                story=self, caption=caption, alt_text=alt_text, display=display
            )
        else:
            content = Content.Separator(story=self, node_id=node_id)
            content._add_separator(story=self)

        # Add to story children
        utils._add_child(self, node_id=node_id, position=position)
        return node_id

    # ----------------------------------------------------------------------
    def move(
        self, node_id: str, position: Optional[int] = None, delete_current: bool = False
    ):
        """
        Move a node to another position. The node currently at that position will
        be moved down one space. The node at the current position can be deleted
        instead of moved if `delete_current` is set to True.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        node_id             Required String. The node id for the content that will be moved. Find a
                            list of node order by using the ``nodes`` property.
        ---------------     --------------------------------------------------------------------
        position            Optional Integer. Indicates the position in which the content will be
                            added. If no position is provided, the node will be placed at the end.
        ---------------     --------------------------------------------------------------------
        delete_current      Optional Boolean. If set to True, the node at the current position will
                            be deleted instead of moved down one space. Default is False.
        ===============     ====================================================================

        .. code-block:: python

            new_story = StoryMap()

            # Example with Image
            >>> image1 = Image("<image-path>.jpg/jpeg/png/gif")
            >>> image2 = Image("<image-path>.jpg/jpeg/png/gif")
            >>> new_node = new_story.add(image1, "my caption", "my alt-text", "float", 2)
            >>> new_story.add(image2)
            >>> new_story.move(new_node, 3, False)

        """
        # Get list of story children
        root_id = self._properties["root"]
        children = self._properties["nodes"][root_id]["children"]

        # Remove node id from list since it will be added again at another position
        self._properties["nodes"][root_id]["children"].remove(node_id)

        # If delete_current is True then remove the node currently at this position
        if delete_current:
            if position == 0 or position == len(children):
                raise Exception(
                    "First and last nodes are reserved for Story Cover and Credits"
                )
            self._properties["nodes"][root_id]["children"].pop(position)

        # Add node to new position
        utils._add_child(self, node_id, position)

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
    def delete_story(self):
        """
        Deletes the story item.
        """
        # Check if item id exists
        # deletes the item
        return utils.delete_item(self)

    # ----------------------------------------------------------------------
    def duplicate(self, title: Optional[str] = None):
        """
        Duplicate the story. All items will be duplicated as they are. This allows you to create
        a story template and duplicate it when you want to work with it.

        It is highly recommended that once the duplicate is created, open it in Story Maps
        builder to ensure the issue checker finds any issues before editing.

        .. note::
            Can be used with ArcGIS Online or with ArcGIS Enterprise starting 10.8.1

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Optional string. The title of the duplicated story. Only available for
                            ArcGISOnline.
        ===============     ====================================================================

        :return:
            The Item that was created.

        .. code-block:: python

            # Example for ArcGIS Online
            >>> story = StoryMap(<story item>)
            >>> story.duplicate("A Story Copy")

            # Example for ArcGIS Enterprise
            >>> story = StoryMap(<story item>)
            >>> story.duplicate()
        """
        # call the duplicate (clones the item)
        return utils.duplicate(self, title)

    # ----------------------------------------------------------------------
    def copy_content(self, target_story: StoryMap, node_list: list):
        """
        Copy the content from one story to another. This will copy the content
        indicated to the target story in the order they are provided. To change the
        order once the nodes are copied, use the `move()` method on the target story.

        .. note::
            Do not forget to save the target story once you are done copying and making
            any further edits.

        .. note::
            This method can take time depending on the number of resources. Each resource coming
            from a file must be copied over and heavy files, such as videos or audio, can be time
            consuming.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        target_story        Required StoryMap instance. The target story that the content will be
                            copied to.
        ---------------     --------------------------------------------------------------------
        node_list           Required list of strings. The list of node ids indicating the content
                            that will be copied to the target story.
        ===============     ====================================================================

        :return:
            True if all nodes have been successfully copied over.

        """
        return utils.copy_content(self, target_story, node_list)
