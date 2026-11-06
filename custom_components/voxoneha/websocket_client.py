"""Async WebSocket client for VoxOne."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import suppress

import aiohttp

from .const import (
    LOGIN_PATH,
    RECONNECT_MAX,
    RECONNECT_MIN,
    SEND_TIMEOUT,
    STATIONS_PATH,
    WATCHDOG_TIMEOUT,
    WS_PATH,
    WS_PROTOCOL,
)
from .exceptions import VoxOneAuthError, VoxOneNotConnectedError
from .models import VoxOneState

_LOGGER = logging.getLogger(__name__)


class VoxOneWebSocketClient:
    """Maintain the connection to a VoxOne radio."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        password: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.host = host
        self.port = port
        self._password = password
        self.state = VoxOneState()
        self.on_state: Callable[[VoxOneState], None] | None = None
        self.on_connection: Callable[[bool], None] | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task[None] | None = None
        self._connected_event = asyncio.Event()
        self._auth_failed_event = asyncio.Event()
        self._auth_error: VoxOneAuthError | None = None
        self._stop = False
        self._cookies: dict[str, object] = {}

    @property
    def is_connected(self) -> bool:
        """Return whether the WebSocket is connected."""
        return self._connected_event.is_set()

    @property
    def base_url(self) -> str:
        """Return the REST base URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        """Return the WebSocket URL."""
        return f"ws://{self.host}:{self.port}{WS_PATH}"

    async def start(self) -> None:
        """Start the connection loop."""
        if self._task is not None and not self._task.done():
            return
        self._stop = False
        self._task = asyncio.create_task(self._run(), name="voxone-ws")

    async def stop(self) -> None:
        """Stop the connection loop and close the WebSocket."""
        self._stop = True
        if self._ws is not None and not self._ws.closed:
            with suppress(aiohttp.ClientError, RuntimeError):
                await self._ws.close()

        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        self._cookies.clear()
        self._auth_failed_event.clear()
        self._auth_error = None
        self._set_disconnected()
        self.on_state = None
        self.on_connection = None

    async def wait_connected(self, timeout_seconds: float | None = None) -> None:
        """Wait until connected or raise a precise authentication error."""
        connected_waiter = asyncio.create_task(self._connected_event.wait())
        auth_waiter = asyncio.create_task(self._auth_failed_event.wait())
        waiters = {connected_waiter, auth_waiter}
        try:
            done, _ = await asyncio.wait(
                waiters,
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if connected_waiter in done:
                return
            if auth_waiter in done:
                raise self._auth_error or VoxOneAuthError("Authentication failed")
            raise TimeoutError
        finally:
            for waiter in waiters:
                waiter.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)

    async def send_command(self, cmd: str, val: str = "1") -> None:
        """Send a command to the connected radio."""
        websocket = self._ws
        if not self.is_connected or websocket is None or websocket.closed:
            raise VoxOneNotConnectedError
        try:
            async with asyncio.timeout(SEND_TIMEOUT):
                await websocket.send_str(f"{cmd}={val}")
        except (TimeoutError, ConnectionError, aiohttp.ClientError, RuntimeError) as err:
            self._set_disconnected()
            raise VoxOneNotConnectedError from err

    async def _login(self) -> bool:
        """Log in, distinguishing rejected credentials from transport errors."""
        if not self._password:
            return True

        try:
            async with self._session.post(
                f"{self.base_url}{LOGIN_PATH}",
                data={"password": self._password},
                headers={"Origin": self.base_url},
                timeout=10,
            ) as response:
                if response.status == 200:
                    self._cookies = dict(response.cookies)
                    return True
                if response.status == 401:
                    raise VoxOneAuthError("Invalid VoxOne password")
                return False
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            _LOGGER.debug("VoxOne login transport error for %s: %s", self.host, err)
            return False

    async def _fetch_stations(self) -> None:
        """Fetch the station list without disrupting the WebSocket loop."""
        headers = self._authenticated_headers()
        try:
            async with self._session.get(
                f"{self.base_url}{STATIONS_PATH}", headers=headers, timeout=10
            ) as response:
                if response.status != 200:
                    return
                data = await response.json()
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError, OSError):
            return

        if not isinstance(data, dict):
            return
        stations = data.get("stations")
        if isinstance(stations, list):
            self.state.station_list = [
                name
                for station in stations
                if isinstance(station, dict) and isinstance((name := station.get("name")), str)
            ]
        current = data.get("current")
        if isinstance(current, int) and not isinstance(current, bool):
            self.state.station_index = current

    async def _run(self) -> None:
        """Connect and reconnect with exponential backoff."""
        backoff = RECONNECT_MIN
        while not self._stop:
            retry_delay = backoff
            try:
                if not await self._login():
                    raise ConnectionError("VoxOne login endpoint unavailable")

                self._auth_error = None
                self._auth_failed_event.clear()
                await self._connect_once()
                backoff = RECONNECT_MIN
            except VoxOneAuthError as err:
                self._auth_error = err
                self._auth_failed_event.set()
                retry_delay = RECONNECT_MAX
                _LOGGER.warning("VoxOne authentication failed for %s", self.host)
            except (TimeoutError, ConnectionError, aiohttp.ClientError, OSError) as err:
                _LOGGER.debug("VoxOne connection error for %s: %s", self.host, err)
            except Exception:
                _LOGGER.exception("Unexpected VoxOne WebSocket error for %s", self.host)
            finally:
                self._set_disconnected()

            if self._stop:
                break
            await asyncio.sleep(retry_delay)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _connect_once(self) -> None:
        """Run one WebSocket connection until it closes."""
        async with self._session.ws_connect(
            self.ws_url,
            headers=self._authenticated_headers(),
            protocols=[WS_PROTOCOL],
            heartbeat=WATCHDOG_TIMEOUT,
        ) as websocket:
            self._ws = websocket
            self._set_connected()
            await self._fetch_stations()
            await self.send_command("getwebstatus")
            await self.send_command("getsystem")
            await self.send_command("getrssi")
            await self.send_command("getindex")

            async for message in websocket:
                if message.type == aiohttp.WSMsgType.TEXT:
                    self._handle_message(message.data)
                elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

    def _authenticated_headers(self) -> dict[str, str]:
        """Build headers shared by authenticated REST and WebSocket requests."""
        headers = {"Origin": self.base_url}
        if self._cookies:
            headers["Cookie"] = "; ".join(
                f"{key}={value.value}"
                for key, value in self._cookies.items()
                if hasattr(value, "value")
            )
        return headers

    def _handle_message(self, raw: object) -> None:
        """Parse a state message, ignoring malformed or unexpected payloads."""
        if not isinstance(raw, str):
            return
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, dict):
            return

        web_status = data.get("webStatus")
        payload = data.get("payload")
        system_info = data.get("systemInfo")
        network_info = data.get("networkInfo")

        if isinstance(web_status, dict):
            self._update_web_status(web_status)
        elif isinstance(payload, list):
            self._update_payload(payload)
        elif isinstance(data.get("current"), int) and not isinstance(data["current"], bool):
            self.state.station_index = data["current"]
        elif isinstance(system_info, dict):
            self._update_system_info(system_info)
        elif isinstance(network_info, dict):
            ip_address = network_info.get("ipaddr")
            if isinstance(ip_address, str):
                self.state.ip = ip_address

        if self.on_state:
            self.on_state(self.state)

    def _update_web_status(self, status: dict[str, object]) -> None:
        """Apply a webStatus object to the state model."""
        self.state.playing = status.get("transport") == "playing"
        for key, attribute in (
            ("name", "station"),
            ("title", "title"),
            ("artist", "artist"),
            ("codec", "codec"),
        ):
            value = status.get(key)
            if isinstance(value, str) or value is None:
                setattr(self.state, attribute, value)

        volume = status.get("volume100")
        if isinstance(volume, int) and not isinstance(volume, bool):
            self.state.volume = volume
        muted = status.get("muted")
        if isinstance(muted, bool):
            self.state.muted = muted
        bitrate = status.get("bitrate")
        if isinstance(bitrate, int) and not isinstance(bitrate, bool):
            self.state.bitrate = bitrate
        source = status.get("activeSource")
        if isinstance(source, str):
            self.state.source = source

    def _update_payload(self, payload: list[object]) -> None:
        """Apply an incremental payload list to the state model."""
        for item in payload:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            value = item.get("value")
            if item_id == "nameset" and isinstance(value, str):
                self.state.station = value
            elif item_id == "meta" and isinstance(value, str):
                self.state.title = value
            elif item_id == "playerwrap":
                self.state.playing = value == "playing"
            elif item_id == "rssi" and isinstance(value, int) and not isinstance(value, bool):
                self.state.rssi = value
            elif item_id == "volume":
                volume = item.get("volume100")
                if isinstance(volume, int) and not isinstance(volume, bool):
                    self.state.volume = volume
                muted = item.get("muted")
                if isinstance(muted, bool):
                    self.state.muted = muted

    def _update_system_info(self, system_info: dict[str, object]) -> None:
        """Apply a systemInfo object to the state model."""
        for key, attribute in (("version", "firmware"), ("mac", "mac")):
            value = system_info.get(key)
            if isinstance(value, str):
                setattr(self.state, attribute, value)

        rssi = system_info.get("rssi")
        if isinstance(rssi, int) and not isinstance(rssi, bool):
            self.state.rssi = rssi
        uptime = system_info.get("uptimeSeconds")
        if isinstance(uptime, int) and not isinstance(uptime, bool):
            self.state.uptime = uptime

    def _set_connected(self) -> None:
        """Mark the client connected and notify listeners."""
        self._connected_event.set()
        if self.on_connection:
            self.on_connection(True)

    def _set_disconnected(self) -> None:
        """Mark the client disconnected and notify listeners on transition."""
        was_connected = self._connected_event.is_set()
        self._connected_event.clear()
        self._ws = None
        if was_connected and self.on_connection:
            self.on_connection(False)
