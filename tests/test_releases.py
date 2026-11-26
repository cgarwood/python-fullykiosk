"""Tests for the release helpers, run with: python -m unittest discover -s tests"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError
from fullykiosk.releases import Release, getApp, getRelease, getReleases

FILES = "https://www.fully-kiosk.com/files/2026"
FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Fully-Kiosk-Browser-v1.61.4.apk</title><link>{FILES}/10/Fully-Kiosk-Browser-v1.61.4.apk</link></item>
<item><title>Fully-Kiosk-Browser-v1.61.4-emm.apk</title><link>{FILES}/10/Fully-Kiosk-Browser-v1.61.4-emm.apk</link></item>
<item><title>Fully-Kiosk-Browser-v1.9.10.apk</title><link>{FILES}/01/Fully-Kiosk-Browser-v1.9.10.apk</link></item>
<item><title>Fully-Kiosk-Browser-v1.61.3.apk</title><link>{FILES}/09/Fully-Kiosk-Browser-v1.61.3.apk</link></item>
<item><title>Fully-Single-App-Kiosk-v1.21.4.apk</title><link>{FILES}/10/Fully-Single-App-Kiosk-v1.21.4.apk</link></item>
<item><title>Fully Kiosk Browser manual.pdf</title><link>{FILES}/10/manual.pdf</link></item>
<item><title>Fully-Video-Kiosk-v1.0.apk</title></item>
</channel></rss>"""

LATEST = Release("Fully-Kiosk-Browser", "1.61.4", None, f"{FILES}/10/Fully-Kiosk-Browser-v1.61.4.apk")
LATEST_EMM = Release("Fully-Kiosk-Browser", "1.61.4", "emm", f"{FILES}/10/Fully-Kiosk-Browser-v1.61.4-emm.apk")
PREVIOUS = Release("Fully-Kiosk-Browser", "1.61.3", None, f"{FILES}/09/Fully-Kiosk-Browser-v1.61.3.apk")
SINGLE_APP = Release("Fully-Single-App-Kiosk", "1.21.4", None, f"{FILES}/10/Fully-Single-App-Kiosk-v1.21.4.apk")


def mockSession(content):
    session = MagicMock()
    response = session.get.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.read = AsyncMock(return_value=content.encode())
    return session


class GetReleasesTest(unittest.IsolatedAsyncioTestCase):
    async def test_releases(self):
        releases = await getReleases(mockSession(FEED))
        self.assertEqual(releases[:2], [LATEST, LATEST_EMM])
        self.assertEqual(len(releases), 5)

    async def test_invalid_feed(self):
        for content in ("<rss", '<!DOCTYPE x [<!ENTITY a "b">]><rss>&a;</rss>'):
            with self.subTest(content=content), self.assertRaises(FullyKioskError):
                await getReleases(mockSession(content))


class GetReleaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.releases = await getReleases(mockSession(FEED))

    def test_matching(self):
        for deviceInfo, version, release in [
            ({"appVersionName": "1.60.1"}, None, LATEST),
            ({"appVersionName": "1.60.1", "packageName": "de.ozerov.fully"}, None, LATEST),
            ({"appVersionName": "1.60.1-emm"}, None, LATEST_EMM),
            ({"appVersionName": "1.60.1", "packageName": "com.fullykiosk.emm"}, None, LATEST_EMM),
            ({"appVersionName": "1.20", "appPackageName": "com.fullykiosk.singleapp"}, None, SINGLE_APP),
            ({"appVersionName": "1.60.1", "packageName": "com.fullykiosk.videokiosk"}, None, None),
            ({"appVersionName": "1.60.1", "packageName": "com.example"}, None, None),
            ({"appVersionName": "1.60.1"}, "1.61.3", PREVIOUS),
            ({"appVersionName": "1.60.1-emm"}, "1.61.4-emm", LATEST_EMM),
            ({"appVersionName": "1.60.1-emm"}, "1.61.4", LATEST_EMM),
            ({"appVersionName": "1.60.1"}, "9.9.9", None),
        ]:
            with self.subTest(deviceInfo=deviceInfo, version=version):
                self.assertEqual(getRelease(self.releases, deviceInfo, version), release)

    def test_app(self):
        self.assertEqual(getApp({}), "Fully-Kiosk-Browser")
        self.assertEqual(getApp({"packageName": "com.fullykiosk.videokiosk"}), "Fully-Video-Kiosk")
        self.assertIsNone(getApp({"packageName": "com.example"}))


@patch("fullykiosk.INSTALL_POLL_INTERVAL", 0)
class InstallReleaseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fully = FullyKiosk(MagicMock(), "host", 2323, "password")
        self.fully.loadApkFile = AsyncMock()
        self.fully.getInstallApkState = AsyncMock()
        self.fully.getDeviceInfo = AsyncMock()

    def installed(self, *versions):
        self.fully.getDeviceInfo.side_effect = [{"appVersionName": v} for v in versions]

    async def test_upgrade(self):
        self.installed("1.61.3", "1.61.3", "1.61.4")
        self.fully.getInstallApkState.side_effect = [
            {"url": "https://example.com/other.apk", "status": "failed"},
            {"url": LATEST.url, "status": "idle"},
            aiohttp.ClientError(),
            {"status": "idle"},
        ]
        await self.fully.installRelease(LATEST)
        self.fully.loadApkFile.assert_awaited_once_with(LATEST.url, force_install=False)

    async def test_downgrade(self):
        self.installed("1.61.4", "1.61.3")
        self.fully.getInstallApkState.return_value = {"status": "success"}
        await self.fully.installRelease(PREVIOUS)
        self.fully.loadApkFile.assert_awaited_once_with(PREVIOUS.url, force_install=True)

    async def test_reinstall(self):
        self.fully.getDeviceInfo.return_value = {"appVersionName": "1.61.4-emm"}
        self.fully.getInstallApkState.side_effect = [
            {"url": LATEST_EMM.url, "status": "idle"},
            {"url": LATEST_EMM.url, "status": "downloading"},
            FullyKioskError(500, ""),
            {"url": LATEST_EMM.url, "status": "idle"},
        ]
        await self.fully.installRelease(LATEST_EMM)
        self.fully.loadApkFile.assert_awaited_once_with(LATEST_EMM.url, force_install=True)
        self.assertEqual(self.fully.getInstallApkState.await_count, 4)

    async def test_restarting(self):
        self.fully.getDeviceInfo.side_effect = [
            {"appVersionName": "1.61.3"},
            *[aiohttp.ClientError()] * 3,
            {"appVersionName": "1.61.4"},
        ]
        self.fully.getInstallApkState.return_value = {"status": "success"}
        await self.fully.installRelease(LATEST)

    async def test_failed(self):
        self.installed("1.61.3")
        self.fully.getInstallApkState.side_effect = [
            {"url": LATEST.url, "status": "downloading"},
            {"url": LATEST.url, "status": "failed", "statustext": "Cancelled"},
        ]
        with self.assertRaises(FullyKioskError):
            await self.fully.installRelease(LATEST)

    async def test_timeout(self):
        self.fully.getDeviceInfo.return_value = {"appVersionName": "1.61.3"}
        self.fully.getInstallApkState.return_value = {"status": "success"}
        with self.assertRaises(asyncio.TimeoutError):
            await self.fully.installRelease(LATEST, timeout=0.05)


if __name__ == "__main__":
    unittest.main()
