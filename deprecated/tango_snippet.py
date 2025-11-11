import asyncio
import tango

# This only works if the device is operating in the PUSH asynch_replies_model
# dev.set_asynch_replies_model(tango.AsynchReplyType.PUSH_CALLBACK)
# This is a Tango 10 feature.
async def main10():
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    dev = tango.DeviceProxy('hasep21eh3:10000/p21/motor/eh3_u4.05')

    def tango_callback(dev_proxy, attr_value):
        """Called by Tango's internal thread when the data arrives."""
        # Push result into asyncio's queue safely
        loop.call_soon_threadsafe(queue.put_nowait, (dev_proxy.name(), attr_value))

    # Kick off continuous async reads
    async def poller():
        while True:
            dev.read_attribute_asynch("Position", tango_callback)
            await asyncio.sleep(0.5)  # control polling rate

    # Start the Tango polling in asyncio
    asyncio.create_task(poller())

    # Consume results asynchronously
    while True:
        dev_name, attr_value = await queue.get()
        print(f"{dev_name}: {attr_value.name} = {attr_value.value}")
        queue.task_done()


async def read_attrs(dev, attrs):
    """Non-blocking read of Tango attributes."""
    return await asyncio.to_thread(dev.read_attributes, attrs)

from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=20)
async def read_attrs_less_threads(dev, attrs):
    """Read Tango attributes using a shared thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, dev.read_attributes, attrs)


async def poll_device(name, attrs, queue, interval=0.2):
    """Continuously poll a Tango device."""
    dev = tango.DeviceProxy(name)
    while True:
        try:
            result = await read_attrs(dev, attrs)
            #values = {a.name: a.value for a in result}
            #print(f"{name}: {values}")
            #await queue.put((name, result))
            name = result[0].name
            timestamp = result[0].time
            value = result[0].value
            await queue.put((name, value, timestamp))

        except tango.DevFailed as e:
            print(f"[{name}] Tango error: {e}")
        await asyncio.sleep(interval)


##############################################


import asyncio
from concurrent.futures import ThreadPoolExecutor
import tango
from typing import List, Dict
import time

# Configuration
MAX_GLOBAL_CONCURRENCY = 20
DEFAULT_POLL_INTERVAL = 0.2  # seconds
SLOW_DEVICE_THRESHOLD = 0.5  # seconds, device considered slow if read takes longer
MAX_BACKOFF = 5.0  # maximum poll interval for slow devices

async def read_attrsA(dev: tango.DeviceProxy, attrs: List[str], global_semaphore: asyncio.Semaphore):
    """
    Read Tango attributes with global concurrency limit.
    """
    async with global_semaphore:
        loop = asyncio.get_running_loop()
        start = time.time()
        try:
            result = await loop.run_in_executor(None, dev.read_attributes, attrs)
        except Exception as e:
            print(f"Error reading attributes from {dev.name()}: {e}")
            return None, 0.0
        duration = time.time() - start
        return result, duration

async def poll_deviceA(name: str, attrs: List[str], queue: asyncio.Queue, global_semaphore: asyncio.Semaphore):
    dev = tango.DeviceProxy(name)
    interval = DEFAULT_POLL_INTERVAL

    while True:
        try:
            result, duration = await read_attrsA(dev, attrs, global_semaphore)
            if result is None:
                # Read failed, apply backoff
                interval = min(MAX_BACKOFF, interval * 2)
                await asyncio.sleep(interval)
                continue
            for attr in result:
                await queue.put({
                    "device": name,
                    "attr": attr.name,
                    "value": attr.value,
                    "timestamp": attr.time
                })

            # Dynamic adjustment of poll interval based on response time
            if duration > SLOW_DEVICE_THRESHOLD:
                interval = min(MAX_BACKOFF, interval * 1.5)  # backoff for slow devices
            else:
                interval = DEFAULT_POLL_INTERVAL

        except tango.DevFailed as e:
            print(f"[{name}] Tango error: {e}")
            interval = min(MAX_BACKOFF, interval * 2)  # exponential backoff on errors

        await asyncio.sleep(interval)

async def consumer(queue: asyncio.Queue):
    while True:
        update = await queue.get()
        print(f"{update['device']} - {update['attr']} = {update['value']} @ {update['timestamp']}")
        queue.task_done()

async def monitor_queue_rate(queue: asyncio.Queue, interval: float = 1.0):
    """Continuously print the rate of messages per second from an asyncio.Queue."""
    last_time = time.perf_counter()
    count = 0
    now = time.perf_counter()
    while True:
        if abs(now - last_time) < interval:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=interval)
                count += 1
                queue.task_done()
            except asyncio.TimeoutError:
                continue
            now = time.perf_counter()
        else:
            now = time.perf_counter()
            # Compute and print rate every interval
            elapsed = now - last_time
            rate = count / elapsed if elapsed > 0 else 0.0
            print(f"Rate: {rate:.2f} msgs/sec")
            
            last_time, count = time.perf_counter(), 0

async def mainA():
    attrs_VME = ['Acceleration', 'BaseRate', 'Conversion', 'SettleTime', 'SlewRate', 'SlewRateMax', 'SlewRateMin', 'StepBacklash', \
             'UnitBacklash', 'UnitCalibration', 'UnitLimitMax', 'UnitLimitMin', 'CwLimit', 'CcwLimit', 'Position', 'AccuLimitMin',\
             'ConversionEncoder', 'PositionEncoder', 'State', 'Status']  # 20 attributes
    attrs_ZMX = ['StopCurrent', 'RunCurrent', 'PreferentialDirection', 'StepWidth', 'DelayTime', 'StepWidthStr', \
                'Temperature', 'IntermediateVoltage', 'Channel_rd', 'AxisName', 'InputLogicLevel', 'Deactivation',\
                'Overdrive', 'OperationMode', 'DeactivationStr', 'PreferentialDirectionStr', 'InputLogicLevelStr', \
                'OverdriveStr', 'State', 'Status'] # 20 attributes
    devices: Dict[str, List[str]] = {**{f'hasep21eh2:10000/p21/motor/eh2_u1.{d:02d}': attrs_VME for d in range(1, 17)},
                                    **{f'hasep21eh2:10000/p21/motor/eh2_u2.{d:02d}': attrs_VME for d in range(1, 17)},\
                                    **{f'hasep21eh2:10000/p21/ZMX/eh2_u1.{d:02d}': attrs_ZMX for d in range(1, 17)},\
                                    **{f'hasep21eh2:10000/p21/ZMX/eh2_u2.{d:02d}': attrs_ZMX for d in range(1, 17)}\
                                    }

    queue = asyncio.Queue()
    global_semaphore = asyncio.BoundedSemaphore(MAX_GLOBAL_CONCURRENCY)

    # Start poller tasks
    pollers = [
        asyncio.create_task(poll_deviceA(name, attrs, queue, global_semaphore))
        for name, attrs in devices.items()
    ]

    # Start consumer task
    #consumer_task = asyncio.create_task(consumer(queue))

    # Start monitoring task
    monitor_task = asyncio.create_task(monitor_queue_rate(queue))

    await asyncio.gather(*pollers, monitor_task,)

if __name__ == "__main__":
    asyncio.run(mainA())





async def main9():
    queue = asyncio.Queue()
    devices = {
        'hasep21eh2:10000/p21/motor/eh2_u1.01': ["Position"],
        'hasep21eh2:10000/p21/motor/eh2_u1.02': ["Position", 'Acceleration'],
    }

    # create a polling task per device
    tasks = [
        asyncio.create_task(poll_device(name, attrs, queue, 1))
        for name, attrs in devices.items()
    ]

    while True:
        mess = await queue.get()
        print(f"Queue received:\n{mess}")
        queue.task_done()

    # optionally: handle graceful cancellation
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("Polling stopped.")


if __name__ == "__main__":
    asyncio.run(mainA())




