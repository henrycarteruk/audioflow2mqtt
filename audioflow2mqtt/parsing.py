"""Pure parsing helpers (no network or MQTT side effects)."""


def parse_wifi_info(wifi):
    """Parse the device's wifi status string into ssid/channel/rssi."""
    ssid = wifi[: wifi.find("[")].strip()
    channel = wifi[wifi.find("[") + 1 : wifi.find("]")].strip()
    rssi = wifi[wifi.find("]") + 3 :].replace("dBm", "").replace(")", "").strip()
    return {"ssid": ssid, "channel": channel, "rssi": rssi}


def parse_command_topic(topic, base_topic):
    """Parse an MQTT command topic into the command and its target.

    Topics look like ``BASE_TOPIC/<serial>/<command>[/<zone>]``. Returns a dict
    with ``command``, ``serial_no``, ``switch_no`` and ``all_zones``, or ``None``
    if the topic is not a recognised command. ``all_zones`` is only meaningful
    for ``set_zone_state`` (a topic with no trailing zone number).
    """
    # The serial number is the path segment immediately after the base topic.
    # Derive it from the path (not from the position of "/set") so it works for
    # every command, including those without a "/set" segment such as reboot.
    remainder = topic[topic.find(base_topic) + len(base_topic) + 1 :]
    serial_no = remainder.split("/")[0]
    switch_no = topic[-1:]
    if "set_zone_state" in topic:
        return {
            "command": "set_zone_state",
            "serial_no": serial_no,
            "switch_no": switch_no,
            "all_zones": topic.endswith("e"),
        }
    if "set_zone_enable" in topic:
        return {
            "command": "set_zone_enable",
            "serial_no": serial_no,
            "switch_no": switch_no,
            "all_zones": False,
        }
    if topic.endswith("/reboot"):
        return {
            "command": "reboot",
            "serial_no": serial_no,
            "switch_no": switch_no,
            "all_zones": False,
        }
    return None
