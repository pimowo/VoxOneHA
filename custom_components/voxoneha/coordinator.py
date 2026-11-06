"""Coordinator bridging the WS client and HA entities."""
from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .models import VoxOneState
from .websocket_client import VoxOneWebSocketClient

_LOGGER = logging.getLogger(__name__)

class VoxOneCoordinator(DataUpdateCoordinator[VoxOneState]):
    def __init__(self, hass: HomeAssistant, client: VoxOneWebSocketClient, name: str) -> None:
        super().__init__(hass, _LOGGER, name=name, update_interval=None)
        self.client = client
        self.client.on_state = self._handle_state
        self.client.on_connection = self._handle_connection

    async def _async_update_data(self) -> VoxOneState:
        if not self.client.is_connected: raise UpdateFailed("VoxOne not connected")
        return self.client.state

    def _handle_state(self, state: VoxOneState) -> None: self.async_set_updated_data(state)
    def _handle_connection(self, connected: bool) -> None: self.async_update_listeners()

    @property
    def connected(self) -> bool: return self.client.is_connected
