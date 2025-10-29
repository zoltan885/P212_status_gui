# tine_poller.py

#!/usr/bin/env python3
import logging
import sys
import PyTine as tine
import asyncio

from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Set


@dataclass(frozen=True)
class TineAddress:
    """Represents a single TINE address."""
    context: str
    server: str
    device: str
    property: str


@dataclass
class TineGroup:
    """Represents a group of devices sharing context, server, and property."""
    context: str
    server: str
    property: str
    devices: Set[str] = field(default_factory=set)

    def add_device(self, device: str) -> None:
        self.devices.add(device)


class TineAddressGroup:
    """Manages and groups TineAddress objects by (context, server, property)."""

    def __init__(self):
        self._grouped: Dict[Tuple[str, str, str], TineGroup] = {}

    def add_address(self, addr: TineAddress) -> None:
        """Add a TineAddress and merge it into its group."""
        key = (addr.context, addr.server, addr.property)
        if key not in self._grouped:
            self._grouped[key] = TineGroup(addr.context, addr.server, addr.property)
        self._grouped[key].add_device(addr.device)

    def add_many(self, addresses: List[TineAddress]) -> None:
        for addr in addresses:
            self.add_address(addr)

    def get_all(self) -> List[TineGroup]:
        return list(self._grouped.values())

    def __repr__(self) -> str:
        return "\n".join(str(group) for group in self._grouped.values())

async def start_query_process(context: str, server: str, property: str, devices: list[str]):
    loop = asyncio.get_event_loop()
    #devs = await loop.run_in_executor(None, tine.list, context, server, property)
    devs = tine.list(context=context, server=server, property=property)
    results = {}
    while True:
        for device in devices:
            try:
                idx = devs['devices'].index(device)
                all_values = await loop.run_in_executor(None, tine.get, f'{context}/{server}/{devs["devices"][0]}', property)
                results[device] = {
                    'timestamp': all_values['timestamp'],
                    'value': all_values['data'][idx],
                    'status': all_values['status'],
                    'address': f"{context}/{server}/{device}",
                    'property': property,
                }
            except ValueError:
                logging.error(f"Device '{device}' not found in TINE device list for property '{property}' on server '{server}' and context '{context}'. Available devices: {devs}")
        logging.debug(f"Results for {context}/{server}/{property}: {results}")
        await asyncio.sleep(1)
    return results

async def async_main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Starting asynchronous TINE polling...")
    group = TineAddressGroup()

    group.add_many([
        TineAddress("PETRA", "HISTORY", "PU21b", "Undulator.Gap"),
        TineAddress("PETRA", "HISTORY", "PU07", "Undulator.Gap"),
        TineAddress("PETRA", "HISTORY", "PU03", "Undulator.Gap"),
        TineAddress("PETRA", "HISTORY", "PU06", "Undulator.Gap"),
        TineAddress("PETRA", "HISTORY", "PS2_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "P1max", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "V2_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "ITR_Mono_B", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "P2max_B", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "V3_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "P3max_B_1", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "P3max_B_2", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "LM5_B", "P21.Stellung"),
    ])

    tasks = []
    for g in group.get_all():
        task = asyncio.create_task(
            start_query_process(g.context, g.server, g.property, sorted(g.devices))
        )
        tasks.append(task)
    await asyncio.sleep(10)  # Allow tasks to start

    # Wait for all queries to complete
    await asyncio.gather(*tasks)


def get_tine_list_idx(context:str, server:str, device:str, property:str) -> dict | None:
    devs = tine.list(context=context, server=server, property=property)
    try:
        idx = devs['devices'].index(device)
    except ValueError:
        logging.error(f"Device '{device}' not found in TINE device list for property '{property}' on server '{server}' and context '{context}'. Available devices: {devs}")
        return None
    return {'index': idx, 'devices': devs}

def get_tine_value(context:str, server:str, device:str, prop:str) -> dict:
    devs = tine.list(context=context, server=server, property=prop)['devices']
    idx = devs.index(device)
    # If we request devs[0], we can get the value for our device by index (idx)
    # If we request another device, the 'data' will come in the same order as the devs list, but will start from the requested device:
    # i.e., if devs = [A, B, C, D] and we request devs[2] (C), the returned 'data' will be [C_value, D_value, A_value, B_value]
    # this means one can always get the correct value by using devs[0] and indexing into 'data' with the index of the desired device.
    # This avoids multiple calls to the TINE server.
    all_values = tine.get(address=f'{context}/{server}/{devs[0]}', property=prop)
    dct = {
        'timestamp': all_values['timestamp'],
        'value': all_values['data'][idx],
        'status': all_values['status'],
        'address': f"{context}/{server}/{device}",
        'property': prop,
        }
    return dct

    
def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    context = 'PETRA'
    server = 'HISTORY'
    device = 'PU21b'
    property = 'Undulator.Gap'

    idx_info = get_tine_list_idx(context, server, device, property)
    if idx_info:
        logging.info(f"Device index info: {idx_info}")

    value_info = get_tine_value(context, server, device, property)
    logging.info(f"Device value info: {value_info}")

if __name__ == "__main__":
    #main()
    asyncio.run(async_main())