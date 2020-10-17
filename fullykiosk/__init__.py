import json
import logging
import requests


class FullyKiosk:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password

        self._deviceInfo = None

    def sendCommand(self, cmd, **kwargs):
        url = f"http://{self.host}:{self.port}/?cmd={cmd}&password={self.password}&type=json"
        for key, value in kwargs.items():
            if value is not None:
                url = url + f"&{key}={value}"

        try:
            result = json.loads(requests.get(url, timeout=10).content)
            return result
        except requests.exceptions.Timeout:
            print("Timeout error")

    def getDeviceInfo(self):
        result = self.sendCommand("deviceInfo")
        self._deviceInfo = result
        return self._deviceInfo

    @property
    def deviceInfo(self):
        return self._deviceInfo

    def startScreensaver(self):
        return self.sendCommand("startScreensaver")

    def stopScreensaver(self):
        return self.sendCommand("stopScreensaver")

    def screenOn(self):
        return self.sendCommand("screenOn")

    def screenOff(self):
        return self.sendCommand("screenOff")

    def setScreenBrightness(self, brightness):
        return self.sendCommand(
            "setStringSetting", key="screenBrightness", value=brightness
        )

    def setAudioVolume(self, volume, stream=None):
        return self.sendCommand("setAudioVolume", volume=volume, stream=stream)

    def restartApp(self):
        return self.sendCommand("restartApp")

    def loadStartUrl(self):
        return self.sendCommand("loadStartUrl")

    def loadUrl(self, url):
        return self.sendCommand("loadUrl", url=url)

    def playSound(self, url, stream=None):
        return self.sendCommand("playSound", url=url, stream=stream)

    def stopSound(self):
        return self.sendCommand("stopSound")

    def toForeground(self):
        return self.sendCommand("toForeground")

    def startApplication(self, application):
        return self.sendCommand("startApplication", package=application)

    def setConfigurationString(self, setting, stringValue):
        return self.sendCommand("setStringSetting", key=setting, value=stringValue)

    def setConfigurationBool(self, setting, boolValue):
        return self.sendCommand("setBooleanSetting", key=setting, value=boolValue)

    def enableLockedMode(self):
        return self.sendCommand("enableLockedMode")

    def disableLockedMode(self):
        return self.sendCommand("disableLockedMode")

    def lockKiosk(self):
        return self.sendCommand("lockKiosk")

    def unlockKiosk(self):
        return self.sendCommand("unlockKiosk")

    def rebootDevice(self):
        return self.sendCommand("rebootDevice")
