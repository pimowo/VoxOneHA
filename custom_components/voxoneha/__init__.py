"""VoxOne integration setup."""
from __future__ import annotations
import logging
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import CONF_PASSWORD, CONF_PORT, CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import VoxOneCoordinator
from .exceptions import VoxOneAuthError
from .websocket_client import VoxOneWebSocketClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = VoxOneWebSocketClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        password=entry.data.get(CONF_PASSWORD),
    )
    
    # Rejestrujemy cleanup PRZED pierwszym await (Bronze requirement)
    entry.async_on_unload(client.stop)
    
    try:
        await client.start()
        await client.wait_connected(timeout=CONNECT_TIMEOUT)
    except VoxOneAuthError as err:
        raise ConfigEntryAuthFailed("VoxOne authentication failed") from err
    except (TimeoutError, aiohttp.ClientError, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to VoxOne at {entry.data[CONF_HOST]}") from err

    coordinator = VoxOneCoordinator(hass, client, entry.title)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
