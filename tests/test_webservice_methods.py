import json
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase
from urllib.parse import parse_qsl

import httpx

from moodle.session import AsyncMoodleClient, MoodleClient


def mock_transport(
    requests: list[dict[str, str]], response: Any
) -> httpx.MockTransport:
    """Return a transport which records the submitted form data and replies with response."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            dict(parse_qsl(request.content.decode(), keep_blank_values=True))
        )
        return httpx.Response(200, content=json.dumps(response).encode())

    return httpx.MockTransport(handler)


COURSES = [{"id": 2, "shortname": "C1", "fullname": "Course 1", "idnumber": ""}]


class WebserviceMethodsTest(TestCase):
    def test_arguments_are_encoded(self) -> None:
        requests: list[dict[str, str]] = []
        transport = mock_transport(requests, COURSES)
        with MoodleClient(
            "https://moodle.invalid", "token", transport=transport
        ) as client:
            courses = client.core_enrol_get_users_courses(
                userid=2, returnusercount=False
            )

        self.assertEqual(courses, COURSES)
        self.assertEqual(
            requests,
            [
                {
                    "wstoken": "token",
                    "moodlewsrestformat": "json",
                    "wsfunction": "core_enrol_get_users_courses",
                    "userid": "2",
                    "returnusercount": "0",
                }
            ],
        )

    def test_omitted_arguments_are_not_sent(self) -> None:
        requests: list[dict[str, str]] = []
        transport = mock_transport(requests, COURSES)
        with MoodleClient(
            "https://moodle.invalid", "token", transport=transport
        ) as client:
            client.core_enrol_get_users_courses(userid=2)

        self.assertNotIn("returnusercount", requests[0])

    def test_keyword_and_nested_arguments(self) -> None:
        requests: list[dict[str, str]] = []
        transport = mock_transport(requests, {"count": 0, "entries": []})
        with MoodleClient(
            "https://moodle.invalid", "token", transport=transport
        ) as client:
            client.mod_glossary_get_entries_by_letter(
                id=1, letter="ALL", from_=5, options={"includenotapproved": True}
            )

        self.assertEqual(requests[0]["from"], "5")
        self.assertEqual(requests[0]["options[includenotapproved]"], "1")

    def test_function_without_return_value(self) -> None:
        requests: list[dict[str, str]] = []
        transport = mock_transport(requests, None)
        with MoodleClient(
            "https://moodle.invalid", "token", transport=transport
        ) as client:
            client.core_course_delete_modules(cmids=[1, 2])

        self.assertEqual(requests[0]["cmids[0]"], "1")
        self.assertEqual(requests[0]["cmids[1]"], "2")


class AsyncWebserviceMethodsTest(IsolatedAsyncioTestCase):
    async def test_arguments_are_encoded(self) -> None:
        requests: list[dict[str, str]] = []
        transport = mock_transport(requests, COURSES)
        async with AsyncMoodleClient(
            "https://moodle.invalid", "token", transport=transport
        ) as client:
            courses = await client.core_enrol_get_users_courses(userid=2)

        self.assertEqual(courses, COURSES)
        self.assertEqual(requests[0]["wsfunction"], "core_enrol_get_users_courses")
        self.assertEqual(requests[0]["userid"], "2")
