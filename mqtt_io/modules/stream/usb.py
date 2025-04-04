"""
USB
"""

from typing import Optional
import time
import errno

from . import GenericStream

REQUIREMENTS = ("pyusb",)

CONFIG_SCHEMA = {
    "vid": {"type": "integer", "required": True, "empty": False},
    "pid": {"type": "integer", "required": True, "empty": False},
    "read_size": {"type": "integer", "required": True, "empty": True},
    "read_timeout": {
        "type": "integer",
        "default": 1000,
        "required": False,
        "empty": True,
    },
    "write_size": {"type": "integer", "required": True, "empty": True},
    "interface": {"type": "integer", "required": True, "empty": True},
    "retry_interval": {
        "type": "integer",
        "default": 3,
        "required": False,
        "empty": True,
    },
}

# pylint: disable=c-extension-no-member


class Stream(GenericStream):
    """
    Stream module for sending to and receiving from USB devices.
    """

    def setup_module(self) -> None:
        self.retry_interval = self.config["retry_interval"]
        self._init_usb()

    def _init_usb(self) -> None:
        import usb.core
        import usb.util

        while True:
            try:
                VENDOR_ID = self.config["vid"]
                PRODUCT_ID = self.config["pid"]
                print(f"Finding device: {hex(VENDOR_ID)}, {hex(PRODUCT_ID)}")
                self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
                if self.dev is None:
                    raise ValueError("Device not found")

                cfg = self.dev.get_active_configuration()
                intf = cfg[(self.config["interface"], 0)]

                self.epIn = usb.util.find_descriptor(
                    intf,
                    custom_match=lambda e: usb.util.endpoint_direction(
                        e.bEndpointAddress
                    )
                    == usb.util.ENDPOINT_IN,
                )
                self.epOut = usb.util.find_descriptor(
                    intf,
                    custom_match=lambda e: usb.util.endpoint_direction(
                        e.bEndpointAddress
                    )
                    == usb.util.ENDPOINT_OUT,
                )

                assert self.epIn is not None, "IN endpoint not found"
                assert self.epOut is not None, "OUT endpoint not found"

                try:
                    self.dev.detach_kernel_driver(self.config["interface"])
                    print(
                        f"Kernel driver detached from interface {self.config['interface']}"
                    )
                except usb.core.USBError as e:
                    print(f"Could not detach kernel driver: {e}")

                self.dev.set_configuration()
                print("USB device initialized successfully.")
                return

            except Exception as e:
                print(f"USB init failed: {e}. Retrying in {self.retry_interval}s...")
                time.sleep(self.retry_interval)

    def _reconnect_usb(self) -> None:
        try:
            import usb.util

            usb.util.dispose_resources(self.dev)
        except Exception as e:
            print(f"Error disposing USB resources: {e}")
        self._init_usb()

    def read(self) -> Optional[bytes]:
        import usb.core

        try:
            data = self.epIn.read(self.config["read_size"], self.config["read_timeout"])
            return bytes(data)
        except usb.core.USBError as e:
            if e.errno == errno.ETIMEDOUT:
                return None  # expected when no data
            print(f"USB read error: {e}")
            self._reconnect_usb()
            return None
        except Exception as e:
            print(f"Unexpected read error: {e}")
            self._reconnect_usb()
            return None

    def write(self, data: bytes) -> None:
        try:
            byte_list = list(data)
            total_length = len(byte_list)
            chunk_size = self.config["write_size"]
            for i in range(0, total_length, chunk_size):
                chunk = byte_list[i : i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk.extend([0] * (chunk_size - len(chunk)))
                self.epOut.write(chunk)
        except Exception as e:
            print(f"USB write error: {e}")
            self._reconnect_usb()

    def cleanup(self) -> None:
        import usb.util

        try:
            usb.util.release_interface(self.dev, self.config["interface"])
            usb.util.dispose_resources(self.dev)
        except Exception as e:
            print(f"Error during USB cleanup: {e}")
