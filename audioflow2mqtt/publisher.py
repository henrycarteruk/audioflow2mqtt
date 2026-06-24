"""The Publisher seam: all outbound MQTT.

Owns the topic structure, QoS, and retain flags for every message the gateway
sends. The live aiomqtt client is bound by Mqtt on (re)connect and cleared on
disconnect; while no client is bound, every publish is a silent no-op — the
same behaviour as the old "skip publishing when disconnected" guards.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiomqtt

    from audioflow2mqtt.config import Config


class Publisher:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client: aiomqtt.Client | None = None

    def bind(self, client: aiomqtt.Client | None) -> None:
        """Attach (or, with None, detach) the live MQTT client. Called by Mqtt."""
        self._client = client

    async def _publish(self, topic: str, payload: str, *, qos: int, retain: bool) -> None:
        if self._client is None:
            return
        try:
            await self._client.publish(topic, payload, qos=qos, retain=retain)
        except Exception as e:
            logging.error(f"Unable to publish to {topic}: {e}")

    async def publish_gateway_status(self, online: bool) -> None:
        await self._publish(f"{self.config.base_topic}/status", "online" if online else "offline", qos=1, retain=True)

    async def publish_device_status(self, serial: str, online: bool) -> None:
        await self._publish(
            f"{self.config.base_topic}/{serial}/status",
            "online" if online else "offline",
            qos=self.config.mqtt_qos,
            retain=True,
        )

    async def publish_zone(self, serial: str, zone: int | str, state: object, enabled: object) -> None:
        base = self.config.base_topic
        qos = self.config.mqtt_qos
        await self._publish(f"{base}/{serial}/zone_state/{zone}", str(state), qos=qos, retain=False)
        await self._publish(f"{base}/{serial}/zone_enabled/{zone}", str(enabled), qos=qos, retain=False)

    async def publish_network_info(self, serial: str, info: dict[str, str]) -> None:
        base = self.config.base_topic
        for key, value in info.items():
            await self._publish(f"{base}/{serial}/network_info/{key}", value, qos=self.config.mqtt_qos, retain=False)
