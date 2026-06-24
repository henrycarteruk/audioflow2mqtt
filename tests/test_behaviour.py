"""Behavioural tests for device HTTP methods and MQTT command routing.

These use fake http/mqtt clients (no network, no broker), made possible by
AudioflowDevice taking injectable ``http`` and ``mqtt`` references.
"""

import asyncio
import json

from audioflow2mqtt import AudioflowDevice, Config, Mqtt

SERIAL = "0123456789"


# --- fakes -----------------------------------------------------------------


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeHttp:
    """Records GET/PUT calls; GET returns canned text keyed by URL substring."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self._text(url))

    async def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return FakeResponse("")

    def _text(self, url):
        for key, text in self.responses.items():
            if key in url:
                return text
        return "{}"

    @property
    def puts(self):
        return [c for c in self.calls if c[0] == "PUT"]


class FailingHttp:
    async def get(self, *a, **k):
        raise Exception("boom")

    async def put(self, *a, **k):
        raise Exception("boom")


class FakePublisher:
    """Records intent calls instead of touching MQTT."""

    def __init__(self):
        self.zones = []  # (serial, zone, state, enabled)
        self.device_status = []  # (serial, online)
        self.network_info = []  # (serial, info)
        self.gateway_status = []  # online

    async def publish_zone(self, serial, zone, state, enabled):
        self.zones.append((serial, zone, state, enabled))

    async def publish_device_status(self, serial, online):
        self.device_status.append((serial, online))

    async def publish_network_info(self, serial, info):
        self.network_info.append((serial, info))

    async def publish_gateway_status(self, online):
        self.gateway_status.append(online)


def make_device(responses=None):
    device = AudioflowDevice(Config(), http=FakeHttp(responses))
    device.publisher = FakePublisher()
    return device


def add_device(device, zone_count=2, zones=None):
    zones = zones or [
        {"zone": 1, "name": "A", "state": "off", "enabled": 1},
        {"zone": 2, "name": "B", "state": "off", "enabled": 1},
    ]
    device.devices[SERIAL] = {
        "device_url": "http://device/",
        "ip_addr": "10.0.1.100",
        "zone_count": zone_count,
        "zones": {"zones": zones},
        "switch_names": ["A", "B"],
        "retry_count": 0,
    }


# --- set_zone_state --------------------------------------------------------


def test_set_zone_state_puts_and_republishes():
    after = json.dumps(
        {
            "zones": [
                {"zone": 1, "name": "A", "state": "on", "enabled": 1},
                {"zone": 2, "name": "B", "state": "off", "enabled": 1},
            ]
        }
    )
    device = make_device({"zones": after})
    add_device(device)
    asyncio.run(device.set_zone_state(SERIAL, "1", "on"))

    assert any(url.endswith("zones/1") and kw.get("content") == "1" for _, url, kw in device.http.puts)
    assert any(z[:3] == (SERIAL, "1", "on") for z in device.publisher.zones)


def test_set_zone_state_invalid_zone_no_put():
    device = make_device()
    add_device(device, zone_count=2)
    asyncio.run(device.set_zone_state(SERIAL, "5", "on"))
    assert device.http.puts == []


def test_set_zone_state_disabled_zone_no_put():
    zones = [
        {"zone": 1, "name": "A", "state": "off", "enabled": 0},
        {"zone": 2, "name": "B", "state": "off", "enabled": 1},
    ]
    device = make_device()
    add_device(device, zones=zones)
    asyncio.run(device.set_zone_state(SERIAL, "1", "on"))
    assert device.http.puts == []


# --- set_all_zone_states ---------------------------------------------------


def test_set_all_zone_states_on_puts_and_republishes():
    after = json.dumps(
        {
            "zones": [
                {"zone": 1, "name": "A", "state": "on", "enabled": 1},
                {"zone": 2, "name": "B", "state": "on", "enabled": 1},
            ]
        }
    )
    device = make_device({"zones": after})
    add_device(device)
    asyncio.run(device.set_all_zone_states(SERIAL, "on"))
    assert any(url.endswith("/zones") and kw.get("content") == "1 1 1 1" for _, url, kw in device.http.puts)


def test_set_all_zone_states_toggle_rejected():
    device = make_device()
    add_device(device)
    asyncio.run(device.set_all_zone_states(SERIAL, "toggle"))
    assert device.http.puts == []


# --- get_all_zones offline transition --------------------------------------


def test_get_all_zones_marks_offline_after_repeated_failure():
    device = AudioflowDevice(Config(), http=FailingHttp())
    device.publisher = FakePublisher()
    add_device(device)
    for _ in range(4):
        asyncio.run(device.get_all_zones(SERIAL))
    assert (SERIAL, False) in device.publisher.device_status, "device should be marked offline after repeated failures"


# --- reboot ----------------------------------------------------------------


def test_reboot_device_calls_reboot_now():
    device = make_device()
    add_device(device)
    asyncio.run(device.reboot_device(SERIAL))
    assert any(method == "GET" and url.endswith("reboot_now") for method, url, _ in device.http.calls)


# --- MQTT command routing --------------------------------------------------


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode()


class FakeBrokerClient:
    def __init__(self, messages):
        self._messages = messages

    @property
    def messages(self):
        return self._iter()

    async def _iter(self):
        for msg in self._messages:
            yield msg


class RecordingDevice:
    def __init__(self):
        self.calls = []

    async def set_zone_state(self, *a):
        self.calls.append(("set_zone_state", a))

    async def set_all_zone_states(self, *a):
        self.calls.append(("set_all_zone_states", a))

    async def set_zone_enable(self, *a):
        self.calls.append(("set_zone_enable", a))

    async def reboot_device(self, *a):
        self.calls.append(("reboot_device", a))


def test_mqtt_listener_routes_commands_and_ignores_others():
    device = RecordingDevice()
    mqtt = Mqtt(Config(), device, FakePublisher())
    messages = [
        FakeMessage(f"audioflow2mqtt/{SERIAL}/set_zone_state/2", "on"),
        FakeMessage(f"audioflow2mqtt/{SERIAL}/set_zone_state", "off"),
        FakeMessage(f"audioflow2mqtt/{SERIAL}/set_zone_enable/1", "1"),
        FakeMessage(f"audioflow2mqtt/{SERIAL}/reboot", "reboot"),
        FakeMessage(f"audioflow2mqtt/{SERIAL}/zone_state/1", "on"),  # not a command -> ignored
    ]
    asyncio.run(mqtt.mqtt_listener(FakeBrokerClient(messages)))

    assert [name for name, _ in device.calls] == [
        "set_zone_state",
        "set_all_zone_states",
        "set_zone_enable",
        "reboot_device",
    ]
    # single-zone state routed with the zone number; all-zones routed without one
    assert device.calls[0][1] == (SERIAL, "2", "on")
    assert device.calls[1][1] == (SERIAL, "off")
