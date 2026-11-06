"""Data model for VoxOne state."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class VoxOneState:
    playing: bool = False
    station: str | None = None
    station_index: int | None = None
    station_list: list[str] = field(default_factory=list)
    title: str | None = None
    artist: str | None = None
    volume: int = 0
    muted: bool = False
    bitrate: int | None = None
    codec: str | None = None
    rssi: int | None = None
    ip: str | None = None
    mac: str | None = None
    firmware: str | None = None
    uptime: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
