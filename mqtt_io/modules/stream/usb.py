from typing import Optional
import time
import usb.core  # type: ignore
import usb.util  # type: ignore

from . import GenericStream

REQUIREMENTS = ("pyusb",)

CONFIG_SCHEMA = {
    "vid": {"type": "integer", "required": True, "empty": False},
    "pid": {"type": "integer", "required": True, "empty": False},
    "read_size": {"type": "integer", "required": True, "empty": True},
    "read_timeout": {"type": "integer", "default": 1, "required": False, "empty": True},
    "write_size": {"type": "integer", "required": True, "empty": True},
    "interface": {"type": "integer", "required": True, "empty": True},
    "reconnect_interval": {
        "type": "integer",
        "default": 2,
        "required": False,
        "empty": True,
    },
}


class Stream(GenericStream):
    """
    Stream module for sending to and receiving from USB devices.
    """

    def setup_module(self) -> None:
        self._connect_usb()

    def _connect_usb(self) -> None:
        VENDOR_ID = self.config["vid"]
        PRODUCT_ID = self.config["pid"]
        INTERFACE = self.config["interface"]

        while True:
            print("Finding device:", hex(VENDOR_ID), hex(PRODUCT_ID))
            self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if self.dev is not None:
                break
            print("Device not found, retrying in 2s...")
            time.sleep(self.config["reconnect_interval"])

        try:
            self.dev.set_configuration()
        except Exception as e:
            print("Error setting configuration:", e)

        cfg = self.dev.get_active_configuration()
        intf = cfg[(INTERFACE, 0)]

        try:
            if self.dev.is_kernel_driver_active(INTERFACE):
                self.dev.detach_kernel_driver(INTERFACE)
                print(f"Detached kernel driver from interface {INTERFACE}")
        except usb.core.USBError as e:
            print(f"Could not detach kernel driver: {e}")

        self.epIn = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN,
        )
        assert self.epIn is not None

        self.epOut = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )
        assert self.epOut is not None

        print("USB connected")

    def _reconnect(self):
        print("Attempting to reconnect USB...")
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass
        self._connect_usb()

    def read(self) -> Optional[bytes]:
        try:
            return bytes(
                self.epIn.read(self.config["read_size"], self.config["read_timeout"])
            )
        except usb.core.USBError as e:
            if e.errno == 19:  # No such device
                print("USB disconnected during read.")
                self._reconnect()
            else:
                print("USB read error:", e)
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
        except usb.core.USBError as e:
            if e.errno == 19:
                print("USB disconnected during write.")
                self._reconnect()
            else:
                print("USB write error:", e)

    def cleanup(self) -> None:
        try:
            usb.util.release_interface(self.dev, self.config["interface"])
        except Exception:
            pass
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass
