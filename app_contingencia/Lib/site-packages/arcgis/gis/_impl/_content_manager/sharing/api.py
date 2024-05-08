from __future__ import annotations
import json
from enum import Enum
from arcgis.auth import EsriSession
from arcgis.auth.tools import LazyLoader
from typing import Union, Any
import requests

arcgis = LazyLoader("arcgis")


class SharingLevel(Enum):
    """
    Sets the sharing level for the `Item`.

    ======================  ========================================================
    **Parameter**            **Description**
    ----------------------  --------------------------------------------------------
    ORG                     Sets the value to have organizational visibility and only
                            authenticated users within the GIS can see/use the item.
    ----------------------  --------------------------------------------------------
    PRIVATE                 Sets the item's sharing level to hidden/private and only
                            the owner of the item can see that item.
    ----------------------  --------------------------------------------------------
    EVERYONE                Make the item public and anyone can use it.
    ======================  ========================================================
    """

    ORG = "ORGANIZATION"
    PRIVATE = "PRIVATE"
    EVERYONE = "EVERYONE"


class SharingGroupManager:
    """
    This class controls the :class:`~arcgis.gis.Group` sharing for a specific
    :class:`~arcgis.gis.Item`.

    ================  ===============================================================
    **Parameter**      **Description**
    ----------------  ---------------------------------------------------------------
    sm                Required
                      :class:`~arcgis.gis._impl._content_manager.SharingManager`
                      object for a specific :class:`~arcgis.gis.Item`.
    ================  ===============================================================

    Objects of this class are not meant to be intialized
    directly, but rather accessed through the
    :attr:`~arcgis.gis._impl._content_manager.SharingManager.groups`
    property of an *item's* *SharingManager*.

    .. code-block:: python

        # Usage example:
        >>> from arcgis.gis import GIS
        >>> gis = GIS(profile="your_organization_profile")

        >>> org_item = gis.content.get("<item_id>")
        >>> item_sharing_mgr = org_item.sharing
        >>> item_grp_sharing_mgr = item_sharing_mgr.groups
        >>> item_grp_sharing_mgr

        <<item_id> SharingGroupManager>

        >>> type(item_grp_sharing_mgr)

        <class 'arcgis.gis._impl._content_manager.sharing.api.SharingGroupManager'>
    """

    __slots__ = ("_item", "_gis", "_session", "_sm")
    _item: arcgis.gis.Item
    _session: EsriSession
    _gis: arcgis.gis.GIS
    _sm: SharingManager

    # ---------------------------------------------------------------------
    def __init__(self, sm: SharingManager):
        """initializer"""
        self._item = sm._item
        self._gis = sm._gis
        self._session = sm._session
        self._sm = sm

    def __repr__(self) -> str:
        return f"< {self._item.id} SharingGroupManager >"

    def __str__(self) -> str:
        return self.__repr__()

    # ---------------------------------------------------------------------
    def add(self, group: arcgis.gis.Group | str) -> bool:
        """
        Shares an :class:`~arcgis.gis.Item` with the :class:`~arcgis.gis.Group`
        entered as the *group* argument.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        group             Required :class:`~arcgis.gis.Group` object to share the *item*
                          with.
        ================  ===============================================================

        :returns:
            Boolean value indicating the status of the operation.

        .. code-block:: python

            # Usage example:
            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_organization_profile")

            >>> org_item = gis.content.get("<item_id>")
            >>> org_group = gis.groups.search("Storm Data Group")[0]

            >>> item_sharing_mgr = org_item.sharing
            >>> item_grp_sharing_mgr = item_sharing_mgr.groups
            >>> item_grp_sharing_mgr.list()
            []

            >>> item_grp_sharing_mgr.add(group=org_group)
            True

            >>> item_grp_sharing_mgr.list()
            [<Group title:"Storm Data Group" owner:web_gis_user1>]
        """
        g: str | arcgis.gis.Group | None = None
        g = [grp.id for grp in self.list()]
        do_update = False
        if hasattr(group, "id") and not getattr(group, "id") in g:
            g.append(getattr(group, "id"))
            groups: str = ",".join(g)
            do_update = True
        elif isinstance(group, str) and not group in g:
            g.append(group)
            groups: str = ",".join(g)
            do_update = True
        if do_update:
            resp = self._sm._share(level=self._sm.sharing_level, groups=groups)
            if (
                "notSharedWith" in resp["results"][0]
                and len(resp["results"][0]["notSharedWith"]) > 0
            ):
                # successfully sent the request, but the group was not shared with
                return False
            return True
        return False

    # ---------------------------------------------------------------------
    def remove(self, group) -> bool:
        """Removes the :class:`item <arcgis.gis.Item>` from the list of
        *items* shared with the :class:`~arcgis.gis.Group` entered as the
        *group* argument.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        group             Required :class:`~arcgis.gis.Group` object with which the
                          *item* will no longer be shared.
        ================  ===============================================================

        :returns:
            Boolean value indicating the status of the operation.
        """
        g: str | arcgis.gis.Group | None = None
        g = [grp.id for grp in self.list()]
        do_update = False
        if hasattr(group, "id"):
            group = getattr(group, "id")
        if isinstance(group, str) and group in g:
            g.pop(g.index(group))
            groups: str = ",".join(g)
            do_update = True
        if do_update:
            self._sm._unshare(groups=group)
            self._sm._share(level=self._sm.sharing_level, groups=groups)
            return True
        return False

    # ---------------------------------------------------------------------
    @property
    def _groups(self) -> list[str]:
        """private method to get the groups shared with a given item."""
        itemid: str = self._item.id
        params: dict[str, Any] = {
            "f": "json",
            "items": itemid,
        }
        url: str = f"{self._gis._portal.resturl}content/itemsgroups"
        resp: requests.Response = self._session.get(url=url, params=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return list(data.keys())

    # ---------------------------------------------------------------------
    def list(self) -> list[arcgis.gis.Group]:
        """
        Lists all the :class:`groups <arcgis.gis.Group>` that the *item* is
        shared with.

        :returns:
            list[:class:`~arcgis.gis.Group`]
            A Python list of *group* objects.
        """
        return [arcgis.gis.Group(gis=self._gis, groupid=grp) for grp in self._groups]


class SharingManager:
    """
    Manages the sharing operations for an :class:`~arcgis.gis.Item`.

    ================  ===============================================================
    **Parameter**      **Description**
    ----------------  ---------------------------------------------------------------
    item              Required Item. The item to manage the sharing on.
    ----------------  ---------------------------------------------------------------
    gis               Optional GIS. The GIS object to the Item.
    ================  ===============================================================

    This class is not meant to be initialized directly. An instance of a
    *SharingManager* is available through the :attr:`~arcgis.gis.Item.sharing`
    property of an *item*.

    .. code-block:: python

        # Usage example:
        >>> gis = GIS(profile="your_organization_profile", verify_cert=False)

        >>> test_item = gis.content.get("4976ad...b9583e")
        >>> sharing_mgr = test_item.sharing

        < "4976ad...b9583e" SharingManager >

        >>> type(sharing_mgr)

        <class 'arcgis.gis._impl._content_manager.sharing.api.SharingManager'>
    """

    __slots__ = ("_item", "_gis", "_session", "_sgm")

    def __init__(
        self,
        item: arcgis.gis.Item,
        *,
        gis: arcgis.gis.GIS | EsriSession | None = None,
    ):
        self._item: arcgis.gis.Item | None = None
        self._gis: arcgis.gis.GIS = None
        self._session: EsriSession | None = None
        self._sgm: SharingGroupManager | None = None

        if isinstance(item, arcgis.gis.Item):
            self._item = item
        else:
            raise ValueError("`item` must be an `Item` object.")
        if isinstance(gis, arcgis.gis.GIS):
            self._session = gis.session
            self._gis = gis
        elif isinstance(gis, EsriSession):
            self._session = gis
            self._gis = item._gis
        elif gis and not isinstance(gis, (EsriSession, arcgis.gis.GIS)):
            raise ValueError("`gis` must be a EsriSession of GIS object.")
        else:
            self._gis = item._gis
            self._session = item._gis.session

    def __repr__(self) -> str:
        return f"< {self._item.id} SharingManager >"

    def __str__(self) -> str:
        return self.__repr__()

    def _share(
        self,
        level: SharingLevel,
        groups: list[arcgis.gis.Group] | str | None = None,
    ) -> dict[str, Any]:
        """
        The share operation shares an item with a public or organization
        sharing level with groups either owned or administered by the user
        performing the request.

        ======================  ========================================================
        **Parameter**            **Description**
        ----------------------  --------------------------------------------------------
        level                   Required SharingLevel. Sets the current state of the item.
        ----------------------  --------------------------------------------------------
        groups                  Optional list[Group]. The individual groups to share
                                with. If the value is set to an empty string, `""` the
                                groups will be unshared.
        ======================  ========================================================
        """
        # if not in org use different url

        if self._gis.users.get(self._item.owner, outside_org=False):
            url: str = "{resturl}content/users/{owner}/shareItems".format(
                resturl=self._gis._portal.resturl, owner=self._item.owner
            )
        else:
            url: str = "{resturl}content/items/{itemid}/share".format(
                resturl=self._gis._portal.resturl, itemid=self._item.itemid
            )

        params: dict[str, Any] = {
            "f": "json",
            "items": self._item.id,
        }
        if level == SharingLevel.ORG:
            params["org"] = True
            params["everyone"] = False
            params["confirmItemControl"] = True
        elif level == SharingLevel.PRIVATE:
            params["org"] = False
            params["everyone"] = False
            params["confirmItemControl"] = True
        elif level == SharingLevel.EVERYONE:
            params["org"] = False
            params["everyone"] = True
            params["confirmItemControl"] = True

        if groups == "" or groups == []:
            params["groups"] = ""
        elif groups is None:
            params["groups"] = ",".join(self.groups._groups)
        elif isinstance(groups, str):
            params["groups"] = groups
        else:
            groups = ""

        params = {
            k: (json.dumps(v) if isinstance(v, bool) else v)
            for (k, v) in params.items()
        }
        resp: requests.Response = self._session.post(url=url, data=params)
        resp.raise_for_status()
        self._item._hydrated = False
        data: dict[str, Any] = resp.json()
        return data

    def _unshare(
        self,
        groups: list[str] | str | None = None,
    ) -> dict[str, Any]:
        """
        The share operation shares an item with a public or organization
        sharing level with groups either owned or administered by the user
        performing the request.

        ======================  ========================================================
        **Parameter**            **Description**
        ----------------------  --------------------------------------------------------
        groups                  Optional list[Group]. The individual groups to share
                                with. If the value is set to an empty string, `""` the
                                groups will be unshared.
        ======================  ========================================================
        """
        # if not in org use different url

        if self._gis.users.get(self._item.owner, outside_org=False):
            url: str = "{resturl}content/users/{owner}/unshareItems".format(
                resturl=self._gis._portal.resturl, owner=self._item.owner
            )
        else:
            url: str = "{resturl}content/items/{itemid}/unshare".format(
                resturl=self._gis._portal.resturl, itemid=self._item.itemid
            )

        params: dict[str, Any] = {
            "f": "json",
            "items": self._item.id,
            "groups": "",
        }

        if groups == "" or groups == []:
            params["groups"] = ""
        elif groups is None:
            return
        elif isinstance(groups, list):
            groups = ",".join(groups)
        params["groups"] = groups
        resp: requests.Response = self._session.post(url=url, data=params)
        resp.raise_for_status()
        self._item._hydrated = False
        data: dict[str, Any] = resp.json()
        return data

    @property
    def groups(self) -> SharingGroupManager:
        """
        Provides access to a
        :class:`~arcgis.gis._impl._content_manager.SharingGroupManager`
        object to manage the *group* sharing properties of the
        :class:`~arcgis.gis.Item` from which the
        :class:`~arcgis.gis._impl._content_manager.SharingManager` was
        initialized

        :returns:
            :class:`~arcgis.gis._impl._content_manager.SharingGroupManager`
            object
        """
        if self._sgm is None:
            self._sgm = SharingGroupManager(sm=self)
        return self._sgm

    # ----------------------------------------------------------------------
    @property
    def sharing_level(self) -> SharingLevel:
        """
        Gets or sets the sharing level of the :class:`~arcgis.gis.Item`.

        :returns:
            :class:`~arcgis.gis._impl._content_manager.SharingLevel`
            enumeration instance.

        .. code-block:: python

            # Usage example: Setting the sharing level to organization
            >>> from arcgis.gis import GIS
            >>> from arcgis.gis._impl._content_manager import SharingLevel

            >>> data_item = gis.content.search(query="Hurricanes 2022")
            >>> sharing_mgr = data_item.sharing
            >>> sharing_mgr.sharing_level

            <SharingLevel.PRIVATE: 'PRIVATE'>

            >>> sharing_mgr.sharing_level = SharingLevel.ORG

            >>> sharing_mgr.sharing_level
            <SharingLevel.ORG: 'ORGANIZATION'>

            >>> type(sharing_mgr.sharing_level)
            <enum 'SharingLevel'>
        """
        return self.shared_with["level"]

    # ----------------------------------------------------------------------
    @sharing_level.setter
    def sharing_level(self, value: Union[SharingLevel, str]) -> None:
        """
        Gets or sets the sharing level of the :class:`~arcgis.gis.Item`.

        :returns:
            :class:`~arcgis.gis._impl._content_manager.SharingLevel` enumeration
            instance.
        """
        if isinstance(value, str):
            for level in SharingLevel:
                name = level.name.lower()
                val = str(level.value).lower()
                if name == value.lower() or val == value.lower():
                    value = level
                    break
        assert isinstance(value, SharingLevel)
        self._share(level=value)
        self._item._hydrated = False
        self._item._hydrate()

    # ----------------------------------------------------------------------
    @property
    def shared_with(self) -> dict[str, Any]:
        """
        The ``shared_with`` property reveals the sharing status with
        :class:`groups <arcgis.gis.Group>` and the sharing level
        of the :class:`~arcgis.gis.Item`. An *item* can be private to its owner,
        or shared in one or more of the following ways:

        * to a specified list of groups
        * to all members in the organization
        * to everyone (including anonymous users), aka publicly

        :returns:
            dict[str,Any]. A dictionary describing the sharing level.

        .. code-block:: python

            # Usage example: Item only visible to the owner.

            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_organization_profile")

            >>> data_item = gis.content.get("269029...2c482e")
            >>> data_item.sharing.shared_with

            {'groups': [], 'level': <SharingLevel.PRIVATE: 'PRIVATE'>}

        """
        sw: dict = self._shared_with
        results: dict[str, Any] = {"groups": sw.get("groups", [])}
        if sw["everyone"]:
            results["level"] = SharingLevel.EVERYONE
        elif sw["everyone"] == False and sw["org"]:
            results["level"] = SharingLevel.ORG
        else:
            results["level"] = SharingLevel.PRIVATE
        return results

    # ----------------------------------------------------------------------
    @property
    def _shared_with(self) -> dict[str, Any]:
        """
        The ``shared_with`` property reveals the privacy or sharing status of the current item. An item can be private
        or shared with one or more of the following:
            1. A specified list of groups
            2. All members in the organization
            3. Everyone (including anonymous users).

        .. note::
            If the return is False for `org`, `everyone` and contains an empty list of `groups`, then the
            item is private and visible only to the owner.

        :return:
            A Dictionary in the following format:
            {
            'groups': [],  # one or more Group objects
            'everyone': True | False,
            'org': True | False
            }
        """
        ret_dict: dict[str, Any] = {
            "everyone": False,
            "org": False,
            "groups": [arcgis.gis.Group(self._gis, grp) for grp in self.groups._groups],
        }
        sharing_info: str = self._item.access
        if sharing_info == "public":
            ret_dict["everyone"] = True
            ret_dict["org"] = True

        if sharing_info == "org":
            ret_dict["org"] = True

        return ret_dict
