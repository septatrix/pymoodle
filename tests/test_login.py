from unittest import IsolatedAsyncioTestCase, TestCase

from moodle.session import AsyncMoodleClient, MoodleClient


class LoginTest(IsolatedAsyncioTestCase):
    async def test_login(self):
        async with AsyncMoodleClient("https://school.moodledemo.net/", "") as client:
            client.wstoken = await client.get_token("manager", "moodle")
            self.assertNotEqual(client.wstoken, "")

        async with AsyncMoodleClient("https://sandbox.moodledemo.net/", "") as client:
            client.wstoken = await client.get_token("admin", "sandbox")
            self.assertNotEqual(client.wstoken, "")
