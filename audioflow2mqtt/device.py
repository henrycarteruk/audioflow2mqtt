"""Audioflow device HTTP communication and MQTT publishing."""

import asyncio
import json
import logging
import time

from audioflow2mqtt.parsing import parse_wifi_info


class AudioflowDevice:
    def __init__(self, config, mqtt=None, http=None):
        self.config = config
        self.mqtt = mqtt  # set by the caller after the Mqtt instance is created
        self.http = http  # shared httpx.AsyncClient, set by the caller in main()
        self.timeout = 3
        self.states = ["off", "on"]
        self.set_all_zones = {"off": "0 0 0 0", "on": "1 1 1 1"}
        self.devices = {}
        self.serial_nos = []

    async def get_device_info(self, device_url, ip, nwk_discovery):
        """Get info about Audioflow device(s)"""
        device = True
        zone_list = ["A", "B", "C", "D"]
        try:
            logging.debug(f"Attempting to connect to {ip}...")
            device_info = await self.http.get(url=device_url + "switch", timeout=self.timeout)
            logging.debug(f"Connected to {ip}.")
        except Exception as e:
            logging.error(f"Unable to connect to {ip}: {e}")
            device = False

        if device:
            device_info = json.loads(device_info.text)
            serial_no = device_info["serial"]
            model = device_info["model"]
            name = device_info["name"]
            self.devices[serial_no] = {}
            self.devices[serial_no]["device_url"] = device_url
            self.devices[serial_no]["ip_addr"] = ip
            self.devices[serial_no]["zones"] = {}
            self.devices[serial_no]["switch_names"] = []
            self.devices[serial_no]["retry_count"] = 0
            self.devices[serial_no]["last_poll_success"] = time.monotonic()
            self.serial_nos.append(serial_no)

            self.devices[serial_no].update(device_info)

            zone_info = await self.http.get(url=device_url + "zones", timeout=self.timeout)
            zone_info = json.loads(zone_info.text)
            self.devices[serial_no]["zone_info"] = zone_info
            zone_count = len(zone_info["zones"])
            self.devices[serial_no]["zone_count"] = zone_count

            message = "discovered at " if nwk_discovery else "found at "
            message += f"{ip}"
            logging.info(f"Audioflow model {model} with name {name} and serial number {serial_no} {message}")

            for x in range(zone_count):
                zone_name = zone_info["zones"][int(x)]["name"]
                self.devices[serial_no]["zones"][x] = zone_name
                if zone_name == "":
                    zone_name = f"Zone {zone_list[x]}"
                self.devices[serial_no]["switch_names"].append(zone_name)

            self.devices[serial_no]["zones"] = zone_info

            logging.debug(self.devices[serial_no])

    async def get_network_info(self, serial_no):
        """
        Get SSID and device signal strength
        String parsing :(
        """
        device_url = self.devices[serial_no]["device_url"]
        retry_count = self.devices[serial_no]["retry_count"]
        if not retry_count:
            try:
                device_info = await self.http.get(url=device_url + "switch", timeout=self.timeout)
            except Exception as e:
                logging.error(f"Unable to get network info: {e}")
                return  # skip this cycle; the next poll will retry
            device_info = json.loads(device_info.text)
            network_info = parse_wifi_info(device_info["wifi"])

            if self.mqtt.connected:
                try:
                    for x in network_info:
                        await self.mqtt.client.publish(
                            f"{self.config.base_topic}/{serial_no}/network_info/{x}",
                            network_info[x],
                            qos=self.config.mqtt_qos,
                        )
                except Exception as e:
                    logging.error(f"Unable to publish network info: {e}")

    async def get_one_zone(self, serial_no, zone_no):
        """Get info about one zone and publish to MQTT"""
        device_url = self.devices[serial_no]["device_url"]
        try:
            zones = await self.http.get(url=device_url + "zones", timeout=self.timeout)
            self.devices[serial_no]["zones"] = json.loads(zones.text)
        except Exception as e:
            logging.error(f"Unable to get zone info: {e}")

        if self.mqtt.connected:
            try:
                zones = self.devices[serial_no]["zones"]["zones"]
                await self.mqtt.client.publish(
                    f"{self.config.base_topic}/{serial_no}/zone_state/{zone_no}",
                    str(zones[int(zone_no) - 1]["state"]),
                    qos=self.config.mqtt_qos,
                )
                await self.mqtt.client.publish(
                    f"{self.config.base_topic}/{serial_no}/zone_enabled/{zone_no}",
                    str(zones[int(zone_no) - 1]["enabled"]),
                    qos=self.config.mqtt_qos,
                )
            except Exception as e:
                logging.error(f"Unable to publish zone state: {e}")

    async def get_all_zones(self, serial_no):
        """Get info about all zones"""
        device_url = self.devices[serial_no]["device_url"]
        ip = self.devices[serial_no]["ip_addr"]
        retry_count = self.devices[serial_no]["retry_count"]
        try:
            zones = await self.http.get(url=device_url + "zones", timeout=self.timeout)
            self.devices[serial_no]["zones"] = json.loads(zones.text)
            await self.publish_all_zones(serial_no)
            if retry_count > 0:
                logging.info(f"Reconnected to Audioflow device at {ip}.")
            self.devices[serial_no]["retry_count"] = 0
            self.devices[serial_no]["last_poll_success"] = time.monotonic()
            if self.mqtt.connected:
                await self.mqtt.client.publish(
                    f"{self.config.base_topic}/{serial_no}/status", "online", qos=self.config.mqtt_qos, retain=True
                )
        except Exception as e:
            if retry_count < 3:
                logging.error(f"Unable to communicate with Audioflow device at {ip}: {e}")
            self.devices[serial_no]["retry_count"] += 1
            if retry_count == 3:
                if self.mqtt.connected:
                    await self.mqtt.client.publish(
                        f"{self.config.base_topic}/{serial_no}/status",
                        "offline",
                        qos=self.config.mqtt_qos,
                        retain=True,
                    )
                logging.warning(f"Audioflow device at {ip} unreachable; marking as offline.")
                logging.warning(f"Trying to reconnect to {ip} every 10 sec in the background...")

    async def publish_all_zones(self, serial_no):
        """Publish info about all zones to MQTT"""
        zone_count = self.devices[serial_no]["zone_count"]
        zones = self.devices[serial_no]["zones"]["zones"]
        if self.mqtt.connected:
            try:
                for x in range(1, zone_count + 1):
                    await self.mqtt.client.publish(
                        f"{self.config.base_topic}/{serial_no}/zone_state/{x}",
                        str(zones[int(x) - 1]["state"]),
                        qos=self.config.mqtt_qos,
                    )
                    await self.mqtt.client.publish(
                        f"{self.config.base_topic}/{serial_no}/zone_enabled/{x}",
                        str(zones[int(x) - 1]["enabled"]),
                        qos=self.config.mqtt_qos,
                    )
            except Exception as e:
                logging.error(f"Unable to publish all zone states: {e}")

    async def set_zone_state(self, serial_no, zone_no, zone_state):
        """Change state of one zone"""
        zone_count = self.devices[serial_no]["zone_count"]
        zones = self.devices[serial_no]["zones"]["zones"]
        device_url = self.devices[serial_no]["device_url"]
        ip = self.devices[serial_no]["ip_addr"]
        if int(zone_no) > zone_count:
            logging.warning(f"{zone_no} is an invalid zone number.")
        elif zones[int(zone_no) - 1]["enabled"] == 0:
            logging.warning(f"Zone {zone_no} is disabled.")
        else:
            if zone_state in ["on", "off", "toggle"]:
                try:
                    current_state = zones[int(zone_no) - 1]["state"]
                    if zone_state in self.states:
                        data = self.states.index(zone_state)
                    else:
                        data = 1 if current_state == "off" else 0
                    await self.http.put(url=device_url + "zones/" + str(zone_no), data=str(data), timeout=self.timeout)
                    await self.get_one_zone(
                        serial_no, zone_no
                    )  # Device does not send new state after state change, so we get the new state and publish it to MQTT
                except Exception as e:
                    logging.error(f"Set zone state for device at {ip} failed: {e}")
            else:
                logging.warning(f'"{zone_state}" is not a valid command. Valid commands are on, off, toggle')

    async def set_all_zone_states(self, serial_no, zone_state):
        """Turn all zones on or off"""
        device_url = self.devices[serial_no]["device_url"]
        ip = self.devices[serial_no]["ip_addr"]
        if zone_state in self.states:
            try:
                data = self.set_all_zones[zone_state]
                await self.http.put(url=device_url + "zones", data=str(data), timeout=self.timeout)
                # Device does not send new state after state change, so we get the new state and publish it to MQTT
                await self.get_all_zones(serial_no)
            except Exception as e:
                logging.error(f"Set all zone states for device at {ip} failed: {e}")
        elif zone_state == "toggle":
            logging.warning("Toggle command can only be used for one zone.")
        else:
            logging.warning(f'"{zone_state}" is not a valid command. Valid commands are on, off')

    async def set_zone_enable(self, serial_no, zone_no, zone_enable):
        """Enable or disable zone"""
        device_url = self.devices[serial_no]["device_url"]
        switch_names = self.devices[serial_no]["switch_names"]
        ip = self.devices[serial_no]["ip_addr"]
        if int(zone_enable) in [0, 1]:
            try:
                # Audioflow device expects the zone name in the same payload when enabling/disabling zone, so we append the existing name here
                await self.http.put(
                    url=device_url + "zonename/" + str(zone_no),
                    data=str(str(zone_enable) + str(switch_names[int(zone_no) - 1]).strip()),
                    timeout=self.timeout,
                )
                await self.get_one_zone(serial_no, zone_no)
            except Exception as e:
                logging.error(f"Enable/disable zone for device at {ip} failed: {e}")

    async def reboot_device(self, serial_no):
        """Reboot the Audioflow device via the GET /reboot_now endpoint"""
        device_url = self.devices[serial_no]["device_url"]
        ip = self.devices[serial_no]["ip_addr"]
        try:
            await self.http.get(url=device_url + "reboot_now", timeout=self.timeout)
            logging.info(f"Reboot command sent to Audioflow device at {ip}.")
        except Exception as e:
            logging.error(f"Reboot command for device at {ip} failed: {e}")

    async def poll_device_state(self, serial_no):
        """Poll for Audioflow device information every 10 seconds in case button(s) is/are pressed on device"""
        while True:
            await asyncio.sleep(10)
            await self.get_all_zones(serial_no)

    async def poll_network_info(self, serial_no):
        """Poll for Audioflow device network information every 60 seconds"""
        while True:
            await asyncio.sleep(60)
            await self.get_network_info(serial_no)

    async def mqtt_discovery(self, serial_no, client):
        """Send Home Assistant MQTT discovery payloads"""
        if self.config.home_assistant:
            base_topic = self.config.base_topic
            zone_count = self.devices[serial_no]["zone_count"]
            zone_info = self.devices[serial_no]["zone_info"]["zones"]
            name = self.devices[serial_no]["name"]
            model = self.devices[serial_no]["model"]
            fw_version = self.devices[serial_no]["version"]
            switch_names = self.devices[serial_no]["switch_names"]
            ha_switch = "homeassistant/switch/"
            ha_button = "homeassistant/button/"
            ha_sensor = "homeassistant/sensor/"
            try:
                # HA switch entities
                for x in range(1, zone_count + 1):
                    name_suffix = (
                        " (Disabled)" if zone_info[int(x) - 1]["enabled"] == 0 else ""
                    )  # append "(Disabled)" to the end of the default entity name if zone is disabled
                    entity_name = f"{switch_names[x - 1]} speakers{name_suffix}"
                    entity_id = f"switch.{entity_name.replace(' ', '_').lower()}_{serial_no}"
                    await client.publish(
                        f"{ha_switch}{serial_no}/{x}/config",
                        json.dumps(
                            {
                                "availability": [
                                    {"topic": f"{base_topic}/status"},
                                    {"topic": f"{base_topic}/{serial_no}/status"},
                                ],
                                "name": entity_name,
                                "default_entity_id": entity_id,
                                "command_topic": f"{base_topic}/{serial_no}/set_zone_state/{x}",
                                "state_topic": f"{base_topic}/{serial_no}/zone_state/{x}",
                                "payload_on": "on",
                                "payload_off": "off",
                                "unique_id": f"{serial_no}{x}",
                                "icon": "mdi:speaker",
                                "device": {
                                    "name": f"{name}",
                                    "identifiers": f"{serial_no}",
                                    "manufacturer": "Audioflow",
                                    "model": f"{model}",
                                    "sw_version": f"{fw_version}",
                                },
                                "platform": "mqtt",
                            }
                        ),
                        qos=1,
                        retain=True,
                    )

                # HA button entities
                for x in ["off", "on"]:
                    entity_name = f"Turn all zones {x}"
                    entity_id = f"button.{entity_name.replace(' ', '_').lower()}_{serial_no}"
                    await client.publish(
                        f"{ha_button}{serial_no}/all_zones_{x}/config",
                        json.dumps(
                            {
                                "availability": [
                                    {"topic": f"{base_topic}/status"},
                                    {"topic": f"{base_topic}/{serial_no}/status"},
                                ],
                                "name": entity_name,
                                "default_entity_id": entity_id,
                                "command_topic": f"{base_topic}/{serial_no}/set_zone_state",
                                "payload_press": x,
                                "unique_id": f"{serial_no}_all_zones_{x}",
                                "icon": f"mdi:power-{x}",
                                "device": {
                                    "name": f"{name}",
                                    "identifiers": f"{serial_no}",
                                    "manufacturer": "Audioflow",
                                    "model": f"{model}",
                                    "sw_version": f"{fw_version}",
                                },
                                "platform": "mqtt",
                            }
                        ),
                        qos=1,
                        retain=True,
                    )

                # HA button entity - reboot
                await client.publish(
                    f"{ha_button}{serial_no}/reboot/config",
                    json.dumps(
                        {
                            "availability": [
                                {"topic": f"{base_topic}/status"},
                                {"topic": f"{base_topic}/{serial_no}/status"},
                            ],
                            "name": "Reboot",
                            "default_entity_id": f"button.reboot_{serial_no}",
                            "command_topic": f"{base_topic}/{serial_no}/reboot",
                            "payload_press": "reboot",
                            "unique_id": f"{serial_no}_reboot",
                            "icon": "mdi:restart",
                            "device": {
                                "name": f"{name}",
                                "identifiers": f"{serial_no}",
                                "manufacturer": "Audioflow",
                                "model": f"{model}",
                                "sw_version": f"{fw_version}",
                            },
                            "platform": "mqtt",
                        }
                    ),
                    qos=1,
                    retain=True,
                )

                # HA sensor entities
                network_info_names = {
                    "ssid": {"name": "SSID", "icon": "mdi:access-point-network"},
                    "channel": {"name": "Wi-Fi channel", "icon": "mdi:access-point"},
                    "rssi": {"name": "RSSI", "icon": "mdi:signal"},
                }
                for x in network_info_names:
                    entity_name = f"{network_info_names[x]['name']}"
                    entity_id = f"sensor.{entity_name.replace(' ', '_').lower()}_{serial_no}"
                    await client.publish(
                        f"{ha_sensor}{serial_no}/{x}/config",
                        json.dumps(
                            {
                                "availability": [
                                    {"topic": f"{base_topic}/status"},
                                    {"topic": f"{base_topic}/{serial_no}/status"},
                                ],
                                "name": entity_name,
                                "default_entity_id": entity_id,
                                "state_topic": f"{base_topic}/{serial_no}/network_info/{x}",
                                "icon": f"{network_info_names[x]['icon']}",
                                "unique_id": f"{serial_no}{x}",
                                "device": {
                                    "name": f"{name}",
                                    "identifiers": f"{serial_no}",
                                    "manufacturer": "Audioflow",
                                    "model": f"{model}",
                                    "sw_version": f"{fw_version}",
                                },
                                "platform": "mqtt",
                            }
                        ),
                        qos=1,
                        retain=True,
                    )

            except Exception as e:
                logging.error(f"Unable to publish Home Assistant MQTT discovery payloads: {e}")
