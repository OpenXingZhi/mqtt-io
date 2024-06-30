"""
USB
"""

from typing import Optional

from . import GenericStream

REQUIREMENTS = ("pyusb",)

CONFIG_SCHEMA = {
    "vid": {"type": "integer", "required": True, "empty": False},
    "pid": {"type": "integer", "required": True, "empty": False},
    "read_size": {"type": "integer", "required": True, "empty": True},
    "read_timeout": {"type": "integer", "default": 1, "required": False, "empty": True},
    "write_size": {"type": "integer", "required": True, "empty": True},
    "interface": {"type": "integer", "required": True, "empty": True},
}

# pylint: disable=c-extension-no-member


class Stream(GenericStream):
    """
    Stream module for sending to and receiving from USB devices.
    """

    def setup_module(self) -> None:
        # pylint: disable=import-error,import-outside-toplevel
        import usb.core  # type: ignore
        import usb.util  # type: ignore

        # Setting up the USB connection
        VENDOR_ID = self.config["vid"]
        PRODUCT_ID = self.config["pid"]
        print("Finding device:", hex(VENDOR_ID), hex(PRODUCT_ID))
        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        # was it found?
        if self.dev is None:
            raise ValueError("Device not found")
        cfg = self.dev.get_active_configuration()
        intf = cfg[(self.config["interface"], 0)]

        self.epIn = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
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

        try:
            self.dev.detach_kernel_driver(1)
        except Exception as e:
            pass

        try:
            self.dev.set_configuration()
        except Exception as e:
            print("Error setting configuration:", e)

        print("Endpoint In:\n", self.epIn)
        print("Endpoint Out:\n", self.epOut)

    def read(self) -> Optional[bytes]:
        try:
            result = bytes(
                self.epIn.read(self.config["read_size"], self.config["read_timeout"])
            )
        except Exception:
            result = None
        return result

    def write(self, data: bytes) -> None:
        byte_list = list(data)
        total_length = len(byte_list)
        chunk_size = self.config["write_size"]
        for i in range(0, total_length, chunk_size):
            chunk = byte_list[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk.extend([0] * (chunk_size - len(chunk)))
            self.epOut.write(chunk)

    def cleanup(self) -> None:
        usb.util.release_interface(self.dev, self.epIn)
        usb.util.release_interface(self.dev, self.epOut)
        usb.util.dispose_resources(self.dev)
