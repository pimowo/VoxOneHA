"""Select platform for VoxOne."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    """Set up VoxOne selects."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([VoxOneSourceSelect(coordinator, entry)])


class VoxOneSourceSelect(VoxOneEntity, SelectEntity):
    """Select the active audio source."""

    _attr_translation_key = "source"
    _attr_icon = "mdi:audio-input-stereo-jack"
    _attr_options = ["radio", "bt"]

    def __init__(self, coordinator: VoxOneCoordinator, entry: VoxOneConfigEntry) -> None:
        super().__init__(coordinator, entry, suffix="select_source")

    @property
    def current_option(self) -> str | None:
        """Return the active audio source."""
        return self.coordinator.data.source if self.coordinator.data else None

    async def async_select_option(self, option: str) -> None:
        """Select an audio source."""
        await self.coordinator.client.send_command("source", option)
