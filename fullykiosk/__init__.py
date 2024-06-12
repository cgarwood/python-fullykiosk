import aiohttp
import json
import logging

from .exceptions import FullyKioskError

_LOGGER = logging.getLogger(__name__)

RESPONSE_STATUS = "status"
RESPONSE_STATUSTEXT = "statustext"
RESPONSE_ERRORSTATUS = "Error"


class FullyKiosk:
    def __init__(self, session, host, port, password, use_ssl=False, verify_ssl=False):
        if not use_ssl:
            verify_ssl = False
        self._rh = _RequestsHandler(session, host, port, use_ssl=use_ssl,
                                    verify_ssl=verify_ssl)
        self._password = password
        self._deviceInfo = None
        self._settings = None

    async def sendCommand(self, cmd, **kwargs):
        data = await self._rh.get(
            cmd=cmd, password=self._password, type="json", **kwargs
        )
        if RESPONSE_STATUS in data and data[RESPONSE_STATUS] == RESPONSE_ERRORSTATUS:
            raise FullyKioskError(RESPONSE_ERRORSTATUS, data[RESPONSE_STATUSTEXT])
        return data

    async def getDeviceInfo(self):
        result = await self.sendCommand("deviceInfo")
        self._deviceInfo = result
        return self._deviceInfo

    async def getSettings(self):
        result = await self.sendCommand("listSettings")
        self._settings = result
        return self._settings

    @property
    def deviceInfo(self):
        return self._deviceInfo

    @property
    def settings(self):
        return self._settings

    async def startScreensaver(self):
        await self.sendCommand("startScreensaver")

    async def stopScreensaver(self):
        await self.sendCommand("stopScreensaver")

    async def screenOn(self):
        await self.sendCommand("screenOn")

    async def screenOff(self):
        await self.sendCommand("screenOff")

    async def setScreenBrightness(self, brightness):
        await self.sendCommand(
            "setStringSetting", key="screenBrightness", value=brightness
        )

    async def setAudioVolume(self, volume, stream=None):
        await self.sendCommand("setAudioVolume", level=volume, stream=stream)

    async def restartApp(self):
        await self.sendCommand("restartApp")

    async def loadStartUrl(self):
        await self.sendCommand("loadStartUrl")

    async def loadUrl(self, url):
        await self.sendCommand("loadUrl", url=url)

    async def playSound(self, url, stream=None):
        await self.sendCommand("playSound", url=url, stream=stream)

    async def stopSound(self):
        await self.sendCommand("stopSound")

    async def toForeground(self):
        await self.sendCommand("toForeground")
    
    async def toBackground(self):
        await self.sendCommand("toBackground")

    async def startApplication(self, application):
        await self.sendCommand("startApplication", package=application)

    async def setConfigurationString(self, setting, stringValue):
        await self.sendCommand("setStringSetting", key=setting, value=stringValue)

    async def setConfigurationBool(self, setting, boolValue):
        await self.sendCommand("setBooleanSetting", key=setting, value=boolValue)

    async def enableLockedMode(self):
        await self.sendCommand("enableLockedMode")

    async def disableLockedMode(self):
        await self.sendCommand("disableLockedMode")

    async def lockKiosk(self):
        await self.sendCommand("lockKiosk")

    async def unlockKiosk(self):
        await self.sendCommand("unlockKiosk")

    async def enableMotionDetection(self):
        await self.setConfigurationBool("motionDetection", True)

    async def disableMotionDetection(self):
        await self.setConfigurationBool("motionDetection", False)

    async def rebootDevice(self):
        await self.sendCommand("rebootDevice")

    async def clearCache(self):
        await self.sendCommand("clearCache")
    
    async def clearWebstorage(self):
        await self.sendCommand("clearWebstorage")
    
    async def clearCookies(self):
        await self.sendCommand("clearCookies")

    async def getCamshot(self):
        return await self._rh.get(cmd="getCamshot", password=self._password)

    async def getScreenshot(self):
        return await self._rh.get(cmd="getScreenshot", password=self._password)


class _RequestsHandler:
    """Internal class to create FullyKiosk requests"""

    def __init__(self, session: aiohttp.ClientSession, host, port, use_ssl=False,
                 verify_ssl=False):
        self.headers = {"Accept": "application/json"}

        self.session = session
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl

    async def get(self, **kwargs):
        url = f"http{'s' if self.use_ssl else ''}://{self.host}:{self.port}"
        params = []

        for key, value in kwargs.items():
            if value is not None:
                params.append((key, str(value)))
        req_params = {"url": url, "headers": self.headers, "params": params}
        if not self.verify_ssl:
            req_params["ssl"] = False

        _LOGGER.debug("Sending request to: %s", url)
        _LOGGER.debug("Parameters: %s", params)
        async with self.session.get(**req_params) as response:
            if response.status != 200:
                _LOGGER.warning(
                    "Invalid response from Fully Kiosk Browser API: %s", response.status
                )
                raise FullyKioskError(response.status, await response.text())

            content_type = response.headers['Content-Type']
            if content_type.startswith("image/"):
                return await response.content.read()
            data = await response.json(content_type=content_type)

            _LOGGER.debug(json.dumps(data))
            return data
