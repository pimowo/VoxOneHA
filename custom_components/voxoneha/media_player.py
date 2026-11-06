"""Media player platform for VoxOne."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    """Set up the VoxOne media player."""
    async_add_entities([VoxOneMediaPlayer(entry.runtime_data.coordinator, entry)])


class VoxOneMediaPlayer(VoxOneEntity, MediaPlayerEntity):
    """Represent a VoxOne radio as a media player."""

    _attr_device_class = "speaker"
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: VoxOneCoordinator, entry: VoxOneConfigEntry) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, entry, suffix="media_player")

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the player state."""
        data = self.coordinator.data
        return MediaPlayerState.PLAYING if data and data.playing else MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return volume as a value between zero and one."""
        return self.coordinator.data.volume / 100.0 if self.coordinator.data else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return whether audio is muted."""
        return self.coordinator.data.muted if self.coordinator.data else None

    @property
    def media_title(self) -> str | None:
        """Return the current media title."""
        return self.coordinator.data.title if self.coordinator.data else None

    @property
    def media_artist(self) -> str | None:
        """Return the current media artist."""
        return self.coordinator.data.artist if self.coordinator.data else None

    @property
    def source(self) -> str | None:
        """Return the selected station."""
        return self.coordinator.data.station if self.coordinator.data else None

    @property
    def source_list(self) -> list[str] | None:
        """Return the available stations."""
        data = self.coordinator.data
        return list(data.station_list) if data and data.station_list else None

    async def async_media_play(self) -> None:
        """Start playback."""
        await self.coordinator.client.send_command("start")

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self.coordinator.client.send_command("stop")

    async def async_media_next_track(self) -> None:
        """Select the next station."""
        await self.coordinator.client.send_command("next")

    async def async_media_previous_track(self) -> None:
        """Select the previous station."""
        await self.coordinator.client.send_command("prev")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume."""
        await self.coordinator.client.send_command("vol100", str(round(volume * 100)))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute audio."""
        await self.coordinator.client.send_command("mute", "1" if mute else "0")

    async def async_volume_up(self) -> None:
        """Increase volume."""
        if self.volume_level is not None:
            await self.async_set_volume_level(min(1.0, self.volume_level + 0.05))

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        if self.volume_level is not None:
            await self.async_set_volume_level(max(0.0, self.volume_level - 0.05))

    async def async_select_source(self, source: str) -> None:
        """Select a station by name."""
        data = self.coordinator.data
        if data is None or not data.station_list:
            return
        try:
            station_index = data.station_list.index(source) + 1
        except ValueError:
            return
        await self.coordinator.client.send_command("playstation", str(station_index))
