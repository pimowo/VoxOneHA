"""Base entity for VoxOne."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN, MANUFACTURER, MODEL
from .coordinator import VoxOneCoordinator
from .models import VoxOneConfigEntry


class VoxOneEntity(CoordinatorEntity[VoxOneCoordinator]):
    """Base class for VoxOne entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VoxOneCoordinator,
        entry: VoxOneConfigEntry,
        suffix: str,
    ) -> None:
        """Initialize a VoxOne entity."""
        super().__init__(coordinator)
        mac = dr.format_mac(entry.data[CONF_MAC])
        self._attr_unique_id = f"{mac}_{suffix}"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            configuration_url=coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.client.is_connected and super().available
