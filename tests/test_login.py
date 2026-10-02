import os
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase, skipIf
from urllib.parse import parse_qsl

import httpx

from moodle.exceptions import MoodleException
from moodle.session import AsyncMoodleClient, MoodleClient

# The public demo sites of Moodle change their passwords regularly,
# the current ones are shown on their login pages.
DEMO_SITES = [
    (
        "https://school.moodledemo.net/",
        "manager",
        os.environ.get("MOODLE_SCHOOL_DEMO_PASSWORD", "moodle26"),
    ),
    (
        "https://sandbox.moodledemo.net/",
        "admin",
        os.environ.get("MOODLE_SANDBOX_DEMO_PASSWORD", "sandbox24"),
    ),
]

HAS_IDP_CREDENTIALS = (
    "MOODLE_USERNAME" in os.environ and "MOODLE_PASSWORD" in os.environ
)


class SyncLoginTest(TestCase):
    def test_login(self) -> None:
        for wwwroot, username, password in DEMO_SITES:
            with self.subTest(wwwroot), MoodleClient(wwwroot, "") as client:
                self.assertNotEqual(client.get_token(username, password), "")

    @skipIf(not HAS_IDP_CREDENTIALS, "No valid credentials provided")
    def test_idp_login(self) -> None:
        with MoodleClient("https://moodle.rwth-aachen.de/", "") as client:
            first_token = client.get_token(
                os.environ["MOODLE_USERNAME"], os.environ["MOODLE_PASSWORD"]
            )

            # Check that fetching tokens is idempotent
            second_token = client.get_token(
                os.environ["MOODLE_USERNAME"], os.environ["MOODLE_PASSWORD"]
            )
            self.assertEqual(first_token, second_token)

            # Check that fetching a token for another service yields a different token
            other_service_token = client.get_token(
                os.environ["MOODLE_USERNAME"],
                os.environ["MOODLE_PASSWORD"],
                service="filter_opencast_authentication",
            )
            self.assertNotEqual(first_token, other_service_token)


class AsyncLoginTest(IsolatedAsyncioTestCase):
    async def test_login(self) -> None:
        for wwwroot, username, password in DEMO_SITES:
            with self.subTest(wwwroot):
                async with AsyncMoodleClient(wwwroot, "") as client:
                    self.assertNotEqual(await client.get_token(username, password), "")

    @skipIf(not HAS_IDP_CREDENTIALS, "No valid credentials provided")
    async def test_idp_login(self) -> None:
        async with AsyncMoodleClient("https://moodle.rwth-aachen.de/", "") as client:
            first_token = await client.get_token(
                os.environ["MOODLE_USERNAME"], os.environ["MOODLE_PASSWORD"]
            )

            # Check that fetching tokens is idempotent
            second_token = await client.get_token(
                os.environ["MOODLE_USERNAME"], os.environ["MOODLE_PASSWORD"]
            )
            self.assertEqual(first_token, second_token)

            # Check that fetching a token for another service yields a different token
            other_service_token = await client.get_token(
                os.environ["MOODLE_USERNAME"],
                os.environ["MOODLE_PASSWORD"],
                service="filter_opencast_authentication",
            )
            self.assertNotEqual(first_token, other_service_token)


PUBLIC_CONFIG = [{"error": False, "data": {"typeoflogin": 1}}]


class GetTokenTest(TestCase):
    def mock_transport(
        self, requests: list[httpx.Request], token_response: Any
    ) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/lib/ajax/service.php":
                return httpx.Response(200, json=PUBLIC_CONFIG)
            return httpx.Response(200, json=token_response)

        return httpx.MockTransport(handler)

    def test_credentials_are_posted(self) -> None:
        requests: list[httpx.Request] = []
        transport = self.mock_transport(requests, {"token": "abc"})
        with MoodleClient("https://moodle.invalid", "", transport=transport) as client:
            self.assertEqual(client.get_token("user", "secret"), "abc")

        token_request = requests[-1]
        self.assertEqual(token_request.method, "POST")
        self.assertEqual(token_request.url.query, b"")
        self.assertEqual(
            dict(parse_qsl(token_request.content.decode())),
            {"username": "user", "password": "secret", "service": "moodle_mobile_app"},
        )

    def test_error_is_raised(self) -> None:
        requests: list[httpx.Request] = []
        transport = self.mock_transport(
            requests, {"error": "Invalid login, please try again"}
        )
        with (
            MoodleClient("https://moodle.invalid", "", transport=transport) as client,
            self.assertRaisesRegex(MoodleException, "Invalid login"),
        ):
            client.get_token("user", "wrong")
