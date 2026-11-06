"""Button platform for VoxOne."""
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: VoxOneCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([VoxOneRestartButton(coordinator, entry)])

class VoxOneRestartButton(VoxOneEntity, ButtonEntity):
    _attr_name = "Restart"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: VoxOneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, suffix="button_restart")

    async def async_press(self) -> None:
        await self.coordinator.client.send_command("reboot")
