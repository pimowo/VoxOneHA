"""Constants for the VoxOne integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "voxoneha"
MANUFACTURER = "VoxOne"
MODEL = "VoxOne Radio"

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]

DEFAULT_PORT = 80
WS_PATH = "/ws"
WS_PROTOCOL = "voxone.v1"
LOGIN_PATH = "/api/security/login"
SECURITY_STATE_PATH = "/api/security/state"
STATIONS_PATH = "/api/stations"

CONNECT_TIMEOUT = 10
WATCHDOG_TIMEOUT = 30
RECONNECT_MIN = 1
RECONNECT_MAX = 60
SEND_TIMEOUT = 5

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PASSWORD = "password"
CONF_NAME = "name"
CONF_MAC = "mac"
CONF_MODEL = "model"
CONF_VERSION = "version"
