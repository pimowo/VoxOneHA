"""Config flow for VoxOne."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONNECT_TIMEOUT,
    DEFAULT_PORT,
    DOMAIN,
    LOGIN_PATH,
    SECURITY_STATE_PATH,
    WS_PATH,
    WS_PROTOCOL,
)

_LOGGER = logging.getLogger(__name__)
_MAC_PATTERN = re.compile(r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _normalize_mac(mac: object) -> str | None:
    """Return a canonical MAC address, or None when the value is invalid."""
    if not isinstance(mac, str):
        return None
    normalized = format_mac(mac.strip())
    if not _MAC_PATTERN.fullmatch(normalized):
        return None
    return normalized


async def _fetch_mac(
    hass: HomeAssistant,
    host: str,
    port: int,
    password: str | None,
) -> str | None:
    """Connect over WebSocket and read the stable MAC address."""
    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"
    headers = {"Origin": base_url}
    cookie_header: str | None = None

    if password:
        try:
            async with session.post(
                f"{base_url}{LOGIN_PATH}",
                data={"password": password},
                headers=headers,
                timeout=CONNECT_TIMEOUT,
            ) as response:
                if response.status != 200:
                    return None
                cookie_header = "; ".join(
                    f"{key}={value.value}" for key, value in response.cookies.items()
                )
        except (TimeoutError, aiohttp.ClientError, OSError):
            return None

    ws_headers = dict(headers)
    if cookie_header:
        ws_headers["Cookie"] = cookie_header

    try:
        async with session.ws_connect(
            f"ws://{host}:{port}{WS_PATH}",
            headers=ws_headers,
            protocols=[WS_PROTOCOL],
            timeout=CONNECT_TIMEOUT,
        ) as websocket:
            await websocket.send_str("getsystem=1")
            async with asyncio.timeout(5):
                async for message in websocket:
                    if message.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        data = json.loads(message.data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    system_info = data.get("systemInfo")
                    if not isinstance(system_info, dict):
                        continue
                    return _normalize_mac(system_info.get("mac"))
    except (TimeoutError, aiohttp.ClientError, OSError) as err:
        _LOGGER.debug("MAC probe failed for %s: %s", host, err)

    return None


async def _validate_host(
    hass: HomeAssistant,
    host: str,
    port: int,
    password: str | None,
) -> str | None:
    """Validate connectivity and credentials before creating an entry."""
    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"
    headers = {"Origin": base_url}

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            async with session.get(f"{base_url}{SECURITY_STATE_PATH}", headers=headers) as response:
                if response.status != 200:
                    return "cannot_connect"
                state = await response.json()

            if not isinstance(state, dict):
                return "cannot_connect"

            security_state = state.get("state")
            if security_state == "protected":
                if not password:
                    return "password_required"
                async with session.post(
                    f"{base_url}{LOGIN_PATH}",
                    data={"password": password},
                    headers=headers,
                ) as response:
                    if response.status == 401:
                        return "invalid_auth"
                    if response.status != 200:
                        return "cannot_connect"
            elif security_state in ("unconfigured", "locked"):
                return "device_unconfigured"

            return None
    except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError, OSError):
        return "cannot_connect"


class VoxOneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a VoxOne config flow."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle setup initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD) or None

            if error := await _validate_host(self.hass, host, port, password):
                errors["base"] = error
            elif mac := await _fetch_mac(self.hass, host, port, password):
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                        CONF_MAC: mac,
                    }
                )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or f"VoxOne ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                        CONF_MAC: mac,
                    },
                )
            else:
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: host})
        self.context["title_placeholders"] = {"name": discovery_info.name.split(".")[0]}
        self.context["host"] = host
        self.context["port"] = discovery_info.port or DEFAULT_PORT
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovered VoxOne device."""
        if user_input is not None:
            return await self.async_step_user(
                {
                    CONF_HOST: self.context["host"],
                    CONF_PORT: self.context["port"],
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                    CONF_NAME: self.context["title_placeholders"]["name"],
                }
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.context["title_placeholders"]["name"]},
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
        )
