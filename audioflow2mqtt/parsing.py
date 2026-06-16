"""Pure parsing helpers (no network or MQTT side effects)."""

from typing import TypedDict


class Command(TypedDict):
    """A parsed MQTT command and its target."""

    command: str
    serial_no: str
    switch_no: str | None
    all_zones: bool


def parse_wifi_info(wifi: str) -> dict[str, str]:
    """Parse the device's wifi status string into ssid/channel/rssi."""
    ssid = wifi[: wifi.find("[")].strip()
    channel = wifi[wifi.find("[") + 1 : wifi.find("]")].strip()
    rssi = wifi[wifi.find("]") + 3 :].replace("dBm", "").replace(")", "").strip()
    return {"ssid": ssid, "channel": channel, "rssi": rssi}


def parse_command_topic(topic: str, base_topic: str) -> Command | None:
    """Parse an MQTT command topic into the command and its target.

    Topics look like ``BASE_TOPIC/<serial>/<command>[/<zone>]``. Returns a
    ``Command`` dict, or ``None`` if the topic is not a recognised command.
    ``all_zones`` is only meaningful for ``set_zone_state`` (a topic with no
    trailing zone number).
    """
    # Split the path after the base topic into its segments so command matching
    # is exact (a base topic containing a command-like word can't misfire) and
    # works for any command, including those without a "/set" segment.
    remainder = topic[topic.find(base_topic) + len(base_topic) + 1 :]
    parts = remainder.split("/")
    serial_no = parts[0]
    command = parts[1] if len(parts) > 1 else ""
    switch_no = parts[2] if len(parts) > 2 else None
    if command == "set_zone_state":
        return Command(command="set_zone_state", serial_no=serial_no, switch_no=switch_no, all_zones=switch_no is None)
    if command == "set_zone_enable":
        return Command(command="set_zone_enable", serial_no=serial_no, switch_no=switch_no, all_zones=False)
    if command == "reboot":
        return Command(command="reboot", serial_no=serial_no, switch_no=switch_no, all_zones=False)
    return None
