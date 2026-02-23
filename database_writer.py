
import logging
import asyncio
import os
import sys
import random
import time
import signal
import dataset
from datetime import datetime, timezone
import dateutil.parser
import uuid

logFormatter = logging.Formatter(
    "%(asctime)-25.25s %(threadName)-12.12s %(name)-25.24s %(levelname)-10.10s %(message)s")
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)


DB_URL = "sqlite:///sensors.db" # Later: "postgresql+psycopg2://myuser:mypass@localhost/mydb"
TABLE_NAME = "measurements"
MAINTENANCE_INTERVAL = 10 # 300
VACUUM_INTERVAL = 30 # 7200
DB_PATH = "sensors.db"
BATCH_SIZE = 200
FLUSH_INTERVAL = 1.0  # seconds

def utcnow():
    return datetime.now(timezone.utc)






class DatabaseWriter():
    def __init__(self, in_queue, db_url=None, table_name=None):
        logging.debug("Initializing DatabaseWriter...")
        self.db_url = db_url or DB_URL  # use default if None, default could come from config later
        self.table_name = table_name or TABLE_NAME
        self.db = dataset.connect(self.db_url)
        self.db_backend = self.db.engine.url.get_backend_name()
        logging.debug("Database connected.")
        self.attr_table_name = 'attr_'+ self.table_name
        self.tine_table_name = 'tine_'+ self.table_name
        self.property_table_name = 'property_'+ self.table_name
        self.default_table_name = 'default_'+ self.table_name
        logging.debug(f"Connecting to database at {self.db_url}...")
        self.attr_table = self.db[self.attr_table_name]
        self.tine_table = self.db[self.tine_table_name]
        self.property_table = self.db[self.property_table_name]
        self.default_table = self.db[self.default_table_name]
        logging.debug("Creating tables if they do not exist...")
        #self._attr_table_creator(self.attr_table)
        #self._tine_table_creator(self.tine_table)
        #self._property_table_creator(self.property_table)
        #self._default_table_creator(self.default_table)
        self.in_queue = in_queue
        self.stop_event = asyncio.Event()
        self.t0 = time.time()
        logging.debug("DatabaseWriter initialized.")
        #return self.db, self.attr_table, self.tine_table, self.property_table


    async def stop(self):
        self.stop_event.set()

    async def start(self):
        await self.run()

    def _attr_table_creator(self, table):
        """Create table and indexes if they do not exist.
        This is meant to be used with Tango attributes
        """
        if not table.exists:
            logging.info(f"Creating table {table.name}")
            # table.create_column("timestamp", dataset.types.datetime)
            # table.create_column("device", type="string")
            # table.create_column("attribute", type="string")
            # table.create_column("value", type="float")
            # table.create_column("unit", type="string")
            # table.create_column("location", type="string")
            # table.create_column("state", type="string")
            # table.create_column("status", type="string")
            # this is an alternative way to create the table by inserting a dummy row
            table.insert({
                "timestamp": time.time(),
                "device": "init",  # this is Tango (p21/test/exp.01) device 
                "attribute": "init",    # this is Tango attribute (e.g. temperature)
                "value": 0.0,
                "unit": None,
                "location": None,
                "state": "Undefined",
                "status": None,
            })
            self.db.commit()
        table.create_index(["device"])
        table.create_index(["attribute"])
        table.create_index(["timestamp"])

    def _tine_table_creator(self, table):
        """Create table and indexes if they do not exist."""
        if not table.exists:
            logging.info(f"Creating table {table.name}")
            # table.create_column("timestamp", type="datetime")
            # table.create_column("context", type="string")
            # table.create_column("server", type="string")
            # table.create_column("device", type="string")
            # table.create_column("property", type="string")
            # table.create_column("value", type="float")
            # table.create_column("unit", type="string")
            # table.create_column("location", type="string")
            # table.create_column("state", type="string")
            # table.create_column("status", type="string")
            # this is an alternative way to create the table by inserting a dummy row
            table.insert({
                "timestamp": time.time(),
                "context": "init",
                "server": "init",
                "device": "init",
                "property": "init",
                "value": 0.0,
                "unit": None,
                "location": None,
                "state": "Undefined",
                "status": None,
            })
            self.db.commit()
        table.create_index(["context"])
        table.create_index(["server"])
        table.create_index(["device"])
        table.create_index(["property"])
        table.create_index(["timestamp"])

    def _property_table_creator(self, table):
        """Create table and indexes if they do not exist."""
        if not table.exists:
            logging.info(f"Creating table {table.name}")
            # table.create_column("timestamp", type="datetime")
            # table.create_column("sensor", type="string")
            # table.create_column("property", type="string")
            # table.create_column("value", type="float")
            # table.create_column("unit", type="string")
            # table.create_column("location", type="string")
            # table.create_column("state", type="string")
            # table.create_column("status", type="string")
            # this is an alternative way to create the table by inserting a dummy row
            table.insert({
                "timestamp": time.time(),
                "sensor": "init",
                "property": "init",
                "value": 0.0,
                "unit": None,
                "location": None,
                "state": "Undefined",
                "status": None,
            })
            self.db.commit()
        table.create_index(["sensor"])
        table.create_index(["property"])
        table.create_index(["timestamp"])

    def _default_table_creator(self, table):
        """Create table and indexes if they do not exist."""
        if not table.exists:
            logging.info(f"Creating table {table.name}")
            # table.create_column("timestamp", type="float")
            # table.create_column("data_type", type="string")
            # table.create_column("value", type="float")
            # this is an alternative way to create the table by inserting a dummy row
            table.insert({
                "timestamp": time.time(),
                "data_type": "init",
                "value": 0.0,
            })
            self.db.commit()
        table.create_index(["data_type"])
        table.create_index(["timestamp"])

    async def _database_maintenance(self, db):
        """
        Periodically checkpoint the WAL and occasionally VACUUM the database.
        Logs file sizes before and after maintenance.
        """
        # Guard clause for non-SQLite backends, where explicit maintenance is not possible
        if self.db_backend != "sqlite":
            logging.warning("[DB] Maintenance called for non-SQLite backend — skipping.")
            return
        
        last_vacuum = self.t0

        while True:
            try:
                wal_path = f"{DB_PATH}-wal"
                shm_path = f"{DB_PATH}-shm"

                # --- Record current file sizes ---
                size_db = os.path.getsize(DB_PATH) / 1e6 if os.path.exists(DB_PATH) else 0
                size_wal = os.path.getsize(wal_path) / 1e6 if os.path.exists(wal_path) else 0
                size_shm = os.path.getsize(shm_path) / 1e6 if os.path.exists(shm_path) else 0

                # --- Run WAL checkpoint ---
                if time.time() - self.t0 > 10:  # suppress initial messages
                    logging.info(f"[DB] Before maintenance — main: {size_db:.2f} MB, WAL: {size_wal:.2f} MB, SHM: {size_shm:.2f} MB")
                    wal_start = time.perf_counter()
                    self.db.executable.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    wal_end = time.perf_counter()
                    logging.info(f"[DB] WAL checkpoint completed in {1000*(wal_end - wal_start):.2f} ms")

                # --- Optionally VACUUM occasionally ---
                if time.time() - last_vacuum > VACUUM_INTERVAL:
                    logging.debug("[DB] Running VACUUM (this may take a moment)...")
                    vac_start = time.perf_counter()
                    self.db.executable.execute("VACUUM;")
                    vac_end = time.perf_counter()
                    logging.debug(f"[DB] VACUUM completed in {1000*(vac_end - vac_start):.2f} ms — database compacted")
                    last_vacuum = time.time()

                # --- Record new file sizes ---
                size_db_after = os.path.getsize(DB_PATH) / 1e6 if os.path.exists(DB_PATH) else 0
                size_wal_after = os.path.getsize(wal_path) / 1e6 if os.path.exists(wal_path) else 0
                if time.time() - self.t0 > 10:  # suppress initial messages
                    logging.info(f"[DB] After maintenance — main: {size_db_after:.2f} MB, WAL: {size_wal_after:.2f} MB\n")

            except Exception as e:
                logging.error(f"[DB] Maintenance error: {e}")

            await asyncio.sleep(MAINTENANCE_INTERVAL)

    def ensure_datetime(self, ts):
        from datetime import datetime, timezone
        if isinstance(ts, (float, int)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, datetime):
            return ts.astimezone(timezone.utc)
        else:
            raise TypeError(f"Unsupported timestamp type: {type(ts)}")

    def ensure_datetime_advanced(self, ts):
        """
        Convert various timestamp formats (float, int, str, datetime)
        into a timezone-aware UTC datetime object.
        """
        # Case 1: UNIX timestamp (float or int)
        if isinstance(ts, (float, int)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        # Case 2: datetime object
        elif isinstance(ts, datetime):
            # If naive, assume it's UTC
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            # Otherwise, normalize to UTC
            return ts.astimezone(timezone.utc)

        # Case 3: ISO-8601 string
        elif isinstance(ts, str):
            try:
                parsed = dateutil.parser.isoparse(ts)
                # If parsed datetime is naive, assume UTC
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except Exception as e:
                raise ValueError(f"Unrecognized timestamp string: {ts!r} ({e})")

        else:
            raise TypeError(f"Unsupported timestamp type: {type(ts).__name__}")

    def ensure_fields(self, msg):
        """Ensure required fields are present in the message."""
        required_fields = ["id", "timestamp", "value", "state"]
        for field in required_fields:
            if field not in msg:
                raise KeyError(f"Missing required field: {field}")
        return True

    async def consumer(self, batch_size=BATCH_SIZE, flush_interval=FLUSH_INTERVAL):
        queue = self.in_queue
        attr_batch, tine_batch, property_batch = [], [], []
        default_batch = []  # this is temporary, in case of unknown message types
        last_flush = time.time()
        logging.debug("Database consumer started.")

        while not (self.stop_event.is_set() and queue.empty()):
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=flush_interval)
                # Convert UNIX timestamp (float) → datetime
                #msg["timestamp"] = self.ensure_datetime(msg["timestamp"])

                # Dispatch to the correct batch
                if "attribute" in msg:
                    attr_batch.append(msg)
                elif "property" in msg:
                    property_batch.append(msg)
                elif "tine" in msg:
                    tine_batch.append(msg)
                else:
                    #raise ValueError("Unknown message type for database insertion")
                    default_batch.append(msg['timestamp'])
                queue.task_done()
            except asyncio.TimeoutError:
                pass

            now = time.time()
            #logging.debug(f"Batch sizes - Attr: {len(attr_batch)}, Tine: {len(tine_batch)}, Property: {len(property_batch)}, Default: {len(default_batch)}")
            maxlen = max(len(attr_batch), len(tine_batch), len(property_batch), len(default_batch))
            #logging.debug(f"Max batch size: {maxlen}")
            if maxlen >= batch_size or (now - last_flush) >= flush_interval:
                if attr_batch:
                    try:
                        self.attr_table.insert_many(attr_batch)
                        logging.debug(f"Inserted {len(attr_batch)} records into attr_table.")
                    except Exception as e:
                        logging.error("DB insert error:", e)
                    attr_batch.clear()
                if tine_batch:
                    try:
                        self.tine_table.insert_many(tine_batch)
                        logging.debug(f"Inserted {len(tine_batch)} records into tine_table.")
                    except Exception as e:
                        logging.error("DB insert error:", e)
                    tine_batch.clear()
                if property_batch:
                    try:
                        self.property_table.insert_many(property_batch)
                        logging.debug(f"Inserted {len(property_batch)} records into property_table.")
                    except Exception as e:
                        logging.error("DB insert error:", e)
                    property_batch.clear()
                if default_batch:
                    try:
                        logging.warning(f"Inserting {len(default_batch)} records into default table (unknown type).")
                        self.default_table.insert_many(default_batch)
                        # Here you might want to insert into a default table or log them
                    except Exception as e:
                        logging.error("DB insert error:", e)
                    default_batch.clear()
                last_flush = now

        # # Final flush after exit condition
        # if batch:
        #     print(f"Flushing {len(batch)} remaining records before shutdown...")
        #     table.insert_many(batch)
        # print("Consumer stopped gracefully.")

    async def run(self):
        self.consumer_task = asyncio.create_task(self.consumer())

        # Only start maintenance for SQLite
        if self.db_backend == "sqlite":
            logging.info("[DB] Starting SQLite maintenance task.")
            self.maintenance_task = asyncio.create_task(self._database_maintenance(self.db))
            await self.maintenance_task
        else:
            self.maintenance_task = None
            logging.info(f"[DB] Maintenance skipped for backend '{self.db_backend}'")

        await self.consumer_task

        await self.stop_event.wait()
        self.consumer_task.cancel()
        if self.maintenance_task:
            self.maintenance_task.cancel()




# -------------------------------------------------------------
# Database initialization
# -------------------------------------------------------------
def init_db():
    """Ensure database, table, and indexes exist."""
    db = dataset.connect(DB_URL)
    table = db[TABLE_NAME]

    # Force creation by inserting a dummy row if needed
    if not table.exists:
        print(f"Creating table '{TABLE_NAME}'...")
        table.insert({
            "timestamp": 0.0,
            "sensor": "init",
            "property": "init",
            "value": 0.0,
            "unit": None,
            "location": None,
            "state": "Undefined",
            "status": None,
        })
        db.commit()

    # Now it’s safe to create indexes
    table.create_index(["sensor"])
    table.create_index(["timestamp"])

    return db, table

# -------------------------------------------------------------
# Database maintenance task
# -------------------------------------------------------------
async def database_maintenance_task(db):
    """
    Periodically checkpoint the WAL and occasionally VACUUM the database.
    Logs file sizes before and after maintenance.
    """
    last_vacuum = time.time()

    while True:
        try:
            wal_path = f"{DB_PATH}-wal"
            shm_path = f"{DB_PATH}-shm"

            # --- Record current file sizes ---
            size_db = os.path.getsize(DB_PATH) / 1e6 if os.path.exists(DB_PATH) else 0
            size_wal = os.path.getsize(wal_path) / 1e6 if os.path.exists(wal_path) else 0
            size_shm = os.path.getsize(shm_path) / 1e6 if os.path.exists(shm_path) else 0

            print(f"[DB] Before maintenance — main: {size_db:.2f} MB, WAL: {size_wal:.2f} MB, SHM: {size_shm:.2f} MB")

            # --- Run WAL checkpoint ---
            db.executable.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            print("[DB] WAL checkpoint completed.")

            # --- Optionally VACUUM occasionally ---
            if time.time() - last_vacuum > VACUUM_INTERVAL:
                print("[DB] Running VACUUM (this may take a moment)...")
                db.executable.execute("VACUUM;")
                print("[DB] VACUUM completed — database compacted.")
                last_vacuum = time.time()

            # --- Record new file sizes ---
            size_db_after = os.path.getsize(DB_PATH) / 1e6 if os.path.exists(DB_PATH) else 0
            size_wal_after = os.path.getsize(wal_path) / 1e6 if os.path.exists(wal_path) else 0

            print(f"[DB] After maintenance — main: {size_db_after:.2f} MB, WAL: {size_wal_after:.2f} MB\n")

        except Exception as e:
            print(f"[DB] Maintenance error: {e}")

        await asyncio.sleep(MAINTENANCE_INTERVAL)


# -------------------------------------------------------------
# Producer and Consumer
# -------------------------------------------------------------
async def producer(queue, stop_event):
    sensors = [f"s{i:03d}" for i in range(100)]
    while not stop_event.is_set():
        for sensor in sensors:
            if random.random() < 0.7:  # simulate varying rates
                msg = {
                    "id": uuid.uuid4().hex,
                    "timestamp": time.time(),
                    "value": round(random.uniform(20, 25), 2),
                    "state": "OK",

                    "sensor": sensor,
                    "property": "temperature",
                    "value2": round(random.uniform(100, 200), 2),
                }
                await queue.put(msg)
        await asyncio.sleep(0.2)
    print("Producer stopped.")


async def consumer(queue, table, stop_event, batch_size=200, flush_interval=1.0):
    batch = []
    last_flush = time.time()

    while not (stop_event.is_set() and queue.empty()):
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=flush_interval)
            batch.append(msg)
            queue.task_done()
        except asyncio.TimeoutError:
            pass

        now = time.time()
        if len(batch) >= batch_size or (now - last_flush) >= flush_interval:
            if batch:
                try:
                    table.insert_many(batch)
                    print(f"Inserted {len(batch)} records into DB.")
                except Exception as e:
                    print("DB insert error:", e)
                batch.clear()
                last_flush = now

    # Final flush after exit condition
    if batch:
        print(f"Flushing {len(batch)} remaining records before shutdown...")
        table.insert_many(batch)
    print("Consumer stopped gracefully.")


# -------------------------------------------------------------
# Main entry
# -------------------------------------------------------------
async def main():
    db, table = init_db()
    queue = asyncio.Queue(maxsize=10000)
    stop_event = asyncio.Event()

    # Signal handlers for graceful stop
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    prod_task = asyncio.create_task(producer(queue, stop_event))
    cons_task = asyncio.create_task(consumer(queue, table, stop_event))

    # Wait for stop signal
    await stop_event.wait()
    print("\nShutdown signal received. Waiting for queue to drain...")
    await queue.join()

    # Wait for consumer to finish flushing
    await cons_task
    prod_task.cancel()
    print("All tasks stopped cleanly.")


async def main2():
    db, table = init_db()
    queue = asyncio.Queue()
    stop_event = asyncio.Event()

    producer_task = asyncio.create_task(producer(queue, stop_event))
    consumer_task = asyncio.create_task(consumer(queue, table, stop_event))
    maintenance_task = asyncio.create_task(database_maintenance_task(db))

    # Handle Ctrl+C (SIGINT) properly
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_stop(*_):
        print("\n[MAIN] Received shutdown signal (Ctrl+C). Stopping...")
        stop_event.set()

    # Register signal handler
    loop.add_signal_handler(signal.SIGINT, handle_stop)
    loop.add_signal_handler(signal.SIGTERM, handle_stop)

    # Wait until user interrupts
    await stop_event.wait()
    await queue.join()

    print("[MAIN] Cancelling background tasks...")
    for task in [producer_task, consumer_task, maintenance_task]:
        task.cancel()

    # Allow all tasks to shut down cleanly
    await asyncio.gather(producer_task, consumer_task, maintenance_task, return_exceptions=True)

    # Final database cleanup
    db.executable.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    db.commit()
    print("[MAIN] Shutdown complete. Database closed.")


async def main_class():
    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    stop_event.clear()

    DBW = DatabaseWriter(queue)

    producer_task = asyncio.create_task(producer(queue, stop_event))
    await DBW.start()

if __name__ == "__main__":
    try:
        asyncio.run(main_class())
    except KeyboardInterrupt:
        print("\nForced exit.")
