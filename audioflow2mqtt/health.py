"""Minimal HTTP health-check endpoint for container orchestration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audioflow2mqtt.config import Config
    from audioflow2mqtt.device import AudioflowDevice
    from audioflow2mqtt.mqtt import Mqtt

DEFAULT_STALENESS_SECONDS = 30


def evaluate_health(
    mqtt_connected: bool, devices: dict[str, dict], now: float, staleness_seconds: int = DEFAULT_STALENESS_SECONDS
) -> tuple[bool, list[str]]:
    """Evaluate gateway health from current state (pure, no I/O).

    Returns ``(healthy, issues)``: unhealthy if MQTT is disconnected, or if any
    device's last successful poll is older than ``staleness_seconds``.
    """
    issues = []
    if not mqtt_connected:
        issues.append("MQTT disconnected")
    for serial_no, info in devices.items():
        last_poll = info.get("last_poll_success")
        if last_poll is not None and now - last_poll > staleness_seconds:
            issues.append(f"Device {serial_no} ({info.get('ip_addr')}) unreachable")
    return (not issues, issues)


async def health_check_server(
    config: Config, device: AudioflowDevice, mqtt: Mqtt, staleness_seconds: int = DEFAULT_STALENESS_SECONDS
) -> None:
    """Serve a plain-text health endpoint on ``config.health_check_port``.

    Responds 200 when healthy and 503 (with a reason body) when not. The
    response is the same for any request path, so a container HEALTHCHECK can
    hit any URL.
    """

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            # Read (and discard) the request, but don't let a client that
            # connects and sends nothing hold the connection open indefinitely.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(reader.read(1024), timeout=5)
            now = time.monotonic()
            healthy, issues = evaluate_health(mqtt.connected, device.devices, now, staleness_seconds)
            if healthy:
                status_line = "HTTP/1.1 200 OK"
                body = "OK"
            else:
                status_line = "HTTP/1.1 503 Service Unavailable"
                body = "\n".join(issues)
            body_bytes = body.encode()
            response = (
                f"{status_line}\r\n"
                f"Content-Type: text/plain\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode() + body_bytes
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "0.0.0.0", config.health_check_port)
    logging.info(f"Health check endpoint listening on port {config.health_check_port}")
    async with server:
        await server.serve_forever()
