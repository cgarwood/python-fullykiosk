from typing import Callable
import json
import logging

from .exceptions import FullyKioskError
from .models import FullyKioskMqttClient, RequestsHandler
from paho.mqtt.client import Client, MQTTMessage

_LOGGER = logging.getLogger(__name__)

RESPONSE_STATUS = "status"
RESPONSE_STATUSTEXT = "statustext"
RESPONSE_ERRORSTATUS = "Error"


class FullyKiosk:

    _rh:RequestsHandler = None
    _password:str = None
    _deviceInfo:str = None
    _settings:str = None
    _device_id:str = None
    _app_id: str = "fully"
    _mqtt_event_callback: Callable[[str], None] = None
    _mqtt_enabled:bool = False

    @property
    def mqttEnableds(self):
        return self._mqtt_enabled

    def __init__(self, session, host, port, password):
        self._rh = RequestsHandler(session, host, port)
        self._password = password
        self._deviceInfo = None
        self._settings = None
    
    async def start(self, mqtt_event_callback:Callable[[str], None] = None) -> None:
        """Initialize the mqtt client if it's enable in the Fully Kiosk Settings"""
        self._mqtt_event_callback = mqtt_event_callback
        self._deviceInfo = await self.getDeviceInfo()
        self._settings = await self.getSettings()
        self._device_id = self._deviceInfo["deviceID"]
        self._mqtt_enabled = self._settings["mqttEnabled"]

        if not self._mqtt_enabled:
            return
        
        mqtt_client = await self._create_client()
        mqtt_client.connect()

    def _replace_ids(self, input:str) -> str:
        return input.replace('$appId', self._app_id).replace('$deviceId', self._device_id).replace('$event', '+')

    async def _create_client(self) -> FullyKioskMqttClient:
        """Create a mqtt client"""
        broker_url_parts = (
            str(self._settings["mqttBrokerUrl"])
            .replace("http://", "")
            .split(":", maxsplit=1)
        )
        client_id = f"ha-{self._settings['mqttClientId']}"
        broker_host = broker_url_parts[0]
        broker_port = int(broker_url_parts[1])
        username = self._settings["mqttBrokerUsername"]
        password = self._settings["mqttBrokerPassword"]

        def on_connect(client:Client):
            deviceInfoTopic = self._replace_ids(self._settings["mqttDeviceInfoTopic"])
            eventTopic = self._replace_ids(self._settings["mqttEventTopic"])
            client.subscribe(deviceInfoTopic)
            client.subscribe(eventTopic)
        
        def on_message(message:MQTTMessage):
            json_payload = json.loads(message.payload)
            message_topic_parts = message.topic.split("/")
            message_type = message_topic_parts[1]
            event_type = message_type
            if message_type == "deviceInfo":
                self._device_info = json_payload
            elif message_type == "event":
                event_type = message_topic_parts[2]
            if self._mqtt_event_callback:
                self._mqtt_event_callback(event_type)           
        
        return FullyKioskMqttClient(broker_host, broker_port, client_id, username, password, on_message, on_connect)

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
