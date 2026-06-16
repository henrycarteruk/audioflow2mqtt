"""MQTT connection, subscription, discovery and command handling."""

import asyncio
import logging

import aiomqtt

from audioflow2mqtt.parsing import parse_command_topic


class Mqtt:
    def __init__(self, config, device):
        self.config = config
        self.device = device
        self.client = None
        self.connected = False
        self.reconnect_attempts = 0
        self.reconnect_interval = 10

    async def mqtt_connect(self, client):
        try:
            await client.publish(f"{self.config.base_topic}/status", "online", qos=1, retain=True)
            logging.info("Connected to MQTT broker.")
            self.connected = True
            self.reconnect_attempts = 0
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to connect to MQTT broker: {e}")
            self.connected = False

    async def mqtt_subscribe(self, client):
        try:
            for serial_no in self.device.serial_nos:
                await client.publish(
                    f"{self.config.base_topic}/{serial_no}/status", "online", qos=self.config.mqtt_qos, retain=True
                )
                await client.subscribe(f"{self.config.base_topic}/{serial_no}/#")
            logging.debug("Subscribed to MQTT topics.")
            self.connected = True
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to subscribe to MQTT topic: {e}")
            self.connected = False

    async def start_mqtt_discovery(self, client):
        try:
            for serial_no in self.device.serial_nos:
                await self.device.mqtt_discovery(serial_no, client)
            logging.debug("Published Home Assistant MQTT discovery payloads.")
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to publish MQTT discovery payload: {e}")

    async def mqtt_listener(self, client):
        try:
            async for msg in client.messages:
                payload = msg.payload.decode("utf-8")
                cmd = parse_command_topic(str(msg.topic), self.config.base_topic)
                if cmd is None:
                    continue
                if cmd["command"] == "set_zone_state":
                    if cmd["all_zones"]:  # no zone number present in topic
                        await self.device.set_all_zone_states(cmd["serial_no"], payload)
                    else:
                        await self.device.set_zone_state(cmd["serial_no"], cmd["switch_no"], payload)
                elif cmd["command"] == "set_zone_enable":
                    await self.device.set_zone_enable(cmd["serial_no"], cmd["switch_no"], payload)
        except aiomqtt.MqttError:
            self.connected = False

    async def mqtt_init(self):
        try:
            async with aiomqtt.Client(
                hostname=self.config.mqtt_host,
                port=self.config.mqtt_port,
                username=self.config.mqtt_user,
                password=self.config.mqtt_password,
                will=aiomqtt.Will(f"{self.config.base_topic}/status", "offline", 1, True),
            ) as client:
                self.client = client
                await self.mqtt_connect(client)
                await self.mqtt_subscribe(client)
                await self.start_mqtt_discovery(client)
                await self.mqtt_listener(client)
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to connect to MQTT broker: {e}")
        finally:
            self.client = None
            self.connected = False

    async def mqtt_reconnect(self):
        while True:
            await asyncio.sleep(self.reconnect_interval)
            if not self.connected:
                await self.mqtt_init()
                if not self.connected:
                    if self.reconnect_attempts < 12:
                        self.reconnect_attempts += 1
                    self.reconnect_interval = self.reconnect_attempts * 10
                    logging.error(f"Attempting to reconnect to MQTT broker in {self.reconnect_interval} seconds...")
