"""Select platform for VoxOne."""
from __future__ import annotations
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: VoxOneCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([VoxOneSourceSelect(coordinator, entry)])

class VoxOneSourceSelect(VoxOneEntity, SelectEntity):
    _attr_name = "Źródło"
    _attr_icon = "mdi:audio-input-stereo-jack"
    
    def __init__(self, coordinator: VoxOneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, suffix="select_source")

    @property
    def options(self) -> list[str]:
        # Na razie statyczna lista. Z czasem można to czytać z "webStatus" -> "availableSources"
        return ["radio", "bt"]

    @property
    def current_option(self) -> str | None:
        # Pobieramy z surowego statusu (w przyszłości dodamy to do modelu)
        if self.coordinator.data and self.coordinator.data.raw:
            return self.coordinator.data.raw.get("activeSource")
        return "radio"

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.send_command("source", option)
