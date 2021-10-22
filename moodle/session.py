import base64
import hashlib
import html
import re
import secrets
import sys
from typing import Any, Iterable, Optional

from httpx import AsyncClient, Client

from moodle.constants import LoginType
from moodle.util import flatten

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class MoodleException(Exception):
    pass


class WebserviceException(MoodleException):
    def __init__(
        self, exception: str, errorcode: str, message: str, debuginfo: Optional[str]
    ) -> None:
        super().__init__(exception, errorcode, message, debuginfo)
        self.exception = exception
        self.errorcode = errorcode
        self.message = message
        self.debuginfo = debuginfo


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

    def login(
        self,
        username: str,
        password: str,
        service: str = "moodle_mobile_app",
    ) -> None:

        public_config = self.ajax(
            [{"methodname": "tool_mobile_get_public_config", "args": {}}]
        )[0]["data"]

        if public_config["typeoflogin"] == LoginType.LOGIN_VIA_APP:
            raise MoodleException("Login type currently not supported")

        redirect_page = self.post(
            self.get(  # type: ignore
                public_config["identityproviders"][0]["url"], follow_redirects=True
            ).url,
            data={
                "j_username": username,
                "j_password": password,
                "_eventId_proceed": "",
            },
        )

        # TODO use python html.parser
        formdata = re.search(
            r'<form action="(?P<form_submit_url>[^"]*)" method="post">'
            r'.*<input type="hidden" name="RelayState" value="(?P<RelayState>[^"]*)"/>'
            r'.*<input type="hidden" name="SAMLResponse" value="(?P<SAMLResponse>[^"]*)"/>',
            html.unescape(redirect_page.text),
            flags=re.MULTILINE | re.DOTALL,
        )

        if not formdata:
            raise MoodleException("Unable to parse login form")

        self.post(
            formdata["form_submit_url"],
            data=formdata.groupdict(),
            follow_redirects=True,
        )

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

        self.wstoken = wstoken


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

    async def login(
        self,
        username: str,
        password: str,
        service: str = "moodle_mobile_app",
    ) -> None:

        public_config = (
            await self.ajax(
                [{"methodname": "tool_mobile_get_public_config", "args": {}}]
            )
        )[0]["data"]

        if public_config["typeoflogin"] == LoginType.LOGIN_VIA_APP:
            raise MoodleException("Login type currently not supported")

        redirect_page = await self.post(
            (
                await self.get(  # type: ignore
                    public_config["identityproviders"][0]["url"], follow_redirects=True
                )
            ).url,
            data={
                "j_username": username,
                "j_password": password,
                "_eventId_proceed": "",
            },
        )

        # TODO use python html.parser
        formdata = re.search(
            r'<form action="(?P<form_submit_url>[^"]*)" method="post">'
            r'.*<input type="hidden" name="RelayState" value="(?P<RelayState>[^"]*)"/>'
            r'.*<input type="hidden" name="SAMLResponse" value="(?P<SAMLResponse>[^"]*)"/>',
            html.unescape(redirect_page.text),
            flags=re.MULTILINE | re.DOTALL,
        )

        if not formdata:
            raise MoodleException("Unable to parse login form")

        await self.post(
            formdata["form_submit_url"],
            data=formdata.groupdict(),
            follow_redirects=True,
        )

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

        self.wstoken = wstoken
