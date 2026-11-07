"""Contract tests for VoxOne Zeroconf discovery."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from ipaddress import IPv4Address
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.voxoneha"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


custom_components = ModuleType("custom_components")
custom_components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components)
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "voxoneha")]
sys.modules[PACKAGE] = package
_load_module(f"{PACKAGE}.const", ROOT / "custom_components/voxoneha/const.py")
config_flow = _load_module(
    f"{PACKAGE}.config_flow", ROOT / "custom_components/voxoneha/config_flow.py"
)


def _service_info(**properties: str) -> ZeroconfServiceInfo:
    address = IPv4Address("192.0.2.10")
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=80,
        hostname="voxone-l0.local.",
        type="_voxone._tcp.local.",
        name="VoxOne L0._voxone._tcp.local.",
        properties=properties,
    )


class ZeroconfFlowTest(unittest.IsolatedAsyncioTestCase):
    """Exercise discovery identity, metadata, and connectivity behavior."""

    def setUp(self) -> None:
        self.flow = config_flow.VoxOneConfigFlow()
        self.flow.hass = MagicMock()
        self.flow.context = {}
        self.flow.async_set_unique_id = AsyncMock()
        self.flow._abort_if_unique_id_configured = MagicMock()
        self.flow.async_create_entry = MagicMock(
            side_effect=lambda **kwargs: {"type": "create_entry", **kwargs}
        )
        self.flow.async_abort = MagicMock(
            side_effect=lambda **kwargs: {"type": "abort", **kwargs}
        )

    async def test_open_device_is_created_from_txt_records(self) -> None:
        """An accessible open device is added without confirmation."""
        info = _service_info(
            mac="AA:BB:CC:DD:EE:FF",
            name="Kitchen VoxOne",
            model="VoxOne-L0",
            version="1.1.0-dev",
        )
        with patch.object(config_flow, "_validate_host", AsyncMock(return_value=None)):
            result = await self.flow.async_step_zeroconf(info)

        self.flow.async_set_unique_id.assert_awaited_once_with("aa:bb:cc:dd:ee:ff")
        self.flow._abort_if_unique_id_configured.assert_called_once()
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Kitchen VoxOne")
        self.assertEqual(
            result["data"],
            {
                "host": "192.0.2.10",
                "port": 80,
                "mac": "aa:bb:cc:dd:ee:ff",
                "name": "Kitchen VoxOne",
                "model": "VoxOne-L0",
                "version": "1.1.0-dev",
            },
        )

    async def test_unreachable_device_is_not_created(self) -> None:
        """Discovery aborts if the aiohttp connectivity probe fails."""
        info = _service_info(
            mac="AA:BB:CC:DD:EE:FF",
            name="Kitchen VoxOne",
            model="VoxOne-L0",
            version="1.1.0-dev",
        )
        with patch.object(
            config_flow, "_validate_host", AsyncMock(return_value="cannot_connect")
        ):
            result = await self.flow.async_step_zeroconf(info)

        self.assertEqual(result, {"type": "abort", "reason": "cannot_connect"})
        self.flow.async_create_entry.assert_not_called()

    async def test_invalid_mac_is_rejected_before_connecting(self) -> None:
        """A malformed TXT MAC cannot become the config-entry identity."""
        info = _service_info(
            mac="not-a-mac",
            name="Kitchen VoxOne",
            model="VoxOne-L0",
            version="1.1.0-dev",
        )
        validate = AsyncMock()
        with patch.object(config_flow, "_validate_host", validate):
            result = await self.flow.async_step_zeroconf(info)

        self.assertEqual(result, {"type": "abort", "reason": "invalid_discovery_info"})
        validate.assert_not_awaited()


class ManifestTest(unittest.TestCase):
    """Validate the dedicated VoxOne service registration."""

    def test_manifest_uses_voxone_service(self) -> None:
        manifest = json.loads(
            (ROOT / "custom_components/voxoneha/manifest.json").read_text()
        )
        self.assertEqual(manifest["zeroconf"], ["_voxone._tcp.local."])
        self.assertEqual(manifest["version"], "1.1.1")


if __name__ == "__main__":
    unittest.main()
