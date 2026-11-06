"""Sensor platform for VoxOne."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorEntity, SensorEntityDescription, SensorStateClass, SensorDeviceClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity
from .models import VoxOneState

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class VoxOneSensorEntityDescription(SensorEntityDescription):
    """Describes VoxOne sensor entity."""
    value_fn: Callable[[VoxOneState], StateType]

SENSORS: tuple[VoxOneSensorEntityDescription, ...] = (
    VoxOneSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        name="Wi-Fi RSSI",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.rssi,
    ),
    VoxOneSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        name="Uptime",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.uptime,
    ),
    VoxOneSensorEntityDescription(
        key="bitrate",
        translation_key="bitrate",
        name="Bitrate",
        native_unit_of_measurement="kbps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.bitrate,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up VoxOne sensors."""
    coordinator: VoxOneCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(VoxOneSensor(coordinator, entry, description) for description in SENSORS)


class VoxOneSensor(VoxOneEntity, SensorEntity):
    """Representation of a VoxOne sensor."""
    entity_description: VoxOneSensorEntityDescription

    def __init__(
        self,
        coordinator: VoxOneCoordinator,
        entry: ConfigEntry,
        description: VoxOneSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, suffix=f"sensor_{description.key}", name=description.name)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        if self.coordinator.data:
            return self.entity_description.value_fn(self.coordinator.data)
        return None
