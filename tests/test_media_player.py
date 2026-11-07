"""Contract tests for the VoxOne media player entity."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError

from custom_components.voxoneha.media_player import VoxOneMediaPlayer
from custom_components.voxoneha.models import VoxOneState


class VoxOneMediaPlayerTest(unittest.IsolatedAsyncioTestCase):
    """Exercise advertised features, source mapping, and WS commands."""

    def setUp(self) -> None:
        self.client = SimpleNamespace(send_command=AsyncMock())
        self.coordinator = SimpleNamespace(data=VoxOneState(), client=self.client)
        self.entity = object.__new__(VoxOneMediaPlayer)
        self.entity.coordinator = self.coordinator
        self.entity.hass = SimpleNamespace()
        self.entity.entity_id = "media_player.voxone"

    def test_supported_features_include_transport_power_source_and_mute(self) -> None:
        """HA receives all controls implemented by the entity."""
        features = self.entity.supported_features
        for feature in (
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.TURN_OFF,
            MediaPlayerEntityFeature.SELECT_SOURCE,
            MediaPlayerEntityFeature.VOLUME_MUTE,
            MediaPlayerEntityFeature.BROWSE_MEDIA,
            MediaPlayerEntityFeature.PLAY_MEDIA,
        ):
            self.assertTrue(features & feature)

    def test_source_uses_home_assistant_labels(self) -> None:
        """Firmware source identifiers are presented as stable HA labels."""
        self.assertEqual(self.entity.source_list, ["Radio", "Bluetooth"])
        self.coordinator.data.source = "radio"
        self.assertEqual(self.entity.source, "Radio")
        self.coordinator.data.source = "bt"
        self.assertEqual(self.entity.source, "Bluetooth")

    def test_source_list_is_available_while_device_state_is_offline(self) -> None:
        """HA keeps source capabilities during a temporary state outage."""
        self.coordinator.data = None
        self.assertEqual(self.entity.source_list, ["Radio", "Bluetooth"])
        self.assertEqual(
            self.entity.capability_attributes["source_list"],
            ["Radio", "Bluetooth"],
        )
        self.assertTrue(self.entity.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE)

    async def test_transport_and_power_commands(self) -> None:
        """Media controls use the firmware WebSocket contract."""
        await self.entity.async_media_play()
        await self.entity.async_media_pause()
        await self.entity.async_media_next_track()
        await self.entity.async_media_previous_track()
        await self.entity.async_turn_on()
        await self.entity.async_turn_off()

        self.client.send_command.assert_has_awaits(
            [
                call("webtransport", "toggle"),
                call("webtransport", "toggle"),
                call("webtransport", "next"),
                call("webtransport", "prev"),
                call("webtransport", "toggle"),
                call("stop"),
            ]
        )

    async def test_source_and_mute_commands(self) -> None:
        """Source and mute values are translated to firmware identifiers."""
        await self.entity.async_select_source("Radio")
        await self.entity.async_select_source("Bluetooth")
        await self.entity.async_mute_volume(True)
        await self.entity.async_mute_volume(False)

        self.client.send_command.assert_has_awaits(
            [
                call("source", "radio"),
                call("source", "bt"),
                call("mute", "1"),
                call("mute", "0"),
            ]
        )

    async def test_unknown_source_is_rejected(self) -> None:
        """An arbitrary label cannot reach the firmware command channel."""
        with self.assertRaisesRegex(ValueError, "Unsupported VoxOne source"):
            await self.entity.async_select_source("Line in")
        self.client.send_command.assert_not_awaited()

    async def test_browse_media_uses_home_assistant_media_source(self) -> None:
        """The entity exposes HA's standard media browser tree."""
        browse_result = object()
        with patch(
            "custom_components.voxoneha.media_player.media_source.async_browse_media",
            AsyncMock(return_value=browse_result),
        ) as browse_media:
            result = await self.entity.async_browse_media("music", "media-source://media")

        self.assertIs(result, browse_result)
        browse_media.assert_awaited_once_with(self.entity.hass, "media-source://media")

    async def test_play_media_sends_direct_url_to_firmware(self) -> None:
        """A direct HTTP URL uses the temporary firmware playback command."""
        url = "https://ha.local:8123/local/announcement.mp3?token=a=b"
        with (
            patch(
                "custom_components.voxoneha.media_player.media_source.is_media_source_id",
                return_value=False,
            ),
            patch(
                "custom_components.voxoneha.media_player.async_process_play_media_url",
                return_value=url,
            ),
        ):
            await self.entity.async_play_media("music", url)

        self.client.send_command.assert_awaited_once_with("playurl", url)

    async def test_play_media_resolves_media_source_to_reachable_url(self) -> None:
        """A media-source identifier is resolved and made reachable by VoxOne."""
        resolved = SimpleNamespace(url="/api/tts_proxy/voice.mp3")
        reachable = "http://192.168.1.2:8123/api/tts_proxy/voice.mp3"
        with (
            patch(
                "custom_components.voxoneha.media_player.media_source.is_media_source_id",
                return_value=True,
            ),
            patch(
                "custom_components.voxoneha.media_player.media_source.async_resolve_media",
                AsyncMock(return_value=resolved),
            ) as resolve_media,
            patch(
                "custom_components.voxoneha.media_player.async_process_play_media_url",
                return_value=reachable,
            ) as process_url,
        ):
            await self.entity.async_play_media("music", "media-source://tts/voice")

        resolve_media.assert_awaited_once_with(
            self.entity.hass,
            "media-source://tts/voice",
            "media_player.voxone",
        )
        process_url.assert_called_once_with(self.entity.hass, resolved.url)
        self.client.send_command.assert_awaited_once_with("playurl", reachable)

    async def test_play_media_rejects_unsupported_or_unsafe_url(self) -> None:
        """Unsupported schemes and command-breaking values never reach VoxOne."""
        with (
            patch(
                "custom_components.voxoneha.media_player.media_source.is_media_source_id",
                return_value=False,
            ),
            patch(
                "custom_components.voxoneha.media_player.async_process_play_media_url",
                return_value="file:///tmp/audio.mp3",
            ),
            self.assertRaises(HomeAssistantError),
        ):
            await self.entity.async_play_media("music", "file:///tmp/audio.mp3")

        self.client.send_command.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
