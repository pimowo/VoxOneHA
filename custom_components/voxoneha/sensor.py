"""Sensor platform for VoxOne."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity
from .models import VoxOneConfigEntry, VoxOneState


@dataclass(frozen=True, kw_only=True)
class VoxOneSensorEntityDescription(SensorEntityDescription):
    """Describes VoxOne sensor entity."""

    value_fn: Callable[[VoxOneState], StateType]


SENSORS: tuple[VoxOneSensorEntityDescription, ...] = (
    VoxOneSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.rssi,
    ),
    VoxOneSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.uptime,
    ),
    VoxOneSensorEntityDescription(
        key="bitrate",
        translation_key="bitrate",
        native_unit_of_measurement="kbps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.bitrate,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoxOneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoxOne sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(VoxOneSensor(coordinator, entry, description) for description in SENSORS)


class VoxOneSensor(VoxOneEntity, SensorEntity):
    """Representation of a VoxOne sensor."""

    entity_description: VoxOneSensorEntityDescription

    def __init__(
        self,
        coordinator: VoxOneCoordinator,
        entry: VoxOneConfigEntry,
        description: VoxOneSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, suffix=f"sensor_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.coordinator.data:
            return self.entity_description.value_fn(self.coordinator.data)
        return None
