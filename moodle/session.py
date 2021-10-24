import logging
import sys
from typing import Any, Iterable

from httpx import AsyncClient, Client

from moodle.constants import LoginType
from moodle.contrib.identityproviders import IdentityProvider
from moodle.exceptions import MoodleException, WebserviceException
from moodle.util import flatten

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


logger = logging.getLogger(__name__)


class AjaxRequest(TypedDict):
    methodname: str
    args: Any


class MoodleClient(Client):
    def __init__(self, wwwroot: str, wstoken: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.wwwroot = wwwroot
        self.wstoken = wstoken

    def ajax(self, requests: Iterable[AjaxRequest]) -> Any:
        indexed_requests = [
            {"index": i, "methodname": req["methodname"], "args": req["args"]}
            for i, req in enumerate(requests)
        ]

        return self.post(
            f"{self.wwwroot}/lib/ajax/service.php", json=indexed_requests
        ).json()

    def webservice(self, wsfunction: str, data: dict = None) -> Any:
        if data is None:
            data = {}

        response = self.post(
            f"{self.wwwroot}/webservice/rest/server.php",
            data={
                **flatten(data),
                "moodlewsrestformat": "json",
                "wstoken": self.wstoken,
                "wsfunction": wsfunction,
            },
        )

        response_data = response.json()
        if response_data and "exception" in response_data:
            exception = response_data["exception"]
            errorcode = response_data["errorcode"]
            message = response_data["message"]
            debuginfo = response_data.get("debuginfo")
            raise WebserviceException(exception, errorcode, message, debuginfo)
        return response_data

    def get_token(
        self,
        username: str,
        password: str,
        service: str = "moodle_mobile_app",
    ) -> str:

        public_config = self.ajax(
            [{"methodname": "tool_mobile_get_public_config", "args": {}}]
        )[0]["data"]

        if public_config["typeoflogin"] == LoginType.LOGIN_VIA_APP:
            tokens = self.get(
                f"{self.wwwroot}/login/token.php",
                params={"username": username, "password": password, "service": service},
            )
            wstoken = tokens.json()["token"]
            if not isinstance(wstoken, str):
                raise MoodleException("Invalid wstoken returned")
            return wstoken

        for idp_info in public_config["identityproviders"]:
            for idp in IdentityProvider.providers:
                if not idp.is_responsible(idp_info):
                    continue
                try:
                    return idp().sync_get_token(
                        self.wwwroot,
                        username,
                        password,
                        service,
                        idp_info,
                        public_config,
                    )
                except MoodleException:
                    logger.warning(
                        f"Error whilst trying to authenticate with {idp}", exc_info=True
                    )

        raise MoodleException("No identityprovider worked")


# Alias for backwards compatibility - will be removed
MoodleSession = MoodleClient


class AsyncMoodleClient(AsyncClient):
    def __init__(self, wwwroot: str, wstoken: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.wwwroot = wwwroot
        self.wstoken = wstoken

    async def ajax(self, requests: Iterable[AjaxRequest]) -> Any:
        indexed_requests = [
            {"index": i, "methodname": req["methodname"], "args": req["args"]}
            for i, req in enumerate(requests)
        ]

        response = await self.post(
            f"{self.wwwroot}/lib/ajax/service.php", json=indexed_requests
        )
        return response.json()

    async def webservice(self, wsfunction: str, data: dict = None) -> Any:
        if data is None:
            data = {}

        response = await self.post(
            f"{self.wwwroot}/webservice/rest/server.php",
            data={
                **flatten(data),
                "moodlewsrestformat": "json",
                "wstoken": self.wstoken,
                "wsfunction": wsfunction,
            },
        )

        response_data = response.json()
        if response_data and "exception" in response_data:
            exception = response_data["exception"]
            errorcode = response_data["errorcode"]
            message = response_data["message"]
            debuginfo = response_data.get("debuginfo")
            raise WebserviceException(exception, errorcode, message, debuginfo)

        return response_data

    async def get_token(
        self,
        username: str,
        password: str,
        service: str = "moodle_mobile_app",
    ) -> str:

        public_config = (
            await self.ajax(
                [{"methodname": "tool_mobile_get_public_config", "args": {}}]
            )
        )[0]["data"]

        if public_config["typeoflogin"] == LoginType.LOGIN_VIA_APP:
            tokens = await self.get(
                f"{self.wwwroot}/login/token.php",
                params={"username": username, "password": password, "service": service},
            )
            wstoken = tokens.json()["token"]
            if not isinstance(wstoken, str):
                raise MoodleException("Invalid wstoken returned")
            return wstoken

        for idp_info in public_config["identityproviders"]:
            for idp in IdentityProvider.providers:
                if not idp.is_responsible(idp_info):
                    continue
                try:
                    return idp().sync_get_token(
                        self.wwwroot,
                        username,
                        password,
                        service,
                        idp_info,
                        public_config,
                    )
                except MoodleException:
                    logger.warning(
                        f"Error whilst trying to authenticate with {idp}", exc_info=True
                    )

        raise MoodleException("No identityprovider worked")
