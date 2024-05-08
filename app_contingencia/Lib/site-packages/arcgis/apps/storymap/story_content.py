from __future__ import annotations
from enum import Enum
import struct
from typing import Optional, Union
import uuid
from arcgis.auth.tools import LazyLoader

arcgis = LazyLoader("arcgis")
briefing = LazyLoader("arcgis.apps.storymap.briefing")
urllib3 = LazyLoader("urllib3")
requests = LazyLoader("requests")
mimetypes = LazyLoader("mimetypes")
puremagic = LazyLoader("puremagic")
html = LazyLoader("html")
os = LazyLoader("os")
io = LazyLoader("io")
_parse = LazyLoader("urllib.parse")
utils = LazyLoader("arcgis.apps.storymap._utils")
briefing = LazyLoader("arcgis.apps.storymap.briefing")
pd = LazyLoader("pandas")


class Language(Enum):
    """
    Represents the supported Languages for the Code Content.
    """

    TEXT = "txt"
    ARCADE = "arcade"
    CSHARP = "cs"
    CSS = "css"
    DIFF = "diff"
    HTML = "html"
    JAVASCRIPT = "js"
    JAVA = "java"
    JSON = "json"
    JSX = "jsx"
    KOTLIN = "kt"
    PYTHON = "py"
    R = "r"
    SQL = "sql"
    SVG = "svg"
    SWIFT = "swift"
    TSX = "tsx"
    TYPESCRIPT = "ts"


class TextStyles(Enum):
    """
    Represents the Supported Text Styles for the Text Content.
    Example: Text(text="foo", style=TextStyles.HEADING)
    """

    PARAGRAPH = "paragraph"
    LARGEPARAGRAPH = "large-paragraph"
    BULLETLIST = "bullet-list"
    NUMBERLIST = "numbered-list"
    HEADING = "h2"
    SUBHEADING = "h3"
    QUOTE = "quote"


class Scales(Enum):
    """
    Scale is a unit-less way of describing how any distance on the map translates
    to a real-world distance. For example, a map at a 1:24,000 scale communicates that 1 unit
    on the screen represents 24,000 of the same unit in the real world.
    So one inch on the screen represents 24,000 inches in the real world.

    This can be used for methods involving viewpoint in the Map Content.
    """

    WORLD = {"scale": 147914382, "zoom": 2}
    CONTINENT = {"scale": 50000000, "zoom": 3}
    COUNTRIESLARGE = {"scale": 25000000, "zoom": 4}
    COUNTRIESSMALL = {"scale": 12000000, "zoom": 5}
    STATES = {"scale": 6000000, "zoom": 6}
    PROVINCES = {"scale": 6000000, "zoom": 6}
    STATE = {"scale": 3000000, "zoom": 7}
    PROVINCE = {"scale": 3000000, "zoom": 7}
    COUNTIES = {"scale": 1500000, "zoom": 8}
    COUNTY = {"scale": 750000, "zoom": 9}
    METROPOLITAN = {"scale": 320000, "zoom": 10}
    CITIES = {"scale": 160000, "zoom": 11}
    CITY = {"scale": 80000, "zoom": 12}
    TOWN = {"scale": 40000, "zoom": 13}
    NEIGHBORHOOD = {"scale": 2000, "zoom": 14}
    STREETS = {"scale": 10000, "zoom": 15}
    STREET = {"scale": 5000, "zoom": 16}
    BUILDINGS = {"scale": 2500, "zoom": 17}
    BUILDING = {"scale": 1250, "zoom": 18}
    SMALLBUILDING = {"scale": 800, "zoom": 19}
    ROOMS = {"scale": 400, "zoom": 20}
    ROOM = {"scale": 100, "zoom": 22}


class SlideLayout(Enum):
    """
    This depicts the various layout types that can be used for a BriefingSlide.
    """

    SINGLE = "single"
    DOUBLE = "double"
    TITLELESSSINGLE = "titleless-single"
    TITLELESSDOUBLE = "titleless-double"
    FULL = "full"
    SECTIONDOUBLE = "section-double"
    SECTIONSINGLE = "section-single"


class SlideSubLayout(Enum):
    """
    Depicts the various subtypes for a BriefingSlide. For example, if the layout type is
    `DOUBLE` then the sublayout type can be `THREE_SEVEN` or `SEVEN_THREE` or `ONE_ONE`.
    """

    THREE_SEVEN = "3-7"
    SEVEN_THREE = "7-3"
    ONE_ONE = "1-1"


###############################################################################################################
class Separator:
    """
    Add a subtle break in between different sections of your story. The exact look of the separator will vary based on the theme you have chosen.

    Class representing a `separator`. You can use this class to edit and remove separators from a storymap.
    This refers to the main separator content type that can be added to a story. For timeline separators use
    the Timeline class.
    """

    def __init__(self, **kwargs) -> None:
        # Can be created from scratch or already exist in story
        # Separator is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "separator"
        self.node = kwargs.pop("node_id", "n-" + uuid.uuid4().hex[0:6])

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "Separator"

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        # Assign the story
        self._story = story

        # Create separator nodes.
        self._story._properties["nodes"][self.node] = {
            "type": "separator",
        }

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)


###############################################################################################################
class Image:
    """
    Class representing an `image` from a url or file.

    .. warning::
        Image must be smaller than 10 MB to avoid having issues when saving or publishing.

    .. note::
        Once you create an Image instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    path                    Required String. The file path or url to the image that will be added.
    ==================      ====================================================================
    """

    def __init__(self, path: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        # Image is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "image"
        # Keep track if URL since different representation style in story dictionary
        self._is_url = False
        self.node = kwargs.pop("node_id", None)
        # If node exists in story, then create from resources and node dictionary provided.
        # If node doesn't already exist, create a new instance.
        self._existing = self._check_node()
        if self._existing is True:
            # Get the resource node id
            self.resource_node = self._story._properties["nodes"][self.node]["data"][
                "image"
            ]
            if (
                self._story._properties["resources"][self.resource_node]["data"][
                    "provider"
                ]
                == "uri"
            ):
                # Indicate that the image comes from a url
                self._is_url = True
            if self._is_url is True:
                # Path differs whether from file path or url originally
                self._path = self._story._properties["resources"][self.resource_node][
                    "data"
                ]["src"]
            else:
                self._path = self._story._properties["resources"][self.resource_node][
                    "data"
                ]["resourceId"]
        else:
            # Create a new instance of Image
            self._path = path
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self.resource_node = "r-" + uuid.uuid4().hex[0:6]

            # Determine if url or file path
            if _parse.urlparse(self._path).scheme == "https":
                self._is_url = True

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        caption = getattr(self, "caption", None)
        if caption:
            return f"Image: {self.caption}"
        else:
            return "Image"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties for the Image.

        :return:
            A dictionary depicting the node dictionary and resource
            dictionary for the image.
            If nothing is returned, make sure your content has been added
            to the story.
        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
                "resource_dict": self._story._properties["resources"][
                    self.resource_node
                ],
            }

    # ----------------------------------------------------------------------
    @property
    def image(self):
        """
        Get/Set the image property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        image               String. The new image path or url for the Image.
        ==================  ========================================

        :return:
            The image that is being used.
        """
        if self._existing is True:
            if self._is_url is False:
                return self._story._properties["resources"][self.resource_node]["data"][
                    "resourceId"
                ]
            else:
                return self._story._properties["resources"][self.resource_node]["data"][
                    "src"
                ]

    # ----------------------------------------------------------------------
    @image.setter
    def image(self, path):
        if self._existing is True:
            self._update_image(path)
            return self.image

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the image.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Image.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the image.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Image.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
            return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set display for image.

        Values: `small` | `wide` | `full` | `float`
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["config"]["size"]

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["config"]["size"] = display
            return self.display

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story, **kwargs):
        # Assign the story
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        # Make an add resource call if not url
        if self._is_url is False:
            utils._add_resource(self._story, self._path)

        # Create image nodes. This is similar for file path and url
        self._story._properties["nodes"][self.node] = {
            "type": "image",
            "data": {
                "image": self.resource_node,
                "caption": "" if caption is None else caption,
                "alt": "" if alt_text is None else alt_text,
            },
            "config": {"size": "" if display is None else display},
        }

        # Create resource node. Different if file path or url
        width, height = self._get_image_dimensions(self._path)
        if self._is_url is False:
            # Get image properties and create the resourceId that corresponds to the resource added
            self._story._properties["resources"][self.resource_node] = {
                "type": "image",
                "data": {
                    "resourceId": os.path.basename(os.path.normpath(self._path)),
                    "provider": "item-resource",
                    "height": height,
                    "width": width,
                },
            }
        else:
            # Get image properties and assign the image src
            self._story._properties["resources"][self.resource_node] = {
                "type": "image",
                "data": {
                    "src": self._path,
                    "provider": "uri",
                    "height": height,
                    "width": width,
                },
            }

    # ----------------------------------------------------------------------
    def _get_image_dimensions(self, image_source):
        if image_source.startswith("http://") or image_source.startswith("https://"):
            # If the source is a URL, fetch the image data
            response = requests.get(image_source)
            if response.status_code == 200:
                image_data = response.content
            else:
                print(f"Failed to fetch image from URL: {image_source}")
                return None
        else:
            # Assume the source is a local file path
            with open(image_source, "rb") as f:
                image_data = f.read()

        # Use puremagic to get MIME type
        mime_info = puremagic.magic_string(image_data)[0]

        # Check if it's an image
        if mime_info.mime_type.startswith("image/"):
            # Use BytesIO to create a file-like object for both local files and fetched data
            with io.BytesIO(image_data) as image_file:
                # Read the first few bytes to identify the image format
                header = image_file.read(32)

                if header.startswith(b"\xff\xd8\xff\xe0\x00\x10JFIF"):  # JPEG
                    # Extract dimensions from the APP0 segment
                    width, height = struct.unpack(">HH", header[7:11])
                    return width, height

                elif header.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
                    # Extract dimensions from the IHDR chunk
                    width, height = struct.unpack(">II", header[16:24])
                    return width, height

        return None

    # ----------------------------------------------------------------------
    def _update_url_date(self, new_image):
        # New image is a Url
        self._is_url = True
        # Use puremagic to get image dimensions
        width, height = self._get_image_dimensions(new_image)
        self._update_dimensions(width, height)

        # Update resource dictionary
        self._update_resource_data(new_image)

    # ----------------------------------------------------------------------
    def _get_resource_id(self):
        return (
            self._story._properties["resources"][self.resource_node]["data"][
                "resourceId"
            ]
            if "resourceId"
            in self._story._properties["resources"][self.resource_node]["data"]
            else None
        )

    # ----------------------------------------------------------------------
    def _update_file_path_data(self, new_image):
        # Update the height and width for the image
        # Use puremagic to get image dimensions
        width, height = self._get_image_dimensions(new_image)
        self._update_dimensions(width, height)

        # Update resource dictionary
        resource_id = self._get_resource_id()
        # Update where file path is held
        self._story._properties["resources"][self.resource_node]["data"][
            "resourceId"
        ] = os.path.basename(os.path.normpath(new_image))
        # Delete path if item was previously a url
        if "src" in self._story._properties["resources"][self.resource_node]["data"]:
            del self._story._properties["resources"][self.resource_node]["data"]["src"]
        # Update provider
        self._story._properties["resources"][self.resource_node]["data"][
            "provider"
        ] = "item-resource"
        # Update the resource by removing old and adding new
        if resource_id:
            utils._remove_resource(self._story, resource_id)
        utils._add_resource(self._story, new_image)

    # ----------------------------------------------------------------------
    def _update_dimensions(self, width, height):
        self._story._properties["resources"][self.resource_node]["data"][
            "height"
        ] = height
        self._story._properties["resources"][self.resource_node]["data"][
            "width"
        ] = width

    # ----------------------------------------------------------------------
    def _update_resource_data(self, new_image):
        # Update resource dictionary
        # Do not need to make a resource
        self._story._properties["resources"][self.resource_node]["data"][
            "src"
        ] = new_image
        # Delete if the image was previously a file path
        if (
            "resourceId"
            in self._story._properties["resources"][self.resource_node]["data"]
        ):
            del self._story._properties["resources"][self.resource_node]["data"][
                "resourceId"
            ]
        # Update provider
        self._story._properties["resources"][self.resource_node]["data"][
            "provider"
        ] = "uri"

    # ----------------------------------------------------------------------
    def _update_image(self, new_image):
        # Check if new_image is url or path
        if _parse.urlparse(new_image).scheme == "https":
            self._update_url_date(new_image)
        else:
            self._update_file_path_data(new_image)
        # Set new path
        return new_image

    # ----------------------------------------------------------------------
    def _check_node(self) -> bool:
        return self._story is not None and self.node is not None


###############################################################################################################
class Video:
    """
    Class representing a `video` from a url or file

    .. note::
        Once you create a Video instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    path                    Required String. The file path or embed url to the video that will
                            be added.

                            .. note::
                                URL must be an embed url.
                                Example: "https://www.youtube.com/embed/G6b7Kgvd0iA"

    ==================      ====================================================================
    """

    def __init__(self, path: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        # Video is not an immersive node
        # Get properties if provided
        self._story = kwargs.pop("story", None)
        self._type = "video"
        # Hold whether video is url, this will impact the dictionary structure
        self._is_url = False
        self.node = kwargs.pop("node_id", None)
        # Check if node already in story, else create new instance
        self._existing = self._check_node()
        if self._existing is True:
            # If node is type video then video came from file path
            if self._story._properties["nodes"][self.node]["type"] == "video":
                self.resource_node = self._story._properties["nodes"][self.node][
                    "data"
                ]["video"]
                self._path = self._story._properties["resources"][self.resource_node][
                    "data"
                ]["resourceId"]
            else:
                # Node is of embedType: video and video came from url
                self.resource_node = None
                self._path = self._story._properties["nodes"][self.node]["data"]["url"]
                self._is_url = True
        else:
            # Create new instance of Video
            self._path = path
            self.node = "n-" + uuid.uuid4().hex[0:6]
            if _parse.urlparse(path).scheme == "https":
                self._is_url = True
                self.resource_node = None
            else:
                self.resource_node = "r-" + uuid.uuid4().hex[0:6]

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        caption = getattr(self, "caption", None)
        if caption:
            return f"Video: {self.caption}"
        else:
            return "Video"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties for the Video.

        :return:
            A dictionary depicting the node dictionary and resource
            dictionary for the video.
            If nothing is returned, make sure the content is part of the story.

        .. note::
            To change various properties of the Video use the other property setters.
        """
        if self._existing is True:
            vid_dict = {
                "node_dict": self._story._properties["nodes"][self.node],
            }
            if self.resource_node:
                vid_dict["resource_dict"] = (
                    self._story._properties["resources"][self.resource_node],
                )
            return vid_dict

    # ----------------------------------------------------------------------
    @property
    def video(self):
        """
        Get/Set the video property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        video               String. The new video path for the Video.
        ==================  ========================================

        :return:
            The video that is being used.
        """
        if self._existing is True:
            if self.resource_node:
                # If resource node exists it means the video comes from a file path
                return self._story._properties["resources"][self.resource_node]["data"][
                    "resourceId"
                ]
            else:
                # No resource node means the video is of type embed and embedType: video
                return self._story._properties["nodes"][self.node]["data"]["url"]

    # ----------------------------------------------------------------------
    @video.setter
    def video(self, path):
        if self._existing is True:
            self._update_video(path)
            return self.video

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the video.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Video.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the video.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Video.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
            return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set display for the video.

        Values: `small` | `wide` | `full` | `float`

        .. note::
            Cannot change display when video is created from a url
        """
        if self._existing is True:
            if self._is_url is True:
                return self._story._properties["nodes"][self.node]["data"]["display"]
            else:
                return self._story._properties["nodes"][self.node]["config"]["size"]

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._existing is True:
            if self._is_url is True:
                self._story._properties["nodes"][self.node]["data"]["display"] = display
        return self.display

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(
        self,
        story=None,
        **kwargs,
    ):
        # Add the story to the node
        self._story = story
        self._existing = True
        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        if not self._is_url:
            # Make an add resource call since it is a file path
            utils._add_resource(self._story, self._path)

            # Create video nodes for file path
            self._create_video_node(caption, alt_text, display)

            # Create resource node for file path
            self._create_resource_node()
        else:
            # Path is a URL, so create an embed node
            self._create_embed_node(caption=caption, alt_text=alt_text)

    # ----------------------------------------------------------------------
    def _create_video_node(self, caption, alt_text, display):
        """
        Create a video node for a file path.
        """
        self._story._properties["nodes"][self.node] = {
            "type": "video",
            "data": {
                "video": self.resource_node,
                "caption": caption or "",
                "alt": alt_text or "",
            },
            "config": {
                "size": display,
            },
        }

    # ----------------------------------------------------------------------
    def _create_resource_node(self):
        """
        Create a resource node for a file path.
        """
        self._story._properties["resources"][self.resource_node] = {
            "type": "video",
            "data": {
                "resourceId": os.path.basename(os.path.normpath(self._path)),
                "provider": "item-resource",
            },
        }

    # ----------------------------------------------------------------------
    def _create_embed_node(self, caption=None, alt_text=None):
        """
        Create an embed node for a URL.
        """
        self._story._properties["nodes"][self.node] = {
            "type": "embed",
            "data": {
                "url": self._path,
                "embedType": "video",
                "caption": caption or "",
                "alt": alt_text or "",
                "display": "inline",
                "aspectRatio": 1.778,
                "addedAsEmbedCode": True,
            },
        }

    # ----------------------------------------------------------------------
    def _update_video(self, new_video):
        # Node structure depends if new_video is file path or url
        # Changes are made and add video call is done since easier than restructuring
        self._path = new_video
        if self.resource_node:
            # If resource node present, remove resource from item.
            resource_id = self._story._properties["resources"][self.resource_node][
                "data"
            ]["resourceId"]
            utils._remove_resource(self._story, resource_id)
            # Remove the resource node since should not exist for url. Will be added back if file path
            del self._story._properties["resources"][self.resource_node]

        video_scheme = _parse.urlparse(new_video).scheme

        if video_scheme == "https":
            # New video is a URL
            self._is_url = True
            self.resource_node = None
            # Update the node by making the add video call with correct parameters
            self._update_video_url()
        else:
            # If the node was not a file path before, need to create resource id
            if self.resource_node is None:
                self.resource_node = "r-" + uuid.uuid4().hex[0:6]
            # display depends on self._url so get it before
            display = self.display
            self._is_url = False
            # Update the node by making the add video call with correct parameters
            self._update_video_file(display)

    # ----------------------------------------------------------------------
    def _update_video_url(self):
        """
        Update video node with a new URL.
        """
        self._add_to_story(
            caption=self.caption,
            alt_text=self.alt_text,
            story=self._story,
            node_id=self.node,
        )

    # ----------------------------------------------------------------------
    def _update_video_file(self, display):
        """
        Update video node with a new file path.
        """
        self._add_to_story(
            caption=self.caption,
            alt_text=self.alt_text,
            display=display,
            story=self._story,
            node_id=self.node,
            resource_node=self.resource_node,
        )

    # ----------------------------------------------------------------------
    def _check_node(self) -> bool:
        return self._story is not None and self.node is not None


###############################################################################################################
class Audio:
    """
    This class represents content that is of type `audio`. It can be created from
    a file path and added to the story.

    .. note::
        Once you create an Audio instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    path                    Required String. The file path to the audio that will be added.
    ==================      ====================================================================

    """

    def __init__(self, path: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        # Audio is not an immersive node
        if not path or _parse.urlparse(path).scheme == "https":
            # Audio cannot be added by URL at this time.
            raise ValueError(
                "To add an audio from an embedded url, use the Embed content class. Update audio with file path only."
            )
        # Assign audio node properties
        self._story = kwargs.pop("story", None)
        self._type = "audio"
        self.node = kwargs.pop("node_id", None)
        # If node does not exist yet, create new instance
        self._existing = self._check_node()
        if self._existing is True:
            # Get existing resource node
            self.resource_node = self._story._properties["nodes"][self.node]["data"][
                "audio"
            ]
            # Get existing audio path
            self._path = self._story._properties["resources"][self.resource_node][
                "data"
            ]["resourceId"]
        else:
            # Create a new instance
            self._path = path
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self.resource_node = "r-" + uuid.uuid4().hex[0:6]

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        caption = getattr(self, "caption", None)
        if caption:
            return f"Audio: {self.caption}"
        else:
            return "Audio"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties for the Audio.

        :return:
            A dictionary depicting the node dictionary and resource
            dictionary for the audio.

            If nothing is returned, make sure the content is part of the story.

        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
                "resource_dict": self._story._properties["resources"][
                    self.resource_node
                ],
            }

    # ----------------------------------------------------------------------
    @property
    def audio(self):
        """
        Get/Set the audio path.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        audio               String. The new audio path for the Audio.
        ==================  ========================================

        :return:
            The audio that is being used.
        """
        if self._existing is True:
            return self._story._properties["resources"][self.resource_node]["data"][
                "resourceId"
            ]

    # ----------------------------------------------------------------------
    @audio.setter
    def audio(self, path):
        if _parse.urlparse(path).scheme == "https":
            raise ValueError(
                "To add an audio from an embedded url, use the Embed content class. Update audio with file path only."
            )
        if self._existing is True:
            self._update_audio(path)
            return self.audio

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the audio.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Audio.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption
            return self.caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the audio.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Audio.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
            return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set display for audio.

        Values: `small` | `wide` | float`
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["config"]["size"]

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._check_node() is True:
            self._story._properties["nodes"][self.node]["config"]["size"] = display
            return self.display

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(
        self,
        story=None,
        **kwargs,
    ):
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        # Make an add resource call
        utils._add_resource(self._story, self._path)

        # Create audio nodes
        self._create_audio_node(caption, alt_text, display)

        # Create resource node
        self._create_resource_node()

    # ----------------------------------------------------------------------
    def _create_audio_node(self, caption, alt_text, display):
        """
        Create an audio node in the story.
        """
        self._story._properties["nodes"][self.node] = {
            "type": "audio",
            "data": {
                "audio": self.resource_node,
                "caption": caption or "",
                "alt": alt_text or "",
            },
            "config": {"size": display},
        }

    # ----------------------------------------------------------------------
    def _create_resource_node(self):
        """
        Create a resource node for the audio.
        """
        self._story._properties["resources"][self.resource_node] = {
            "type": "audio",
            "data": {
                "resourceId": os.path.basename(os.path.normpath(self._path)),
                "provider": "item-resource",
            },
        }

    # ----------------------------------------------------------------------
    def _update_audio(self, new_audio):
        # Assign new path
        self._path = new_audio

        # Assign new resource id, get old one to delete resource
        resource_id = self._story._properties["resources"][self.resource_node]["data"][
            "resourceId"
        ]
        self._story._properties["resources"][self.resource_node]["data"][
            "resourceId"
        ] = os.path.basename(os.path.normpath(self._path))

        # Add new resource and remove old one
        utils._add_resource(self._story, self._path)
        utils._remove_resource(self._story, resource_id)

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Embed:
    """
    Class representing a `webpage` or `embedded audio`.
    Embed will show as a card in the story.

    .. note::
        Once you create an Embed instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    path                    Required String. The url that will be added as a webpage, video, or
                            audio embed into the story.
    ==================      ====================================================================
    """

    def __init__(self, path: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        # Embed is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "embed"
        self.node = kwargs.pop("node_id", None)
        # If node doesn't already exist, create new instance
        self._existing = self._check_node()
        if self._existing is True:
            # Get the link path
            self._path = self._story._properties["nodes"][self.node]["data"]["url"]

            # check if offline dependent
            if "dependents" in self._story._properties["nodes"][self.node]:
                self._offline_dependent = self._story._properties["nodes"][self.node][
                    "dependents"
                ]["offline"]
        else:
            # Create new instance, notice no resource node is needed for embed
            self._path = path
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._offline_dependent = None

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties for the Embed.

        .. note::
            To change various properties of the Embed use the other property setters.

        :return:
            A dictionary depicting the node dictionary for the embed.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
            }

    # ----------------------------------------------------------------------
    @property
    def offline_media(self):
        """
        Get/Set the offline media property for the embed.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        offline_media       Image or Video. The new offline_media for the Embed.
        ==================  ========================================

        :return:
            The offline media that is being used.
        """
        if self._existing is True:
            if self._offline_dependent:
                return utils._assign_node_class(
                    story=self._story, node_id=self._offline_dependent
                )
        return None

    # ----------------------------------------------------------------------
    @offline_media.setter
    def offline_media(self, value: Image | Video):
        if self._existing:
            # can only set for briefing
            if isinstance(self._story, briefing.Briefing):
                if isinstance(value, Image) or isinstance(value, Video):
                    value._add_to_story(story=self._story)
                    self._story._properties["nodes"][self.node]["dependents"] = {
                        "offline": value.node
                    }
                    self._offline_dependent = value.node
                else:
                    raise ValueError("offline_media must be an Image or Video")
            else:
                raise ValueError("offline_media can only be set for a Briefing")
        else:
            raise ValueError(
                "offline_media can only be set for an Embed that has been added to a Briefing."
            )

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Embed: {self.link}"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def link(self):
        """
        Get/Set the link property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        link                String. The new url for the Embed.
        ==================  ========================================

        :return:
            The embed that is being used.
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["url"]

    # ----------------------------------------------------------------------
    @link.setter
    def link(self, path):
        if self._existing is True:
            self._update_link(path)
            return self.link

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the webpage.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Embed.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption
            return self.caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the embed.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Embed.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
            return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set display for embed.

        Values: `card` | `inline`
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["display"]

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._existing:
            self._story._properties["nodes"][self.node]["data"]["display"] = display
            return self.display

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        sections = _parse.urlparse(self._path)
        # Create embed node, no resource node needed
        self._create_link_node(caption, alt_text, display, sections)

    # ----------------------------------------------------------------------
    def _create_link_node(self, caption, alt_text, display, sections):
        """
        Create a link node in the story.
        """
        self._story._properties["nodes"][self.node] = {
            "type": "embed",
            "data": {
                "url": self._path,
                "embedType": "link",
                "title": sections.netloc,
                "description": caption or "",
                "providerUrl": sections.netloc,
                "alt": alt_text or "",
                "display": display or "inline",
            },
        }

    # ----------------------------------------------------------------------
    def _update_link(self, new_link):
        # parse new url
        sections = _parse.urlparse(new_link)
        # set new path
        self._path = new_link
        # update dictionary properties
        self._story._properties["nodes"][self.node]["data"]["url"] = self._path
        self._story._properties["nodes"][self.node]["data"]["title"] = sections.netloc
        self._story._properties["nodes"][self.node]["data"][
            "providerUrl"
        ] = sections.netloc

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Map:
    """
    Class representing a `webmap` or `webscene` for the story

    .. note::
        Once you create a Map instance you must add it to the story to be able to edit it further.

    =================       ====================================================================
    **Parameter**            **Description**
    -----------------       --------------------------------------------------------------------
    item                    An Item of type :class:`~arcgis.mapping.WebMap` or
                            :class:`~arcgis.mapping.WebScene` or a String representing the item
                            id to add to the story map.
    =================       ====================================================================
    """

    def __init__(self, item: Optional[arcgis.gis.Item] = None, **kwargs):
        # Can be created from scratch or already exist in story
        # Map is not an immersive node
        self._story = kwargs.pop("story", None)
        self.node = kwargs.pop("node_id", None)
        # Check if node exists else create new instance
        self._existing = self._check_node()
        if self._existing:
            # Gather all existing properties needed
            self.resource_node = self._story._properties["nodes"][self.node]["data"][
                "map"
            ]
            # The item id is in the resource node
            self._path = self.resource_node[2::]
            rdata = self._story._properties["resources"][self.resource_node]["data"]
            ndata = self._story._properties["nodes"][self.node]["data"]
            # map layers
            if "mapLayers" in ndata:
                self._map_layers = ndata["mapLayers"]
            elif "mapLayers" in rdata:
                self._map_layers = rdata["mapLayers"]
            else:
                self._map_layers = None

            # extent
            if "extent" in ndata:
                self._extent = ndata["extent"]
            elif "extent" in rdata:
                self._extent = rdata["extent"]
            else:
                self._extent = {}

            # center
            if "center" in ndata:
                self._center = ndata["center"]
            elif "center" in rdata:
                self._center = rdata["center"]
            else:
                self._center = None

            # viewpoint
            if "viewpoint" in ndata:
                self._viewpoint = ndata["viewpoint"]
            elif "viewpoint" in rdata:
                self._viewpoint = rdata["viewpoint"]
            else:
                self._viewpoint = {"rotation": 0, "scale": -1, "targetGeometry": {}}

            # zoom
            if "zoom" in ndata:
                self._zoom = ndata["zoom"]
            elif "zoom" in rdata:
                self._zoom = rdata["zoom"]
            else:
                self._zoom = 2

            # only in rdata
            self._type = rdata["itemType"]
            if self._type == "Web Scene":
                self._lighting_date = self._story._properties["resources"][
                    self.resource_node
                ]["data"]["lightingDate"]

            # check if offline dependents exist
            if "dependents" in self._story._properties["nodes"][self.node]:
                self._offline_dependent = self._story._properties["nodes"][self.node][
                    "dependents"
                ]["offline"]
        else:
            # Create new instance
            if isinstance(item, str):
                # If string id get the item
                item = arcgis.env.active_gis.content.get(item)
            # Create map object to extract properties
            if isinstance(item, arcgis.gis.Item):
                if item.type == "Web Map":
                    map_item = arcgis.mapping.WebMap(item)
                elif item.type == "Web Scene":
                    map_item = arcgis.mapping.WebScene(item)
                else:
                    raise ValueError("Item must be of Type Web Map or Web Scene")
            # Assign properties
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self.resource_node = "r-" + item.id
            self._path = item
            self._type = item.type
            self._offline_dependent = None
            if item.type == "Web Map":
                self._extent = map_item._mapview.extent
                if map_item._mapview.center is None:
                    x_center = (self._extent["xmin"] + self._extent["xmax"]) / 2
                    y_center = (self._extent["ymin"] + self._extent["ymax"]) / 2
                    self._center = {
                        "spatialReference": map_item.definition.spatialReference,
                        "x": x_center,
                        "y": y_center,
                    }
                else:
                    self._center = map_item._mapview.center
                self._zoom = map_item._mapview.zoom if map_item.zoom is not False else 2
                self._viewpoint = {
                    "rotation": map_item._mapview.rotation,
                    "scale": map_item._mapview.scale,
                    "targetGeometry": self._center,
                }

                layers = []
                # Create layer dictionary:
                for layer in map_item.layers:
                    layer_props = {}
                    layer_props["id"] = layer["id"]
                    layer_props["title"] = layer["title"]
                    if "visibility" in layer:
                        layer_props["visible"] = layer["visibility"]
                    elif "layer_visibility" in map_item:
                        layer_props["visible"] = map_item["layer_visibility"]
                    layers.append(layer_props)
                self._map_layers = layers
            # Add properties for Web Scene
            elif item.type == "Web Scene":
                layers = []
                # Create layer dictionary:
                for layer in map_item["operationalLayers"]:
                    layer_props = {}
                    layer_props["id"] = layer["id"]
                    layer_props["title"] = layer["title"]
                    if "visibility" in layer:
                        layer_props["visible"] = layer["visibility"]
                    else:
                        layer_props["visible"] = False
                    layers.append(layer_props)
                self._map_layers = layers
                self._extent = None
                self._center = map_item["initialState"]["viewpoint"]["camera"][
                    "position"
                ]
                self._zoom = 2
                self._viewpoint = map_item["initialState"]["viewpoint"]
                self._camera = map_item["initialState"]["viewpoint"]["camera"]
                self._lighting_date = map_item["initialState"]["environment"][
                    "lighting"
                ]["datetime"]

    # ----------------------------------------------------------------------
    def __repr__(self):
        return self._type

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties for the Map.

        :return:
            A dictionary depicting the node dictionary and resource
            dictionary for the map. The resource dictionary depicts the
            original map settings. The node dictionary depicts the current map settings.
            If nothing it returned, make sure the content is part of the story.

        .. note::
            To change various properties of the Map use the other property setters.
        """
        if self._check_node() is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
                "resource_dict": self._story._properties["resources"][
                    self.resource_node
                ],
            }

    # ----------------------------------------------------------------------
    @property
    def map(self):
        """
        Get/Set the map property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        map                 One of three choices:

                            * String being an item id for an Item of type
                            :class:`~arcgis.mapping.WebMap`
                            or :class:`~arcgis.mapping.WebScene`.

                            * An :class:`~arcgis.gis.Item` of type
                            :class:`~arcgis.mapping.WebMap`
                            or :class:`~arcgis.mapping.WebScene`.
        ==================  ========================================

        .. note::
            Only replace a Map with a new map of same type. Cannot replace a
            2D map with 3D.

        :return:
            The item id for the map that is being used.
        """
        if self._existing is True:
            map_id = self._story._properties["resources"][self.resource_node]["data"][
                "itemId"
            ]
            return self._story._gis.content.get(map_id)

    # ----------------------------------------------------------------------
    @map.setter
    def map(self, map):
        if self._existing is True:
            self._update_map(map)
            return self.map

    # ----------------------------------------------------------------------
    def set_viewpoint(self, extent: dict = None, scale: Scales = None):
        """
        Set the extent and/or scale for the map in the story.

        If you have an extent to use from a bookmark,
        find this extent by using the `bookmarks` property in
        the :class:`~arcgis.mapping.WebMap` Class.
        The `map` property on this class will return the Web Map
        Item being used. By passing this item into
        the :class:`~arcgis.mapping.WebMap` Class you can retrieve a list of all
        bookmarks and their extents with the `bookmarks` property.

        To see the current viewpoint call the `properties` property on the Map
        node.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        extent              Optional dictionary representing the extent of
                            the map. This will update the extent, center and viewpoint
                            accordingly.

                            Example:
                                | {'spatialReference': {'latestWkid': 3857, 'wkid': 102100},
                                | 'xmin': -609354.6306080809,
                                | 'ymin': 2885721.2797636474,
                                | 'xmax': 6068184.160383142,
                                | 'ymax': 6642754.094035632}
        ------------------  ----------------------------------------
        scale               Optional Scales enum class value or dict with 'scale' and 'zoom' keys.

                            Scale is a unit-less way of describing how any distance on the map translates
                            to a real-world distance. For example, a map at a 1:24,000 scale communicates that 1 unit
                            on the screen represents 24,000 of the same unit in the real world.
                            So one inch on the screen represents 24,000 inches in the real world.
        ==================  ========================================

        :return: The current viewpoint dictionary
        """
        rdata_dict = self._story._properties["resources"][self.resource_node]["data"]
        if "viewpoint" not in self._story._properties["nodes"][self.node]["data"]:
            try:
                self._story._properties["nodes"][self.node]["data"]["viewpoint"] = (
                    rdata_dict["viewpoint"]
                )
            except Exception:
                self._story._properties["nodes"][self.node]["data"]["viewpoint"] = {
                    "rotation": 0,
                    "scale": -1,
                    "targetGeometry": {},
                }

        change_made = False
        # set new extent if specified
        if extent:
            if isinstance(extent, dict):
                if not all(k in extent for k in ("xmin", "xmax", "ymin", "ymax")):
                    raise ValueError(
                        "Extent dictionary missing one or more of these keys: 'xmin', 'xmax', 'ymin', 'ymax'"
                    )
                if "spatialReference" not in extent:
                    try:
                        extent["spatialReference"] = self._story._properties[
                            "resources"
                        ][self.resource_node]["data"]["extent"]["spatialReference"]
                    except Exception:
                        extent["spatialReference"] = {"wkid": 4326}

                # In order to correctly edit, the viewpoint, extent, and center must be updated.
                # update extent
                self._story._properties["nodes"][self.node]["data"]["extent"] = extent
                # update center
                center_x = (extent["xmin"] + extent["xmax"]) / 2
                center_y = (extent["ymin"] + extent["ymax"]) / 2
                self._story._properties["nodes"][self.node]["data"]["center"] = {
                    "spatialReference": extent["spatialReference"],
                    "x": center_x,
                    "y": center_y,
                }
                # update viewpoint
                self._story._properties["nodes"][self.node]["data"]["viewpoint"][
                    "targetGeometry"
                ] = self._story._properties["nodes"][self.node]["data"]["center"]

                change_made = True
        # set new scale if specified
        if scale:
            if isinstance(scale, Scales):
                self._story._properties["nodes"][self.node]["data"]["viewpoint"][
                    "scale"
                ] = scale.value["scale"]
                self._story._properties["nodes"][self.node]["data"]["zoom"] = (
                    scale.value["zoom"]
                )
                change_made = True
            elif isinstance(scale, dict):
                self._story._properties["nodes"][self.node]["data"]["viewpoint"][
                    "scale"
                ] = scale["scale"]
                self._story._properties["nodes"][self.node]["data"]["zoom"] = scale[
                    "zoom"
                ]

        if change_made:
            # Once the update made, remove the original information from resources
            new_data = {
                "itemId": rdata_dict["itemId"],
                "itemType": rdata_dict["itemType"],
                "type": "minimal",
            }
            self._story._properties["resources"][self.resource_node]["data"] = new_data

        return self._story._properties["nodes"][self.node]["data"]["viewpoint"]

    # ----------------------------------------------------------------------
    @property
    def show_legend(self):
        """Get/Set the showing legend toggle. True if enabled and False if disabled"""
        if self._existing is True:
            if "isShowingLegend" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"][
                    "isShowingLegend"
                ]
            else:
                return False

    # ----------------------------------------------------------------------
    @show_legend.setter
    def show_legend(self, value: bool):
        self._story._properties["nodes"][self.node]["data"]["isShowingLegend"] = value

    # ----------------------------------------------------------------------
    @property
    def legend_pinned(self):
        """
        Get/Set the legend pinned toggle. True if enabled and False if disabled.

        .. note::
            If set to True, make sure `show_legend` is also True. Otherwise, you will not
            see the legend pinned.
        """
        if self._existing is True:
            if "legendPinned" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"][
                    "legendPinned"
                ]
            else:
                return False

    # ----------------------------------------------------------------------
    @legend_pinned.setter
    def legend_pinned(self, value: bool):
        self._story._properties["nodes"][self.node]["data"]["legendPinned"] = value

    # ----------------------------------------------------------------------
    @property
    def show_search(self):
        """Get/Set the search toggle. True if enabled and False if disabled"""
        if self._existing is True:
            if "search" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["search"]
            else:
                return False

    # ----------------------------------------------------------------------
    @show_search.setter
    def show_search(self, value: bool):
        self._story._properties["nodes"][self.node]["data"]["search"] = value

    # ----------------------------------------------------------------------
    @property
    def time_slider(self):
        """Get/Set the time slider toggle. True if enabled and False if disabled"""
        if self._existing is True:
            if "time_slider" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["timeSlider"]
            else:
                return False

    # ----------------------------------------------------------------------
    @time_slider.setter
    def time_slider(self, value: bool):
        self._story._properties["nodes"][self.node]["data"]["timeSlider"] = value

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the map.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Map.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption
            return self.caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the map.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Map.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
            return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set the display type of the map.

        Values: `standard` | `wide` | `full` | `float right` | `float left`
        """
        if self._existing is True:
            if "config" in self._story._properties["nodes"][self.node]:
                return self._story._properties["nodes"][self.node]["config"]["size"]
            else:
                return None

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._existing is True:
            if "float" in display.lower():
                self._story._properties["nodes"][self.node]["config"]["size"] = "float"
                if "right" in display.lower():
                    self._story._properties["nodes"][self.node]["config"][
                        "floatAlignment"
                    ] = "end"
                else:
                    self._story._properties["nodes"][self.node]["config"][
                        "floatAlignment"
                    ] = "start"
            else:
                self._story._properties["nodes"][self.node]["config"][
                    "size"
                ] = display.lower()
                self._story._properties["nodes"][self.node]["config"].pop(
                    "floatAlignment", None
                )
            return self.display

    # ----------------------------------------------------------------------
    @property
    def offline_media(self):
        """
        Get/Set the offline media. This is an alternative version of this media
        for offline viewing using the ArcGIS StoryMaps Briefings app.

        .. note::
            This property is only available for ArcGIS StoryMaps Briefings and
            the map must be part of the Briefing before setting this property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        offline_media       The new offline media for the Map or Scene.
                            This can either be the item of
                            a Mobile Map Package or Mobile Scene Package or it
                            can be an item of type Image or Video from Story Contents.
        ==================  ========================================
        """
        # find the type of dependent based on the type of the dependent
        # either an Image, Video, or ArcGIS Item.
        if self._existing is True:
            if self._offline_dependent:
                # Find it in the story
                node = self._story._properties["nodes"][self._offline_dependent]
                # Find the type of dependent
                if node["type"] in ["image", "video"]:
                    return utils._assign_node_class(
                        story=self._story, node_id=self._offline_dependent
                    )
                else:
                    # Find the itemId of the dependent
                    resource = self._story._properties["resources"][
                        node["data"]["package"]
                    ]
                    item_id = resource["data"]["itemId"]
                    return self._story._gis.content.get(item_id)
        else:
            return None

    # ----------------------------------------------------------------------
    @offline_media.setter
    def offline_media(self, value: arcgis.gis.Item | Image | Video):
        if self._existing:
            if not isinstance(self._story, briefing.Briefing):
                raise ValueError("offline_media can only be set for a Briefing")
            if isinstance(value, arcgis.gis.Item):
                # check if item is a MMPK or MSPK
                if value.type in ["Mobile Map Package", "Mobile Scene Package"]:
                    # create new node
                    self._create_offline_node(value)
                    # update dependent
                    self._story._properties["nodes"][self.node]["dependents"] = {
                        "offline": self._offline_dependent
                    }
                else:
                    raise ValueError(
                        "Item must be of type Mobile Map Package or Mobile Scene Package"
                    )
            elif isinstance(value, Image) or isinstance(value, Video):
                value._add_to_story(story=self._story)
                self._offline_dependent = value.node
                # update dependent
                self._story._properties["nodes"][self.node]["dependents"] = {
                    "offline": self._offline_dependent
                }
            else:
                raise ValueError("Value must be an Item, Image, or Video")

    def _create_offline_node(self, item):
        """
        Create an offline node in the story.
        """
        self._offline_dependent = "n-" + uuid.uuid4().hex[0:6]
        self._story._properties["nodes"][self._offline_dependent] = {
            "type": "mobile-package",
            "data": {
                "package": "r-" + item.id,
                "title": item.title,
            },
        }
        self._story._properties["resources"]["r-" + item.id] = {
            "type": "portal-item",
            "data": {
                "itemId": item.id,
                "itemType": item.type,
            },
        }

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        # Create webmap nodes
        # This represents the map as seen in the story
        self._story._properties["nodes"][self.node] = {
            "type": "webmap",
            "data": {
                "map": self.resource_node,
                "caption": "" if caption is None else caption,
                "alt": "" if alt_text is None else alt_text,
            },
            "config": {"size": display},
        }
        # Create resource node
        # This represents the original map item and it's properties
        self._story._properties["resources"][self.resource_node] = {
            "type": "webmap",
            "data": {
                "extent": self._extent,
                "center": self._center,
                "zoom": self._zoom,
                "mapLayers": self._map_layers,
                "viewpoint": self._viewpoint,
                "itemId": self._path.id,
                "itemType": self._type,
                "type": "minimal",
            },
        }

        # Add for Web Scene
        if self._type == "Web Scene":
            self._story._properties["resources"][self.resource_node]["data"][
                "lightingDate"
            ] = self._lighting_date
            self._story._properties["resources"][self.resource_node]["data"][
                "camera"
            ] = self._camera
            self._story._properties["nodes"][self.node]["data"][
                "lightingDate"
            ] = self._lighting_date
            self._story._properties["nodes"][self.node]["data"]["camera"] = self._camera

    # ----------------------------------------------------------------------
    def _update_map(self, map):
        new_map = Map(map)
        # Check for error.
        if (
            new_map._type
            != self._story._properties["resources"][self.resource_node]["data"][
                "itemType"
            ]
        ):
            raise ValueError("New Map must be of same type as the existing map.")

        # Get all the old properties but update with new map where needed

        # remove old resource node
        self._story._properties["resources"][new_map.resource_node] = (
            self._story._properties["resources"].pop(self.resource_node)
        )
        # assign new resource node
        self.resource_node = new_map.resource_node
        # set the new item id in the story resources dictionary for this resource
        self._story._properties["resources"][new_map.resource_node]["data"][
            "itemId"
        ] = new_map._path.id
        # set the new map layers in the story resources dict for this resource
        self._story._properties["resources"][new_map.resource_node]["data"][
            "mapLayers"
        ] = new_map._map_layers
        # Update path to resource node in the node dictionary
        self._story._properties["nodes"][self.node]["data"][
            "map"
        ] = new_map.resource_node

        # Extra necessary updates when it is a Web Scene (3D Map)
        if self._type == "Web Scene":
            self._story._properties["resources"][self.resource_node]["data"][
                "lightingDate"
            ] = new_map._lighting_date
            self._story._properties["resources"][self.resource_node]["data"][
                "camera"
            ] = new_map._camera
            self._story._properties["nodes"][self.node]["data"][
                "lightingDate"
            ] = new_map._lighting_date
            self._story._properties["nodes"][self.node]["data"][
                "camera"
            ] = new_map._camera

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Text:
    """
    Class representing a `text` and a style of text.

    .. note::
        Once you create a Text instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    text                    Required String. The text that will be shown in the story.

                            .. code-block:: python

                                # Usage Example for paragraph:

                                >>> text = Text('''Paragraph with <strong>bold</strong>, <em>italic</em>
                                                and <a href=\"https://www.google.com\" rel=\"noopener noreferrer\"
                                                target=\"_blank\">hyperlink</a> and a <span
                                                class=\"sm-text-color-080\">custom color</span>''')

                                # Usage Example for numbered list:

                                >>> text = Text("<li>List Item1</li> <li>List Item2</li> <li>List Item3</li>")

                                # Usage Example to link item in org:
                                >>> text = Text("<span data-action-type="attachment-action" id="a-CmrIH8">Testing Linked Item Text</span>", style = TextStyles.PARAGRAPH)

    ------------------      --------------------------------------------------------------------
    style                   Optional TextStyles type. There are 7 different styles of text that can be
                            added to a story.

                            Values: PARAGRAPH | LARGEPARAGRAPH | NUMBERLIST | BULLETLIST |
                            HEADING | SUBHEADING | QUOTE
    ------------------      --------------------------------------------------------------------
    custom_color            Optional String. The hex color value without the #.
                            Only available when type is either 'paragraph', 'bullet-list', or
                            'numbered-list'.


                            Ex: custom_color = "080"
    -------------------     --------------------------------------------------------------------
    size                    Optional String. Used for 'paragraph', 'bullet-list', or 'numbered-list'.
                            The size of the text. For a Storymap it can be 'large' or 'medium'.
                            For a Briefing it can be 'large', 'medium', or 'small'.
    ==================      ====================================================================


    Properties of the different text types:

    ===================     ====================================================================
    **Type**                **Text**
    -------------------     --------------------------------------------------------------------
    paragraph               String can contain the following tags for text formatting:
                            <strong>, <em>, <a href="{link}" rel="noopener noreferer" target="_blank"
                            and a class attribute to indicate color formatting:
                            class=sm-text-color-{values} attribute in the <strong> | <em> | <a> | <span> tags

                            Values: `themeColor1` | `themeColor2` | `themeColor3` | `customTextColors`
    -------------------     --------------------------------------------------------------------
    heading                 String can only contain <em> tag
    -------------------     --------------------------------------------------------------------
    subheading              String can only contain <em> tag
    -------------------     --------------------------------------------------------------------
    bullet-list             String can contain the following tags for text formatting:
                            <strong>, <em>, <a href="{link}" rel="noopener noreferer" target="_blank"
                            and a class attribute to indicate color formatting:
                            class=sm-text-color-{values} attribute in the <strong> | <em> | <a> | <span> tags

                            Values: `themeColor1` | `themeColor2` | `themeColor3` | `customTextColors`
    -------------------     --------------------------------------------------------------------
    numbered-list           String can contain the following tags for text formatting:
                            <strong>, <em>, <a href="{link}" rel="noopener noreferer" target="_blank"
                            and a class attribute to indicate color formatting:
                            class=sm-text-color-{values} attribute in the <strong> | <em> | <a> | <span> tags

                            Values: `themeColor1` | `themeColor2` | `themeColor3` | `customTextColors`
    -------------------     --------------------------------------------------------------------
    quote                   String can only contain <strong> and <em> tags
    ===================     ====================================================================

    """

    def __init__(
        self,
        text: Optional[str] = None,
        style: TextStyles = TextStyles.PARAGRAPH,
        color: str = None,
        size: str = None,
        **kwargs,
    ):
        # Can be created from scratch or already exist in story
        # Text is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "text"
        self.node = kwargs.pop("node_id", None)
        # Check if node exists in story else create new instance.
        self._existing = self._check_node()
        if self._existing is True:
            self._text = self._story._properties["nodes"][self.node]["data"]["text"]
            self._style = self._story._properties["nodes"][self.node]["data"]["type"]
            self._size = (
                self._story._properties["nodes"][self.node]["data"]["textSize"]
                if "textSize" in self._story._properties["nodes"][self.node]["data"]
                else None
            )
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._text = text
            if isinstance(style, TextStyles):
                self._style = style.value

            # Color only applies certain styles
            if self._style in [
                "paragraph",
                "large-paragraph",
                "bullet-list",
                "numbered-list",
            ]:
                self._color = color
            else:
                self._color = None

            # Size only applies to certain styles
            if self._style in [
                "paragraph",
                "bullet-list",
                "numbered-list",
            ]:
                self._size = size
            else:
                self._size = None

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        if self.text:
            return f"Text: {self._style}"
        else:
            return "Text"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get the properties for the text.

        :return:
            The Text dictionary for the node.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
            }

    # ----------------------------------------------------------------------
    @property
    def text(self):
        """
        Get/Set the text itself for the text node.

        ==================  ==================================================
        **Parameter**        **Description**
        ------------------  --------------------------------------------------
        text                Optional String. The new text to be displayed.
        ==================  ==================================================

        :return:
            The text for the node.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["text"]

    # ----------------------------------------------------------------------
    @text.setter
    def text(self, text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["text"] = text
            return self.text
        self._text = text

    # ----------------------------------------------------------------------
    @property
    def size(self):
        """
        Get/Set the size for the text node.

        ==================  ==================================================
        **Parameter**        **Description**
        ------------------  --------------------------------------------------
        size                Optional String. The new size to be displayed.
                            Applicable for Paragraph, Bullet List, and Numbered List.

                            Values: `small` | `medium` | `large`

                            .. note::
                                "small" can only be used in a Briefing.
        ==================  ==================================================

        :return:
            The size for the node.
            If nothing is returned, make sure the content is part of the story.
        """
        return self._size

    # ----------------------------------------------------------------------
    @size.setter
    def size(self, size):
        if self._existing is True:
            # check for common errors
            if size not in ["small", "medium", "large"]:
                raise ValueError("Size must be 'small', 'medium', or 'large'")
            if size == "small" and not isinstance(self._story, briefing.Briefing):
                raise ValueError("Size 'small' can only be used in a Briefing")

            self._story._properties["nodes"][self.node]["data"]["textSize"] = size

        self._size = size

    # ----------------------------------------------------------------------
    def add_attachment(
        self, content: arcgis.gis.Item | Image | Video, text: str = None
    ) -> bool:
        """
        Add a text action to your text. You can specify the data of the action.
        This can only be used within a Briefing

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Required content that can be added as an attachment.
                            Content can be:
                            * An Item object of type: Web Map, Image, StoryMap, Collection, Dashboard,
                            Web Experience, or other arcgis Apps.
                            * A story content of type Image or Video
        ---------------     --------------------------------------------------------------------
        text                Optional String. The part of the text that the attachment will be linked to. The text
                            must already exist in the text node.

                            For example, if the entire text is "Look at this dog." and you want to link the word "dog"
                            to the attachment, then the text parameter would be "dog".
        ===============     ====================================================================

        :return: True if successful.
        """
        if self._existing is True and isinstance(self._story, briefing.Briefing):
            content_node = None
            content_type = None

            # First determine what type of content we are dealing with.
            if isinstance(content, arcgis.gis.Item):
                # Need to check the item type.
                # If Web Map we create a Map instance, otherwise we create a custom embed dictionary
                if content.type == "Web Map":
                    # create the map
                    content = Map(content)
                    content_node = content.node
                    content_type = "Web Map"
                else:
                    # content gets added to story in custom method
                    content_type = "collection"
                    content_node = self._create_item_embed(content)
                    content = "custom embed"
            elif isinstance(content, (Image, Video)):
                content_node = content.node
                content_type = content._type

            if content_node is None:
                # It means it didn't go through the if statement above
                raise ValueError(
                    "Content is not of type: Web Map, Image, StoryMap, Collection, Dashboard, Web Experience, or other arcgis Apps. Or a story content of type Image or Video."
                )

            if content != "custom embed":
                # Now content is either type Map, Image, or Video
                content._add_to_story(story=self._story)
            action_id = "a-" + uuid.uuid4().hex[0:6]
            action_dict = {
                "origin": self.node,
                "trigger": "InlineAction_Apply",
                "target": self._story._properties["root"],
                "event": "Briefing_ShowAttachment",
                "data": {
                    "actionId": action_id,
                    "attachment": content_node,
                    "attachmentType": content_type,
                },
            }

            # Need to edit the text so that the format is: <span data-action-type="attachment-action" id="a-Mr9KE4">This is an attachment to ArcGIS Content</span>
            # There are two cases:
            # 1. The text is the entire text of the node
            # 2. The text is a part of the text of the node
            # Case 1:
            if text is None:
                # Add the action to the text
                new_text = (
                    f'<span data-action-type="attachment-action" id="{action_id}">'
                    + self.text
                    + "</span>"
                )
            # Case 2:
            else:
                # First get the text
                full_text = self.text
                if text not in full_text:
                    raise ValueError("The text must be part of the text of the node.")
                new_text = full_text.replace(
                    text,
                    f'<span data-action-type="attachment-action" id="{action_id}">{text}</span>',
                )
            # Now update the text
            self.text = new_text

            # add to actions list in story properties
            if "actions" in self._story._properties:
                self._story._properties["actions"].append(action_dict)
            else:
                self._story._properties["actions"] = [action_dict]

            return True
        else:
            raise ValueError(
                "This can only be used within a Briefing and the Text must exist in a Block."
            )

    # ----------------------------------------------------------------------
    def remove_attachment(self, text: str = None):
        """
        Remove an attachment from the text. If text_to_remove is None, remove all attachments.
        This can only be used within a Briefing.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        text                Optional String. The part of the text that the attachment will be removed from.
                            The text must already exist in the text class. If text is None, then all
                            attachments will be removed.
        ===============     ====================================================================

        :return: True if successful.
        """
        if self._existing is True and isinstance(self._story, briefing.Briefing):
            # First get the text
            full_text = self.text
            # Initialize an empty list to store removed action IDs
            removed_action_ids = []

            if text:
                # Remove the specified attachment if text_to_remove is provided
                if f'<span data-action-type="attachment-action" id="' in text:
                    # Get the action id to remove it from the dictionary
                    action_id = text.split('id="')[1].split('">')[0]
                    # Remove the action from the text
                    full_text = full_text.replace(
                        f'<span data-action-type="attachment-action" id="{action_id}">',
                        "",
                    ).replace("</span>", "")
                    # Add the removed action ID to the list
                    removed_action_ids.append(action_id)
            else:
                # Remove all attachments if text_to_remove is not provided
                while '<span data-action-type="attachment-action" id="' in full_text:
                    # Get the action id to remove it from the dictionary
                    action_id = full_text.split('id="')[1].split('">')[0]
                    # Remove the action from the text
                    full_text = full_text.replace(
                        f'<span data-action-type="attachment-action" id="{action_id}">',
                        "",
                    ).replace("</span>", "")
                    # Add the removed action ID to the list
                    removed_action_ids.append(action_id)

            # Now update the text
            self.text = full_text

            # Remove the corresponding actions from the actions list in the story properties
            if "actions" in self._story._properties:
                self._story._properties["actions"] = [
                    action
                    for action in self._story._properties["actions"]
                    if action["data"]["actionId"] not in removed_action_ids
                ]
        else:
            return False

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _create_item_embed(self, item):
        """
        Create the embed dictionary when adding an item as a text attachment.
        """
        # first create resource dictionary
        resource_id = "r-" + uuid.uuid4().hex[0:6]
        resource_dict = {
            "type": "portal-item",
            "data": {
                "itemId": item.id,
            },
        }
        # add the resource to the resources
        self._story._properties["resources"][resource_id] = resource_dict

        # second create the embed dictionary
        embed_dict = {
            "type": "embed",
            "data": {
                "embedResourceId": resource_id,
                "url": item.homepage,
                "isInteractiveByDefault": True,
                "display": "inline",
            },
        }

        # add the embed dict to the nodes
        # create node id
        node_id = "n-" + uuid.uuid4().hex[0:6]
        # add to nodes
        self._story._properties["nodes"][node_id] = embed_dict
        # return the node id
        return node_id

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True
        self._story._properties["nodes"][self.node] = {
            "type": "text",
            "data": {
                "type": self._style,
                "text": self._text,
            },
        }
        if self._color is not None:
            self._story._properties["nodes"][self.node]["data"]["customTextColors"] = [
                self._color
            ]
        if self._size is not None:
            # if story is not a briefing and size is 'small' then set to 'medium'
            if not isinstance(self._story, briefing.Briefing) and self._size == "small":
                self._size = "medium"
            self._story._properties["nodes"][self.node]["data"]["textSize"] = self._size

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Button:
    """
    Class representing a `button`.

    .. note::
        Once you create a Button instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    link                    Required String. When user clicks on button, they will be brought to
                            the link.
    ------------------      --------------------------------------------------------------------
    text                    Required String. The text that shows on the button.
    ==================      ====================================================================

    """

    def __init__(
        self, link: Optional[str] = None, text: Optional[str] = None, **kwargs
    ):
        # Can be created from scratch or already exist in story
        # Button is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "button"
        self.node = kwargs.pop("node_id", None)
        # Check if node exists else create new instance
        self._existing = self._check_node()
        if self._existing is True:
            self._link = self._story._properties["nodes"][self.node]["data"]["link"]
            self._text = self._story._properties["nodes"][self.node]["data"]["text"]
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._link = link
            self._text = text

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Button: {self.text}"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get the properties for the button.

        :return:
            The Button dictionary for the node.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return {"node_dict": self._story._properties["nodes"][self.node]}

    # ----------------------------------------------------------------------
    @property
    def text(self):
        """
        Get/Set the text for the button.

        ==================  ==================================================
        **Parameter**        **Description**
        ------------------  --------------------------------------------------
        text                Optional String. The new text to be displayed.
        ==================  ==================================================

        :return:
            The text for the node.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["text"]

    # ----------------------------------------------------------------------
    @text.setter
    def text(self, text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["text"] = text
            return self.text

    # ----------------------------------------------------------------------
    @property
    def link(self):
        """
        Get/Set the link for the button.

        ==================  ==================================================
        **Parameter**        **Description**
        ------------------  --------------------------------------------------
        link                Optional String. The new path for the button.
        ==================  ==================================================

        :return:
            The link being used.
            If nothing is returned, make sure the content is part of the story.
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["link"]

    # ----------------------------------------------------------------------
    @link.setter
    def link(self, link):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["link"] = link
            return self.link

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story, **kwargs):
        self._story = story
        self._existing = True
        self._story._properties["nodes"][self.node] = {
            "type": "button",
            "data": {"text": self._text, "link": self._link},
        }

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Check if node exists
        if self._story is None:
            return False
        elif self.node is None:
            return False
        else:
            return True


###############################################################################################################
class Gallery:
    """
    Class representing an `image gallery`

    To begin with a new gallery, simply call the class. Once added to the story,
    you can add up to 12 images.

    .. note::
        Once you create a Gallery instance you must add it to the story to be able to edit it further.

    .. code-block:: python

        # Images to add to the gallery.
        >>> image1 = Image(<url or path>)
        >>> image2 = Image(<url or path>)
        >>> image3 = Image(<url or path>)

        # Create a gallery and add to story before adding images to it.
        >>> gallery = Gallery()
        >>> my_story.add(gallery)
        >>> gallery.add_images([image1, image2, image3])
    """

    def __init__(self, **kwargs):
        # Can be created from scratch or already exist in story
        # Gallery is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "gallery"
        self.node = kwargs.pop("node_id", None)
        # Check if node exists, else create new empty instance
        self._existing = self._check_node()
        if self._existing is True:
            self._children = self._story._properties["nodes"][self.node]["children"]
        else:
            # Create new empty instance
            self._children = []
            self.node = "n-" + uuid.uuid4().hex[0:6]

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Image Gallery"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties of the Gallery object

        :return:
            A dictionary depicting the node in the story.
            If nothing is returned, make sure the gallery is part of the story.
        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
            }

    # ----------------------------------------------------------------------
    @property
    def images(self):
        """
        Get/Set list of image nodes in the image gallery. Setting the lists allows the images
        to be reordered.

        ==================      ====================================================================
        **Parameter**            **Description**
        ------------------      --------------------------------------------------------------------
        images                  List of node ids for the images in the gallery. Nodes must already be
                                in the gallery and this list will adjust the order of the images.

                                To add new images to the gallery use:
                                    Gallery.add_images(images)
                                To delete an image from a gallery use:
                                    Gallery.delete_image(node_id)
        ==================      ====================================================================

        :return:
            A list of node ids in order of image appearance in the gallery.
            If nothing is returned, make sure the gallery is part of the story.
        """
        if self._existing:
            # Update incase addition or removal was made in between last check.
            self._children = self._story._properties["nodes"][self.node]["children"]
            images = []
            for child in self._children:
                images.append(utils._assign_node_class(self._story, child))
            return images
        else:
            raise Warning(
                "Image Gallery must be added to the story before adding Images."
            )

    # ----------------------------------------------------------------------
    @images.setter
    def images(self, images):
        if self._existing:
            if images != self.images:
                raise ValueError(
                    "You cannot add or remove images through this method, only rearrange them."
                )
            children = []
            for image in images:
                children.append(image.node)
            self._children = children
            self._story._properties["nodes"][self.node]["children"] = children
        return self.images

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the swipe.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Gallery.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if isinstance(caption, str):
            self._story._properties["nodes"][self.node]["data"]["caption"] = caption
        return self.caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the swipe.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Gallery.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text
        return self.alt_text

    # ----------------------------------------------------------------------
    @property
    def display(self):
        """
        Get/Set the display type of the Gallery.

        Values: `jigsaw` | `square-dynamic`
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["config"]["size"]

    # ----------------------------------------------------------------------
    @display.setter
    def display(self, display):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["config"]["size"] = display
            return self.display

    # ----------------------------------------------------------------------
    def add_images(self, images: list[Image]):
        """
        ==================      ====================================================================
        **Parameter**            **Description**
        ------------------      --------------------------------------------------------------------
        images                  Required list of images of type Image.
        ==================      ====================================================================
        """
        if self._existing:
            if len(self.images) == 12:
                raise Warning(
                    "Maximum amount of images permitted is 12. Use Gallery.delete(image_node) to remove images before adding."
                )
            if images is not None:
                for image in images:
                    if image.node in self._story._properties["nodes"]:
                        image.node = "n-" + uuid.uuid4().hex[0:6]
                    image._add_to_story(story=self._story)
                    self._story._properties["nodes"][self.node]["children"].append(
                        image.node
                    )
        return self.images

    # ----------------------------------------------------------------------
    def delete_image(self, image: str | Image):
        """
        The delete_image method is used to delete one image from the gallery. To see a list of images
        used in the gallery, use the :meth:`~arcgis.apps.storymap.story_content.Gallery.images` property.

        ==================      ====================================================================
        **Parameter**            **Description**
        ------------------      --------------------------------------------------------------------
        image                   Required String. The node id for the image to be removed from the gallery or the Image instance.
        ==================      ====================================================================

        :return: The current list of images in the gallery.
        """
        if isinstance(image, Image):
            image = image.node
        image_nodes = [im.node for im in self.images]
        if image in image_nodes:
            # Remove from the gallery list
            self._story._properties["nodes"][self.node]["children"].remove(image)
            utils._delete(self._story, image)
        self._children = self._story._properties["nodes"][self.node]["children"]
        return self.images

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        # Create image nodes
        self._story._properties["nodes"][self.node] = {
            "type": "gallery",
            "data": {
                "galleryLayout": display if display is not None else "jigsaw",
                "caption": "" if caption is None else caption,
                "alt": "" if alt_text is None else alt_text,
            },
            "children": self._children,
        }

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        if self._existing is True:
            return utils._delete(self._story, self.node)
        else:
            return False

    # ----------------------------------------------------------------------
    def _check_node(self):
        if self._story is None:
            return False
        elif self.node is None:
            return False
        else:
            return True


###############################################################################################################
class Swipe:
    """
    Create a Swipe node.

    .. note::
        Once you create a Swipe instance you must add it to the story to be able to edit it further.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    node_id             Required String. The node id for the swipe type.
    ---------------     --------------------------------------------------------------------
    story               Required :class:`~arcgis.apps.storymap.story.StoryMap` that the swipe belongs to.
    ===============     ====================================================================

    .. code-block:: python

        >>> my_story.nodes #use to find swipe node id

        # Method 1: Use the Swipe Class
        >>> swipe = Swipe()

        # Method 2: Use the get method in story
        >>> swipe = my_story.get(node = <node_id>)

    """

    def __init__(self, **kwargs):
        self._story = kwargs.pop("story", None)
        self._type = "swipe"
        if "node" in kwargs:
            # legacy
            self.node = kwargs.pop("node", None)
        else:
            self.node = kwargs.pop("node_id", None)

        # Find the type of media that the swipe supports.
        # Both contents are of the same type so only need to look at one.
        # Check if node exists else create new instance
        self._existing = self._check_node()
        if self._existing is True:
            if "data" in self._story._properties["nodes"][self.node]:
                self._slides = self._story._properties["nodes"][self.node]["data"][
                    "contents"
                ]
                # get the media for the swipe (image or map)
                media_node = self._story._properties["nodes"][self.node]["data"][
                    "contents"
                ]["0"]

                # Find the type, this is important since swipe must only have one media type
                if media_node == "":
                    # First position is empty
                    # Check the second position
                    second_media = self._story._properties["nodes"][self.node]["data"][
                        "contents"
                    ]["1"]
                    if second_media == "":
                        # No media set yet, type is empty
                        self._media_type = ""
                    else:
                        self._media_type = self._story._properties["nodes"][
                            second_media
                        ]["type"]
                else:
                    # Use the media type of the first position
                    self._media_type = self._story._properties["nodes"][media_node][
                        "type"
                    ]

            else:
                # Empty swipe node
                self._slides = []
                self._media_type = ""
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._slides = []
            self._media_type = ""

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Swipe: {self._media_type}"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Get properties of the Swipe object

        :return:
            A dictionary depicting the node in the story.
        """
        if self._existing is True:
            return {
                "node_dict": self._story._properties["nodes"][self.node],
            }
        else:
            return None

    # ----------------------------------------------------------------------
    @property
    def caption(self):
        """
        Get/Set the caption property for the swipe.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        caption             String. The new caption for the Swipe.
        ==================  ========================================

        :return:
            The caption that is being used.
        """
        if self._existing is True:
            if "caption" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["caption"]
        else:
            return None

    # ----------------------------------------------------------------------
    @caption.setter
    def caption(self, caption):
        if self._existing is True:
            if isinstance(caption, str):
                self._story._properties["nodes"][self.node]["data"]["caption"] = caption

    # ----------------------------------------------------------------------
    @property
    def alt_text(self):
        """
        Get/Set the alternate text property for the swipe.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        alt_text            String. The new alt_text for the Swipe.
        ==================  ========================================

        :return:
            The alternate text that is being used.
        """
        if self._existing is True:
            if "alt" in self._story._properties["nodes"][self.node]["data"]:
                return self._story._properties["nodes"][self.node]["data"]["alt"]
        else:
            return None

    # ----------------------------------------------------------------------
    @alt_text.setter
    def alt_text(self, alt_text):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["alt"] = alt_text

    # ----------------------------------------------------------------------
    def edit(
        self,
        content: Optional[Union[Image, Map]] = None,
        position: str = "right",
    ):
        """
        Edit the media content of a Swipe item. To save your edits and see them
        in the StoryMap's builder, make sure to save the story.

        Use this method to add new content if your swipe is empty. You can specify the content to add
        and which side of the swipe it should be on.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Required story content of type: :class:`~arcgis.apps.storymap.story_content.Image`
                            or :class:`~arcgis.apps.storymap.story_content.Map`. Must be the same media type
                            on both panels.
        ---------------     --------------------------------------------------------------------
        position            Optional String. Either "right" or "left". Default is "right" so content
                            will be added to right panel.
        ===============     ====================================================================

        :return: True if successful
        """
        if self._existing is True:
            # Media type must be same for right and left slide.
            if isinstance(content, Image) and self._media_type == "webmap":
                raise ValueError(
                    "Media type is established as webmap. Can only accept another webmap."
                )
            if isinstance(content, Map) and self._media_type == "image":
                raise ValueError(
                    "Media type is established as image. Can only accept another image."
                )
            # Add node to story.
            self._add_item_story(content)

            if "data" not in self._story._properties["nodes"][self.node]:
                self._story._properties["nodes"][self.node]["data"] = {"contents": {}}
            # Add to content in position wanted
            if position == "left":
                self._story._properties["nodes"][self.node]["data"]["contents"][
                    "0"
                ] = content.node
            else:
                self._story._properties["nodes"][self.node]["data"]["contents"][
                    "1"
                ] = content.node
            return True
        else:
            raise KeyError(
                "The instance of Swipe must first be added to the story before you can start editing."
            )

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        if self._existing is True:
            return utils._delete(self._story, self.node)
        else:
            return False

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True

        # Get parameters
        caption = kwargs.pop("caption", None)
        alt_text = kwargs.pop("alt_text", None)
        display = kwargs.pop("display", None)

        # Create swipe node
        self._story._properties["nodes"][self.node] = {
            "type": "swipe",
            "data": {
                "contents": {"0": "", "1": ""},
                "caption": "" if caption is None else caption,
                "alt": "" if alt_text is None else alt_text,
            },
        }
        if display:
            self._story._properties["nodes"][self.node]["config"] = {"size": display}

    # ----------------------------------------------------------------------
    def _add_item_story(self, content: Union[Image, Map]):
        if content and content.node in self._story._properties["nodes"]:
            content.node = "n-" + uuid.uuid4().hex[0:6]

        content._add_to_story(story=self._story)
        if isinstance(content, Image):
            self._media_type = "image"
        elif isinstance(content, Map):
            self._media_type = "webmap"

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Sidecar:
    """
    Create an Sidecar immersive object.

    A sidecar is composed of slides. Slides are composed of two sub structures: a narrative panel and a media panel.
    The media node can be a(n): Image, Video, Embed, Map, or Swipe.
    The narrative panel can contain multiple types of content including Image, Video, Embed, Button, Text, Map, and more.

    .. note::
        Once you create a Sidecar instance you must add it to the story to be able to edit it further.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    style               Optional string that depicts the sidecar style.
                        Values: 'floating-panel' | 'docked-panel' | 'slideshow'
    ===============     ====================================================================

    .. code-block:: python

        >>> my_story.nodes #use to find sidecar node id

        # Method 1: Use the Sidecar Class
        >>> sidecar = Sidecar("floating-panel") # create from scratch

        # Method 2: Use the get method in story
        >>> sidecar = my_story.content_list()[3] # sidecar is fourth item in story
    """

    def __init__(self, style: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        self._story = kwargs.pop("story", None)
        self._type = "immersive"
        if "node" in kwargs:
            # legacy
            self.node = kwargs.pop("node", None)
        else:
            self.node = kwargs.pop("node_id", None)
        # Check if node exists else create new instance
        self._existing = self._check_node()
        if self._existing is True:
            self._style = self._story._properties["nodes"][self.node]["data"]["subtype"]
            self._slides = self._story._properties["nodes"][self.node]["children"]
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._style = style if style else "floating-panel"
            self._slides = []

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Sidecar"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "Sidecar"

    # ----------------------------------------------------------------------
    def _add_to_story(
        self,
        story=None,
        **kwargs,
    ):
        # Add the story to the node
        self._story = story
        self._existing = True
        # Create timeline nodes
        self._story._properties["nodes"][self.node] = {
            "type": "immersive",
            "data": {
                "type": "sidecar",
                "subtype": self._style,
                "narrativePanelPosition": "start",
                "narrativePanelSize": "medium",
            },
            "children": [],
        }

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        List all slides and their children for a Sidecar node.

        :return:
            A list where the first item is the node id for the sidecar. Next
            items are slides with the dictionary their children.
        """
        sidecar_tree = []
        for slide in self._slides:
            narrative_panel = self._story._properties["nodes"][slide]["children"][0]
            children = (
                self._story._properties["nodes"][narrative_panel]["children"]
                if "children" in self._story._properties["nodes"][narrative_panel]
                else ""
            )
            narrative_children = []
            for child in children:
                info = self._story._properties["nodes"][child]
                narrative_children.append({info["type"]: child})

            # there will always be a narrative panel node but not always a media node
            if len(self._story._properties["nodes"][slide]["children"]) == 2:
                media_item = self._story._properties["nodes"][slide]["children"][1]
                media_type = self._story._properties["nodes"][media_item]["type"]
            else:
                media_item = ""
                media_type = ""

            # construct tree like structure
            sidecar_tree.append(
                {
                    slide: {
                        "narrative_panel": {
                            "panel": narrative_panel,
                            "children": narrative_children,
                        },
                        "media": {media_type: media_item},
                    }
                }
            )
        return sidecar_tree

    # ----------------------------------------------------------------------
    @property
    def content_list(self):
        """
        Get a list of all the content within the sidecar in order of appearance.
        The content will be displayed in the following order:
        A list of the content in slide 1, a list of the content in slide 2, etc.
        Each sub-list will contain content found in the narrative panel, if any, and the media content, if any.
        """
        contents = []
        # get the values from the nodes list and return only these
        sidecar_dict = self.properties
        for slide in sidecar_dict:
            content = []
            # get the entire slide dict
            slide_dict = list(slide.values())[0]
            if (
                "narrative_panel" in slide_dict
                and "children" in slide_dict["narrative_panel"]
                and len(slide_dict["narrative_panel"]["children"]) > 0
            ):
                # Get the content that are children of the narrative panel
                children = slide_dict["narrative_panel"]["children"]
                for child in children:
                    # Get each class from the node value
                    content.append(self.get(list(child.values())[0]))
            if "media" in slide_dict and (
                slide_dict["media"] is not None or slide_dict["media"] != {}
            ):
                # Get the media content for the slide
                media = list(slide_dict["media"].values())[0]

                if media is None or media == "":
                    pass
                else:
                    # Get the class using the node value
                    content.append(self.get(media))
            contents.append(content)
        return contents

    # ----------------------------------------------------------------------
    def edit(
        self,
        content: Union[Image, Video, Map, Embed],
        slide_number: int,
    ):
        """
        Edit method can be used to edit the **type** of media in a slide of the Sidecar.
        This is done by specifying the slide number and the media content to be added.
        The media can only be of type: Image, Video, Map, or Embed.

        .. note::
            This method should not be used to edit the narrative panel of the Sidecar. To better edit both
            the media and the narrative panel, it is recommended to use the :func:`~Sidecar.get` method
            in the Sidecar class. The `get` method can be used to change media if the content is of the same
            type as what is currently present and preserve the node_id.


        ==================      =======================================================================
        **Parameter**            **Description**
        ------------------      -----------------------------------------------------------------------
        content                 Required item that is a story content item.
                                Item type for the media node can be: :class:`~arcgis.apps.storymap.story_content.Image`,
                                :class:`~arcgis.apps.storymap.story_content.Video`, :class:`~arcgis.apps.storymap.story_content.Map`
                                :class:`~arcgis.apps.storymap.story_content.Embed`, :class:`~arcgis.apps.storymap.story_content.Swipe`
        ------------------      -----------------------------------------------------------------------
        slide_number            Required Integer. The slide that will be edited. First slide is 1.
        ==================      =======================================================================

        .. code-block:: python

            # Get sidecar from story and see the properties
            sc = story.get(<sidecar_node_id>)
            sc.properties
            >> returns a dictionary structure of the sidecar

            # If a slide 2 contains a map and you want to change it to an image
            im = Image(<img_url_or_path>)
            sc.edit(im, 2)
            sc.properties
            >> notice slide 2 now has an image

            # If I want to update the image then 2 methods:
            # OPTION 1
            im2 = Image(<img_url_or_path>)
            sc.edit(im2, 2)

            # OPTION 2 (only applicable if content is of same type as existing)
            im2 = sc.get(im.node_id)
            im2.image = <img_url_or_path>

        """
        # Find media child
        slide = self.properties[slide_number - 1]
        slide_node = list(slide.keys())[0]
        media_node = list(slide[slide_node]["media"].values())[0]

        # Add to node properties
        self._add_item_story(content)

        if media_node:
            utils._delete(self._story, media_node)
        self._story._properties["nodes"][slide_node]["children"].insert(1, content.node)

    # ----------------------------------------------------------------------
    def get(self, node_id: str):
        """
        The get method is used to get the node that will be edited. Use `sidecar.properties` to
        find all nodes associated with the sidecar.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        node_id             Required String. The node id for the content that will be returned.
        ===============     ====================================================================

        :return: An class instance of the node type.

        .. code-block:: python

            # Find the nodes associated with the sidecar
            sc = story.get(<sidecar_node_id>)
            sc.properties
            >> returns a dictionary structure of the sidecar

            # Get a node associated with the sidecar, in this example an image, and change the image
            im = sc.get(<node_id>)
            im.image = <new_image_path>

            # Save the story to see changes applied in Story Map builder
            story.save()

        """
        return utils._assign_node_class(self._story, node_id)

    # ----------------------------------------------------------------------
    def add_action(
        self,
        slide_number: int,
        text: str,
        viewpoint: dict,
        extent: dict | None = None,
        map_layers: list[dict] | None = None,
    ):
        """
        Add a map action button to a slide. You can specify the data of the action.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        slide_number        Required Integer. The slide that the map action will be added to. First slide is 1.
        ---------------     --------------------------------------------------------------------
        text                Required String. The map action button text
        ---------------     --------------------------------------------------------------------
        viewpoint           Required Dictionary. The viewpoint to be set. The minimum keys to include are
                            an x and y center point in the target geometry.

                            Example:
                                viewpoint = {
                                    "rotation": 0,
                                    "scale": 18055.954822,
                                    "targetGeometry": {
                                        "spatialReference": {
                                            "latestWkid": 3857,
                                            "wkid": 102100
                                        },
                                        "x": -8723429.856341356,
                                        "y": 4019095.847955684
                                    }
                                }
        ---------------     --------------------------------------------------------------------
        extent              Optional Dictionary. The extent of the map that will be shown when
                            the action button is used.

                            Example:
                                extent = {
                                    "spatialReference": {
                                        "latestWkid": 3857,
                                        "wkid": 102100
                                    },
                                    "xmin": -8839182.968379805,
                                    "ymin": 3907027.5240857545,
                                    "xmax": -8824335.075635428,
                                    "ymax": 3915378.269425899
                                }
        ---------------     --------------------------------------------------------------------
        map_layers          Optional list of dictionaries. Each dictionary represents a map layer
                            and the parameters set on the map layer.

                            Example:
                                map_layers = [
                                    {
                                        "id": "18511776c33-layer-2",
                                        "title": "USA Forest Type",
                                        "visible": true
                                    }
                                ]
        ===============     ====================================================================

        :return: The node id for the action that was added to the slide
        """
        # create node for the action
        node = "n-" + uuid.uuid4().hex[0:6]

        # find the target map
        slide_node = self._slides[slide_number - 1]
        slide_dict = self.properties[slide_number][slide_node]
        if "media" not in slide_dict:
            raise ValueError(
                "The slide needs a webmap or expressmap for the map action to be created."
            )

        # get the map type
        map_type = list(slide_dict["media"].keys())[0]
        if map_type not in ["expressmap", "webmap"]:
            raise ValueError(
                "The slide needs a webmap or expressmap for the map action to be created."
            )
        map_node = slide_dict["media"][map_type]

        # compose the action dict
        action_dict = {
            "origin": node,
            "trigger": "ActionButton_Apply",
            "target": map_node,
            "event": (
                "ExpressMap_UpdateData"
                if map_type == "expressmap"
                else "WebMap_UpdateData"
            ),
            "data": {},
        }
        if extent and not viewpoint:
            action_dict["data"]["extent"] = extent
            x_center = (extent["xmin"] + extent["xmax"]) / 2
            y_center = (extent["ymin"] + extent["ymax"]) / 2
            viewpoint = {
                "rotation": 0,
                "targetGeometry": {
                    "spatialReference": (
                        extent["spatialReference"]
                        if "spatialReference" in extent
                        else {"latestWkid": 3857, "wkid": 102100}
                    ),
                    "x": x_center,
                    "y": y_center,
                },
            }
        if map_layers:
            action_dict["data"]["mapLayers"] = map_layers
        if viewpoint:
            action_dict["data"]["viewpoint"] = viewpoint

        # add to actions list in story properties
        if "actions" in self._story._properties:
            self._story._properties["actions"].append(action_dict)
        else:
            self._story._properties["actions"] = [action_dict]

        # compose the node dict in story properties
        self._story._properties["nodes"][node] = {
            "type": "action-button",
            "data": {"text": text},
            "config": {"size": "wide"},
        }

        # add to the narrative panel
        narrative_panel_node = slide_dict["narrative_panel"]["panel"]
        self._story._properties["nodes"][narrative_panel_node]["children"].append(node)

        return node

    # ----------------------------------------------------------------------
    def add_slide(
        self,
        contents: list | None = None,
        media: Image | Video | Map | Embed | None = None,
        slide_number: int = None,
    ):
        """
        Add a slide to the sidecar. You are able to specify the position of the slide, the
        content of the narrative panel and the media of the slide.

        =======================     ====================================================================
        **Parameter**                **Description**
        -----------------------     --------------------------------------------------------------------
        contents                    Optional list of story content item(s). The instances of story content that
                                    will be added to the narrative panel such as Text, Image, Embed, etc.
        -----------------------     --------------------------------------------------------------------
        media                       Optional item that is a story content item.
                                    Item type for the media node can be: Image, Video, Map, Embed, or Swipe.
        -----------------------     --------------------------------------------------------------------
        slide_number                Optional Integer. The position at which the new slide will be.
                                    If none is provided then it will be added as the last slide.

                                    First slide is 1.
        =======================     ====================================================================

        .. code-block:: python

            # Get sidecar from story and see the properties
            sc = story.get(<sidecar_node_id>)
            sc.properties
            >> returns a dictionary structure of the sidecar

            # create the content we will add to narrative_panel_nodes parameter
            im = Image(<img_url_or_path>)
            txt = Text("Hello World")
            embed = Embed(<url>)
            narrative_nodes = [im, txt, embed]

            mmap = Map(<item_id webmap>)

            # Add new slide with the content:
            sc.add_slide(narrative_nodes, mmap, 4)
            >> New slide added with the content at position 4
        """
        # Loop to:
        # 1. Add the content to the story if not already added
        # 2. Add the node ids to list to pass as children later
        if self._existing:
            np_children = []
            if contents:
                for content in contents:
                    self._add_item_story(content)
                    np_children.append(content.node)
            if media:
                self._add_item_story(media)

            # For reference on some styles, grab first slide to go off of
            if len(self._slides) > 0:
                first_slide = self._story._properties["nodes"][self._slides[0]]
                first_np = self._story._properties["nodes"][first_slide["children"][0]]
                data = first_np["data"]  # keep same settings as other slide
            else:
                if self._style == "slideshow":
                    data = {"position": "start-top", "panelStyle": "themed"}
                else:
                    data = {
                        "position": "start",
                        "size": "small",
                        "panelStyle": "themed",
                    }

            # Create narrative panel node
            np_node = "n-" + uuid.uuid4().hex[0:6]
            np_def = {
                "type": "immersive-narrative-panel",
                "data": data,
                "children": np_children,
            }
            self._story._properties["nodes"][np_node] = np_def

            # Create slide node and add the other nodes to it
            slide_node = "n-" + uuid.uuid4().hex[0:6]
            slide_def = {
                "type": "immersive-slide",
                "data": {"transition": "fade"},
                "children": [np_node],  # First listed node is the Narrative Panel
            }
            # If no media given then put a background color instead
            if media:
                slide_def["children"].append(media.node)
            else:
                slide_def["data"]["backgroundColor"] = "#FFFFFF"
            self._story._properties["nodes"][slide_node] = slide_def

            # Add slide node to sidecar node children at position indicated or last.
            if slide_number is None:
                # If no slide number then insert slide last
                slide_number = len(self._slides) + 1
            else:
                # Correct for the indexing (user puts position 1, index is 0)
                slide_number = slide_number - 1
            self._story._properties["nodes"][self.node]["children"].insert(
                slide_number, slide_node
            )
            # Update slide definition for the class to reflect new list
            self._slides = self._story._properties["nodes"][self.node]["children"]
            return {"New Slide": slide_node}
        else:
            return Exception(
                "The sidecar must first be added to a story before editing."
            )

    # ----------------------------------------------------------------------
    def remove_slide(self, slide: str):
        """
        Remove a slide from the sidecar.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        slide               Required String. The node id for the slide that will be removed.
        ===============     ====================================================================
        """
        # Remove slide and all associated children.
        self._remove_associated(slide)
        self._story._properties["nodes"][self.node]["children"].remove(slide)
        utils._delete(self._story, slide)
        self._slides = self._story._properties["nodes"][self.node]["children"]
        return True

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _remove_associated(self, slide):
        # Get narrative panel, always first child of the slide
        narrative_panel: str = self._story._properties["nodes"][slide]["children"][0]
        # Delete the children of the narrative panel
        if "children" in self._story._properties["nodes"][narrative_panel]:
            children: list = self._story._properties["nodes"][narrative_panel][
                "children"
            ]
            for child in children:
                utils._delete(self._story, child)
        # Delete the narrative panel itself
        utils._delete(self._story, narrative_panel)

        # Remove media item and resource node if one exists
        if len(self._story._properties["nodes"][slide]["children"]) >= 1:
            media_item: str = self._story._properties["nodes"][slide]["children"][0]
            utils._delete(self._story, media_item)

    # ----------------------------------------------------------------------
    def _add_item_story(self, content: Union[Image, Video, Map, Embed, Swipe]):
        if content and content.node in self._story._properties["nodes"]:
            content.node = "n-" + uuid.uuid4().hex[0:6]
        if (
            isinstance(content, Image)
            or isinstance(content, Video)
            or isinstance(content, Map)
            or isinstance(content, Audio)
        ):
            content._add_to_story(display="wide", story=self._story)
        elif isinstance(content, Embed):
            content._add_to_story(display="card", story=self._story)
        else:
            content._add_to_story(story=self._story)

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Node is not in the story if no story or node id is present
        return self._story is not None and self.node is not None


###############################################################################################################
class Timeline:
    """
    Create a Timeline object from a pre-existing `timeline` node.

    A timeline is composed of events.
    Events are composed of maximum three nodes: an image, a sub-heading text, and a paragraph text.

    .. note::
        Once you create a Timeline instance you must add it to the story to be able to edit it further.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    style               Required string, the style type of the timeline. If the timeline will be
                        added to a Sidecar, then only `waterfall` and `single-sided` are allowed.


                        Values: 'waterfall' | 'single-side' | 'condensed'
    ===============     ====================================================================

    .. code-block:: python

        >>> my_story.nodes #use to find timeline node id

        # Method 1: Use the Timeline Class
        >>> timeline = Timeline(my_story, <node_id>)

        # Method 2: Use the get method in story
        >>> timeline = my_story.get(node = <node_id>)
    """

    def __init__(self, style: Optional[str] = None, **kwargs):
        # Can be created from scratch or already exist in story
        self._story = kwargs.pop("story", None)
        self._type = "timeline"
        if "node" in kwargs:
            # legacy
            self.node = kwargs.pop("node", None)
        else:
            self.node = kwargs.pop("node_id", None)
        # Check if node exists else create new instance
        self._existing = self._check_node()
        if self._existing is True:
            self._style = self._story._properties["nodes"][self.node]["data"]["type"]
            self._events = self._story._properties["nodes"][self.node]["children"]
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._style = style if style else "waterfall"
            self._events = []

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Timeline"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "Timeline"

    # ----------------------------------------------------------------------
    def _add_to_story(
        self,
        story=None,
    ):
        # Add the story to the node
        self._story = story
        # Create timeline nodes
        self._story._properties["nodes"][self.node] = {
            "type": "timeline",
            "data": {
                "type": self._style,
            },
            "children": [],
        }
        self._existing = True

    # ----------------------------------------------------------------------
    @property
    def properties(self):
        """
        List all events and their children

        :return:
            A list where the first item is the node id for the timeline. Next
            items are dictionary of events and their children.
        """
        timeline = {self.node: {}}
        for event in self._events:
            timeline[self.node][event] = {}
            if "children" in self._story._properties["nodes"][event]:
                for child in self._story._properties["nodes"][event]["children"]:
                    node_type = self._story._properties["nodes"][child]["type"]
                    if node_type == "text":
                        node_type = self._story._properties["nodes"][child]["data"][
                            "type"
                        ]
                        if node_type == "h3":
                            node_type = "subheading"
                    timeline[self.node][event][node_type] = child
            else:
                node_type = self._story._properties["nodes"][event]["type"]
                timeline[self.node][event] = node_type
        return timeline

    # ----------------------------------------------------------------------
    @property
    def style(self) -> str:
        """
        Get/Set the style of the timeline

        Values: `waterfall` | `single-slide` | `condensed`
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["type"]
        else:
            return self._style

    # ----------------------------------------------------------------------
    @style.setter
    def style(self, style):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["type"] = style
            self._style = style

    # ----------------------------------------------------------------------
    def edit(
        self,
        content: Union[Image, Text],
        event: int,
    ):
        """
        Edit event text or image content. To add a new event use the `add_event` method.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Required content to replace current content.
                            Item type can be :class:`~arcgis.apps.storymap.story_content.Image` or :class:`~arcgis.apps.storymap.story_content.Text` .

                            Text can only be of style TextStyles.SUBHEADING or TextStyles.PARAGRAPH
        ---------------     --------------------------------------------------------------------
        event               Required Integer. The event that will be edited. First event is 1.
        ===============     ====================================================================
        """
        # Find children nodes
        event = self._events[event - 1]

        # Get position of new item, if None: needs to be added in.
        position = self._find_position_content(content, event)

        # Check to see if content has been added to node properties
        if content.node not in self._story._properties["nodes"]:
            content._add_to_story(story=self._story)

        # Insert new content
        if isinstance(content, Text):
            # Can either be the heading or subheading of the timeline.
            # Need to either replace old or add new if not already existing.
            if position is not None:
                old_text_node = self._story._properties["nodes"][event]["children"].pop(
                    position
                )
                utils._delete(self._story, old_text_node)
                self._story._properties["nodes"][event]["children"].insert(
                    position, content.node
                )
            else:
                self._story._properties["nodes"][event]["children"].append(content.node)
        elif isinstance(content, Image):
            # Remove current image content and add new content if image already present
            if position is not None:
                old_image_node = self._story._properties["nodes"][event][
                    "children"
                ].pop(position)
                utils._delete(self._story, old_image_node)
                self._story._properties["nodes"][event]["children"].insert(
                    position, content.node
                )
            else:
                # Image was not currently present so simply add
                self._story._properties["nodes"][event]["children"].append(content.node)

    # ----------------------------------------------------------------------
    def add_event(
        self, contents: list[Image | Text] | None = None, position: int | None = None
    ) -> bool:
        """
        Add event or spacer to the timeline.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        contents            Optional item list that will be in the event. Need to be passed in
                            by order of appearance.
                            Item type can be :class:`~arcgis.apps.storymap.story_content.Image` or :class:`~arcgis.apps.storymap.story_content.Text` .

                            Text can only be of style TextStyles.SUBHEADING or TextStyles.PARAGRAPH

                            .. note::
                                To create timeline spacer, do not pass in any value for this parameter.
        ---------------     --------------------------------------------------------------------
        position            Optional Integer. The position at which the even will be added. First event is 1.
                            If None, then the event will be added to the end.
        ===============     ====================================================================

        """
        if self._existing is True:
            # Check if able to add event (20 max)
            if len(self._events) == 20:
                raise ValueError(
                    "There is a maximum of 20 events allowed per timeline. To remove an event use the `remove_event` method."
                )

            event_node = "n-" + uuid.uuid4().hex[0:6]
            if position:
                self._story._properties["nodes"][self.node]["children"].insert(
                    position - 1, event_node
                )
            else:
                self._story._properties["nodes"][self.node]["children"].append(
                    event_node
                )
            if contents:
                contents_ids = []
                for content in contents:
                    # Check to see if content has been added to node properties
                    if content.node not in self._story._properties["nodes"]:
                        content._add_to_story(story=self._story)
                    contents_ids.append(content.node)
                self._story._properties["nodes"][event_node] = {
                    "type": "timeline-event",
                    "children": contents_ids,
                }
            else:
                self._story._properties["nodes"][event_node] = {
                    "type": "timeline-spacer"
                }

            # update self._events
            self._events = self._story._properties["nodes"][self.node]["children"]

            return True
        else:
            return Exception("The node must be part of a story before editing")

    # ----------------------------------------------------------------------
    def remove_event(self, event: str):
        """
        Remove an event from the timeline.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        event               Required String. The node id for the timeline event that will be removed.
        ===============     ====================================================================
        """
        self._remove_associated(event)
        self._story._properties["nodes"][self.node]["children"].remove(event)
        utils._delete(self._story, event)
        return True

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _remove_associated(self, event):
        # Remove narrative panel and text associated
        if "children" in self._story._properties["nodes"][event]:
            children = self._story._properties["nodes"][event]["children"]
            for child in children:
                utils._delete(self._story, child)
            utils._delete(self._story, event)

    # ----------------------------------------------------------------------
    def _find_position_content(self, content, event_node):
        # Find the position in which to insert the new content
        if isinstance(content, Text):
            content_type = "text"
            subtype = content._style
        elif isinstance(content, Image):
            content_type = "image"

        # Find the position of the node that corresponds to the content being added
        # If a user does not previously have a type of content, the position is None.
        for child in self._story._properties["nodes"][event_node]["children"]:
            if (
                self._story._properties["nodes"][child]["type"] == content_type
                and content_type == "image"
            ):
                position = self._story._properties["nodes"][event_node][
                    "children"
                ].index(child)
                return position
            elif (
                self._story._properties["nodes"][child]["type"] == content_type
                and self._story._properties["nodes"][child]["data"]["type"] == subtype
            ):
                position = self._story._properties["nodes"][event_node][
                    "children"
                ].index(child)
                return position
            else:
                # Content type doesn't exist yet and will need to be added in.
                position = None
        return position

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Node is not in the story if no story or node id is present
        return self._story is not None and self.node is not None


###############################################################################################################
class MapTour:
    """
    Create a MapTour object from a pre-existing `maptour` node.

    .. note::
        Once you create a MapTour instance you must add it to the story to be able to edit it further.

    .. code-block:: python

        >>> my_story.nodes #use to find map tour node id

        # Method 1: Use the MapTour Class
        >>> maptour = MapTour(my_story, <node_id>)

        # Method 2: Use the get method in story
        >>> maptour = my_story.get(node = <node_id>)
    """

    def __init__(self, **kwargs):
        # Content must already exist in the story
        # Map Tour is not an immersive node
        self._story = kwargs.pop("story", None)
        self.node = kwargs.pop("node_id", None)
        self._existing = self._check_node()

        if self._existing:
            self.map = self._story._properties["nodes"][self.node]["data"]["map"]
            if self._story._properties["nodes"][self.node]["type"] != "tour":
                raise Exception("This node is not of type tour.")
            self._type = self._story._properties["nodes"][self.node]["data"]["type"]
            self._subtype = self._story._properties["nodes"][self.node]["data"][
                "subtype"
            ]
            self._places = self._story._properties["nodes"][self.node]["data"]["places"]
        else:
            raise ValueError(
                "You cannot create a Map Tour from scratch at this time. Please use an existing Map Tour."
            )

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Map Tour"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "Map Tour"

    # ----------------------------------------------------------------------
    @property
    def _children(self) -> list:
        """private method to gather all children of a map tour from places data"""
        children = [self.map]
        for place in self.places:
            if "children" in place and place["contents"]:
                for content in place["contents"]:
                    children.append(content)
            if "media" in place and place["media"]:
                children.append(place["media"])
            if "title" in place and place["title"]:
                children.append(place["title"])
        return children

    # ----------------------------------------------------------------------
    @property
    def style(self):
        """Get the type and subtype of the map tour"""
        return (
            self._story._properties["nodes"][self.node]["data"]["type"]
            + " - "
            + self._story._properties["nodes"][self.node]["data"]["subtype"]
        )

    # ----------------------------------------------------------------------
    @property
    def places(self):
        """
        List all places on the map
        """
        return self._story._properties["nodes"][self.node]["data"]["places"]

    # ----------------------------------------------------------------------
    def get(self, node_id: str):
        """
        The get method is used to get the node that will be edited. Use `maptour.properties` to
        find all nodes associated with the sidecar.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        node_id             Required String. The node id for the content that will be returned.
        ===============     ====================================================================

        :return: An class instance of the node type.

        .. code-block:: python

            # Find the nodes associated with the map tour
            mt = story.get(<maptour_node_id>)
            mt.places
            >> returns places of the map tour

            # Get a node associated with the map tour, in this example an image, and change the image
            im = mt.get(<node_id>)
            im.image = <new_image_path>

            # Save the story to see changes applied in Story Map builder
            story.save()

        """
        return utils._assign_node_class(self._story, node_id)

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Node is not in the story if no story or node id is present
        return self._story is not None and self.node is not None


###############################################################################################################
class MapAction:
    """
    Within the sidecar block, there are stationary media panels and scrolling narrative panels works hand in hand
    to deliver an immersive experience. If the media panel consists of a web map or web scene, the map actions
    functionality allows authors to include options for further interactivity.
    Simply put, map actions are buttons that change something on the map or scene when toggled.
    These buttons can be configured to modify the map extent, the visibility of different layers etc., and this can be
    useful to include additional details without deviating from the primary narrative.

    There are two main types: Inline text map actions and map action blocks in sidecar.

    To create a map action you must use the `create_action` method found in the sidecar.

    ===============     ====================================================================
    **Parameter**        **Description**
    ---------------     --------------------------------------------------------------------
    node_id             Required String. The node id for the map tour type.
    ---------------     --------------------------------------------------------------------
    story               Required :class:`~arcgis.apps.storymap.story.StoryMap` that the map tour belongs to.
    ===============     ====================================================================

    """

    def __init__(self, **kwargs) -> None:
        node = kwargs.pop("node_id", None)
        story = kwargs.pop("story", None)
        if node:
            self.node = node
            self._story = story
            actions = story._properties["actions"]
            for action in actions:
                if action["origin"] == node:
                    self.target = action["target"]
                    self.properties = action
        else:
            self.node = "n-" + uuid.uuid4().hex[0:6]
            self._story = story

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Map Action"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "Map Action"

    # ----------------------------------------------------------------------
    @property
    def viewpoint(self) -> dict:
        for action in self._story._properties["actions"]:
            if action["origin"] == self.node:
                return action["data"]["viewpoint"]

    # ----------------------------------------------------------------------
    @property
    def text(self) -> str:
        """
        Get/Set the button text for a map action button.
        """
        node_dict = self._story._properties["nodes"][self.node]
        if "text" in node_dict["data"]:
            return node_dict["data"]["text"]
        return ""

    # ----------------------------------------------------------------------
    @text.setter
    def text(self, text: str) -> None:
        """"""
        if isinstance(text, str):
            self._story._properties["nodes"][self.node]["data"]["text"] = text
        else:
            raise TypeError("Text must be of type string.")

    # ----------------------------------------------------------------------
    def set_viewpoint(
        self, target_geometry: dict, scale: Scales, rotation: int | None = None
    ):
        """
        Set the extent and/or scale for the map action in the story.

        To see the current viewpoint call the `viewpoint` property on the Map Action
        node.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        target_geometry     Required dictionary representing the target geometry of the
                            viewpoint.

                            Example:
                                | {'spatialReference': {'latestWkid': 3857, 'wkid': 102100},
                                | 'x': -609354.6306080809,
                                | 'y': 2885721.2797636474}
        ------------------  ----------------------------------------
        scale               Required Scales enum class value or int.

                            Scale is a unit-less way of describing how any distance on the map translates
                            to a real-world distance. For example, a map at a 1:24,000 scale communicates that 1 unit
                            on the screen represents 24,000 of the same unit in the real world.
                            So one inch on the screen represents 24,000 inches in the real world.
        ------------------  ----------------------------------------
        rotation            Optional float. Determine the rotation for an
                            action on a 3D map.
        ==================  ========================================

        :return: The current viewpoint dictionary
        """
        for idx, action in enumerate(self._story._properties["actions"]):
            if action["origin"] == self.node:
                if rotation is None:
                    if "viewpoint" in self._story._properties["actions"][idx]["data"]:
                        rotation = (
                            self._story._properties["actions"][idx]["data"][
                                "viewpoint"
                            ]["rotation"]
                            if "rotation"
                            in self._story._properties["actions"][idx]["data"][
                                "viewpoint"
                            ]
                            else 0
                        )
                if isinstance(scale, Scales):
                    scale = scale.value
                self._story._properties["actions"][idx]["data"]["viewpoint"] = {
                    "rotation": rotation,
                    "scale": scale,
                    "targetGeometry": target_geometry,
                }
        return self.viewpoint

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the map action.
        """
        for idx, action in enumerate(self._story._properties["actions"]):
            if action["origin"] == self.node:
                del self._story._properties["actions"][idx]
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Node is not in the story if no story or node id is present
        return self._story is not None and self.node is not None


###############################################################################################################
class ExpressMap:
    """
    Class representing an ExpressMap.

    .. note::
        You can only create an ExpressMap from a pre-existing `expressmap` in a story or briefing. You cannot create
        an ExpressMap from scratch.
    """

    def __init__(self, **kwargs):
        # Content must already exist in the story
        # ExpressMap is not an immersive node
        self._story = kwargs.pop("story", None)
        self.node = kwargs.pop("node_id", None)
        self._existing = self._check_node()

        if self._existing:
            self._map_resource = self._story._properties["nodes"][self.node]["data"][
                "map"
            ]
            # check if offline dependent
            if "dependents" in self._story._properties["nodes"][self.node]:
                self._offline_dependent = self._story._properties["nodes"][self.node][
                    "dependents"
                ]["offline"]
        else:
            raise ValueError(
                "You cannot create an ExpressMap from scratch at this time. Please use an existing ExpressMap."
            )

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "ExpressMap"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return "ExpressMap"

    # ----------------------------------------------------------------------
    @property
    def offline_media(self):
        """
        Get/Set the offline media property for the embed.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        offline_media       Image or Video. The new offline_media for the Embed.
        ==================  ========================================

        :return:
            The offline media that is being used.
        """
        if self._existing is True:
            if self._offline_dependent:
                return utils._assign_node_class(
                    story=self._story, node_id=self._offline_dependent
                )
        return None

    # ----------------------------------------------------------------------
    @offline_media.setter
    def offline_media(self, value: Image | Video):
        if self._existing:
            # can only set for briefing
            if isinstance(self._story, briefing.Briefing):
                if isinstance(value, Image) or isinstance(value, Video):
                    value._add_to_story(story=self._story)
                    self._story._properties["nodes"][self.node]["dependents"] = {
                        "offline": value.node
                    }
                    self._offline_dependent = value.node
                else:
                    raise ValueError("offline_media must be an Image or Video")
            else:
                raise ValueError("offline_media can only be set for a Briefing")
        else:
            raise ValueError(
                "offline_media can only be set for an ExpressMap that has been added to a Briefing."
            )

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the map action.
        """
        for idx, action in enumerate(self._story._properties["actions"]):
            if action["origin"] == self.node:
                del self._story._properties["actions"][idx]
        return utils._delete(self._story, self.node)

    # ----------------------------------------------------------------------
    def _check_node(self):
        # Node is not in the story if no story or node id is present
        return self._story is not None and self.node is not None


###############################################################################################################
class Code:
    """
    Class representing a `code` content card.
    Code will show as a block of code in your Storymap.

    .. note::
        Once you create a Code instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    content                 Required String. The code content to have in the block.
    ------------------      --------------------------------------------------------------------
    language                Required Language or String. The coding language of the content provided.
                            For values see Language Enum Class.
    ==================      ====================================================================
    """

    def __init__(
        self,
        content: Optional[str] = None,
        language: Optional[Union[Language, str]] = None,
        **kwargs,
    ):
        # Can be created from scratch or already exist in story
        # Code is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "code"
        self.node = kwargs.pop("node_id", None)
        # If node doesn't already exist, create new instance
        self._existing = self._check_node()
        if self._existing is True:
            # Get the content and language
            self._content = self._story._properties["nodes"][self.node]["data"][
                "content"
            ]
            if "lang" in self._story._properties["nodes"][self.node]["data"]:
                self._language = self._story._properties["nodes"][self.node]["data"][
                    "lang"
                ]
            else:
                self._language = "txt"
        else:
            # Create new instance, notice no resource node is needed for code
            self._content = content

            if isinstance(language, Language):
                self._language = language.value
            elif isinstance(language, str) and language in [e.value for e in Language]:
                self._language = language
            else:
                raise ValueError(
                    "Language provided is not part of the accepted languages. Please make sure to provide one from the list."
                )
            self.node = "n-" + uuid.uuid4().hex[0:6]

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Code: {self.language}"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def content(self) -> str:
        """
        Get/Set the content property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        content             String. The new content for the code block.
        ==================  ========================================

        :return:
            The content that is being used.
        """
        return self._content

    # ----------------------------------------------------------------------
    @content.setter
    def content(self, content: str):
        if self._existing is True:
            self._update_content(content)
        else:
            self._content = content

    # ----------------------------------------------------------------------
    @property
    def language(self) -> str:
        """
        Get/Set the language property.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        language            Language value. The new language for the code block.
        ==================  ========================================

        :return:
            The language that is being used.
        """
        return self._language

    # ----------------------------------------------------------------------
    @language.setter
    def language(self, language: Language | str):
        if self._existing is True:
            # Figure out correct language
            if isinstance(language, Language):
                language = language.value
            elif isinstance(language, str) and language in Language:
                language = language
            else:
                raise ValueError(
                    "The language provided is not a valid value. Please see the Language Enum class for valid values."
                )

            # Change the language
            self._story._properties["nodes"][self.node]["data"]["lang"] = language
            if language in ["html", "json"]:
                self._story._properties["nodes"][self.node]["data"]["isEncoded"] = True
                # reassign content so it gets encoded correctly
                # known limit: this will cause an issue if a user goes from html to json or vise versa
                self.content = self._content
            else:
                self._story._properties["nodes"][self.node]["data"]["isEncoded"] = False
            self._language = language

    # ----------------------------------------------------------------------
    @property
    def line_number(self) -> bool:
        """
        Get/Set whether line number property is set.

        ==================  ========================================
        **Parameter**        **Description**
        ------------------  ----------------------------------------
        enabled             Bool. Set to True if you want line numbers, False otherwise.
        ==================  ========================================

        :return:
            True if line numbers are enabled and False if not.
        """
        if self._existing is True:
            return self._story._properties["nodes"][self.node]["data"]["lineNumbers"]

    # ----------------------------------------------------------------------
    @line_number.setter
    def line_number(self, enabled):
        if self._existing is True:
            self._story._properties["nodes"][self.node]["data"]["lineNumbers"] = enabled

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return self._story._delete(self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None):
        self._story = story
        self._existing = True
        # Create embed node, no resource node needed
        self._story._properties["nodes"][self.node] = {
            "type": "code",
            "data": {
                "lineNumbers": False,
                "content": self._content,
                "lang": self._language,
                "isEncoded": True if self._language in ["html", "json"] else False,
            },
        }

    # ----------------------------------------------------------------------
    def _update_content(self, content):
        if self._language in ["html", "json"]:
            # same encoding for html and json
            content = html.escape(content)
        # set new content
        self._content = content
        # update dictionary properties
        self._story._properties["nodes"][self.node]["data"]["content"] = content

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class BriefingSlide:
    """
    Represents a Slide for a Briefing.

    .. note::
        To create a new slide use the `add` method in the Briefing class.
    """

    def __init__(
        self,
        **kwargs,
    ):
        self._story: briefing.Briefing = kwargs.pop("story")
        self._type: str = "briefing-slide"
        self.node: str = kwargs.pop("node_id", None)
        # Check if node exists else create a new instance
        self._existing: bool = self._check_node()

        if self._existing:
            # initialize the slide
            self._initialize_existing_slide()
            self._set_block_children()
        else:
            # check the kwargs and create the slide
            layout: Union[SlideLayout, str] = kwargs.pop("layout", "single")
            sublayout: Union[SlideSubLayout, str] | None = kwargs.pop("sublayout", None)
            title: Text | str | None = kwargs.pop("title", None)
            subtitle: Text | str | None = kwargs.pop("subtitle", None)
            section_position: str | None = kwargs.pop("section_position", None)
            self._initialize_new_slide(
                layout, sublayout, title, subtitle, section_position
            )

    def _initialize_existing_slide(self):
        # Existing slide logic
        if "data" in self._story._properties["nodes"][self.node]:
            node_data = self._story._properties["nodes"][self.node]["data"]
            self._children: dict = node_data.get("contents", {})
            self._layout: str = node_data.get("layout", None)
            self._sublayout: str = node_data.get("sublayout", None)

            subtitle = node_data.get("subtitle", None)
            if subtitle:
                self._subtitle: Text | None = utils._assign_node_class(
                    story=self._story, node_id=subtitle
                )
            else:
                self._subtitle: Text | None = None

            title_node = node_data.get("title", None)
            if title_node:
                self._title: Text = utils._assign_node_class(self._story, title_node)
            else:
                self._title: Text | None = None

            self._section_position: str | None = node_data.get("sectionPosition", None)

    def _initialize_new_slide(
        self, layout, sublayout, title, subtitle, section_position
    ):
        # New slide logic
        self.node: str = "n-" + uuid.uuid4().hex[0:6]
        self._children: dict = {}

        self._apply_layout(layout, sublayout, section_position)

        # set title
        if title:
            self._title: Text = (
                Text(title, TextStyles.SUBHEADING) if isinstance(title, str) else title
            )
        else:
            self._title: Text | None = None

        # set subtitle
        if subtitle:
            self._subtitle: Text = (
                Text(subtitle, TextStyles.PARAGRAPH)
                if isinstance(subtitle, str)
                else subtitle
            )
        else:
            self._subtitle: Text | None = None

    def _apply_layout(self, layout, sublayout, section_position):
        # set layout and sublayout
        if layout in SlideLayout.__members__.values():
            self._layout: str = layout.value
        elif layout in [
            "single",
            "double",
            "titleless-single",
            "titleless-double",
            "full",
            "section-single",
            "section-double",
        ]:
            self._layout: str = layout
        else:
            raise ValueError(
                "Layout must be one of the following: single, double, titleless-single, titleless-double, full, section-single, section-double"
            )

        if self._layout in ["double", "titleless-double"]:
            if sublayout and sublayout in SlideSubLayout.__members__.values():
                self._sublayout: str = sublayout.value
            elif sublayout and sublayout in ["3-7", "7-3", "1-1"]:
                self._sublayout: str = sublayout
            elif sublayout:
                raise ValueError("Invalid sublayout type")
            else:
                self._sublayout: str = "1-1"
        else:
            self._sublayout: str | None = None

        if self._layout == "section-double" and section_position:
            self._section_position: str = section_position
        else:
            self._section_position: str | None = None

    def _set_block_children(self):
        # Logic for fixing children, section double is special case
        if self._layout == "section-single":
            self._set_special_layout()
        elif (
            "single" in self._layout
            or self._layout == "full"
            or self._layout == "section-double"
        ):
            self._set_single_layout()
        elif "double" in self._layout:
            self._set_double_layout()

    def _set_special_layout(self):
        # Logic to fix the section-single layout, can be added to later
        # section-single has no blocks, put empty dictionary
        if "contents" not in self._story._properties["nodes"][self.node]["data"]:
            self._story._properties["nodes"][self.node]["data"]["contents"] = {}
        self._children = self._story._properties["nodes"][self.node]["data"]["contents"]
        self._delete_keys(1)

    def _set_single_layout(self):
        # Logic for fixing single layout
        if "0" not in self._children:
            self._story._properties["nodes"][self.node]["data"]["contents"]["0"] = []
            self._children = self._story._properties["nodes"][self.node]["data"][
                "contents"
            ]
        self._delete_keys(1)

    def _set_double_layout(self):
        # Logic for fixing double layout
        for key in ["0", "1"]:
            if key not in self._children:
                self._story._properties["nodes"][self.node]["data"]["contents"][
                    key
                ] = []
        self._children = self._story._properties["nodes"][self.node]["data"]["contents"]
        self._delete_keys(2)

    def _delete_keys(self, value):
        """delete the keys starting at the value and upwards"""
        for key in range(value, 2):
            try:
                del self._story._properties["nodes"][self.node]["data"]["contents"][
                    str(key)
                ]
            except KeyError:
                pass

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Briefing Slide: {self.layout}"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def blocks(self) -> list[Block]:
        """
        Get blocks of the Slide. Blocks hold content of various types such as
        Text, Image, Map, Swipe, etc. If you want to edit the content you can access
        the `add_content`, `delete_content` method of the block.

        :return:
            A list of blocks in the slide
        """
        # If the slide is a cover slide, then the children are the contents
        if self._story._properties["nodes"][self.node]["data"]["layout"] == "cover":
            # self._children is a list of node ids in this case
            return [
                utils._assign_node_class(self._story, node_id)
                for node_id in self._children
            ]

        # Slide is not a cover slide and has contents, even if empty
        contents = []
        for key, _ in self._children.items():
            # the key will be "0", "1" depending on the layout
            contents.append(Block(key, self, self._story))
        return contents

    # ----------------------------------------------------------------------
    @property
    def title(self) -> str | None:
        """
        Get/Set the title of the slide.

        .. note::
            To get or change the title of the cover slide, use the `cover` method in the Briefing class.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Text instance or string depicting the title of the slide.
        ===============     ====================================================================
        """
        if self._title:
            return self._title.text
        else:
            return None

    # ----------------------------------------------------------------------
    @title.setter
    def title(self, title: Union[Text, str]):
        if self._layout in ["titleless-single", "titleless-double", "full"]:
            raise Exception("This slide does not have a title.")
        if self._existing is True:
            # If string then need to create text node and add to story
            if isinstance(title, str):
                title = Text(title, TextStyles.HEADING)
                title._add_to_story(story=self._story)
            elif isinstance(title, Text):
                if title._style != TextStyles.HEADING:
                    raise ValueError(
                        "Title must be of style TextStyles.HEADING. Please change the style."
                    )
                # If text created but not in story
                if title._existing is False:
                    title._add_to_story(story=self._story)
            # Set the title node id in data of slide
            self._story._properties["nodes"][self.node]["data"]["title"] = title.node
        self._title = title

    # ----------------------------------------------------------------------
    @property
    def subtitle(self) -> str | None:
        """Get/Set the subtitle when the layout is either 'section-single' or 'section-double'."""
        if self._subtitle:
            return self._subtitle.text
        else:
            return None

    # ----------------------------------------------------------------------
    @subtitle.setter
    def subtitle(self, subtitle: Union[Text, str]):
        if self._layout not in ["section-single", "section-double"]:
            raise Exception("This slide does not have a subtitle.")

        # If string then need to create text node and add to story
        if isinstance(subtitle, str):
            subtitle = Text(subtitle, TextStyles.PARAGRAPH)
            subtitle._add_to_story(story=self._story)
        elif isinstance(subtitle, Text):
            # If text created but not in story
            if subtitle._existing is False:
                subtitle._add_to_story(story=self._story)
        # Set the title node id in data of slide
        self._story._properties["nodes"][self.node]["data"]["subtitle"] = subtitle.node

        if self._subtitle:
            # delete previous subtitle
            self._subtitle.delete()

        # assign new subtitle
        self._subtitle = subtitle

    # ----------------------------------------------------------------------
    @property
    def layout(self) -> str:
        """
        Get the layout of the slide.

        .. note::
            Once a slide is created, the layout cannot be changed.

        :return:
            A string of the layout type.
        """
        return self._layout

    # ----------------------------------------------------------------------
    @property
    def sublayout(self) -> str:
        """
        Get/Set the sublayout when the layout is "double". This determines
        the proportion of the slide that the content takes up.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        sublayout           SlideSubLayout value or String depicting the sublayout type of the slide.
                            Only applicable when the layout is "double" or "titleless-double".
        ===============     ====================================================================
        """
        return self._sublayout

    # ----------------------------------------------------------------------
    @sublayout.setter
    def sublayout(self, sublayout: str | SlideSubLayout):
        if sublayout not in SlideSubLayout.__members__.values() and not isinstance(
            sublayout, str
        ):
            raise ValueError(
                "Invalid sublayout value. Please provide a string or SlideSubLayout value."
            )

        if sublayout in SlideSubLayout.__members__.values():
            sublayout = sublayout.value

        # assign to the property
        self._sublayout = sublayout

        # update the story
        layout = self._story._properties["nodes"][self.node]["data"]["layout"]
        if layout in ["double", "titleless-double"]:
            self._story._properties["nodes"][self.node]["data"]["sublayout"] = sublayout

    # ----------------------------------------------------------------------
    @property
    def section_position(self) -> str:
        """
        Get/Set the title panel position for a section-double layout slide.

        Values: 'start' or 'end'
        """
        return self._section_position

    # ----------------------------------------------------------------------
    @section_position.setter
    def section_position(self, position: str):
        if self._layout != "section-double":
            raise Exception("This slide does not have a section position.")
        if position not in ["start", "end"]:
            raise ValueError("Invalid position value. Please provide 'start' or 'end'.")

        self._section_position = position
        self._story._properties["nodes"][self.node]["data"][
            "titlePanelPosition"
        ] = position

    # ----------------------------------------------------------------------
    def delete(self) -> bool:
        """
        Delete the node

        :return: True if successful.
        """
        if self._existing is True:
            return utils._delete(self._story, self.node)
        else:
            return False

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True
        # Create swipe node
        self._story._properties["nodes"][self.node] = {
            "type": "briefing-slide",
            "data": {"layout": self._layout, "contents": self._children},
        }

        # add sublayout
        if self._sublayout:
            self._story._properties["nodes"][self.node]["data"][
                "sublayout"
            ] = self._sublayout

        # add section position
        if self._section_position:
            self._story._properties["nodes"][self.node]["data"][
                "titlePanelPosition"
            ] = self._section_position

        # Add title if it exists
        if self._title:
            if self._title._existing is False:
                self._title._add_to_story(story=self._story)
            self._story._properties["nodes"][self.node]["data"][
                "title"
            ] = self._title.node

        # Add subtitle if it exists
        if self._subtitle:
            if self._subtitle._existing is False:
                self._subtitle._add_to_story(story=self._story)
            self._story._properties["nodes"][self.node]["data"][
                "subtitle"
            ] = self._subtitle.node

        # For editing purposes, have children even if empty
        self._set_block_children()

    # ----------------------------------------------------------------------
    def _check_node(self):
        return self._story is not None and self.node is not None


###############################################################################################################
class Block:
    """
    Represents a block in a briefing slide.

    .. note::
        Blocks are automatically created when you create a new slide. You can access the blocks
        through the `blocks` property of the slide. Do not create this class directly.
    """

    def __init__(self, block_index, slide: BriefingSlide, story) -> None:
        self._index: int = block_index
        self._slide: BriefingSlide = slide
        self._story = story
        # list of strings or single node as string
        self._content: list[str] | str = self._story._properties["nodes"][
            self._slide.node
        ]["data"]["contents"][str(self._index)]

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        if self._index == "0" and self._slide.layout in [
            "single",
            "titleless-single",
            "full",
            "section-double",
        ]:
            return "Block"
        elif self._index == "0" and self._slide.layout in [
            "double",
            "titleless-double",
        ]:
            return "Left Block"
        elif self._index == "1" and self._slide.layout in [
            "double",
            "titleless-double",
        ]:
            return "Right Block"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    @property
    def content(self) -> list:
        """
        Get the contents of the block. This will return a list of the content
        objects in the block. The content objects can be of type Text, Image, Map, etc.

        :return:
            A list of content objects in the block.
        """
        if isinstance(self._content, list) and len(self._content) > 0:
            # This is a list of content items
            return [
                utils._assign_node_class(self._story, node_id)
                for node_id in self._content
            ]
        elif isinstance(self._content, list) and len(self._content) == 0:
            # There are no contents in the block
            return []
        else:
            # There is only one content in the block
            return [utils._assign_node_class(self._story, self._content)]

    # ----------------------------------------------------------------------
    def add_content(
        self,
        content: Text | Image | Video | Embed | Map | Swipe | Gallery | Code | Table,
    ) -> bool:
        """
        Add content to the block.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Required content object to be added to the block. The content
                            object can be of type Text, Image, Video, Embed, Map, or Swipe. There
                            can be more than one Text contents in the same block but only one of the
                            other types of content.
                            Setting an Image, Video, Embed, Map, or Swipe content will overwrite the
                            current content. Setting a Text content will add the text to the block.
        ===============     ====================================================================

        :return:
            The Content object that was added to the block.
        """
        # check that the content is not None
        if content is None:
            raise Exception(
                "The content cannot be None. To remove content use the delete_content method."
            )
        # check that the content is of the correct type
        if not isinstance(
            content, (Text, Image, Video, Embed, Map, Swipe, Gallery, Code, Table)
        ):
            raise Exception(
                "The content must be of type Text, Image, Video, Embed, Map, Swipe, Gallery, Code, or Table."
            )

        content._add_to_story(story=self._story)
        # If content is text and the current content is a list, append to the list
        if isinstance(content, Text) and isinstance(self._content, list):
            self._content.append(content.node)
        # If content is text and the current content is not a list, create a list and append
        elif isinstance(content, Text) and not isinstance(self._content, list):
            # check the type of the current content
            current = self.content[0]
            if isinstance(current, Text):
                # There can be multiple text contents in a block
                self._content = [self._content, content.node]
            else:
                # There can only be one of the other types of contents
                self._content = content.node
        # If another type, then assign to content's node id, this overwrites what is currently there
        else:
            self._content = content.node

        # add to the slide in the story
        self._story._properties["nodes"][self._slide.node]["data"]["contents"][
            str(self._index)
        ] = self._content
        return content

    # ----------------------------------------------------------------------
    def delete_content(self, index: Optional[int] = None) -> bool:
        """
        Delete content from the block.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        index               Optional integer, the index of the content to be deleted. If not
                            specified, all content will be deleted.
        ===============     ====================================================================

        :return: True if successful.
        """
        if index is None:
            # delete all content
            self._content = []
        elif isinstance(index, int):
            # delete content at index
            if isinstance(self._content, list) and len(self._content) > 0:
                if 0 <= index < len(self._content):
                    del self._content[index]
                else:
                    raise Exception("Index is out of range.")
            else:
                raise Exception("There is no content at the specified index.")
        else:
            raise Exception("The index must be an integer.")

        # Update the story with the modified content
        self._story._properties["nodes"][self._slide.node]["data"]["contents"][
            str(self._index)
        ] = self._content

        return True


###############################################################################################################
class Table:
    """
    Class representing a `table block`.
    Table will show as a gridded table in your Storymap.

    .. note::
        Once you create a Table instance you must add it to the story to be able to edit it further.

    ==================      ====================================================================
    **Parameter**            **Description**
    ------------------      --------------------------------------------------------------------
    rows                    Optional int. The number of rows in the table. Table supports a maximum
                            of 10 rows. Minimum of 2 rows supported.
    ------------------      --------------------------------------------------------------------
    columns                 Optional int. The number of columns in the table. Table supports a
                            maximum of 8 columns. Minimum of 1 column supported.
    ==================      ====================================================================
    """

    def __init__(
        self,
        rows: Optional[int] = None,
        columns: Optional[int] = None,
        **kwargs,
    ):
        # Can be created from scratch or already exist in story
        # Code is not an immersive node
        self._story = kwargs.pop("story", None)
        self._type = "table"
        self.node = kwargs.pop("node_id", None)
        # If node doesn't already exist, create new instance
        self._existing = self._check_node()
        if self._existing is True:
            self._numRows = self._story._properties["nodes"][self.node]["data"][
                "numRows"
            ]
            self._numColumns = self._story._properties["nodes"][self.node]["data"][
                "numColumns"
            ]
            self._cells = (
                self._story._properties["nodes"][self.node]["data"]["cells"]
                if "cells" in self._story._properties["nodes"][self.node]["data"]
                else {}
            )
        else:
            # Create new instance, notice no resource node is needed for code
            self._numRows = rows if rows and (rows > 2 and rows <= 10) else 2
            self._numColumns = (
                columns if columns and (columns > 1 and columns <= 8) else 1
            )
            self._cells = {}
            self.node = "n-" + uuid.uuid4().hex[0:6]

    # ----------------------------------------------------------------------
    @property
    def content(self):
        """
        Get the content of the table as a panda's DataFrame.
        Each cell content is held within a dictionary where the
        'value' key is the text of the cell. The other key that can be included in
        the dictionary is the 'textAlignment' key.

        ===============     ====================================================================
        **Parameter**        **Description**
        ---------------     --------------------------------------------------------------------
        content             Required pandas DataFrame. The content of the table as a pandas
                            DataFrame. The index of the DataFrame will be the row headers and
                            the columns of the DataFrame will be the column headers.
        ===============     ====================================================================

        """
        if self._existing is True:
            df = pd.DataFrame.from_dict(
                self._cells,
                orient="index",
                columns=[f"{i}" for i in range(self._numColumns)],
            )
            # Iterate through the DataFrame
            for column in df.columns:
                for index, cell_value in enumerate(df[column]):
                    # Check if the cell value is a dictionary and has the key "value"
                    if isinstance(cell_value, dict) and "value" in cell_value:
                        # Update the value key to be an instance of the text class
                        df.at[str(index), column]["value"] = Text(cell_value["value"])
            return df

    # ----------------------------------------------------------------------
    @content.setter
    def content(self, content: pd.DataFrame):
        if self._existing is True and isinstance(content, pd.DataFrame):
            # check that the number of rows and columns didn't change, if so update
            if (
                content.shape[0] != self._numRows
                or content.shape[1] != self._numColumns
            ):
                # add check that rows are not more than 10 and columns are not more than 8.
                if content.shape[0] > 10 or content.shape[0] < 2:
                    raise ValueError("A table can only have between 2-10 rows.")
                if content.shape[1] > 8 or content.shape[1] < 1:
                    raise ValueError("A table can only have between 1-8 columns.")

                # Update the number of rows and columns
                self._numRows = content.shape[0]
                self._numColumns = content.shape[1]
                self._story._properties["nodes"][self.node]["data"][
                    "numRows"
                ] = self._numRows
                self._story._properties["nodes"][self.node]["data"][
                    "numColumns"
                ] = self._numColumns
            # First go through each cell and if the value is a text instance, keep only the text
            for column in content.columns:
                for index, cell_value in enumerate(content[column]):
                    if not isinstance(cell_value, dict):
                        raise ValueError(
                            "The content of each cell must be a dictionary. The text is held in the key 'value'."
                        )
                    if isinstance(cell_value["value"], Text):
                        content.at[str(index), column]["value"] = cell_value[
                            "value"
                        ]._text
            # convert the dataframe to a dictionary
            self._cells = content.to_dict(orient="index")
            self._story._properties["nodes"][self.node]["data"]["cells"] = self._cells

    # ----------------------------------------------------------------------
    def __str__(self) -> str:
        return "Table"

    # ----------------------------------------------------------------------
    def __repr__(self) -> str:
        return self.__str__()

    # ----------------------------------------------------------------------
    def delete(self):
        """
        Delete the node

        :return: True if successful.
        """
        return self._story._delete(self.node)

    # ----------------------------------------------------------------------
    def _add_to_story(self, story=None, **kwargs):
        self._story = story
        self._existing = True
        # Create embed node, no resource node needed
        self._story._properties["nodes"][self.node] = {
            "type": "table",
            "data": {
                "numRows": self._numRows,
                "numColumns": self._numColumns,
            },
            "config": {"size": "full"},
        }

    # ----------------------------------------------------------------------
    def _check_node(self):
        if self._story is None:
            return False
        elif self.node is None:
            return False
        else:
            return True
