import hid
import time

# enumerate USB devices

for d in hid.enumerate():
    keys = list(d.keys())
    keys.sort()
    for key in keys:
        print("%s : %s" % (key, d[key]))
    print()

# try opening a device, then perform write and read
h = hid.device()
try:
    print("Opening the device")
    h.open(0x0091, 0xFFFE)  # TREZOR VendorID/ProductID

    print("Manufacturer: %s" % h.get_manufacturer_string())
    print("Product: %s" % h.get_product_string())
    print("Serial No: %s" % h.get_serial_number_string())

    # enable non-blocking mode
    h.set_nonblocking(1)

    # # write some data to the device
    # print("Write the data")
    # data = bytes.fromhex("55 AA 01 00 00 FE")
    # h.write(data)

    # wait
    time.sleep(0.05)

    # read back the answer
    print("Read the data")
    while True:
        d = h.read(64)
        if d:
            print(" ".join([hex(byte) for byte in d]))
        else:
            break

    print("Closing the device")
    h.close()

except IOError as ex:
    print(ex)
    print("hid error:")
    print(h.error())
    print("")
    print("You probably don't have the hard-coded device.")
    print("Update the h.open() line in this script with the one")
    print("from the enumeration list output above and try again.")

print("Done")
