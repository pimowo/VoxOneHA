"""VoxOne integration setup."""
from __future__ import annotations
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import CONF_PASSWORD, CONF_PORT, CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import VoxOneCoordinator
from .websocket_client import VoxOneWebSocketClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = VoxOneWebSocketClient(session=session, host=entry.data[CONF_HOST], port=entry.data.get(CONF_PORT, DEFAULT_PORT), password=entry.data.get(CONF_PASSWORD))
    try:
        await client.start()
        await client.wait_connected(timeout=CONNECT_TIMEOUT)
    except (TimeoutError, Exception) as err:
        await client.stop()
        raise ConfigEntryNotReady(f"Cannot connect to VoxOne at {entry.data[CONF_HOST]}") from err
    coordinator = VoxOneCoordinator(hass, client, entry.title)
    try: await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.stop()
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"client": client, "coordinator": coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None: await data["client"].stop()
    return unload_ok

async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
