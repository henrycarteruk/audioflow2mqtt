"""Tests for configuration loading and coercion helpers in audioflow2mqtt."""

import pytest

from audioflow2mqtt import env_to_bool, load_config


class TestEnvToBool:
    @pytest.mark.parametrize("value", ["False", "false", "FALSE", "0", "no", "off", ""])
    def test_falsey_strings(self, value):
        assert env_to_bool(value, default=True) is False

    @pytest.mark.parametrize("value", ["True", "true", "1", "yes", "on", "anything"])
    def test_truthy_strings(self, value):
        assert env_to_bool(value, default=False) is True

    def test_unset_uses_default(self):
        # os.getenv returns None when the variable is unset.
        assert env_to_bool(None, default=True) is True
        assert env_to_bool(None, default=False) is False

    def test_whitespace_is_stripped(self):
        assert env_to_bool("  False  ", default=True) is False

    def test_regression_home_assistant_false_disables(self):
        # Regression for the bug where HOME_ASSISTANT=False (a non-empty string)
        # was always truthy, so HA discovery could never be disabled via env var.
        assert env_to_bool("False", default=True) is False


class TestLoadConfig:
    def test_from_yaml(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "mqtt:\n"
            "  host: 10.0.0.2\n"
            "  port: 1884\n"
            "  qos: 2\n"
            "  base_topic: myroom\n"
            "  home_assistant: False\n"
            "general:\n"
            "  devices:\n"
            "  - 10.0.1.100\n"
            "  - 10.0.1.101\n"
            "  log_level: warning\n"
            "  discovery_port: 12345\n"
        )
        cfg = load_config(str(config_path))
        assert cfg.from_file is True
        assert cfg.mqtt_host == "10.0.0.2"
        assert cfg.mqtt_port == 1884
        assert cfg.mqtt_qos == 2
        assert cfg.base_topic == "myroom"
        assert cfg.home_assistant is False
        assert cfg.device_ips == ["10.0.1.100", "10.0.1.101"]
        assert cfg.log_level == "WARNING"
        assert cfg.discovery_port == 12345

    def test_from_env_defaults_and_device_ip_split(self, monkeypatch):
        for var in ("MQTT_PORT", "MQTT_QOS", "BASE_TOPIC", "HOME_ASSISTANT", "DEVICES", "LOG_LEVEL", "DISCOVERY_PORT"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("MQTT_HOST", "broker.local")
        monkeypatch.setenv("DEVICE_IPS", "1.1.1.1,2.2.2.2")
        cfg = load_config("definitely-missing.yaml")
        assert cfg.from_file is False
        assert cfg.mqtt_host == "broker.local"
        assert cfg.device_ips == ["1.1.1.1", "2.2.2.2"]
        # Defaults when env vars are unset.
        assert cfg.mqtt_port == 1883
        assert cfg.base_topic == "audioflow2mqtt"
        assert cfg.home_assistant is True

    def test_env_missing_host_is_none(self, monkeypatch):
        monkeypatch.delenv("MQTT_HOST", raising=False)
        monkeypatch.delenv("DEVICE_IPS", raising=False)
        monkeypatch.delenv("DEVICES", raising=False)
        cfg = load_config("definitely-missing.yaml")
        assert cfg.mqtt_host is None
        assert cfg.device_ips is None
