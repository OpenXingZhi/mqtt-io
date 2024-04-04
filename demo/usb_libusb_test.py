import usb.core
import usb.util
import sys

VENDOR_ID = 0x0525
PRODUCT_ID = 0xA4AC


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


def logData(data):
    return " ".join([f"0x{byte:02X}" for byte in data])


dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

# was it found?
if dev is None:
    raise ValueError("Device not found")

for cfg in dev:
    print("Getting cfg:\n", cfg)

cfg = dev.get_active_configuration()

print("Active cfg:\n", cfg)

intf = cfg[(1, 0)]

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
    dev.detach_kernel_driver(1)
except Exception as e:
    pass

try:
    dev.set_configuration()
except Exception as e:
    print("Error setting configuration:", e)

print("Endpoint In:\n", epIn)
print("Endpoint Out:\n", epOut)

data = bytes.fromhex("55 AA 01 00 00 FE")
print("Data:\n", logData(data))

sendBytes(data, epOut)

try:
    while True:
        recv = epIn.read(1024)
        recv_data = " ".join(hex(x) for x in recv)
        print("Received data:\n", recv_data)
except KeyboardInterrupt:
    pass
finally:
    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)
