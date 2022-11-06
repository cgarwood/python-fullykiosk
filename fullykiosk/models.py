""" Holds models for FK api"""
import logging
from typing import Callable
import paho.mqtt.client as mqtt
import aiohttp
from .exceptions import FullyKioskError
import json

_LOGGER = logging.getLogger(__name__)


class FullyKioskMqttClient:
    """Client to handle FullyKiosk mqtt messages"""
    _broker_url:str = None
    _port:int = None
    _client_id = None
    _username:str = None
    _password:str = None
    _on_message_callback = Callable
    _on_connect_callback = Callable
    _mqtt_client:mqtt.Client = None

    def __init__(self, broker_url:str, port:int, client_id:str, username:str, password:str, on_message_callback:Callable, on_connect_callback:Callable) -> None:
        """Initalize the FullyKioskMqttClient class"""
        self._broker_url = broker_url
        self._port = port
        self._client_id = client_id
        self._username = username
        self._password = password
        self._on_message_callback = on_message_callback
        self._on_connect_callback = on_connect_callback
        self._mqtt_client = self._create_client()

    def _create_client(self) -> mqtt.Client:
        """Create the actual client"""
        mqtt_client = mqtt.Client(self._client_id)
        mqtt_client.username_pw_set(self._username, self._password)
        mqtt_client.enable_logger(_LOGGER)
        mqtt_client.on_connect = self._on_connect
        mqtt_client.on_message = self._on_message
        return mqtt_client

    def _on_connect(self, client:mqtt.Client, userdata, flags, resultCode) -> None:
        """Callback to execute after connecting to the mqtt broker"""
        if resultCode == 0:
            _LOGGER.info('Connected to MQTT broker')
            client.on_message = self._on_message
            if self._on_connect_callback:
                self._on_connect_callback(client)
        elif resultCode == 5:
            self._mqtt_client.username_pw_set(self._username, self._password)
            self.connect()
    
    def _on_message(self, client:mqtt.Client, userdata, message:mqtt.MQTTMessage) -> None:
        """Callback to execute after message is received"""
        _LOGGER.debug("****************** MQTT message received ******************")
        _LOGGER.debug(f"Topic: {message.topic}")
        _LOGGER.debug(f"Message:")
        _LOGGER.debug(f"{message.payload}")
        _LOGGER.debug("***********************************************************")
        if self._on_message_callback:
            self._on_message_callback(message)
    
    def connect(self):
        """Connect to the mqtt broker"""    
        self._mqtt_client.connect(self._broker_url, self._port)
        self._mqtt_client.loop_start()

    def subscribe(self, topic:str) -> None:
        """Subscribe to topic on the broker"""
        self._mqtt_client.subscribe(topic)

class RequestsHandler:
    """Internal class to create FullyKiosk requests"""

    def __init__(self, session: aiohttp.ClientSession, host, port):
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
            except aiohttp.client_exceptions.ContentTypeError:
                data = await response.json(content_type="text/html")

            _LOGGER.debug(json.dumps(data))
            return data
        
