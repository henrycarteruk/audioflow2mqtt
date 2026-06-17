# Audioflow to MQTT Gateway

audioflow2mqtt enables local control of your Audioflow speaker switch(es) via MQTT. It supports Home Assistant MQTT discovery for easy integration. It can also automatically discover the Audioflow devices on your network via UDP discovery, or you can specify the IP address of the Audioflow devices if you don't want to use UDP discovery.

<br>

# Configuration
audioflow2mqtt can be configured using environment variables or by using a configuration file named **config.yaml**. Example config.yaml with all possible configuration options:
```yaml
mqtt:
  host: 10.0.0.2
  port: 1883
  user: user
  password: password
  qos: 1
  base_topic: audioflow2mqtt
  home_assistant: True

general:
  devices:
  - 10.0.1.100
  - 10.0.1.101
  discovery_port: 54321
  health_check_port: 8080
  log_level: debug
```

**Configuration options:**

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MQTT_HOST` | None | True |IP address or hostname of the MQTT broker to connect to. |
| `MQTT_PORT` | 1883 | False | The port the MQTT broker is bound to. |
| `MQTT_USER` | None | False | The user to send to the MQTT broker. |
| `MQTT_PASSWORD` | None | False | The password to send to the MQTT broker. |
| `MQTT_QOS` | 1 | False | The MQTT QoS level. |
| `BASE_TOPIC` | audioflow2mqtt | False | The topic prefix to use for all payloads. |
| `HOME_ASSISTANT` | True | False | Set to `True` to enable Home Assistant MQTT discovery or `False` to disable. |
| `DEVICES` | None | Depends* | IP address(es) of your Audioflow device(s). If using environment variables, must be a comma-separated string (if multiple); otherwise, it must be a list. <br>\* Required if you don't plan to use UDP discovery. |
| `DISCOVERY_PORT` | 54321 | False | The port to open on the host to send/receive UDP discovery packets. |
| `HEALTH_CHECK_PORT` | 8080 | False | Port for the HTTP health-check endpoint (used by the Docker `HEALTHCHECK`). |
| `LOG_LEVEL` | info | False | Set minimum log level. Valid options are `debug`, `info`, `warning`, and `error` |

<br>

# How to run

The image is published to Docker Hub as **`henrycarteruk/audioflow2mqtt`**, tagged by version (e.g. `henrycarteruk/audioflow2mqtt:0.8.1`). You can also build it yourself with `make docker`.

**docker-compose with config.yaml**
```yaml
services:
  audioflow2mqtt:
    container_name: audioflow2mqtt
    image: henrycarteruk/audioflow2mqtt:0.8.1
    volumes:
    - /path/to/config.yaml:/config.yaml
    restart: unless-stopped
    network_mode: host # only required if you rely on UDP discovery (no device IPs set)
```

**docker-compose with environment variables** (no config.yaml)
```yaml
services:
  audioflow2mqtt:
    container_name: audioflow2mqtt
    image: henrycarteruk/audioflow2mqtt:0.8.1
    environment:
    - MQTT_HOST=10.0.0.2
    - MQTT_PORT=1883
    - MQTT_USER=user
    - MQTT_PASSWORD=password
    - MQTT_QOS=1
    - BASE_TOPIC=audioflow2mqtt
    - HOME_ASSISTANT=True
    - DEVICES=10.0.1.100,10.0.1.101
    - DISCOVERY_PORT=54321
    - HEALTH_CHECK_PORT=8080
    - LOG_LEVEL=debug
    - TZ=Europe/London # optional, but will ensure logging has local time instead of UTC (change to your timezone).
    restart: unless-stopped
    network_mode: host # only required if DEVICES is not set
```

Bring it up with `docker-compose up -d audioflow2mqtt`. The equivalent `docker run` works the same way — mount your `config.yaml` at `/config.yaml`, or pass the same values as `-e` variables, and add `--network host` if you rely on UDP discovery.

The container exposes an HTTP health endpoint on `HEALTH_CHECK_PORT` (default `8080`) and defines a Docker `HEALTHCHECK` against it, so orchestrators can detect an unhealthy gateway.

<br>

**Local (from source)**

Running from source uses [uv](https://docs.astral.sh/uv/) for dependency management and a `Makefile` for common tasks. Install uv first (see the [uv install docs](https://docs.astral.sh/uv/getting-started/installation/)), then:

1. Set the necessary environment variables or create `config.yaml`
2. `git clone https://github.com/henrycarteruk/audioflow2mqtt`
3. `cd audioflow2mqtt`
4. `make install` — create the virtualenv and install the pinned dependencies
5. `make run` — start the gateway

Other targets: `make lint`, `make format`, `make typecheck`, `make test`, `make coverage`, and `make docker` (build the image locally). Run `make` on its own to list them.

To catch lint/format issues before committing, install the git hooks once with `make hooks` (runs `ruff` on commit via [pre-commit](https://pre-commit.com/)).

<br>

# Home Assistant
audioflow2mqtt supports Home Assistant MQTT discovery which creates a Device for the Audioflow switch with the following:
- Switch entities for each zone
- Button entities to turn all zones on/off, plus a Reboot button
- Sensors for SSID, RSSI (signal strength), and Wi-Fi channel

![Home Assistant Device screenshot](ha_screenshot.png)

<br>

# MQTT topic structure and examples
The command topic syntax is `BASE_TOPIC/serial_number/command/zone_number` where `BASE_TOPIC` is the base topic you define, `serial_number` is the device serial number (found on the sticker on the bottom of the device), `command` is one of the below commands, and `zone_number` is the zone you want to control (zone A on the switch is zone number 1, zone B is zone number 2, and so on).

Valid commands are `set_zone_state`, `set_zone_enable`, and `reboot`. The examples below assume the base topic is the default (`audioflow2mqtt`) and the serial number is `0123456789`.

**Turn zone B (zone number 2) on or off, or toggle between states**

Topic: `audioflow2mqtt/0123456789/set_zone_state/2`

Valid payloads: `on`, `off`, `toggle`

**Turn all zones on or off**

Topic: `audioflow2mqtt/0123456789/set_zone_state` (note the lack of a zone number at the end of the topic)

Valid payloads: `on`, `off`

**Enable or disable zone A (zone number 1)**
_This might not really be something you would need, but I figured I'd add it anyway_

Topic: `audioflow2mqtt/0123456789/set_zone_enable/1`

Valid payloads: `1` for enabled, `0` for disabled

**Reboot the device**

Topic: `audioflow2mqtt/0123456789/reboot`

Valid payload: `reboot` (any message on this topic triggers a reboot)

<br>

When the zone state or enabled/disabled status is changed, audioflow2mqtt publishes the result to the following topics:

**Zone state:** `audioflow2mqtt/0123456789/zone_state/ZONE`

**Zone enabled/disabled:** `audioflow2mqtt/0123456789/zone_enabled/ZONE`

<br>

Network info is published to the following topics:

**SSID:** `audioflow2mqtt/0123456789/network_info/ssid`

**Wi-fi channel:** `audioflow2mqtt/0123456789/network_info/channel`

**RSSI:** `audioflow2mqtt/0123456789/network_info/rssi`

<br>

# Important notes
When running separate instances for multiple devices, you will need to set a **different base topic for each instance**. Also, while audioflow2mqtt does support UDP discovery of Audioflow devices, creating a DHCP reservation for your Audioflow device(s) and setting `DEVICES` is recommended. UDP discovery will only work if the Audioflow device is on the same subnet as the machine audioflow2mqtt is running on.

<br>
<a href="https://www.buymeacoffee.com/tediore" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

<br>

# TODO
1. ~~Handle Audioflow device disconnects/reconnects~~
2. Add support for re-discovery of Audioflow switch if its IP address changes
3. ~~Add support for multiple Audioflow switches? Not sure how many people would have more than one.~~
4. You tell me!
