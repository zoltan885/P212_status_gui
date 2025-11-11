from abc import ABC, abstractmethod
import inspect
import logging
import asyncio
import threading

log = logging.getLogger(__name__)

from dataclasses import dataclass, field, replace
from typing import Dict, Tuple, List, Set, Optional

class StrictABC(ABC):
    """Base class that enforces method signatures of abstract methods."""

    def __init_subclass__(cls):
        super().__init_subclass__()

        # Go through all base classes that are ABCs
        for base in cls.__mro__[1:]:
            # Skip if not a subclass of our strict system
            if not issubclass(base, StrictABC):
                continue

            # Find all abstract methods in the base
            abstracts = {
                name: func
                for name, func in base.__dict__.items()
                if getattr(func, "__isabstractmethod__", False)
            }

            # For each abstract method, compare signatures
            for name, base_func in abstracts.items():
                # Check that subclass defines the method
                sub_func = getattr(cls, name, None)
                if sub_func is None or getattr(sub_func, "__isabstractmethod__", False):
                    continue  # not implemented yet (still abstract)

                base_sig = inspect.signature(base_func)
                sub_sig = inspect.signature(sub_func)

                if base_sig != sub_sig:
                    raise TypeError(
                        f"Signature mismatch for method '{name}' in {cls.__name__}: "
                        f"{sub_sig} != {base_sig}"
                    )





class AsyncPoller(StrictABC):
    """
    Async Poller with sync/async API compatibility.

    add_entity(), start(), pause(), resume(), stop()
    are available from either synchronous or asynchronous code.
    """

    def __init_subclass__(cls):
        """Automatically assign a class-specific logger."""
        super().__init_subclass__()
        cls.logger = logging.getLogger(cls.__name__)  # unique per subclass

    def __init__(self, queue: asyncio.Queue):
        self.startEvent = asyncio.Event()
        self.pauseEvent = asyncio.Event()
        self.stopEvent = asyncio.Event()

        self.queue = queue  # this is the output queue
        # self._tasks_dct = {}
        # self.log = {}
        # self.current_state = {}
        # self.last_state = []

        self._loop = None
        self._loop_thread = None

    @property
    @abstractmethod
    def _grace(self) -> float:
        """Get polling grace period in seconds."""
        pass
    
    @_grace.setter
    @abstractmethod
    def _grace(self, value: float):
        """Set polling grace period in seconds."""
        pass
    
    # ------------------------
    # Public methods (context-aware)
    # ------------------------
    def add_entry(self, *args, **kwargs):
        return self._call_context_aware(self._add_attr_async(*args, **kwargs))

    def start(self):
        return self._call_context_aware(self._start_async())

    def pause(self):
        return self._call_context_aware(self._pause_async())

    def resume(self):
        return self._call_context_aware(self._resume_async())

    def stop(self):
        return self._call_context_aware(self._stop_async(), stop_loop=True)

    # ------------------------
    # Async core methods
    # ------------------------
    @abstractmethod
    async def _add_entry(self, entitydict: dict):
        pass

    @abstractmethod
    async def _remove_entry(self, ID: str):
        pass

    @abstractmethod
    async def _worker(self, index, ID, attrProxy, devProxy, queue, logged=False, name=None):  # signature has to be decided
        pass

    async def _start_async(self):
        self.startEvent.set()
        self.pauseEvent.clear()  # could be used for resuming
        self.logger.debug('Poller tasks started')

    async def _pause_async(self):
        self.pauseEvent.set()
        self.logger.debug('Poller tasks paused')

    async def _resume_async(self):
        self.pauseEvent.clear()
        self.logger.debug('Poller tasks started')

    async def _stop_async(self):
        self.stopEvent.set()
        self.logger.debug('Poller tasks stopped')
        for t in self._tasks_dct.values():
            try:
                await t.task
            except asyncio.CancelledError:
                pass

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


# @dataclass(frozen=True)
# class TineAddress:
#     """Represents a single TINE address."""
#     context: str
#     server: str
#     device: str
#     property: str

@dataclass(frozen=True)
class TineAddress:
    """Represents a single TINE address."""
    context: str
    server: str
    device: str
    property: str
    id: Optional[str] = None

    def add_id(self, new_id: str) -> "TineAddress":
        """Return a new instance with the given ID."""
        return replace(self, id=new_id)


@dataclass
class TineGroup:
    """Represents a group of devices sharing context, server, and property."""
    context: str
    server: str
    property: str
    devices: Set[str] = field(default_factory=set)

    def add_device(self, device: str) -> None:
        self.devices.add(device)


class TineGroupCollection:
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

    def remove_address(self, addr: TineAddress) -> None:
        """Remove a TineAddress from its group."""
        key = (addr.context, addr.server, addr.property)
        if key in self._grouped:
            group = self._grouped[key]
            group.devices.discard(addr.device)
            if not group.devices:
                del self._grouped[key]
    
    def remove_many(self, addresses: List[TineAddress]) -> None:
        for addr in addresses:
            self.remove_address(addr)

    def get_all(self) -> List[TineGroup]:
        return list(self._grouped.values())
    
    def get_groups(self) -> Dict[Tuple[str, str, str], TineGroup]:
        return self._grouped

    def __repr__(self) -> str:
        return "\n".join(str(group) for group in self._grouped.values())