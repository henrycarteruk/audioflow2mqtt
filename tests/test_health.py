"""Tests for the health-check evaluation logic."""

from audioflow2mqtt import evaluate_health

NOW = 1000.0


def _device(last_poll_success, ip="10.0.1.100"):
    return {"ip_addr": ip, "last_poll_success": last_poll_success}


class TestEvaluateHealth:
    def test_healthy_when_connected_and_fresh(self):
        devices = {"0123456789": _device(NOW - 5)}
        healthy, issues = evaluate_health(True, devices, NOW, staleness_seconds=30)
        assert healthy is True
        assert issues == []

    def test_unhealthy_when_mqtt_disconnected(self):
        devices = {"0123456789": _device(NOW - 5)}
        healthy, issues = evaluate_health(False, devices, NOW, staleness_seconds=30)
        assert healthy is False
        assert "MQTT disconnected" in issues

    def test_unhealthy_when_device_poll_stale(self):
        devices = {"0123456789": _device(NOW - 60)}
        healthy, issues = evaluate_health(True, devices, NOW, staleness_seconds=30)
        assert healthy is False
        assert any("0123456789" in i and "10.0.1.100" in i for i in issues)

    def test_device_without_poll_timestamp_is_ignored(self):
        # A device that has never recorded a successful poll is not flagged stale.
        devices = {"0123456789": _device(None)}
        healthy, issues = evaluate_health(True, devices, NOW, staleness_seconds=30)
        assert healthy is True
        assert issues == []

    def test_multiple_issues_reported_together(self):
        devices = {"AAA": _device(NOW - 60), "BBB": _device(NOW - 1)}
        healthy, issues = evaluate_health(False, devices, NOW, staleness_seconds=30)
        assert healthy is False
        assert "MQTT disconnected" in issues
        assert any("AAA" in i for i in issues)
        assert not any("BBB" in i for i in issues)
