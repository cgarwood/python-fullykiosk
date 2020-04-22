import json
import logging
import requests

class FullyKiosk():
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password

        self.getDeviceInfo()

    def sendCommand(self, cmd, **kwargs):
        url = f"http://{self.host}:{self.port}/?cmd={cmd}&password={self.password}&type=json"
        for key, value in kwargs.items():
            url = url + f"&{key}={value}"

        result = json.loads(requests.get(url).content)
        print("{}".format(result))

    def getDeviceInfo(self):
        result = self.sendCommand('deviceInfo')
        self.deviceInfo = result
        return self.deviceInfo


    def startScreensaver(self):
        return self.sendCommand('startScreensaver')

    def stopScreensaver(self):
        return self.sendCommand('stopScreensaver')

    def screenOn(self):
        return self.sendCommand('screenOn')

    def screenOff(self):
        return self.sendCommand('screenOff')

    def restartApp(self):
        return self.sendCommand('restartApp')

    def loadStartUrl(self):
        return self.sendCommand('loadStartUrl')

    def loadUrl(self, url):
        return self.sendCommand('loadUrl', url=url)

