from __future__ import annotations
from arcgis.auth import EsriSession
from arcgis.auth.tools import LazyLoader
from typing import Any, Generator
import os
import json
import logging
import requests
import urllib.parse
from functools import lru_cache

_arcgis_gis = LazyLoader("arcgis.gis")
_log = logging.getLogger()


@lru_cache(maxsize=255)
def _get_org_id(url: str, session: EsriSession, return_type: str = "url_key") -> str:
    parsed: urllib.parse.ParseResult = urllib.parse.urlparse(url)
    parsed_url: str = f"{parsed.scheme}://{parsed.netloc}/sharing/rest/portals/self"
    params: dict[str, Any] = {
        "f": "json",
    }
    resp: requests.Response = session.get(url=parsed_url, params=params)
    resp.raise_for_status()
    if return_type == "url_key":
        return resp.json().get("urlKey")
    else:
        return resp.json().get("id")


class PartneredCollaboration:
    """Represents a single `partnered collaboration
    <https://doc.arcgis.com/en/arcgis-online/administer/understand-collaborations.htm>`_
    for the organization."""

    _url: str
    _gis: _arcgis_gis.GIS
    _session: EsriSession
    _properties: dict[str, Any] | None = None

    def __init__(self, url: str, gis: _arcgis_gis.GIS) -> None:
        self._gis: _arcgis_gis.GIS = gis
        self._url: str = url
        self._session = gis.session

    @property
    def url(self) -> str:
        return self._url

    @property
    def session(self) -> EsriSession:
        """Returns an :class:`~arcgis.auth.api.EsriSession` object."""
        return self._session

    @property
    def properties(self) -> dict[str, Any]:
        """Returns a dictionary indicating various attributes of the
        *collaboration* from the perspective of the organization.

        .. code-block:: python

            #Usage Example
            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> partner_collab_mgr = gis.admin.partnered_collaboration

            >>> partner_collab = next(partner_collab_mgr.collaboration(include_hub=False))
            >>> partner_collab.properties

            {'from': {'orgId': 'JXM4...',
                      'usersAccess': True,
                      'established': 1706041472000,
                      'hub': False,
                      'state': 'active'},
             'to': {'orgId': 'SPK1...',
                    'usersAccess': True,
                    'established': 1706218200000,
                    'name': 'My Account',
                    'hub': False,
                    'state': 'active'}}

        """
        if self._properties is None:
            url: str = f"{self.url}"
            params: dict[str, Any] = {
                "f": "json",
            }
            resp: requests.Response = self.session.get(url=url, params=params)
            resp.raise_for_status()
            self._properties = resp.json()
        return self._properties

    @property
    def suspend(self) -> bool:
        """
        Gets/sets the state of the collaboration.  To suspend collaboration, set
        the property to `True`

        :returns: Boolean. `False` means the collaboration is not suspended.
             `True` means the partnership is suspended.

        .. code-block:: python

            # Usage Example: Suspend the collaboration
            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> partner_collab_mgr = gis.admin.partnered_collaboration
            >>> partner_collab = next(partner_collab_mgr.collaborations())

            # Get current suspension status
            >>> partner_collab.suspend
            False

            # Suspend the collaboration
            >>> partner_collab.suspend = True
        """
        return self.properties["to"]["state"] == "suspended"

    @suspend.setter
    def suspend(self, value: bool) -> None:
        state = self.properties["to"]["state"] == "suspended"
        if state == value:
            return
        else:
            if value == False:
                state = "active"
            elif value == True:
                state = "suspended"
            url: str = f"{self.url}/update"
            orgid: str = self.properties["to"]["orgId"]
            params: dict[str, Any] = {
                "f": "json",
                "orgId": orgid,
                "state": state,
            }
            self.session.post(url=url, data=params)
            self._properties = None

    @property
    def groups(self) -> Generator[_arcgis_gis.Group]:
        """Returns a generator for accessing the
        :class:`groups <arcgis.gis.Group>` who have members in either of the
        organizations in a *partnered collaboration*."""
        to_id: str = self.properties["to"]["orgId"]
        from_id: str = self.properties["from"]["orgId"]
        for group in self._gis.groups.search(f"orgid:{from_id} memberorgids:{to_id}"):
            yield group

    @property
    def search_users(self) -> bool:
        """Property used to get or set the ability for collaboration members
        to search for :class:`users <arcgis.gis.User>` with public or organization
        access profiles within collaborating organizations.

        .. code-block:: python

            # Usage Example:
            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> partner_collab = next(gis.admin.partnered_collaboration.collaborations())
            >>> parnter_collab.search_users = True
        """
        return self.properties["to"]["usersAccess"]

    @search_users.setter
    def search_users(self, value: bool) -> None:
        if self.properties["from"]["usersAccess"] == value:
            return
        if self.properties["to"]["established"] == -1:
            raise ValueError(
                "You cannot change the `search_users` until the collaboration is accepted."
            )
        url: str = f"{self.url}/update"
        orgid: str = self.properties["from"]["orgId"]
        params: dict[str, Any] = {
            "f": "json",
            "orgId": orgid,
            "searchUsers": json.dumps(value),
        }
        self.session.post(url=url, data=params)
        self._properties = None

    def delete(self, message: str | None = None) -> bool:
        """This operation ends the partnered collaboration

        =============     ================================================
        **Parameter**     **Description**
        -------------     ------------------------------------------------
        message           Optional String. Text to appear in the email
                          notification to the collaboration partner
                          administrators and coordinators when ending the
                          collaboration.
        =============     ================================================
        """
        url: str = f"{self.url}/delete"
        params: dict[str, Any] = {
            "f": "json",
            "message": message,
            "async": json.dumps(True),
        }
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        return resp.json().get("success", False)

    @property
    def is_active(self) -> bool:
        """Checks whether the collaboration is active between both
        collaborating organizations."""
        self._properties = None
        return (
            self.properties["from"]["established"] != -1
            and self.properties["to"]["established"] != -1
        )

    @property
    def is_accepted(self) -> bool:
        """Checks whether a partnered collaboration has been accepted."""
        self._properties = None
        return self.properties["from"]["established"] != -1

    def accept(self, user_access: bool) -> bool:
        """Accepts the invitation and establishes a partnered collaboration.

        =================     =============================================
        **Parameter**         **Description**
        -----------------     ---------------------------------------------
        user_access           Required Boolean. Indicates whether the
                              :class:`users <arcgis.gis.User>` within the
                              partnered organization can search for users
                              within the accepting organization.
        =================     =============================================
        """
        if self.is_accepted == False:
            params: dict = {
                "f": "json",
                "orgId": self.properties["to"]["orgId"],
                "searchUsers": json.dumps(user_access),
            }
            url: str = os.path.dirname(self.url).replace(
                "/trustedOrgs", "/addTrustedOrg"
            )
            resp: requests.Response = self._session.post(url=url, data=params)
            data: dict = resp.json()
            self._properties = None
            return self.is_accepted

        else:
            _log.warning("Collaboration already established, skipping")
            return False


class PartneredCollabManager:
    """
    A class for managing *partnered collaborations*, which are utilized
    to seamlessly share content with other ArcGIS Online organizations. When two
    or more organizations create a partnered collaboration, they enter a
    partnership that allows their members to work closely with each other
    and each other's content using :class:`groups <arcgis.gis.Group>`. For
    further details see
    `Understanding collaborations <https://doc.arcgis.com/en/arcgis-online/administer/understand-collaborations.htm#ESRI_SECTION1_1FA3EDFCBDBE432AA9EE9B0FB62AB5F8>`_.
    For detailed workflow example, please read `The Power of Partnered
    Collaboration <https://www.esri.com/arcgis-blog/products/arcgis-online/administration/the-power-of-partnered-collaboration-in-arcgis-online/?rsource=https%3A%2F%2Flinks.esri.com%2Fagol-help%2Fblog%2Fpartnered-collaboration>`_.

    A user **must** have administrator privileges to access this object.
    Instances are not meant to be created directly, but rather returned
    using the :attr:`~arcgis.gis.admin.partnered_colloboration`
    property of an :class:`ArcGIS Online Administrator <arcgis.gis.admin.AGOLAdminManager>`
    object.

    .. code-block:: python

        # Usage Example:
        >>> from arcgis.gis import GIS
        >>> gis = GIS(profile="your_online_admin_profile")

        >>> agol_mgr = gis.admin
        >>> partnered_collab_mgr = agol_mgr.partnered_colloboration
        >>> partnered_collab_mgr

        <arcgis.gis.admin._partnercollab.PartneredCollabManager object at <memory address>>
    """

    _url: str
    _gis: _arcgis_gis.GIS
    _session: EsriSession
    _properties: dict[str, Any] | None = None

    def __init__(self, url: str, gis: _arcgis_gis.GIS) -> None:
        if gis._is_arcgisonline == False:
            raise ValueError("The `GIS` must be an ArcGIS Online Organization")
        url = url.split("/sharing/rest")[0] + "/sharing/rest/portals/self/trustedOrgs"
        self._gis: _arcgis_gis.GIS = gis

        self._url: str = url
        self._session = gis.session

    @property
    def url(self) -> str:
        """returns the URL of the endpoint"""
        return self._url

    @property
    def session(self) -> EsriSession:
        """returns the current EsriSession"""
        return self._session

    @property
    def properties(self) -> dict[str, Any]:
        """
        Returns various attributes about partnered collaborations of the
        current organzations.

        .. note::
            ArcGIS Hub is implemented with a similar mechanism to Partnered
            Collaborations. Properties about the relationship with ArcGIS
            Hub is returned in this dictionary as well.

        .. code-block:: python

            # Usage Example: Organization that initiated a Partner Collaboration
            #                and uses Hub Basic

            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> collab_mgr = gis.admin.partnered_collaboration
            >>> collab_mgr.properties

            {'total': 2,
             'start': 1,
             'num': 10,
             'nextStart': -1,
             'trustedOrgs': [{'from': {'orgId': 'JQx...',
                                      'usersAccess': True,
                                      'established': 1566327495000,
                                      'hub': True,
                                      'state': 'active'},
                             'to': {'orgId': 'aee...',
                                    'usersAccess': True,
                                    'established': 1566327495000,
                                    'name': 'Hub Community',
                                    'hub': True,
                                    'state': 'active'}},
                            {'from': {'orgId': 'JQx...',
                                      'usersAccess': False,
                                      'established': 1705623169000,
                                      'hub': False,
                                      'state': 'active'},
                             'to': {'orgId': 'KRW...',
                                    'usersAccess': False,
                                    'established': -1,
                                    'name': 'Organization for Demo',
                                    'hub': False,
                                    'state': 'active'}}]}


        :return: dict
        """
        if self._properties is None:
            url: str = f"{self.url}"
            params: dict[str, Any] = {
                "f": "json",
            }
            resp: requests.Response = self.session.get(url=url, params=params)
            resp.raise_for_status()
            self._properties = resp.json()
        return self._properties

    @property
    def limits(self) -> dict[str, Any]:
        """Returns the Organization's limits of creating collaborations"""
        url: str = f"{self.url.replace('/trustedOrgs', '')}/limits"
        params: dict[str, Any] = {
            "f": "json",
            "limitsType": "Collaboration",
            "limitName": "MaxTrustedOrgs",
        }
        resp: requests.Response = self.session.get(url=url, params=params)
        resp.raise_for_status()
        return resp.json()

    def collaborations(
        self, include_hub: bool = False
    ) -> Generator[PartneredCollaboration]:
        """Returns a Python generator that can retrieve all the *partnered
        collaborations* for the current organization.

        ===============     ====================================================
        **Parameter**       **Description**
        ---------------     ----------------------------------------------------
        include_hub         Optional Boolean. Indicates whether *collaborations*
                            implemented through ArcGIS Hub should be included in
                            the generator returned by this method. Default value
                            is `False`.
        ===============     ====================================================

        .. code-block:: python

            # Usage Example:
            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> partner_collab_mgr = gis.admin.partnered_collaboration
            >>> partner_collab_gen = partner_collab_mgr.collaborations()

            >>> partner_collab_obj = next(partner_collab_gen)
            >>> partner_collab_obj

            <arcgis.gis.admin._partnercollab.PartneredCollaboration object at 0x...>
        """
        url: str = f"{self.url}"
        params = {
            "f": "json",
            "num": 100,
            "start": 1,
        }
        resp: requests.Response = self.session.get(url=url, params=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        for org in data["trustedOrgs"]:
            orgid: str = org["to"]["orgId"]
            if include_hub:
                yield PartneredCollaboration(url=f"{url}/{orgid}", gis=self._gis)
            elif include_hub == False and org["from"]["hub"] == False:
                yield PartneredCollaboration(url=f"{url}/{orgid}", gis=self._gis)
        while data.get("nextStart", -1) != -1:
            resp: requests.Response = self.session.get(url=url, params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            for org in data["trustedOrgs"]:
                orgid: str = org["to"]["orgId"]
                if include_hub:
                    yield PartneredCollaboration(url=f"{url}/{orgid}", gis=self._gis)
                elif include_hub == False and org["from"]["hub"] == False:
                    yield PartneredCollaboration(url=f"{url}/{orgid}", gis=self._gis)

    # ---------------------------------------------------------------------
    @property
    def coordinators(self) -> Generator[_arcgis_gis.User]:
        """returns a Python generator object that can be used to get
        the org :class:`users <arcgis.gis.User>` assigned as coordinators for
        partner collaborations. This property also serves as the way to set
        additional coordinators by assigning a list of :class:`~arcgis.gis.User`
        objects.

        .. note::
            In order to serve as *coordinators*, users must be either an
            *Administrator* in the org or assigned the *Facilitator* role. In
            addition, users must have their profile access set to *Organization*
            or *Everyone*.
            See `Manage collaboration coordinators <https://doc.arcgis.com/en/arcgis-online/administer/manage-partnered-collaborations.htm#ESRI_SECTION1_DE8B1894C2914A26AF5AD3D822CC3524>`_
            for details.

        .. code-block:: python

            #Usage example to set coordinators

            >>> from arcgis.gis import GIS
            >>> gis = GIS(profile="your_online_admin_profile")

            >>> partner_clb_mgr = gis.admin.partnered_collaboration

            >>> new_coordinators = [usr for usr in gis.users.search("*")
                                    if usr.role == "org_admin"][:3]
            >>> partner_clb_mgr.coordinators = new_coordinators

            >>> for clb_coordinator in partner_clb_mgr.coordinators:
                    print(f"{clb_coordinator.username:25}{type(clb_coordinator)}")

            Collab_Coordinator1      <class 'arcgis.gis.User'>
            Org_Admin_Overall        <class 'arcgis.gis.User'>
        """
        params: dict[str, Any] = {
            "f": "json",
            "num": 100,
            "collaborators": "false",
            "type": "collaboration",
            "start": 1,
        }
        url: str = self.url.replace("/trustedOrgs", "/contacts")
        resp: requests.Response = self.session.get(url=url, params=params)
        data: dict = resp.json()
        for user in data.get("users", []):
            yield _arcgis_gis.User(gis=self._gis, username=user["username"])
        while data.get("nextStart", -1) > -1:
            params["start"] = data.get("nextStart", -1)
            url: str = self.url.replace("/trustedOrgs", "/contacts")
            resp: requests.Response = self.session.get(url=url, params=params)
            data: dict = resp.json()
            for user in data.get("users", []):
                yield _arcgis_gis.User(gis=self._gis, username=user["username"])

    # ---------------------------------------------------------------------
    @coordinators.setter
    def coordinators(self, value: list[_arcgis_gis.User]) -> None:
        if value is None:
            value = []
        users: list[str] = [user.username for user in value]
        params: dict[str, Any] = {
            "f": "json",
            "users": ",".join(users),
            "type": "collaboration",
        }

        url: str = f"{self.url.replace('/trustedOrgs', '/updateContacts')}"
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        data: dict = resp.json()
        if not "success" in data:
            raise Exception(f"{data}")

    # ---------------------------------------------------------------------
    def create(
        self,
        message: str,
        org_url: str | None = None,
        org_id: str | None = None,
        search_users: bool = False,
    ) -> bool:
        """Creates a partnered collaboration on the ArcGIS Online site.

        ================  ===============================================================
        **Parameter**      **Description**
        ----------------  ---------------------------------------------------------------
        message           Required String. The message to send to the organization about
        ----------------  ---------------------------------------------------------------
        org_url           Required String. The url of the organization to partner with.
        ----------------  ---------------------------------------------------------------
        org_id            Optional String. The ID of the organization to partner with.
        ----------------  ---------------------------------------------------------------
        search_users      Optional boolean. Allows partnered organization members to
                          search for :class:`users <arcgis.gis.User>` within your
                          organization.
        ================  ===============================================================

        :return: bool
        """
        if org_id is None and org_url is None:
            raise ValueError(
                "Please provide an `org_id` or `org_url` argument in order to create a new partnered collaboration."
            )
        url_key: str = _get_org_id(url=org_url, session=EsriSession())
        url: str = f"{self.url.replace('/trustedOrgs', '')}/addTrustedOrg"
        params: dict[str, Any] = {
            "orgId": org_id,
            "urlKey": url_key,
            "message": message,
            "searchUsers": json.dumps(search_users),
            "f": "json",
        }
        if params["orgId"] is None:
            del params["orgId"]
        if params["urlKey"] is None:
            del params["urlKey"]
        resp: requests.Response = self.session.post(url=url, data=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data.get("success", False):
            return True
        else:
            return data
