from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.case import skip

from moodle.session import AsyncMoodleClient, MoodleClient


class SyncLoginTest(TestCase):
    def test_login(self):
        with MoodleClient("https://school.moodledemo.net/", "") as client:
            self.assertNotEqual(client.get_token("manager", "moodle"), "")

        with MoodleClient("https://sandbox.moodledemo.net/", "") as client:
            self.assertNotEqual(client.get_token("admin", "sandbox"), "")

    @skip("No valid credentials provided")
    def test_idp_login(self):
        with MoodleClient("https://moodle.rwth-aachen.de/", "") as client:
            self.assertNotEqual(client.get_token("ab123456", "Pa55w0rd"), "")


class AsyncLoginTest(IsolatedAsyncioTestCase):
    async def test_login(self):
        async with AsyncMoodleClient("https://school.moodledemo.net/", "") as client:
            self.assertNotEqual(await client.get_token("manager", "moodle"), "")

        async with AsyncMoodleClient("https://sandbox.moodledemo.net/", "") as client:
            self.assertNotEqual(await client.get_token("admin", "sandbox"), "")

    @skip("No valid credentials provided")
    async def test_idp_login(self):
        async with AsyncMoodleClient("https://moodle.rwth-aachen.de/", "") as client:
            self.assertNotEqual(await client.get_token("ab123456", "Pa55w0rd"), "")
