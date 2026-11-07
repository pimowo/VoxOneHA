"""Media player platform for VoxOne."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import VoxOneCoordinator
from .entity import VoxOneEntity
from .models import VoxOneConfigEntry

SOURCE_RADIO = "Radio"
SOURCE_BLUETOOTH = "Bluetooth"
SOURCE_LIST = [SOURCE_RADIO, SOURCE_BLUETOOTH]

_SOURCE_TO_COMMAND = {
    SOURCE_RADIO.casefold(): "radio",
    SOURCE_BLUETOOTH.casefold(): "bt",
}
_COMMAND_TO_SOURCE = {
    "radio": SOURCE_RADIO,
    "bt": SOURCE_BLUETOOTH,
}


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
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
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
        """Return the active VoxOne source."""
        data = self.coordinator.data
        if data is None:
            return None
        return _COMMAND_TO_SOURCE.get(data.source.casefold())

    @property
    def source_list(self) -> list[str]:
        """Return the sources exposed by VoxOne."""
        return list(SOURCE_LIST)

    async def async_turn_on(self) -> None:
        """Resume playback for the active source."""
        await self.coordinator.client.send_command("webtransport", "toggle")

    async def async_turn_off(self) -> None:
        """Turn off playback."""
        await self.coordinator.client.send_command("stop")

    async def async_media_play(self) -> None:
        """Start playback."""
        await self.coordinator.client.send_command("webtransport", "toggle")

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self.coordinator.client.send_command("webtransport", "toggle")

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self.coordinator.client.send_command("stop")

    async def async_media_next_track(self) -> None:
        """Select the next item for the active source."""
        await self.coordinator.client.send_command("webtransport", "next")

    async def async_media_previous_track(self) -> None:
        """Select the previous item for the active source."""
        await self.coordinator.client.send_command("webtransport", "prev")

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
        """Select Radio or Bluetooth as the active VoxOne source."""
        source_command = _SOURCE_TO_COMMAND.get(source.casefold())
        if source_command is None:
            raise ValueError(f"Unsupported VoxOne source: {source}")
        await self.coordinator.client.send_command("source", source_command)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant media sources."""
        return await media_source.async_browse_media(self.hass, media_content_id)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Resolve and play a temporary HTTP(S) media URL on VoxOne."""
        if media_source.is_media_source_id(media_id):
            resolved = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = resolved.url

        play_url = async_process_play_media_url(self.hass, media_id)
        try:
            parsed = urlsplit(play_url)
            invalid = (
                parsed.scheme.casefold() not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or len(play_url.encode("ascii")) >= 512
                or any(
                    ord(character) <= 0x20
                    or ord(character) >= 0x7F
                    or character in {"\\", '"', "<", ">"}
                    for character in play_url
                )
            )
        except (UnicodeEncodeError, ValueError):
            invalid = True
        if invalid:
            raise HomeAssistantError("VoxOne requires a safe HTTP or HTTPS media URL")

        await self.coordinator.client.send_command("playurl", play_url)
