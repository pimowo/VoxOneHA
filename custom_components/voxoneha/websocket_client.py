cat > custom_components/voxoneha/websocket_client.py <<'EOF'
"""Async WebSocket client for VoxOne."""
from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import suppress
import aiohttp

from .const import LOGIN_PATH, RECONNECT_MAX, RECONNECT_MIN, SEND_TIMEOUT, STATIONS_PATH, WATCHDOG_TIMEOUT, WS_PATH, WS_PROTOCOL
from .exceptions import VoxOneAuthError, VoxOneNotConnected
from .models import VoxOneState

_LOGGER = logging.getLogger(__name__)

class VoxOneWebSocketClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, password: str | None = None) -> None:
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
        self._stop = False
        self._auth_ok = False
        self._cookies = {}

    @property
    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}{WS_PATH}"

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop = False
        self._task = asyncio.create_task(self._run(), name="voxone-ws")

    async def stop(self) -> None:
        """Bezpieczne zatrzymanie klienta (zgodnie z audytem)"""
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
        self._set_disconnected()
        self.on_state = None
        self.on_connection = None

    async def wait_connected(self, timeout: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
        except TimeoutError:
            if not self._auth_ok: 
                raise VoxOneAuthError("Authentication failed")
            raise

    async def send_command(self, cmd: str, val: str = "1") -> None:
        ws = self._ws
        if not self.is_connected or ws is None or ws.closed: 
            raise VoxOneNotConnected()
        try:
            async with asyncio.timeout(SEND_TIMEOUT):
                await ws.send_str(f"{cmd}={val}")
        except (TimeoutError, ConnectionError, aiohttp.ClientError, RuntimeError) as err:
            self._set_disconnected()
            raise VoxOneNotConnected() from err

    async def _login(self) -> bool:
        if not self._password: return True
        headers = {"Origin": self.base_url}
        try:
            async with self._session.post(f"{self.base_url}{LOGIN_PATH}", data={"password": self._password}, headers=headers, timeout=10) as resp:
                if resp.status == 200: 
                    self._cookies = resp.cookies
                    return True
                if resp.status == 401:
                    _LOGGER.error("VoxOne: Invalid password")
                    return False
        except Exception as err: 
            _LOGGER.debug("VoxOne login exception: %s", err)
        return False

    async def _fetch_stations(self) -> None:
        headers = {"Origin": self.base_url}
        if self._cookies:
            headers["Cookie"] = "; ".join([f"{k}={v.value}" for k, v in self._cookies.items()])
        try:
            async with self._session.get(f"{self.base_url}{STATIONS_PATH}", headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.state.station_list = [s["name"] for s in data.get("stations", [])]
                    self.state.station_index = data.get("current")
        except Exception: pass

    async def _run(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stop:
            try:
                self._auth_ok = await self._login()
                if not self._auth_ok:
                    await asyncio.sleep(RECONNECT_MAX)
                    continue
                await self._connect_once()
                backoff = RECONNECT_MIN
            except Exception as err: 
                _LOGGER.debug("VoxOne WS error (%s): %s", self.host, err)
            finally:
                self._set_disconnected()
                
            if self._stop: break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _connect_once(self) -> None:
        headers = {"Origin": self.base_url}
        if self._cookies:
            headers["Cookie"] = "; ".join([f"{k}={v.value}" for k, v in self._cookies.items()])
            
        async with self._session.ws_connect(self.ws_url, headers=headers, protocols=[WS_PROTOCOL], heartbeat=WATCHDOG_TIMEOUT) as ws:
            self._ws = ws
            self._set_connected()
            await self._fetch_stations()
            await self.send_command("getwebstatus")
            await self.send_command("getsystem")
            await self.send_command("getrssi")
            await self.send_command("getindex")
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT: 
                    self._handle_message(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR): 
                    break

    def _handle_message(self, raw: str) -> None:
        try: data = json.loads(raw)
        except json.JSONDecodeError: return
        if not isinstance(data, dict): return
        
        # Audyt: zabezpieczenie typów przed crashem
        if "webStatus" in data and isinstance(data["webStatus"], dict):
            st = data["webStatus"]
            self.state.playing = st.get("transport") == "playing"
            self.state.station = st.get("name")
            self.state.title = st.get("title")
            self.state.artist = st.get("artist")
            self.state.volume = st.get("volume100", self.state.volume)
            self.state.muted = st.get("muted", self.state.muted)
            self.state.codec = st.get("codec")
            self.state.bitrate = st.get("bitrate")
            self.state.source = st.get("activeSource", "radio")
            
        elif "payload" in data and isinstance(data["payload"], list):
            for item in data["payload"]:
                if not isinstance(item, dict): continue
                item_id = item.get("id")
                val = item.get("value")
                if item_id == "nameset": self.state.station = val
                elif item_id == "meta": self.state.title = val
                elif item_id == "playerwrap": self.state.playing = (val == "playing")
                elif item_id == "rssi": self.state.rssi = val
                elif item_id == "volume":
                    self.state.volume = item.get("volume100", self.state.volume)
                    self.state.muted = item.get("muted", self.state.muted)
                    
        elif "current" in data: 
            self.state.station_index = data["current"]
            
        elif "systemInfo" in data and isinstance(data["systemInfo"], dict):
            sysinfo = data["systemInfo"]
            self.state.firmware = sysinfo.get("version")
            self.state.mac = sysinfo.get("mac")
            self.state.rssi = sysinfo.get("rssi")
            self.state.uptime = sysinfo.get("uptimeSeconds")
            
        elif "networkInfo" in data and isinstance(data["networkInfo"], dict): 
            # Audyt: poprawka błędu odczytu IP
            self.state.ip = data["networkInfo"].get("ipaddr", self.state.ip)
            
        if self.on_state: self.on_state(self.state)

    def _set_connected(self) -> None:
        self._connected_event.set()
        if self.on_connection: self.on_connection(True)

    def _set_disconnected(self) -> None:
        was_connected = self._connected_event.is_set()
        self._connected_event.clear()
        self._ws = None
        if was_connected and self.on_connection: 
            self.on_connection(False)
EOF