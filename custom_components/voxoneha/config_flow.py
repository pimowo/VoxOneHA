"""Config flow for VoxOne."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components import zeroconf
from .const import CONF_PASSWORD, CONF_PORT, CONF_MAC, CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, LOGIN_PATH, SECURITY_STATE_PATH, WS_PATH, WS_PROTOCOL

_LOGGER = logging.getLogger(__name__)

async def _fetch_mac(hass, host: str, port: int, password: str | None) -> str | None:
    """Łączy się przez WS tylko po to, żeby wyciągnąć MAC (stabilny ID)."""
    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"
    headers = {"Origin": base_url}
    
    cookies = {}
    if password:
        try:
            async with session.post(f"{base_url}{LOGIN_PATH}", data={"password": password}, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return None
                cookies = resp.cookies
        except Exception:
            return None
    
    ws_headers = {"Origin": base_url}
    if cookies:
        ws_headers["Cookie"] = "; ".join([f"{k}={v.value}" for k, v in cookies.items()])
    
    try:
        async with session.ws_connect(f"ws://{host}:{port}{WS_PATH}", headers=ws_headers, protocols=[WS_PROTOCOL], timeout=10) as ws:
            await ws.send_str("getsystem=1")
            async with asyncio.timeout(5):
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if isinstance(data, dict) and "systemInfo" in data:
                            mac = data["systemInfo"].get("mac")
                            await ws.close()
                            return mac
    except Exception as err:
        _LOGGER.debug("MAC probe failed: %s", err)
    return None

async def _validate_host(hass, host: str, port: int, password: str | None) -> str | None:
    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"
    headers = {"Origin": base_url}
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            async with session.get(f"{base_url}{SECURITY_STATE_PATH}", headers=headers) as resp:
                if resp.status != 200: return "cannot_connect"
                state = await resp.json()
            if state.get("state") == "protected":
                if not password: return "password_required"
                async with session.post(f"{base_url}{LOGIN_PATH}", data={"password": password}, headers=headers) as resp:
                    if resp.status == 401: return "invalid_auth"
                    elif resp.status != 200: return "cannot_connect"
            elif state.get("state") in ("unconfigured", "locked"): return "device_unconfigured"
            return None
    except (TimeoutError, aiohttp.ClientError): return "cannot_connect"

class VoxOneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD) or None
            
            error = await _validate_host(self.hass, host, port, password)
            if error:
                errors["base"] = error
            else:
                mac = await _fetch_mac(self.hass, host, port, password)
                if not mac:
                    errors["base"] = "cannot_connect"
                else:
                    mac_norm = mac.replace(":", "").replace("-", "").lower()
                    unique_id = f"voxone-{mac_norm}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME) or f"VoxOne ({host})",
                        data={CONF_HOST: host, CONF_PORT: port, CONF_PASSWORD: password, CONF_MAC: mac_norm},
                    )
        
        schema = vol.Schema({
            vol.Required(CONF_HOST): str, 
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int, 
            vol.Optional(CONF_NAME): str, 
            vol.Optional(CONF_PASSWORD): str
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        self._async_abort_entries_match({CONF_HOST: host})
        self.context["title_placeholders"] = {"name": discovery_info.name.split(".")[0]}
        self.context["host"] = host
        self.context["port"] = port
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return await self.async_step_user({
                CONF_HOST: self.context["host"],
                CONF_PORT: self.context["port"],
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_NAME: self.context["title_placeholders"]["name"]
            })
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.context["title_placeholders"]["name"]},
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str})
        )
