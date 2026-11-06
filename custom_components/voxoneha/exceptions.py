"""Exceptions for the VoxOne integration."""
from __future__ import annotations

class VoxOneError(Exception):
    """Base error."""

class VoxOneNotConnected(VoxOneError):
    """Raised when a command is sent while the WebSocket is down."""

class VoxOneAuthError(VoxOneError):
    """Raised when the device rejects our credentials."""

class VoxOneProtocolError(VoxOneError):
    """Raised when a message cannot be parsed / makes no sense."""
