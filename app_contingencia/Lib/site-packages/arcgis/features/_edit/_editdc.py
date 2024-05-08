from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

__all__ = ["AddAttachment", "UpdateAttachment", "VersionInfo", "Attachments"]


@dataclass
class AddAttachment:
    """
    Information about a single attachment add
    """

    uploadId: str
    name: str
    contentType: str
    globalId: str | None = None
    parentGlobalId: str | None = None


@dataclass
class UpdateAttachment:
    """
    Information about a single attachment update
    """

    globalId: str
    name: str
    uploadId: str
    contentType: str | None


@dataclass
class VersionInfo:
    """
    This provides the version information for the edit session
    """

    version: str
    session_id: str | None = None
    use_previous_edit_moment: bool = False


@dataclass
class Attachments:
    """
    Attachments is a helper class used to ensure the proper format is given to the `apply_edits` method.

    This class adds, updates, or deletes attachments. It applies only when the `use_global_ids` parameter
    is set to true. When set to adds, the globalIds values of the attachments provided by the client are
    preserved. When `use_global_ids` is true, the updates and deletes options are identified by each
    feature or attachment globalId value, rather than their objectId or attachmentId value.

    This requires the layer's `supportsApplyEditsWithGlobalIds` property to be true.
    """

    # A list of attachments that will be added to the Feature Layer
    adds: list[AddAttachment] = field(default_factory=list)
    # A list of attachments that will be updated
    updates: list[UpdateAttachment] = field(default_factory=list)
    # A list of attachments to delete by Global ID
    deletes: list[str] = field(default_factory=list)
