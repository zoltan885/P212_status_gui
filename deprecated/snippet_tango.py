import PyTango as tango


# Callback function
def read_callback(attr_value, exc=None):
    if exc:
        print(f"Error occurred: {exc}")
    else:
        print(f"Attribute value: {attr_value.value}")

# Create the DeviceProxy
device = tango.DeviceProxy('hasep21eh3:10000/p21/motor/eh3_u4.05')

# Asynchronous read request
device.read_attribute_asynch("Acceleration", read_callback)

# Keep the IPython kernel alive long enough for the callback to trigger
import time
time.sleep(10)  # Adjust time depending on how long it takes to read the attribute
