import base64
import hashlib
import logging
import secrets
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
            token = tokens.json()["token"]
            if not isinstance(token, str):
                raise MoodleException("Invalid wstoken returned")
            return token

        idp_type, idp_info = IdentityProvider.get_responsible_idp(
            public_config["identityproviders"]
        )
        idp_type(
            self.wwwroot,
            username,
            password,
            idp_info,
        ).sync_login(self)

        passport = secrets.token_urlsafe()

        token_response = self.post(
            public_config["launchurl"],
            params={"service": service, "passport": passport},
            follow_redirects=False,
        )

        token = token_response.headers["Location"][len("moodlemobile://token=") :]
        signature, wstoken, *_ = base64.b64decode(token).decode().split(":::")

        expected_signature = hashlib.md5(
            (public_config["wwwroot"] + passport).encode()
        ).hexdigest()

        if signature != expected_signature:
            raise MoodleException("Invalid signature")

        return wstoken


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
            token = tokens.json()["token"]
            if not isinstance(token, str):
                raise MoodleException("Invalid wstoken returned")
            return token

        idp_type, idp_info = IdentityProvider.get_responsible_idp(
            public_config["identityproviders"]
        )
        await idp_type(
            self.wwwroot,
            username,
            password,
            idp_info,
        ).async_login(self)

        passport = secrets.token_urlsafe()

        token_response = await self.post(
            public_config["launchurl"],
            params={"service": service, "passport": passport},
            follow_redirects=False,
        )

        token = token_response.headers["Location"][len("moodlemobile://token=") :]
        signature, wstoken, *_ = base64.b64decode(token).decode().split(":::")

        expected_signature = hashlib.md5(
            (public_config["wwwroot"] + passport).encode()
        ).hexdigest()

        if signature != expected_signature:
            raise MoodleException("Invalid signature")

        return wstoken
