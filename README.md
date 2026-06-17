# Audioflow to MQTT Gateway

audioflow2mqtt enables local control of your Audioflow speaker switch(es) via MQTT. It supports Home Assistant MQTT discovery for easy integration. It can also automatically discover the Audioflow devices on your network via UDP discovery, or you can specify the IP address of the Audioflow devices if you don't want to use UDP discovery.

<br>

# Configuration
audioflow2mqtt is configured with a **config.yaml** file or with environment variables. The two are mutually exclusive. If a `config.yaml` is present in the working directory (mounted at `/config.yaml` in the container) it is used and environment variables are ignored; otherwise configuration comes entirely from the environment. Example config.yaml with all possible configuration options:
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
| `DEVICES` | None | False | By default the gateway finds your Audioflow device(s) automatically via UDP discovery. Set this to **disable UDP discovery** and use the supplied IP address(es) instead. If using environment variables, must be a comma-separated string (if multiple); otherwise, it must be a list. |
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

Bring it up with `docker-compose up -d audioflow2mqtt`. The equivalent `docker run` works the same way: mount your `config.yaml` at `/config.yaml`, or pass the same values as `-e` variables, and add `--network host` if you rely on UDP discovery.

The container exposes an HTTP health endpoint on `HEALTH_CHECK_PORT` (default `8080`) and defines a Docker `HEALTHCHECK` against it, so orchestrators can detect an unhealthy gateway.

<br>

**Local (from source)**

Running from source uses [uv](https://docs.astral.sh/uv/) for dependency management and a `Makefile` for common tasks. Install uv first (see the [uv install docs](https://docs.astral.sh/uv/getting-started/installation/)), then:

1. Set the necessary environment variables or create `config.yaml`
2. `git clone https://github.com/henrycarteruk/audioflow2mqtt`
3. `cd audioflow2mqtt`
4. `make install`: create the virtualenv and install the pinned dependencies
5. `make run`: start the gateway

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

# MQTT topic structure

All topics are prefixed with your `BASE_TOPIC` (default `audioflow2mqtt`). The examples below use the default base topic and the serial number `0123456789` (found on the sticker on the bottom of the device). Zones are numbered A = 1, B = 2, and so on.

## Commands you send

Publish to these topics to control a device. Per-zone commands take a trailing zone number; the others don't.

| Command topic | Payload | Effect |
|---------------|---------|--------|
| `audioflow2mqtt/0123456789/set_zone_state/<zone>` | `on`, `off`, `toggle` | Turn one zone on/off, or toggle it |
| `audioflow2mqtt/0123456789/set_zone_state` | `on`, `off` | Turn **all** zones on/off (no zone number; `toggle` isn't supported here) |
| `audioflow2mqtt/0123456789/set_zone_enable/<zone>` | `1`, `0` | Enable (`1`) or disable (`0`) one zone |
| `audioflow2mqtt/0123456789/reboot` | _(ignored)_ | Reboot the device; any payload triggers it |

## Topics the gateway publishes

**Zone state**, published after any change and on each poll:

- `audioflow2mqtt/0123456789/zone_state/<zone>`: `on` or `off`
- `audioflow2mqtt/0123456789/zone_enabled/<zone>`: `1` or `0`

> The device doesn't report a new state after a command, so the gateway re-reads the affected zone(s) and republishes.

**Network info**, polled periodically:

- `audioflow2mqtt/0123456789/network_info/ssid`
- `audioflow2mqtt/0123456789/network_info/channel`
- `audioflow2mqtt/0123456789/network_info/rssi`

**Availability**, retained for Home Assistant and monitoring:

- `audioflow2mqtt/status`: `online`/`offline` for the gateway itself; if the gateway disconnects unexpectedly, the broker publishes `offline` on its behalf
- `audioflow2mqtt/0123456789/status`: `online`/`offline` for an individual device

<br>

# Important notes
A single instance handles multiple Audioflow devices. Every topic is namespaced by the device serial number, so they don't collide. You only need a separate instance (with a **different base topic**) if you deliberately run more than one copy against the same broker.

For reliability, give each Audioflow device a static IP (e.g. a DHCP reservation) and set `DEVICES` rather than relying on UDP discovery. UDP discovery only works when the device is on the same subnet as the machine running audioflow2mqtt.

<br>

# TODO

Tracked as open GitHub issues:

- Re-discover an Audioflow device if its IP address changes ([#50](https://github.com/henrycarteruk/audioflow2mqtt/issues/50))
- Publish a multi-arch (amd64 + arm64) Docker image to Docker Hub ([#51](https://github.com/henrycarteruk/audioflow2mqtt/issues/51))
- Add a CI smoke-test that runs the built image ([#52](https://github.com/henrycarteruk/audioflow2mqtt/issues/52))

<br>

# License

Licensed under the [GNU GPLv3](LICENSE).

This is a modified fork of the original [audioflow2mqtt](https://github.com/tediore/audioflow2mqtt) by [tediore](https://github.com/tediore). Original work © [tediore](https://github.com/tediore); modifications © [henrycarteruk](https://github.com/henrycarteruk). As a derivative of a GPLv3 project, it remains under GPLv3.

If you find it useful, consider buying the original author a coffee to support their work:

<a href="https://www.buymeacoffee.com/tediore" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
