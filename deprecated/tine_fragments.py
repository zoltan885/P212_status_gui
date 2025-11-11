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
                logger.error(f"Device '{device}' not found in TINE device list for property '{property}' on server '{server}' and context '{context}'. Available devices: {devs}")
        logger.debug(f"Results for {context}/{server}/{property}: {results}")
        await asyncio.sleep(1)
    return results

class AsyncTinePoller():
    def __init__(self, queue: asyncio.Queue):
        self.startEvent = asyncio.Event()
        self.pauseEvent = asyncio.Event()
        self.stopEvent = asyncio.Event()
        self.startEvent.clear()
        self.pauseEvent.clear()
        self.stopEvent.clear()

        self.queue = queue
        self.tasks = {}
        #self.log = {}
        #self.current_state = {}
        #self.last_state = []
        self._grace = GRACE

        self.group_collection = TineGroupCollection()

        self._loop = None
        self._loop_thread = None

        if TEST:
            task = asyncio.create_task(
                    self.queue_consumer(self.queue)
                )
            

    # ------------------------
    # Public methods (context-aware)
    # ------------------------
    def add_entry(self, *args, **kwargs):
        return self._call_context_aware(self._add_entry(*args, **kwargs))

    def start(self):
        return self._call_context_aware(self._start_async())

    def pause(self):
        return self._call_context_aware(self._pause_async())

    def resume(self):
        return self._call_context_aware(self._resume_async())

    def stop(self):
        return self._call_context_aware(self._stop_async(), stop_loop=True)
    
    async def _start_async(self):
        self.startEvent.set()
        self.pauseEvent.clear()  # could be used for resuming

    async def _pause_async(self):
        self.pauseEvent.set()

    async def _resume_async(self):
        self.pauseEvent.clear()

    async def _stop_async(self):
        self.stopEvent.set()
        logger.debug('Poller stopping...')
        for task in list(self.tasks.values()):
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()
        logger.debug('All tasks stopped.')

    # ------------------------
    # Async core methods
    # ------------------------
    
    async def _add_entry(self, addr: TineAddress | list[TineAddress]):
        '''
        adds TineAddress or list of TineAddress to the polling group
        takes care of starting the process if it is not running yet
        '''
        if isinstance(addr, list):
            self.group_collection.add_many(addr)
        else:
            self.group_collection.add_address(addr)

        # TineGroupCollection already handles adding new addresses only.
        # Now we need to create tasks for the new TineGroup entries, but not for all Addresses in the group.
        # We need IDs for TineGroup entries, not TineAddress entries. But this means we end up with multiple devices having the same ID.

        all_addresses = self.group_collection.get_groups()
        new_addresses = [g for g in all_addresses.values() if utilities.create_ID(g) not in self.tasks]

        for g in new_addresses:
            ID = utilities.create_ID(g)
            if ID in self.tasks:
                logger.info(f'Task with ID {ID} already exists')
                continue
            task = asyncio.create_task(
                self.start_query_process(g.context, g.server, g.property)
            )
            self.tasks[ID] = task
            print(f'Created polling task for ID {ID}')


    async def remove_entry(self, addr: TineAddress):   # this needs to be more complex as we need to check if other devices are still using the same server/property
        ID = utilities.create_ID(addr)
        task = self.tasks.pop(ID, None)
        if task:
            task.cancel()
            logger.info(f"Cancelled task for ID {ID}")


    async def start_query_process(self, context: str, server: str, property: str):
        loop = asyncio.get_event_loop()

        #devs = await loop.run_in_executor(None, tine.list, context, server, property)
        all_devs_in_tine = tine.list(context=context, server=server, property=property)
        results = {}
        await self.startEvent.wait()
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                await asyncio.sleep(0.1)
                continue
            key = (context, server, property)
            devices = list(self.group_collection.get_groups()[key].devices)  # get all devices for this group
            for device in devices:
                ID = device.id
                try:
                    idx = all_devs_in_tine['devices'].index(device)
                    all_values = await loop.run_in_executor(None, tine.get, f'{context}/{server}/{all_devs_in_tine["devices"][0]}', property)
                    results[device] = {
                        'ID': ID,
                        'timestamp': all_values['timestamp'],
                        'value': all_values['data'][idx],
                        'status': all_values['status'],
                        'address': f"{context}/{server}/{device}",
                        'property': property,
                    }
                except ValueError:
                    logger.error(f"Device '{device}' not found in TINE device list for property '{property}' on server '{server}' and context '{context}'. Available devices: {all_devs_in_tine}")
            # print(f'{self.group_collection=}')
            # key = (context, server, property)
            # print(f'{self.group_collection.get_groups()[key].devices=}')
            print(f"Results for {context}/{server}/{property}: {results}")
            for d in results.values():
                await self.queue.put(d)
            await asyncio.sleep(self._grace)


    # ------------------------
    # Context handling helper
    # ------------------------
    def _call_context_aware(self, coro, stop_loop=False):
        """Runs async method in correct context."""
        try:
            loop = asyncio.get_running_loop()
            # Already in async context
            return coro
        except RuntimeError:
            # Sync context
            self._ensure_loop()
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            result = fut.result()
            if stop_loop and self._loop:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._loop_thread.join()
                self._loop = None
                self._loop_thread = None
            return result

    def _ensure_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
            self._loop_thread.start()

    async def queue_consumer(self, queue: asyncio.Queue):
        while True:
            msg = await queue.get()
            print(f"Queue Consumer received:\n{msg}")
            queue.task_done()




    async def query_process_old(self, context: str, server: str, property: str):
        loop = asyncio.get_event_loop()

        all_devs_in_tine = tine.list(context=context, server=server, property=property)
        results = {}
        await self.startEvent.wait()
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                await asyncio.sleep(0.1)
                continue
            key = (context, server, property)
            devices = list(self.group_collection.get_groups()[key].devices)  # get all devices for this group
            for device in devices:
                ID = device.id
                try:
                    idx = all_devs_in_tine['devices'].index(device)
                    all_values = await loop.run_in_executor(None, tine.get, f'{context}/{server}/{all_devs_in_tine["devices"][0]}', property)
                    results[device] = {
                        'ID': ID,
                        'timestamp': all_values['timestamp'],
                        'value': all_values['data'][idx],
                        'status': all_values['status'],
                        'address': f"{context}/{server}/{device}",
                        'property': property,
                    }
                except ValueError:
                    logger.error(f"Device '{device}' not found in TINE device list for property '{property}' on server '{server}' and context '{context}'. Available devices: {all_devs_in_tine}")
            # print(f'{self.group_collection=}')
            # key = (context, server, property)
            # print(f'{self.group_collection.get_groups()[key].devices=}')
            print(f"Results for {context}/{server}/{property}: {results}")
            for d in results.values():
                await self.queue.put(d)
            await asyncio.sleep(self._grace)



async def class_main():
    global TEST
    TEST = True
    queue = asyncio.Queue()
    ATP = AsyncTinePoller(queue)
    entries = [
        TineAddress("PETRA", "HISTORY", "PS2_B", "P21.Stellung"),
        #TineAddress("PETRA", "HISTORY", "P1max", "P21.Druck"),
        #TineAddress("PETRA", "HISTORY", "V2_B", "P21.Stellung"),
        #TineAddress("PETRA", "HISTORY", "ITR_Mono_B", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "P2max_B", "P21.Druck"),
        #TineAddress("PETRA", "HISTORY", "V3_B", "P21.Stellung"),
        #TineAddress("PETRA", "HISTORY", "P3max_B_1", "P21.Druck"),
        #TineAddress("PETRA", "HISTORY", "P3max_B_2", "P21.Druck"),
        #TineAddress("PETRA", "HISTORY", "LM5_B", "P21.Stellung"),
    ]

    entries2 = [
        TineAddress("PETRA", "HISTORY", "V2_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "PU21b", "Undulator.Gap"),
        #TineAddress("PETRA", "HISTORY", "PU07", "Undulator.Gap"),
        #TineAddress("PETRA", "HISTORY", "PU03", "Undulator.Gap"),
        #TineAddress("PETRA", "HISTORY", "PU06", "Undulator.Gap"),
    ]
    await ATP.add_entry(entries)
    logger.info("Entries added to AsyncTinePoller")
    print("Entries added to AsyncTinePoller")
    await asyncio.sleep(1)
    print("Starting AsyncTinePoller")
    await ATP.start()
    await asyncio.sleep(5)
    print("Adding more entries to AsyncTinePoller")
    await ATP.add_entry(entries2)
    print("More entries added to AsyncTinePoller")
    await asyncio.sleep(5)
    # print("Removing an entry from AsyncTinePoller")
    # await ATP.remove_entry(entries[0])
    # await asyncio.sleep(5)

    #await ATP.pause()
    #print("AsyncTinePoller paused")
    #await asyncio.sleep(5)
    #await ATP.resume()
    #print("AsyncTinePoller resumed")
    #await asyncio.sleep(10)
    await ATP.stop()
    print("AsyncTinePoller stopped")


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
