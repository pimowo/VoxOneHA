"""Contract tests for the VoxOne media player entity."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from homeassistant.components.media_player import MediaPlayerEntityFeature

from custom_components.voxoneha.media_player import VoxOneMediaPlayer
from custom_components.voxoneha.models import VoxOneState


class VoxOneMediaPlayerTest(unittest.IsolatedAsyncioTestCase):
    """Exercise advertised features, source mapping, and WS commands."""

    def setUp(self) -> None:
        self.client = SimpleNamespace(send_command=AsyncMock())
        self.coordinator = SimpleNamespace(data=VoxOneState(), client=self.client)
        self.entity = object.__new__(VoxOneMediaPlayer)
        self.entity.coordinator = self.coordinator

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
        ):
            self.assertTrue(features & feature)

    def test_source_uses_home_assistant_labels(self) -> None:
        """Firmware source identifiers are presented as stable HA labels."""
        self.assertEqual(self.entity.source_list, ["Radio", "Bluetooth"])
        self.coordinator.data.source = "radio"
        self.assertEqual(self.entity.source, "Radio")
        self.coordinator.data.source = "bt"
        self.assertEqual(self.entity.source, "Bluetooth")

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
                call("start"),
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


if __name__ == "__main__":
    unittest.main()
