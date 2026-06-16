"""Tests for AudioflowDevice behaviour that doesn't require a live device."""

import asyncio

from audioflow2mqtt import AudioflowDevice, Config


class _RaisingClient:
    """Stand-in httpx client whose GET always fails."""

    async def get(self, *args, **kwargs):
        raise Exception("connection refused")


def test_get_network_info_survives_request_failure():
    # Regression: a failed request used to fall through to json.loads on an
    # unset variable, raising UnboundLocalError and killing the poll loop.
    device = AudioflowDevice(Config(), http=_RaisingClient())
    serial = "0123456789"
    device.devices[serial] = {"device_url": "http://device/", "retry_count": 0}

    # Must return cleanly (no UnboundLocalError) so the poll loop survives.
    asyncio.run(device.get_network_info(serial))
