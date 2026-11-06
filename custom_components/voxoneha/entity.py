"""Base entity for VoxOne."""
from __future__ import annotations
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import VoxOneCoordinator

class VoxOneEntity(CoordinatorEntity[VoxOneCoordinator]):
    _attr_has_entity_name = True
    def __init__(self, coordinator: VoxOneCoordinator, entry, suffix: str, name: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        if name is not None: self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER, model=MODEL, name=entry.title,
            configuration_url=f"http://{coordinator.client.host}/",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.client.is_connected and super().available
