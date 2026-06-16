"""Configuration loading for audioflow2mqtt.

Configuration comes from a ``config.yaml`` file if present, otherwise from
environment variables. Loading is explicit (call ``load_config()``) rather than
a module-import side effect, so the rest of the package has no global state.
"""

import os
from dataclasses import dataclass

import yaml

VERSION = "0.8.1"


def env_to_bool(value: object, default: bool = True) -> bool:
    """Interpret an environment-variable string (or bool) as a boolean.

    Returns ``default`` when ``value`` is ``None`` (variable unset). Otherwise
    "false", "0", "no", "off" and "" (case-insensitive) are False; everything
    else is True.
    """
    if value is None:
        return default
    return str(value).strip().lower() not in ("false", "0", "no", "off", "")


@dataclass
class Config:
    """Resolved runtime configuration."""

    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None
    mqtt_qos: int = 1
    base_topic: str = "audioflow2mqtt"
    home_assistant: bool = True
    device_ips: list[str] | None = None
    log_level: str = "INFO"
    discovery_port: int = 54321
    health_check_port: int = 8080
    from_file: bool = False
    version: str = VERSION


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from ``config_path`` if it exists, else from the environment.

    ``device_ips`` is normalised to a list (or ``None``) regardless of source.
    """
    if os.path.exists(config_path):
        with open(config_path) as file:
            config = yaml.safe_load(file)
        mqtt = config["mqtt"]
        gen = config["general"]
        return Config(
            mqtt_host=mqtt.get("host"),
            mqtt_port=mqtt.get("port", 1883),
            mqtt_user=mqtt.get("user"),
            mqtt_password=mqtt.get("password"),
            mqtt_qos=mqtt.get("qos", 1),
            base_topic=mqtt.get("base_topic", "audioflow2mqtt"),
            home_assistant=mqtt.get("home_assistant", True),
            device_ips=gen.get("devices"),
            log_level=gen["log_level"].upper() if "log_level" in gen else "INFO",
            discovery_port=gen.get("discovery_port", 54321),
            health_check_port=gen.get("health_check_port", 8080),
            from_file=True,
        )

    device_ips_env = os.getenv("DEVICE_IPS") if os.getenv("DEVICE_IPS") is not None else os.getenv("DEVICES")
    return Config(
        mqtt_host=os.getenv("MQTT_HOST"),
        mqtt_port=int(os.getenv("MQTT_PORT", 1883)),
        mqtt_user=os.getenv("MQTT_USER"),
        mqtt_password=os.getenv("MQTT_PASSWORD"),
        mqtt_qos=int(os.getenv("MQTT_QOS", 1)),
        base_topic=os.getenv("BASE_TOPIC", "audioflow2mqtt"),
        home_assistant=env_to_bool(os.getenv("HOME_ASSISTANT"), True),
        device_ips=device_ips_env.split(",") if device_ips_env is not None else None,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        discovery_port=int(os.getenv("DISCOVERY_PORT", 54321)),
        health_check_port=int(os.getenv("HEALTH_CHECK_PORT", 8080)),
        from_file=False,
    )
