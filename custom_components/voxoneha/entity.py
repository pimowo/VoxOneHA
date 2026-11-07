"""Base entity for VoxOne."""
from __future__ import annotations
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL, CONF_MAC
from .coordinator import VoxOneCoordinator

class VoxOneEntity(CoordinatorEntity[VoxOneCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VoxOneCoordinator, entry: ConfigEntry, suffix: str, name: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_MAC]}_{suffix}"
        if name is not None:
            self._attr_name = name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_MAC])},
            connections={(CONNECTION_NETWORK_MAC, format_mac(entry.data[CONF_MAC]))},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            configuration_url=f"http://{coordinator.client.host}:{coordinator.client.port}/",
            sw_version=coordinator.data.firmware if coordinator.data else None,
        )

    @property
    def available(self) -> bool:
        return self.coordinator.client.is_connected and super().available
