import os
from unittest import IsolatedAsyncioTestCase, TestCase, skipIf

from moodle.session import AsyncMoodleClient, MoodleClient


class SyncLoginTest(TestCase):
    def test_login(self) -> None:
        with MoodleClient("https://school.moodledemo.net/", "") as client:
            self.assertNotEqual(client.get_token("manager", "moodle"), "")

        with MoodleClient("https://sandbox.moodledemo.net/", "") as client:
            self.assertNotEqual(client.get_token("admin", "sandbox"), "")

    @skipIf(
        "MOODLE_USERNAME" not in os.environ or "MOODLE_PASSWORD" not in os.environ,
        "No valid credentials provided",
    )
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
        async with AsyncMoodleClient("https://school.moodledemo.net/", "") as client:
            self.assertNotEqual(await client.get_token("manager", "moodle"), "")

        async with AsyncMoodleClient("https://sandbox.moodledemo.net/", "") as client:
            self.assertNotEqual(await client.get_token("admin", "sandbox"), "")

    @skipIf(
        "MOODLE_USERNAME" not in os.environ or "MOODLE_PASSWORD" not in os.environ,
        "No valid credentials provided",
    )
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
