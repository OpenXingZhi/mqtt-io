import sys
import usb.core
import usb.util
import time

VENDOR_ID = 0xFFFE
PRODUCT_ID = 0x0091

# 设定 interface 0
INTERFACE = 0


# 输入字节串 bytes 到输出端口 outPoint，每次发送 64 字节
def sendBytes(bytes, outPoint):
    byte_list = list(bytes)
    total_length = len(byte_list)
    chunk_size = 64

    # 将字节串分块发送
    for i in range(0, total_length, chunk_size):
        chunk = byte_list[i : i + chunk_size]
        # 如果不足64字节，则补0
        if len(chunk) < chunk_size:
            chunk.extend([0] * (chunk_size - len(chunk)))
        # 发送数据块到输出端口
        outPoint.write(chunk)


def list_devices():
    """Lists all connected USB devices."""
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


def logData(data):
    return " ".join([f"0x{byte:02X}" for byte in data])


def detach_all_interfaces(dev):
    """Detach all kernel drivers for the device's interfaces."""
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


dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

list_devices()

# was it found?
if dev is None:
    raise ValueError("Device not found")

detach_all_interfaces(dev)  # Detach all interfaces

cfg = dev.get_active_configuration()
print("Active cfg:\n", cfg)

# Set the interface to 0 at the top
intf = cfg[(INTERFACE, 0)]
print("Interface:\n", intf)

epIn = usb.util.find_descriptor(
    intf,
    # match the first OUT endpoint
    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
    == usb.util.ENDPOINT_IN,
)

assert epIn is not None

epOut = usb.util.find_descriptor(
    intf,
    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
    == usb.util.ENDPOINT_OUT,
)

assert epOut is not None

try:
    dev.set_configuration()
except Exception as e:
    print("Error setting configuration:", e)

print("Endpoint In:\n", epIn)
print("Endpoint Out:\n", epOut)

try:
    while True:
        data = bytes.fromhex("08 AA 07 FF FE 01 04 4B 66")
        print("Data:\n", logData(data))
        sendBytes(data, epOut)
        recv = epIn.read(1024)
        recv_data = " ".join(hex(x) for x in recv)
        print("Received data:\n", recv_data)
        time.sleep(2)
except KeyboardInterrupt:
    pass
finally:
    usb.util.release_interface(dev, INTERFACE)
    usb.util.dispose_resources(dev)
