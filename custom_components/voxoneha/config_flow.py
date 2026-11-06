"""Config flow for VoxOne."""
from __future__ import annotations
import asyncio
import logging
from typing import Any
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import CONF_PASSWORD, CONF_PORT, CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, LOGIN_PATH, SECURITY_STATE_PATH

_LOGGER = logging.getLogger(__name__)

async def _validate_host(hass, host: str, port: int, password: str | None) -> str | None:
    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"
    # VoxOne wymaga nagłówka Origin dla zapytań POST (mutacji)
    headers = {"Origin": base_url}
    
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            async with session.get(f"{base_url}{SECURITY_STATE_PATH}", headers=headers) as resp:
                if resp.status != 200: 
                    return "cannot_connect"
                state = await resp.json()
            
            if state.get("state") == "protected":
                if not password: 
                    return "password_required"
                async with session.post(f"{base_url}{LOGIN_PATH}", data={"password": password}, headers=headers) as resp:
                    if resp.status == 401: 
                        return "invalid_auth"
                    elif resp.status != 200: 
                        return "cannot_connect"
            elif state.get("state") in ("unconfigured", "locked"): 
                return "device_unconfigured"
            return None
    except (TimeoutError, aiohttp.ClientError): 
        return "cannot_connect"

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
                unique_id = f"voxone-{host}:{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or f"VoxOne ({host})",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_PASSWORD: password},
                )
        schema = vol.Schema({vol.Required(CONF_HOST): str, vol.Optional(CONF_PORT, default=DEFAULT_PORT): int, vol.Optional(CONF_NAME): str, vol.Optional(CONF_PASSWORD): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
