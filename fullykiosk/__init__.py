"""Manage the connection with FullyKiosk"""

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Callable, Coroutine
from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError
from asyncio_mqtt import Client, MqttError

from .exceptions import FullyKioskError

_LOGGER = logging.getLogger(__name__)

RESPONSE_STATUS = "status"
RESPONSE_STATUSTEXT = "statustext"
RESPONSE_ERRORSTATUS = "Error"


class FullyKiosk:
    """FullyKiosk class"""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        password: str,
        use_mqtt_if_available: bool = True,
        mqtt_callback_func: Callable[[str], None] = None,
    ):
        """Initialize the FullyKiosk class"""
        self._rh = _RequestsHandler(session, host, port)
        self._password = password
        self._use_mqtt_if_available = use_mqtt_if_available
        self._device_info = None
        self._settings = None
        self._device_id = None
        self._mqtt_device_info_topic = None
        self._mqtt_broker_ip = None
        self._mqtt_broker_port = 1883
        self._mqtt_broker_password = None
        self._mqtt_client_id = None
        self._mqtt_event_topic = None
        self._mqtt_enabled = None
        self._mqtt_broker_username = None
        self._app_id = "fully"
        self._mqtt_client = None
        self._callback_func = mqtt_callback_func

    async def start(self):
        """Start the connection"""

        device_info = await self.get_device_info()
        device_settings = await self.get_settings()
        self._device_info = device_info
        self._settings = device_settings
        self._device_id = device_info["deviceID"]
        self._mqtt_enabled = self._settings["mqttEnabled"]
        if self._mqtt_enabled and self._use_mqtt_if_available:
            _LOGGER.debug("MQTT is enabled!")
            self._mqtt_device_info_topic = self._settings["mqttDeviceInfoTopic"]
            broker_url_parts = (
                str(self._settings["mqttBrokerUrl"])
                .replace("http://", "")
                .split(":", maxsplit=1)
            )
            self._mqtt_broker_ip = broker_url_parts[0]
            self._mqtt_broker_port = int(broker_url_parts[1])

            self._mqtt_broker_password = self._settings["mqttBrokerPassword"]
            self._mqtt_client_id = self._settings["mqttClientId"]
            self._mqtt_event_topic = self._settings["mqttEventTopic"]
            self._mqtt_broker_username = self._settings["mqttBrokerUsername"]
            reconnect_interval = 3
            while True:
                try:
                    await self._start_mqtt_listener()
                except MqttError as error:
                    _LOGGER.error(
                        'Error "%1s". Reconnecting in %2s seconds.',
                        error,
                        reconnect_interval,
                    )
                finally:
                    await asyncio.sleep(reconnect_interval)

    async def _start_mqtt_listener(self):
        """Listen to mqtt"""
        _LOGGER.debug("Start MQTT listener.")
        # We 💛 context managers. Let's create a stack to help
        # us manage them.
        async with AsyncExitStack() as stack:
            # Keep track of the asyncio tasks that we create, so that
            # we can cancel them on exit
            tasks = set()
            stack.push_async_callback(self.cancel_tasks, tasks)

            # Connect to the MQTT broker
            client = Client(
                self._mqtt_broker_ip,
                port=self._mqtt_broker_port,
                username=self._mqtt_broker_username,
                password=self._mqtt_broker_password,
                client_id=f"ha-{self._mqtt_client_id}",
            )
            await stack.enter_async_context(client)
            event_topic = f"{self._app_id}/event/+/{self._device_id}"
            info_topic = f"{self._app_id}/deviceInfo/{self._device_id}"

            # You can create any number of topic filters
            topic_filters = (
                event_topic,
                info_topic
                # 👉 Try to add more filters!
            )
            for topic_filter in topic_filters:
                # Log all messages that matches the filter
                manager = client.filtered_messages(topic_filter)
                messages = await stack.enter_async_context(manager)
                template = f'[topic_filter="{topic_filter}"] {{}}'
                task = asyncio.create_task(self.handle_messages(messages, template))
                tasks.add(task)

            # Messages that doesn't match a filter will get logged here
            messages = await stack.enter_async_context(client.unfiltered_messages())
            task = asyncio.create_task(
                self.handle_messages(messages, "[unfiltered] {}")
            )
            tasks.add(task)

            # Subscribe to topic(s)
            # 🤔 Note that we subscribe *after* starting the message
            # loggers. Otherwise, we may miss retained messages.
            await client.subscribe(event_topic)
            await client.subscribe(info_topic)

            await asyncio.gather(*tasks)

    async def handle_messages(self, messages, template):
        """Handle MQTT messages"""
        async for message in messages:
            # 🤔 Note that we assume that the message paylod is an
            # UTF8-encoded string (hence the `bytes.decode` call).
            _LOGGER.debug(
                template.format(f"{message.topic} | {message.payload.decode()}")
            )
            json_payload = json.loads(message.payload)
            message_topic_parts = message.topic.split("/")
            message_type = message_topic_parts[1]
            event_type = message_type
            if message_type == "deviceInfo":
                self._device_info = json_payload
            elif message_type == "event":
                event_type = message_topic_parts[2]

            if self._callback_func is not None:
                await self._callback_func(event_type)

    async def cancel_tasks(self, tasks):
        """Cancel tasks."""
        for task in tasks:
            if task.done():
                continue
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass

    async def sendCommand(self, cmd, **kwargs):
        """Send REST command to FulyKiosk"""
        data = await self._rh.get(
            cmd=cmd, password=self._password, type="json", **kwargs
        )
        if RESPONSE_STATUS in data and data[RESPONSE_STATUS] == RESPONSE_ERRORSTATUS:
            raise FullyKioskError(RESPONSE_ERRORSTATUS, data[RESPONSE_STATUSTEXT])
        return data

    async def get_device_info(self):
        """Retrieve device info using REST"""
        result = await self.sendCommand("deviceInfo")
        self._device_info = result
        if self._rh.host != result["ip4"]:
            _LOGGER.info(
                "Device %1s IP address is changed to %2s.", self._rh.host, result["ip4"]
            )
            self._rh.host = result["ip4"]
        return result

    async def get_settings(self):
        """Retrieve device info using REST"""
        result = await self.sendCommand("listSettings")
        self._settings = result
        return result

    @property
    def device_info(self) -> str:
        return self._device_info

    @property
    def settings(self) -> str:
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


class _RequestsHandler:
    """Internal class to create FullyKiosk requests"""

    def __init__(self, session: ClientSession, host, port):
        self.headers = {"Accept": "application/json"}

        self.session = session
        self.host = host
        self.port = port

    async def get(self, **kwargs):
        url = f"http://{self.host}:{self.port}"
        params = []

        for key, value in kwargs.items():
            if value is not None:
                params.append((key, str(value)))

        _LOGGER.debug("Sending request to: %s", url)
        _LOGGER.debug("Parameters: %s", params)
        async with self.session.get(
            url, headers=self.headers, params=params
        ) as response:
            if response.status != 200:
                _LOGGER.warning(
                    "Invalid response from Fully Kiosk Browser API: %s", response.status
                )
                raise FullyKioskError(response.status, await response.text())

            try:
                data = await response.json()
            except ContentTypeError:
                data = await response.json(content_type="text/html")

            _LOGGER.debug(json.dumps(data))
            return data
