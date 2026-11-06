"""Button platform for VoxOne."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity
from .models import VoxOneConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoxOneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoxOne buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([VoxOneRestartButton(coordinator, entry)])


class VoxOneRestartButton(VoxOneEntity, ButtonEntity):
    """Restart the VoxOne radio."""

    _attr_translation_key = "restart"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: VoxOneCoordinator, entry: VoxOneConfigEntry) -> None:
        super().__init__(coordinator, entry, suffix="button_restart")

    async def async_press(self) -> None:
        """Restart the radio."""
        await self.coordinator.client.send_command("reboot")
