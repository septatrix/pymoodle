import base64
import hashlib
import html
import inspect
import re
import secrets
import sys
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List, Type

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from httpx import Client

from moodle.exceptions import MoodleException


class IDPInfo(TypedDict):
    name: str
    iconurl: str
    url: str


class IdentityProvider(ABC):
    providers: ClassVar[List[Type["IdentityProvider"]]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if not inspect.isabstract(cls):
            IdentityProvider.providers.append(cls)

    @staticmethod
    @abstractmethod
    def is_responsible(public_config: IDPInfo) -> bool:
        ...

    @abstractmethod
    def get_token(
        self,
        wwwroot: str,
        username: str,
        password: str,
        service: str,
        idp: IDPInfo,
        public_config: Dict[str, Any],
    ) -> str:
        ...

    def sync_get_token(
        self,
        wwwroot: str,
        username: str,
        password: str,
        service: str,
        idp: IDPInfo,
        public_config: Dict[str, Any],
    ) -> str:
        return self.get_token(wwwroot, username, password, service, idp, public_config)

    async def async_get_token(
        self,
        wwwroot: str,
        username: str,
        password: str,
        service: str,
        idp: IDPInfo,
        public_config: Dict[str, Any],
    ) -> str:
        return self.get_token(wwwroot, username, password, service, idp, public_config)


class RWTHSingleSignOn(IdentityProvider):
    @staticmethod
    def is_responsible(idp: IDPInfo) -> bool:
        return idp["name"] == "RWTH Single Sign On"

    def get_token(
        self,
        wwwroot: str,
        username: str,
        password: str,
        service: str,
        idp: IDPInfo,
        public_config: Dict[str, Any],
    ) -> str:

        with Client() as client:
            redirect_page = client.post(
                client.get(idp["url"], follow_redirects=True).url,  # type: ignore
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

            client.post(
                formdata["form_submit_url"],
                data=formdata.groupdict(),
                follow_redirects=True,
            )

            passport = secrets.token_urlsafe()

            token_response = client.post(
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
