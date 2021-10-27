import sys
from unittest import TestCase
from unittest.case import skip, skipIf

from moodle.session import AsyncMoodleClient, MoodleClient

if sys.version_info >= (3, 8, 0):
    from unittest import IsolatedAsyncioTestCase
elif sys.version_info >= (3, 7, 0):
    from later.unittest.backport.async_case import IsolatedAsyncioTestCase
else:
    IsolatedAsyncioTestCase = type  # Fallback to allow subclassing


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


@skipIf(
    sys.version_info < (3, 7, 0), "Python 3.6 does not support IsolatedAsyncioTestCase"
)
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
