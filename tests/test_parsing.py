"""Unit tests for the pure parsing helpers in audioflow2mqtt."""

from audioflow2mqtt import parse_command_topic, parse_wifi_info

BASE_TOPIC = "audioflow2mqtt"
SERIAL = "0123456789"


class TestParseWifiInfo:
    def test_typical_string(self):
        assert parse_wifi_info("MyNetwork [6] (-45dBm)") == {
            "ssid": "MyNetwork",
            "channel": "6",
            "rssi": "-45",
        }

    def test_ssid_with_spaces(self):
        assert parse_wifi_info("My Home Wi-Fi [11] (-72dBm)") == {
            "ssid": "My Home Wi-Fi",
            "channel": "11",
            "rssi": "-72",
        }

    def test_malformed_input_does_not_raise(self):
        # No brackets at all: must return the three keys without throwing.
        result = parse_wifi_info("garbage with no brackets")
        assert set(result) == {"ssid", "channel", "rssi"}


class TestParseCommandTopic:
    def test_single_zone_state(self):
        topic = f"{BASE_TOPIC}/{SERIAL}/set_zone_state/2"
        assert parse_command_topic(topic, BASE_TOPIC) == {
            "command": "set_zone_state",
            "serial_no": SERIAL,
            "switch_no": "2",
            "all_zones": False,
        }

    def test_all_zones_state(self):
        # No trailing zone number -> all-zones command.
        topic = f"{BASE_TOPIC}/{SERIAL}/set_zone_state"
        cmd = parse_command_topic(topic, BASE_TOPIC)
        assert cmd["command"] == "set_zone_state"
        assert cmd["serial_no"] == SERIAL
        assert cmd["all_zones"] is True

    def test_set_zone_enable(self):
        topic = f"{BASE_TOPIC}/{SERIAL}/set_zone_enable/1"
        assert parse_command_topic(topic, BASE_TOPIC) == {
            "command": "set_zone_enable",
            "serial_no": SERIAL,
            "switch_no": "1",
            "all_zones": False,
        }

    def test_reboot(self):
        # Reboot has no "/set" segment, so the serial must come from the path.
        topic = f"{BASE_TOPIC}/{SERIAL}/reboot"
        assert parse_command_topic(topic, BASE_TOPIC) == {
            "command": "reboot",
            "serial_no": SERIAL,
            "switch_no": "t",
            "all_zones": False,
        }

    def test_non_command_topic_returns_none(self):
        # The gateway subscribes to the whole serial subtree, including the
        # state topics it publishes itself; those must be ignored.
        topic = f"{BASE_TOPIC}/{SERIAL}/zone_state/1"
        assert parse_command_topic(topic, BASE_TOPIC) is None

    def test_custom_base_topic(self):
        topic = f"livingroom/{SERIAL}/set_zone_state/3"
        cmd = parse_command_topic(topic, "livingroom")
        assert cmd["serial_no"] == SERIAL
        assert cmd["switch_no"] == "3"
        assert cmd["all_zones"] is False
