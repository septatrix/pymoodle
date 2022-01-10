import html
import inspect
import re
import sys
from abc import ABC, abstractmethod
from typing import ClassVar, List, Tuple, Type

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from httpx import URL, AsyncClient, Client

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

    @classmethod
    def get_responsible_idp(
        cls, idp_infos: List[IDPInfo]
    ) -> Tuple[Type["IdentityProvider"], IDPInfo]:
        for idp_info in idp_infos:
            for idp_type in IdentityProvider.providers:
                if idp_type.is_responsible(idp_info):
                    return idp_type, idp_info
        raise MoodleException("No responsible identityprovider found")

    def __init__(
        self,
        wwwroot: str,
        username: str,
        password: str,
        idp: IDPInfo,
    ) -> None:
        super().__init__()
        self.wwwroot = wwwroot
        self.username = username
        self.password = password
        self.idp = idp

    @staticmethod
    @abstractmethod
    def is_responsible(idp: IDPInfo) -> bool:
        ...

    def login(self, client: Client) -> None:
        return None

    def sync_login(self, client: Client) -> None:
        return self.login(client)

    async def async_login(self, client: AsyncClient) -> None:
        with Client(cookies=client.cookies) as sync_client:
            self.login(sync_client)
            client.cookies.update(sync_client.cookies)


class RWTHSingleSignOn(IdentityProvider):
    requires_response_body = True

    @staticmethod
    def is_responsible(idp: IDPInfo) -> bool:
        return idp["name"] == "RWTH Single Sign On"

    def sync_login(self, client: Client) -> None:
        login_page_url = client.get(self.idp["url"], follow_redirects=True).url

        if login_page_url is None:
            raise MoodleException("URL unexpectedly not set on response")

        if login_page_url.netloc == URL(self.wwwroot).netloc:
            # We were redirected to Moodle so we are presumably logged in already
            return

        csrf_match = re.search(
            r'<input type="hidden" name="csrf_token" value="(?P<csrf_token>[^"]*)" />',
            html.unescape(client.get(login_page_url).text),
        )

        if not csrf_match:
            raise MoodleException("Unable to find csrf token")

        redirect_page = client.post(
            login_page_url,
            data={
                "j_username": self.username,
                "j_password": self.password,
                "_eventId_proceed": "",
                "csrf_token": csrf_match["csrf_token"],
            },
        )

        # TODO use python html.parser
        formdata = re.search(
            r'<form action="(?P<form_submit_url>[^"]*)" method="post">'
            r'.*<input type="hidden" name="RelayState" value="(?P<RelayState>[^"]*)"/>'
            r'.*<input type="hidden" name="SAMLResponse" value="(?P<SAMLResponse>[^"]*)"/>',
            html.unescape(redirect_page.text),
            flags=re.DOTALL,
        )

        if not formdata:
            raise MoodleException("Unable to parse login form")

        client.post(
            formdata["form_submit_url"],
            data=formdata.groupdict(),
            follow_redirects=True,
        )

    async def async_login(self, client: AsyncClient) -> None:
        login_page_url = (await client.get(self.idp["url"], follow_redirects=True)).url

        if login_page_url is None:
            raise MoodleException("URL unexpectedly not set on response")

        if login_page_url.netloc == URL(self.wwwroot).netloc:
            # We were redirected to Moodle so we are presumably logged in already
            return

        csrf_match = re.search(
            r'<input type="hidden" name="csrf_token" value="(?P<csrf_token>[^"]*)" />',
            html.unescape((await client.get(login_page_url)).text),
        )

        if not csrf_match:
            raise MoodleException("Unable to find csrf token")

        redirect_page = await client.post(
            login_page_url,
            data={
                "j_username": self.username,
                "j_password": self.password,
                "_eventId_proceed": "",
                "csrf_token": csrf_match["csrf_token"],
            },
        )

        # TODO use python html.parser
        formdata = re.search(
            r'<form action="(?P<form_submit_url>[^"]*)" method="post">'
            r'.*<input type="hidden" name="RelayState" value="(?P<RelayState>[^"]*)"/>'
            r'.*<input type="hidden" name="SAMLResponse" value="(?P<SAMLResponse>[^"]*)"/>',
            html.unescape(redirect_page.text),
            flags=re.DOTALL,
        )

        if not formdata:
            raise MoodleException("Unable to parse login form")

        await client.post(
            formdata["form_submit_url"],
            data=formdata.groupdict(),
            follow_redirects=True,
        )
