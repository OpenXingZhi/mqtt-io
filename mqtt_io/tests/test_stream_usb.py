"""Regression tests for USB stream cleanup and device loss."""

import errno
import sys
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Tuple
from unittest.mock import MagicMock, patch

from mqtt_io.modules.stream.usb import CONFIG_SCHEMA, Stream


def _config() -> Dict[str, Any]:
    return {
        "vid": 0x0525,
        "pid": 0xA4AC,
        "read_size": 1024,
        "read_timeout": 1,
        "write_size": 64,
        "interface": 1,
    }


def _mocks() -> Tuple[MagicMock, MagicMock, MagicMock]:
    mock_usb = MagicMock()
    mock_core = MagicMock()
    mock_util = MagicMock()
    mock_usb.core = mock_core
    mock_usb.util = mock_util
    device = MagicMock(name="device")
    cfg = MagicMock()
    cfg.__getitem__.return_value = MagicMock()
    device.get_active_configuration.return_value = cfg
    mock_core.find.return_value = device
    mock_util.find_descriptor.side_effect = lambda *args, **kwargs: MagicMock()
    return mock_usb, mock_core, mock_util


@contextmanager
def _patched(mock_usb: MagicMock, mock_core: MagicMock, mock_util: MagicMock) -> Iterator[None]:
    with patch.dict(
        sys.modules, {"usb": mock_usb, "usb.core": mock_core, "usb.util": mock_util}
    ):
        yield


def test_cleanup_releases_configured_interface_once_then_disposes() -> None:
    """cleanup releases the configured interface once, then disposes the device."""
    interface = 1
    mock_usb, mock_core, mock_util = _mocks()
    device = mock_core.find.return_value
    with _patched(mock_usb, mock_core, mock_util):
        stream = Stream(_config())
        stream.cleanup()

    mock_util.release_interface.assert_called_once_with(device, interface)
    mock_util.dispose_resources.assert_called_once_with(device)


def test_read_timeout_is_empty_not_device_loss() -> None:
    """An empty read is a timeout and must not look like a lost device."""
    mock_usb, mock_core, mock_util = _mocks()

    class USBError(Exception):
        """Stand-in for usb.core.USBError."""

        errno = errno.ETIMEDOUT

    mock_core.USBError = USBError
    with _patched(mock_usb, mock_core, mock_util):
        stream = Stream(_config())
        stream.ep_in.read.side_effect = USBError()
        assert stream.read() is None


def test_read_raises_when_the_device_disappears() -> None:
    """Device loss is raised so the shared stream poller can reopen it."""
    mock_usb, mock_core, mock_util = _mocks()

    class USBError(Exception):
        """Stand-in for usb.core.USBError."""

        errno = errno.ENODEV

    mock_core.USBError = USBError
    with _patched(mock_usb, mock_core, mock_util):
        stream = Stream(_config())
        stream.ep_in.read.side_effect = USBError()
        try:
            stream.read()
        except USBError:
            return
    raise AssertionError("expected the USB error to propagate")


def test_reconnect_opens_a_device_that_was_missing_at_startup() -> None:
    """A late scanner does not have to be open before other streams start."""
    mock_usb, mock_core, mock_util = _mocks()
    device = mock_core.find.return_value
    mock_core.find.side_effect = [None, device]
    with _patched(mock_usb, mock_core, mock_util):
        stream = Stream(_config())
        stream.reconnect()

    assert mock_core.find.call_count == 2
    assert stream.dev is device


def test_read_timeout_default_matches_a_usb_transfer() -> None:
    """One millisecond is shorter than a USB transfer, so idle reads timed out."""
    assert CONFIG_SCHEMA["read_timeout"]["default"] == 1000
