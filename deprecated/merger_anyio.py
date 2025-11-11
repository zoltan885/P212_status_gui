############### Alternative using anyio #####################

import anyio
import random
import time

# Configuration
N_PRODUCERS = 3
QUEUE_SIZE = 20
MASTER_QUEUE_SIZE = 100
PRODUCE_INTERVAL = (0.05, 0.15)
CONSUME_INTERVAL = 0.1


# ------------------------------------------------
# Producer
# ------------------------------------------------
async def producer(name, send_stream):
    async with send_stream:
        for i in range(200):  # simulate ongoing updates
            await send_stream.send((name, i, time.time()))
            await anyio.sleep(random.uniform(*PRODUCE_INTERVAL))
        print(f"{name} finished producing.")


# ------------------------------------------------
# Adaptive merger
# ------------------------------------------------
async def adaptive_merger(receive_streams, master_send, check_interval=0.2):
    """
    Merge items from all producer streams into master_send,
    adapting to backpressure based on master buffer fill.
    """
    async with master_send:
        async with anyio.create_task_group() as tg:
            # Start a forwarding task per input stream
            for recv in receive_streams:
                tg.start_soon(forward_stream, recv, master_send, check_interval)


async def forward_stream(recv, master_send, check_interval):
    async with recv:
        async for item in recv:
            # Monitor how full the master stream is
            buf = master_send._state.buffer
            buf_size = len(buf)
            buf_max = master_send._state.max_buffer_size

            fill_ratio = buf_size / buf_max if buf_max else 0.0

            # Dynamic adaptation: slow down or speed up
            if fill_ratio > 0.8:
                # Master queue almost full → apply backpressure
                await anyio.sleep(check_interval * 2)
            elif fill_ratio > 0.5:
                # Moderate pressure → slight slowdown
                await anyio.sleep(check_interval * 0.5)

            # Forward message
            await master_send.send(item)


# ------------------------------------------------
# Consumer
# ------------------------------------------------
async def consumer(master_recv):
    async with master_recv:
        async for (name, value, ts) in master_recv:
            # Simulate varying processing load
            await anyio.sleep(CONSUME_INTERVAL * random.uniform(0.8, 1.5))
            print(f"[{name}] val={value} time={ts:.3f}")


# ------------------------------------------------
# Monitor (optional)
# ------------------------------------------------
async def monitor(master_send, interval=1.0):
    while True:
        buf = master_send._state.buffer
        buf_size = len(buf)
        buf_max = master_send._state.max_buffer_size
        fill_ratio = buf_size / buf_max if buf_max else 0
        print(f"[MONITOR] master buffer {buf_size}/{buf_max} ({fill_ratio*100:.1f}%)")
        await anyio.sleep(interval)


# ------------------------------------------------
# Main
# ------------------------------------------------
async def main():
    recv_streams = []
    producers = []

    # Create individual producer streams
    for i in range(N_PRODUCERS):
        send, recv = anyio.create_memory_object_stream(max_buffer_size=QUEUE_SIZE)
        producers.append((f"producer{i+1}", send))
        recv_streams.append(recv)

    # Create master output stream
    master_send, master_recv = anyio.create_memory_object_stream(max_buffer_size=MASTER_QUEUE_SIZE)

    async with anyio.create_task_group() as tg:
        # Producers
        for name, send in producers:
            tg.start_soon(producer, name, send)

        # Adaptive merger
        tg.start_soon(adaptive_merger, recv_streams, master_send)

        # Consumer
        tg.start_soon(consumer, master_recv)

        # Monitor (optional)
        tg.start_soon(monitor, master_send, 1.0)

anyio.run(main)