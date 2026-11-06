"""Media player platform for VoxOne."""
from __future__ import annotations
import logging
from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: VoxOneCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([VoxOneMediaPlayer(coordinator, entry)])

class VoxOneMediaPlayer(VoxOneEntity, MediaPlayerEntity):
    _attr_device_class = "speaker"
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: VoxOneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, suffix="media_player")

    @property
    def state(self) -> MediaPlayerState | None:
        s = self.coordinator.data
        return MediaPlayerState.PLAYING if s and s.playing else MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None: return self.coordinator.data.volume / 100.0 if self.coordinator.data else None
    @property
    def is_volume_muted(self) -> bool | None: return self.coordinator.data.muted if self.coordinator.data else None
    @property
    def media_title(self) -> str | None: return self.coordinator.data.title if self.coordinator.data else None
    @property
    def media_artist(self) -> str | None: return self.coordinator.data.artist if self.coordinator.data else None
    @property
    def source(self) -> str | None: return self.coordinator.data.station if self.coordinator.data else None
    @property
    def source_list(self) -> list[str] | None: return list(self.coordinator.data.station_list) if self.coordinator.data and self.coordinator.data.station_list else None

    async def async_media_play(self) -> None: await self.coordinator.client.send_command("start")
    async def async_media_stop(self) -> None: await self.coordinator.client.send_command("stop")
    async def async_media_next_track(self) -> None: await self.coordinator.client.send_command("next")
    async def async_media_previous_track(self) -> None: await self.coordinator.client.send_command("prev")
    async def async_set_volume_level(self, volume: float) -> None: await self.coordinator.client.send_command("vol100", str(round(volume * 100)))
    async def async_mute_volume(self, mute: bool) -> None: await self.coordinator.client.send_command("mute", "1" if mute else "0")
    async def async_volume_up(self) -> None:
        if self.volume_level is not None: await self.async_set_volume_level(min(1.0, self.volume_level + 0.05))
    async def async_volume_down(self) -> None:
        if self.volume_level is not None: await self.async_set_volume_level(max(0.0, self.volume_level - 0.05))
    async def async_select_source(self, source: str) -> None:
        s = self.coordinator.data
        if s is None or not s.station_list: return
        try: await self.coordinator.client.send_command("playstation", str(s.station_list.index(source) + 1))
        except ValueError: pass
