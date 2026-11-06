"""VoxOne integration setup."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONNECT_TIMEOUT,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import VoxOneCoordinator
from .exceptions import VoxOneAuthError
from .models import VoxOneConfigEntry, VoxOneRuntimeData
from .websocket_client import VoxOneWebSocketClient

_LOGGER = logging.getLogger(__name__)

_ENTITY_UNIQUE_ID_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("media_player", "media_player"),
    ("sensor", "sensor_rssi"),
    ("sensor", "sensor_uptime"),
    ("sensor", "sensor_bitrate"),
    ("button", "button_restart"),
    ("select", "select_source"),
)


async def async_setup_entry(hass: HomeAssistant, entry: VoxOneConfigEntry) -> bool:
    """Set up VoxOne from a config entry."""
    session = async_get_clientsession(hass)
    client = VoxOneWebSocketClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        password=entry.data.get(CONF_PASSWORD),
    )

    entry.async_on_unload(client.stop)

    try:
        await client.start()
        await client.wait_connected(timeout_seconds=CONNECT_TIMEOUT)
    except VoxOneAuthError as err:
        raise ConfigEntryAuthFailed("VoxOne authentication failed") from err
    except (TimeoutError, aiohttp.ClientError, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to VoxOne at {entry.data[CONF_HOST]}") from err

    coordinator = VoxOneCoordinator(hass, client, entry.title)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = VoxOneRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VoxOneConfigEntry) -> bool:
    """Unload a VoxOne config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: VoxOneConfigEntry) -> bool:
    """Migrate host-based identity to a MAC-based identity."""
    if entry.version > 2:
        return False
    if entry.version == 2:
        return True

    # Import locally to keep config-flow-only dependencies out of normal setup.
    from .config_flow import _fetch_mac, _normalize_mac

    mac = _normalize_mac(entry.data.get(CONF_MAC))
    if mac is None:
        discovered_mac = await _fetch_mac(
            hass,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data.get(CONF_PASSWORD),
        )
        mac = _normalize_mac(discovered_mac)

    if mac is None:
        _LOGGER.error("Cannot migrate VoxOne entry %s: MAC address unavailable", entry.entry_id)
        return False

    if any(
        other.entry_id != entry.entry_id and other.unique_id == mac
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        _LOGGER.error(
            "Cannot migrate VoxOne entry %s: MAC %s is already configured", entry.entry_id, mac
        )
        return False

    entity_registry = er.async_get(hass)
    for entity_domain, suffix in _ENTITY_UNIQUE_ID_SUFFIXES:
        old_unique_id = f"{entry.entry_id}_{suffix}"
        if entity_id := entity_registry.async_get_entity_id(entity_domain, DOMAIN, old_unique_id):
            entity_registry.async_update_entity(
                entity_id,
                new_unique_id=f"{mac}_{suffix}",
            )

    device_registry = dr.async_get(hass)
    if device := device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}):
        device_registry.async_update_device(
            device.id,
            new_identifiers={(DOMAIN, mac)},
            new_connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        )

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_MAC: mac},
        unique_id=mac,
        version=2,
    )
    return True
