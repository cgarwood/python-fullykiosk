"""APK releases of the Fully Kiosk apps, as listed on the Fully Kiosk website."""

from __future__ import annotations

import re
from dataclasses import dataclass

import aiohttp
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from .exceptions import FullyKioskError

RELEASES_URL = "https://www.fully-kiosk.com/feed/media"

_APK_FILENAME = re.compile(
    r"^(?P<app>[\w-]+)-v(?P<version>\d+(?:\.\d+)+)(?:-(?P<variant>[\w-]+))?\.apk$"
)

_BROWSER_APP = "Fully-Kiosk-Browser"
_EMM_PACKAGE = "com.fullykiosk.emm"
_APP_BY_PACKAGE = {
    _EMM_PACKAGE: _BROWSER_APP,
    "com.fullykiosk.singleapp": "Fully-Single-App-Kiosk",
    "com.fullykiosk.videokiosk": "Fully-Video-Kiosk",
    "de.ozerov.fully": _BROWSER_APP,
}


@dataclass(frozen=True)
class Release:
    """An APK release of a Fully Kiosk app."""

    app: str
    version: str
    variant: str | None
    url: str

    @property
    def versionName(self) -> str:
        """Return the version the app reports once the release is installed."""
        return f"{self.version}-{self.variant}" if self.variant else self.version


def versionKey(versionName: str) -> tuple[int, ...]:
    """Return a sortable key for a version, ignoring an edition suffix like -emm."""
    return tuple(int(part) for part in re.findall(r"\d+", versionName.split("-")[0]))


async def getReleases(session: aiohttp.ClientSession) -> list[Release]:
    """
    Get the APK releases from the Fully Kiosk website.

    Raises FullyKioskError if the release feed cannot be parsed.
    """
    async with session.get(RELEASES_URL) as response:
        response.raise_for_status()
        content = await response.read()

    try:
        root = fromstring(content)
    except (ParseError, DefusedXmlException) as err:
        raise FullyKioskError("ParseError", str(err)) from err

    releases = []
    for item in root.iter("item"):
        title = item.findtext("title")
        link = item.findtext("link")
        if title and link and (match := _APK_FILENAME.match(title.strip())):
            releases.append(
                Release(
                    match["app"], match["version"], match["variant"], link.strip()
                )
            )
    return releases


def _getPackage(deviceInfo: dict) -> str | None:
    # Older versions of Fully do not report the package
    return deviceInfo.get("packageName") or deviceInfo.get("appPackageName")


def getApp(deviceInfo: dict) -> str | None:
    """Return the name of the app in the releases, or None if it has no releases."""
    if (package := _getPackage(deviceInfo)) is None:
        return _BROWSER_APP
    return _APP_BY_PACKAGE.get(package)


def getRelease(
    releases: list[Release], deviceInfo: dict, version: str | None = None
) -> Release | None:
    """
    Return the latest release of the app and edition the device runs.

    :param releases: The releases from getReleases().
    :param deviceInfo: The device info from FullyKiosk.getDeviceInfo().
    :param version: Return this version instead of the latest, with or without
    the edition suffix, like 1.61.4 or 1.61.4-emm.
    """
    app = getApp(deviceInfo)
    variant = (
        "emm"
        if deviceInfo["appVersionName"].endswith("-emm")
        or _getPackage(deviceInfo) == _EMM_PACKAGE
        else None
    )
    return max(
        (
            release
            for release in releases
            if release.app == app
            and release.variant == variant
            and version in (None, release.version, release.versionName)
        ),
        key=lambda release: versionKey(release.version),
        default=None,
    )
