"""Application entry point: load config, wire components, run the event loop."""

import asyncio
import logging
import sys
from threading import Thread

import httpx

from audioflow2mqtt.config import load_config
from audioflow2mqtt.device import AudioflowDevice
from audioflow2mqtt.discovery import NetworkDiscovery
from audioflow2mqtt.health import health_check_server
from audioflow2mqtt.mqtt import Mqtt


class HttpxGetFilter(logging.Filter):
    """Drop the noisy per-request ``HTTP Request: GET ...`` lines httpx emits.

    The frequent zone/network polls would otherwise flood the logs at INFO.
    """

    def filter(self, record):
        return "HTTP Request: GET " not in record.getMessage()


async def main():
    config = load_config()

    valid_log_levels = ["debug", "info", "warning", "error"]
    log_level_invalid = config.log_level.lower() not in valid_log_levels
    logging.basicConfig(
        level="INFO" if log_level_invalid else config.log_level, format="%(asctime)s %(levelname)s: %(message)s"
    )
    if log_level_invalid:
        logging.warning(f'Selected log level "{config.log_level}" is not valid; using default (info)')

    # Quiet httpx's per-request GET logging unless the user actually wants DEBUG.
    if config.log_level.upper() != "DEBUG":
        logging.getLogger("httpx").addFilter(HttpxGetFilter())

    logging.info(f"=== audioflow2mqtt version {config.version} started ===")

    if config.from_file:
        logging.info("Configuration file found.")
    else:
        logging.info("No configuration file found; loading environment variables.")

    if config.mqtt_host is None:
        logging.error("Please specify the IP address or hostname of your MQTT broker.")
        logging.error("Exiting...")
        sys.exit(1)

    device = AudioflowDevice(config)
    mqtt = Mqtt(config, device)
    device.mqtt = mqtt
    discovery = NetworkDiscovery(config.discovery_port)

    if config.device_ips is not None:
        nwk_discovery = False
        device_ips = config.device_ips
        s = "s" if len(device_ips) > 1 else ""
        logging.info(f"Device IP{s} set; network discovery is disabled.")
    else:
        nwk_discovery = True

    if nwk_discovery:
        device_ips = []
        logging.info("No device IPs set; network discovery is enabled.")
        nwk_discover_rx = Thread(target=discovery.nwk_discover_receive, daemon=True)
        nwk_discover_rx.start()
        discovery.nwk_discover_send()
        if discovery.discovered_devices:
            device_ips = discovery.discovered_devices
            logging.info("Network discovery stopped")
            discovery.sock.close()
        else:
            logging.error("No Audioflow devices found.")
            logging.error(
                "Confirm that you have host networking enabled and that the Audioflow device is on the same subnet."
            )
            discovery.sock.close()
            sys.exit(1)

    async with httpx.AsyncClient() as httpx_async:
        device.http = httpx_async
        for ip in device_ips:
            device_url = f"http://{ip}/"
            await device.get_device_info(device_url, ip, nwk_discovery)
        device_state_polling = [device.poll_device_state(serial_no) for serial_no in device.serial_nos]
        network_info_polling = [device.poll_network_info(serial_no) for serial_no in device.serial_nos]

        await asyncio.gather(
            mqtt.mqtt_init(),
            *device_state_polling,
            *network_info_polling,
            mqtt.mqtt_reconnect(),
            health_check_server(config, device, mqtt),
        )
