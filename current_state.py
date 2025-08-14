
import time
import logging
from collections import namedtuple, deque
from multiprocessing import Event
from threading import Lock
import threading
from queue import Queue, Empty

statetuple = namedtuple('state', ['value', 'state', 'timestamp'])


UPDATE_INTERVAL = 0.5  # seconds
UPDATE_MIN_INTERVAL = 0.1  # seconds
UPDATE_MAX_INTERVAL = 5.0  # seconds

RTOL = 1e-3  # relative tolerance for float comparison
ATOL = 1e-4  # absolute tolerance for float comparison

DEBUG = False  # set to True to enable debug logging

# TODO - consider using a more sophisticated data structure for state management, like a custom class or a more complex namedtuple
# TODO - consider adding type hints for better clarity and type checking
# TODO - consider adding more detailed logging for debugging purposes
# TODO - the outgoing messages should not contain pytango states, but just a string representation of them


class OverwritingSingleSlotQueue:
    """
    A thread-safe queue with a single slot that overwrites its content on each put.
    This queue is designed to hold only one item at a time. When a new item is put into the queue,
    it replaces the existing item if present. The queue supports thread-safe put and get operations,
    where get will wait for an item to become available, optionally with a timeout.
    Methods
    -------
    put(item):
        Add an item to the queue, overwriting any existing item.
    get(timeout=None):
        Retrieve the current item from the queue without removing it.
        If the queue is empty, waits until an item is available or until the timeout expires.
        Raises TimeoutError if no item is available within the timeout.
    empty():
        Returns True if the queue is empty, False otherwise.
    
    """
    def __init__(self):
        self._data = deque(maxlen=1)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)

    def put(self, item):
        with self._lock:
            self._data.append(item)
            self._not_empty.notify_all()

    def get(self, timeout=None):
        with self._not_empty:
            if not self._data:
                if not self._not_empty.wait(timeout=timeout):
                    raise TimeoutError("Timeout waiting for item.")
            if self._data:
                return self._data[0]  # Return without removing
            raise TimeoutError("Timeout waiting for item.")  # Edge case

    def empty(self):
        with self._lock:
            return len(self._data) == 0


class CurrentStateMonitor:
    '''
    CurrentStateMonitor is a class designed to monitor, filter, and report the state of messages received from an input queue.
    It maintains an internal state of messages, detects significant changes in message values or states, and manages the periodic
    reporting of filtered messages to an update queue. The class also supports snapshotting the current state and provides
    threaded, interval-based reporting with pause and stop controls.
    Attributes:
        in_queue (Queue): The input queue from which messages are received.
        update_queue (Queue): The queue to which filtered messages are sent for updates.
        snapshot_queue (Queue): The queue to which snapshots of the current state are sent.
        filtered_messages (deque): A fixed-length deque holding the most recent filtered messages.
        state (dict): A dictionary mapping message IDs to their latest message data.
        threads (list): A list to keep track of any additional threads (currently unused).
        _report_interval (float): The interval (in seconds) between automatic reports.
        pause_report (Event): Threading event to pause the reporting thread.
        stop_report (Event): Threading event to stop the reporting thread.
        report_thread (Thread): The background thread responsible for periodic reporting.
    Methods:
        _isclose(a, b, rtol=RTOL, atol=ATOL):
            Determines if two numeric values are close within specified tolerances.
        _value_changed(old_value, new_value):
            Checks if the value has changed significantly between two inputs.
        _state_changed(old_state, new_state):
            Checks if the state has changed between two inputs.
        filter_messages():
            Processes and filters messages from the input queue, updating internal state and filtered messages.
        snapshot():
            Creates and sends a snapshot of the current state to the snapshot queue.
        report():
            Sends all filtered messages to the update queue and clears the filtered messages list.
        start_self_report():
            Unpauses the reporting thread to resume periodic reporting.
        pause_self_report():
            Pauses the reporting thread, halting periodic reporting.
        stop_self_report():
            Stops the reporting thread and waits for it to terminate.
        _report_worker():
            The worker method run by the reporting thread, periodically calling report() based on the report interval.
    Properties:
        report_interval (float): Gets or sets the interval (in seconds) between automatic reports, enforcing min/max bounds.
    Usage:
        Instantiate the class with appropriate queues, then use the reporting controls to manage periodic reporting.
        The class is designed to be thread-safe and to operate in the background, filtering and reporting state changes as needed.
    '''

    def __init__(self,
                 in_queue:Queue = None,
                 update_queue:Queue = None,
                 snapshot_queue:OverwritingSingleSlotQueue = None):
        self.in_queue = in_queue
        self.filtered_messages = deque([], maxlen=10000)  # to keep the messages in their original format, agnostic to message details
        self.update_queue = update_queue
        self.snapshot_queue = snapshot_queue
        self.state = {}# defaultdict(lambda: statetuple(None, None))
        self.threads = []
        self._report_interval = UPDATE_INTERVAL

        self.pause_report = Event()
        self.pause_report.set()  # initially paused
        self.stop_report = Event()
        self._lock = threading.Lock()
        
        self.report_thread = threading.Thread(target=self._report_worker)
        self.report_thread.daemon = True  # to ensure the thread will not block program exit
        self.report_thread.start()

        self.snapshot_thread = threading.Thread(target=self._snapshot_worker)
        self.snapshot_thread.daemon = True  # to ensure the thread will not block program exit
        self.snapshot_thread.start()


    def _isclose(self, a, b, rtol=RTOL, atol=ATOL):
        """
        Determine whether two values are close to each other within a relative or absolute tolerance.

        Args:
            a (float): First value to compare.
            b (float): Second value to compare.
            rtol (float, optional): Relative tolerance. Defaults to RTOL.
            atol (float, optional): Absolute tolerance. Defaults to ATOL.

        Returns:
            bool: True if the values are close within the specified tolerances, False otherwise.

        Notes:
            - The function avoids division by zero by using a small epsilon (1e-30) in the denominator.
            - Returns False if either the absolute or relative difference exceeds the respective tolerance.
        """
        abs_diff = abs(a - b)
        rel_diff = abs_diff / max(abs(a), abs(b), 1e-30)  # avoid division by zero
        abs_fail = abs_diff > atol
        rel_fail = rel_diff > rtol
        if abs_fail or rel_fail:
            return False
        return True
    
    def _value_changed(self, old_value, new_value):
        """
        Determine if the value has changed between two inputs.

        Compares the old and new values to check if a significant change has occurred.
        For numeric types (float or int), it uses a tolerance-based comparison via the
        `_isclose` method with predefined relative (`RTOL`) and absolute (`ATOL`) tolerances.
        For strings, it checks for direct equality.

        Args:
            old_value (float | int | str): The previous value.
            new_value (float | int | str): The new value to compare against the old value.

        Returns:
            bool: True if the value has changed significantly (for numbers) or is different (for strings),
                  False otherwise.
        """
        if isinstance(old_value, (float, int)) and isinstance(new_value, (float, int)):
            return not self._isclose(old_value, new_value, rtol=RTOL, atol=ATOL)
        elif isinstance(old_value, str) and isinstance(new_value, str):
            if old_value == new_value:
                return False
            else:
                return True
        return old_value != new_value  # fallback for other types (e.g., None, lists, etc.)
    
    def _state_changed(self, old_state, new_state):
        return old_state != new_state

    @property
    def report_interval(self):
        return self._report_interval
    
    @report_interval.setter
    def report_interval(self, value):
        value = abs(float(value))
        if value < UPDATE_MIN_INTERVAL:
            self._report_interval = UPDATE_MIN_INTERVAL
        elif value > UPDATE_MAX_INTERVAL:
            self._report_interval = UPDATE_MAX_INTERVAL
        else:
            self._report_interval = value
    
    def filter_messages(self):
        """
        Processes messages from the input queue, filters them based on changes in value or state,
        and updates the internal state and filtered messages list accordingly.
        For each message in the input queue:
            - If the message's ID is already tracked in the internal state:
                - Compares the new value and state with the existing ones.
                - If either has changed, updates the state and ensures only the latest message for that ID
                  is present in the filtered messages list.
            - If the message's ID is new:
                - Adds it to the internal state and filtered messages list.
        The method clears the filtered messages list at the start and processes all messages currently
        available in the input queue.
        Exceptions during message retrieval or processing will terminate the filtering loop.
        """
        
        self.filtered_messages.clear()
        with self._lock:
            while not self.in_queue.empty():
                try:
                    msg = self.in_queue.get(timeout=0.01)
                    logging.info(f"Got message: {msg}")
                    ID = msg['ID']
                    value = msg['value']
                    state = msg['state']
                    timestamp = msg['timestamp']
                    if ID in self.state:
                        logging.debug(f"ID in state: {ID}")
                        logging.debug(f'Comparing: {self.state[ID]['value']}, {value}, {self.state[ID]['state']}, {state}')
                        if self._value_changed(self.state[ID]['value'], value) or \
                        self._state_changed(self.state[ID]['state'], state):
                            logging.debug(f'Value or state changed for ID: {ID}')
                            self.state[ID] = msg
                            #self.filtered_messages.append(msg)

                            # keep only the latest message for the ID

                            # This could be done at the beginning but then one would need to keep the incoming messages in a list
                            # and then filter them, which is also not too elegant
                            for i in range(len(self.filtered_messages)):
                                if self.filtered_messages[i]['ID'] == ID:
                                    self.filtered_messages[i] = msg
                                    break
                            else:
                                self.filtered_messages.append(msg)
                    else:
                        logging.debug(f"ID not in state {ID}")
                        self.state[ID] = msg
                        self.filtered_messages.append(msg)
                except Empty as e:
                    break
                except Exception as e:
                    logging.error("Exception in filter_messages: %s", e)
                    break


    def snapshot(self):
        """
        Creates a snapshot of the current messages state and sends it to the snapshot_queue.

        Iterates over the current state messages, collects them into a list, and puts the list
        into the snapshot_queue if it is not empty.
        """

        snapshot = []
        with self._lock:
            if not self.snapshot_queue.empty():
                logging.warning('Snapshot queue is not empty, clearing it before new snapshot')
                while not self.snapshot_queue.empty():
                    self.snapshot_queue.get()
            
            for ID, msg in self.state.items():
                snapshot.append(msg)
            if snapshot:
                self.snapshot_queue.put(snapshot)

    def report(self):
        """
        Send all filtered messages to the update queue.

        Filters messages and places each filtered message into the update queue if it is set.
        If the update queue is not set, logs an error. Clears the filtered messages after processing.
        """

        self.filter_messages()
        with self._lock:
            if self.update_queue is not None:
                while len(self.filtered_messages) > 0:
                    msg = self.filtered_messages.popleft()
                    self.update_queue.put(msg)
            else:
                logging.error('No update queue set, cannot send message')
            # self.filtered_messages.clear()

    def start_self_report(self):
        '''
        unpauses the reporting thread
        '''
        self.pause_report.clear()  # unpause the reporting thread
    
    def pause_self_report(self):
        '''
        pauses the reporting thread
        '''
        self.pause_report.set()
    
    def stop_self_report(self):
        '''
        stops the reporting thread
        '''
        self.stop_report.set()
        if self.report_thread.is_alive():
            self.report_thread.join()

    def _report_worker(self):
        """
        Runs in a separate thread to periodically call the report method while not paused or stopped.

        The method continuously checks two threading events:
        - If `stop_report` is set, the loop exits and the worker stops.
        - If `pause_report` is set, reporting is paused and a debug message is logged.
        - Otherwise, it calls the `report()` method, logging any exceptions that occur.

        After each iteration, the thread sleeps for `report_interval` seconds before checking again.
        """
    
        while not self.stop_report.is_set():
            if not self.pause_report.is_set():
                try:
                    self.report()
                except Exception as e:
                    logging.error('Error in report worker: %s', e)
            else:
                pass
                #logging.debug('Report worker is paused')
            time.sleep(self.report_interval)

    def _snapshot_worker(self):
        """
        Worker method to periodically create and send snapshots of the current state.
        
        This method runs in a separate thread and calls the snapshot method at intervals defined by
        the report_interval attribute. It handles exceptions that may occur during snapshot creation.
        """
        while not self.stop_report.is_set():
            if not self.pause_report.is_set():
                try:
                    self.snapshot()
                except Exception as e:
                    logging.error('Error in snapshot worker: %s', e)
            time.sleep(self.report_interval)

    def __del__(self):
        """
        Destructor to ensure the reporting thread is stopped when the instance is deleted.
        """
        self.stop_self_report()
        logging.info('CurrentStateMonitor instance deleted, reporting thread stopped.')