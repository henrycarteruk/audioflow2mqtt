"""Tests for the httpx log filter."""

import logging

from audioflow2mqtt.app import HttpxGetFilter


def _record(msg):
    return logging.LogRecord("httpx", logging.INFO, __file__, 1, msg, None, None)


class TestHttpxGetFilter:
    def test_drops_get_request_lines(self):
        f = HttpxGetFilter()
        assert f.filter(_record('HTTP Request: GET http://device/switch "HTTP/1.1 200 OK"')) is False

    def test_keeps_non_get_request_lines(self):
        f = HttpxGetFilter()
        # PUT requests (zone changes) and ordinary messages must still appear.
        assert f.filter(_record('HTTP Request: PUT http://device/zones "HTTP/1.1 200 OK"')) is True
        assert f.filter(_record("Connected to MQTT broker.")) is True
