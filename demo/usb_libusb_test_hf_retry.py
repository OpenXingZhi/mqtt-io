import sys
import usb.core
import usb.util
import time
import traceback

VENDOR_ID = 0xFFFE
PRODUCT_ID = 0x0091
INTERFACE = 0


def logData(data):
    return " ".join([f"0x{byte:02X}" for byte in data])


def list_devices():
    devices = usb.core.find(find_all=True)
    if devices:
        print("Connected USB Devices:")
        for dev in devices:
            try:
                print(
                    f"  Vendor: 0x{dev.idVendor:04X}, Product: 0x{dev.idProduct:04X}, "
                    f"Manufacturer: {dev.manufacturer}, Product Name: {dev.product}"
                )
            except usb.core.USBError as e:
                print(f"  Error accessing device: {e}")
    else:
        print("No USB devices found.")


def sendBytes(bytes_data, outPoint):
    byte_list = list(bytes_data)
    total_length = len(byte_list)
    chunk_size = 64
    for i in range(0, total_length, chunk_size):
        chunk = byte_list[i : i + chunk_size]
        if len(chunk) < chunk_size:
            chunk.extend([0] * (chunk_size - len(chunk)))
        outPoint.write(chunk)


def detach_all_interfaces(dev):
    for cfg in dev:
        for intf in cfg:
            try:
                if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    dev.detach_kernel_driver(intf.bInterfaceNumber)
                    print(
                        f"Detached kernel driver from interface {intf.bInterfaceNumber}"
                    )
            except usb.core.USBError as e:
                print(
                    f"Could not detach kernel driver from interface {intf.bInterfaceNumber}: {e}"
                )


def init_device():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Device not found")
        return None, None, None
    try:
        detach_all_interfaces(dev)
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = cfg[(INTERFACE, 0)]

        epIn = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN,
        )
        epOut = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )

        if epIn is None or epOut is None:
            print("Could not find required endpoints")
            return None, None, None

        print("Device initialized.")
        return dev, epIn, epOut

    except Exception as e:
        print("Failed to initialize device:", e)
        return None, None, None


def cleanup(dev):
    try:
        if dev:
            usb.util.release_interface(dev, INTERFACE)
            usb.util.dispose_resources(dev)
    except Exception as e:
        print("Cleanup error:", e)


# 主逻辑循环
def main_loop():
    dev, epIn, epOut = init_device()

    while True:
        if dev is None:
            print("Retrying connection in 3 seconds...")
            time.sleep(3)
            dev, epIn, epOut = init_device()
            continue

        try:
            data = bytes.fromhex("08 AA 07 FF FE 01 04 4B 66")
            print("Sending data:\n", logData(data))
            sendBytes(data, epOut)
            recv = epIn.read(1024, timeout=2000)
            recv_data = " ".join(hex(x) for x in recv)
            print("Received data:\n", recv_data)
            time.sleep(2)

        except usb.core.USBError as e:
            print("USB error occurred:", e)
            cleanup(dev)
            dev = epIn = epOut = None

        except Exception as e:
            print("Unexpected error:", e)
            traceback.print_exc()
            cleanup(dev)
            dev = epIn = epOut = None


try:
    list_devices()
    main_loop()
except KeyboardInterrupt:
    print("Interrupted by user.")
