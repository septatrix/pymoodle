import base64
import hashlib
import html
import json
import re
import secrets
from typing import Any, Container, Iterable, Mapping, Text, Tuple, TypedDict, Union

from requests.adapters import BaseAdapter
from requests.models import PreparedRequest, Response
from requests.sessions import Session

from moodle.constants import LoginType
from moodle.util import flatten


class MoodleException(Exception):
    pass


class MoodleAdapter(BaseAdapter):
    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Union[float, Tuple[float, float], Tuple[float, None]] = None,
        verify: Union[bool, str] = True,
        cert: Union[Union[bytes, Text], Container[Union[bytes, Text]]] = None,
        proxies: Mapping[str, str] = None,
    ) -> Response:
        response = Response()
        response.url = request.url or ""
        response.status_code = 200
        response.reason = "OK"

        return response

    def close(self) -> None:
        return


class AjaxRequest(TypedDict):
    methodname: str
    args: Any


class MoodleSession(Session):
    def __init__(self, wwwroot: str, wstoken: str) -> None:
        super().__init__()
        self.wwwroot = wwwroot
        self.wstoken = wstoken

    def ajax(self, requests: Iterable[AjaxRequest]) -> Any:
        indexed_requests = [
            {"index": i, "methodname": req["methodname"], "args": req["args"]}
            for i, req in enumerate(requests)
        ]

        return self.post(
            f"{self.wwwroot}/lib/ajax/service.php",
            data=json.dumps(indexed_requests),
        ).json()

    def webservice(self, wsfunction: str, data: dict = None) -> Any:
        if data is None:
            data = {}

        data.update()
        response = self.post(
            f"{self.wwwroot}/webservice/rest/server.php",
            data={
                "moodlewsrestformat": "json",
                "wstoken": self.wstoken,
                "wsfunction": wsfunction,
                **flatten(data),
            },
        )

        response_data = response.json()
        if response_data and "exception" in response_data:
            raise MoodleException(response_data)
        return response_data

    @classmethod
    def get_token(
        cls,
        wwwroot: str,
        username: str,
        password: str,
        service: str = "moodle_mobile_app",
    ) -> str:
        session = cls(wwwroot, "")
        session.mount("moodlemobile://", MoodleAdapter())

        public_config = session.ajax(
            [{"methodname": "tool_mobile_get_public_config", "args": {}}]
        )[0]["data"]

        if public_config["typeoflogin"] == LoginType.LOGIN_VIA_APP:
            raise MoodleException("Login type currently not supported")

        redirect_page = session.post(
            session.get(public_config["identityproviders"][0]["url"]).url,
            data={
                "j_username": username,
                "j_password": password,
                "_eventId_proceed": "",
            },
        )

        formdata = re.search(
            r'<form action="(?P<form_submit_url>[^"]*)" method="post">'
            r'.*<input type="hidden" name="RelayState" value="(?P<RelayState>[^"]*)"/>'
            r'.*<input type="hidden" name="SAMLResponse" value="(?P<SAMLResponse>[^"]*)"/>',
            html.unescape(redirect_page.text),
            flags=re.MULTILINE | re.DOTALL,
        )

        if not formdata:
            raise MoodleException("Unable to parse login form")

        session.post(formdata["form_submit_url"], data=formdata.groupdict())

        passport = secrets.token_urlsafe()

        token_response = session.get(
            public_config["launchurl"],
            params={"service": service, "passport": passport},
        )

        token = token_response.url[len("moodlemobile://token=") :]
        signature, wstoken, *_ = base64.b64decode(token).decode().split(":::")

        expected_signature = hashlib.md5(
            (public_config["wwwroot"] + passport).encode()
        ).hexdigest()

        if signature != expected_signature:
            raise MoodleException("Invalid signature")

        return wstoken
