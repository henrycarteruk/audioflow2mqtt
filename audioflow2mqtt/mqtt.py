"""MQTT connection, subscription, discovery and command handling."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiomqtt

from audioflow2mqtt.parsing import parse_command_topic

if TYPE_CHECKING:
    from audioflow2mqtt.config import Config
    from audioflow2mqtt.device import AudioflowDevice


class Mqtt:
    def __init__(self, config: Config, device: AudioflowDevice) -> None:
        self.config = config
        self.device = device
        self.client: aiomqtt.Client | None = None
        self.connected = False
        self.reconnect_attempts = 0
        self.reconnect_interval = 10

    async def mqtt_connect(self, client: aiomqtt.Client) -> None:
        try:
            await client.publish(f"{self.config.base_topic}/status", "online", qos=1, retain=True)
            logging.info("Connected to MQTT broker.")
            self.connected = True
            self.reconnect_attempts = 0
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to connect to MQTT broker: {e}")
            self.connected = False

    async def mqtt_subscribe(self, client: aiomqtt.Client) -> None:
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

    async def start_mqtt_discovery(self, client: aiomqtt.Client) -> None:
        try:
            for serial_no in self.device.serial_nos:
                await self.device.mqtt_discovery(serial_no, client)
            logging.debug("Published Home Assistant MQTT discovery payloads.")
        except aiomqtt.MqttError as e:
            logging.error(f"Unable to publish MQTT discovery payload: {e}")

    async def mqtt_listener(self, client: aiomqtt.Client) -> None:
        try:
            async for msg in client.messages:
                payload = msg.payload.decode("utf-8")
                cmd = parse_command_topic(str(msg.topic), self.config.base_topic)
                if cmd is None:
                    continue
                serial_no = cmd["serial_no"]
                switch_no = cmd["switch_no"]
                if cmd["command"] == "set_zone_state":
                    if cmd["all_zones"]:  # no zone number present in topic
                        await self.device.set_all_zone_states(serial_no, payload)
                    elif switch_no is not None:
                        await self.device.set_zone_state(serial_no, switch_no, payload)
                elif cmd["command"] == "set_zone_enable" and switch_no is not None:
                    await self.device.set_zone_enable(serial_no, switch_no, payload)
                elif cmd["command"] == "reboot":
                    await self.device.reboot_device(serial_no)
        except aiomqtt.MqttError:
            self.connected = False

    async def mqtt_init(self) -> None:
        # main() exits if mqtt_host is unset, so it is always present here.
        assert self.config.mqtt_host is not None
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

    async def mqtt_reconnect(self) -> None:
        while True:
            await asyncio.sleep(self.reconnect_interval)
            if not self.connected:
                await self.mqtt_init()
                if not self.connected:
                    if self.reconnect_attempts < 12:
                        self.reconnect_attempts += 1
                    self.reconnect_interval = self.reconnect_attempts * 10
                    logging.error(f"Attempting to reconnect to MQTT broker in {self.reconnect_interval} seconds...")
