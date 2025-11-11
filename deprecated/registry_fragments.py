



class SensorRegistry:
    """In-memory registry. Optionally backed by KV, DB, or file."""
    def __init__(self):
        self._sensors: Dict[str, Sensor] = {}

    def register_sensor(self, cfg: dict) -> str:
        sensor = Sensor(**cfg)
        self._sensors[sensor.id] = sensor
        return sensor.id

    def update_sensor(self, sid: str, updates: dict):
        s = self._sensors.get(sid)
        if not s:
            raise KeyError(sid)
        self._sensors[sid] = s.model_copy(update=updates)

    def get(self, sid: str) -> Sensor | None:
        return self._sensors.get(sid)

    def all(self) -> Dict[str, Sensor]:
        return dict(self._sensors)

    def remove_sensor(self, sid: str) -> Sensor:
        """Remove a sensor from the registry and return it."""
        try:
            return self._sensors.pop(sid)
        except KeyError:
            raise KeyError(f"Sensor ID not found: {sid}")

    # Optional persistence
    def to_json(self) -> str:
        return json.dumps([s.model_dump() for s in self._sensors.values()], indent=2)

    def load_json(self, text: str):
        sensors = json.loads(text)
        for s in sensors:
            sensor = Sensor(**s)
            self._sensors[sensor.id] = sensor



class SensorRegistry2:
    """Smart registry that avoids duplicates and groups Tango sensors."""

    def __init__(self):
        self._sensors: Dict[str, Sensor] = {}
        self._by_key: Dict[Tuple[str, str, str | None, str | None], str] = {}
        self._groups: Dict[str, List[str]] = {}  # Tango grouping by address

    # ---------------------
    # Internal helpers
    # ---------------------
    def _make_key(self, cfg: dict | Sensor) -> Tuple[str, str, str | None, str | None]:
        """Create a unique key from identifying fields."""
        if isinstance(cfg, Sensor):
            return (cfg.type, cfg.address, cfg.property, cfg.attribute)
        return (
            cfg.get("type"),
            cfg.get("address"),
            cfg.get("property"),
            cfg.get("attribute"),
        )

    def _update_groups(self, sensor: Sensor):
        """Update Tango grouping map."""
        if sensor.type.lower() == "tango":
            addr = sensor.address
            if addr not in self._groups:
                self._groups[addr] = []
            if sensor.id not in self._groups[addr]:
                self._groups[addr].append(sensor.id)

    # ---------------------
    # Public API
    # ---------------------
    def register_sensor(self, cfg: dict) -> str:
        """Register or update a sensor. Returns the sensor ID."""
        key = self._make_key(cfg)

        # If sensor already exists
        if key in self._by_key:
            sid = self._by_key[key]
            existing = self._sensors[sid]
            new_data = Sensor(**{**existing.model_dump(), **cfg})

            # Check if configuration changed
            if existing != new_data:
                self._sensors[sid] = new_data
                self._update_groups(new_data)
            return sid

        # Create a new sensor
        sensor = Sensor(**cfg)
        sid = sensor.id
        self._sensors[sid] = sensor
        self._by_key[key] = sid
        self._update_groups(sensor)
        return sid

    def update_sensor(self, sid: str, updates: dict):
        """Update an existing sensor’s configuration."""
        if sid not in self._sensors:
            raise KeyError(f"Sensor ID not found: {sid}")
        sensor = self._sensors[sid].model_copy(update=updates)
        self._sensors[sid] = sensor

        # Update key index
        old_keys = [k for k, v in self._by_key.items() if v == sid]
        for k in old_keys:
            del self._by_key[k]
        self._by_key[self._make_key(sensor)] = sid

        self._update_groups(sensor)

    def remove_sensor(self, sid: str) -> Sensor:
        """Remove a sensor and its group references."""
        try:
            sensor = self._sensors.pop(sid)
        except KeyError:
            raise KeyError(f"Sensor ID not found: {sid}")

        key = self._make_key(sensor)
        self._by_key.pop(key, None)

        if sensor.type.lower() == "tango":
            addr = sensor.address
            if addr in self._groups:
                self._groups[addr] = [i for i in self._groups[addr] if i != sid]
                if not self._groups[addr]:
                    del self._groups[addr]
        return sensor

    def get(self, sid: str) -> Sensor | None:
        return self._sensors.get(sid)

    def all(self) -> Dict[str, Sensor]:
        return dict(self._sensors)

    def tango_groups(self) -> Dict[str, List[str]]:
        """Return mapping of Tango addresses to their sensor IDs."""
        return dict(self._groups)

    def to_json(self) -> str:
        return json.dumps([s.model_dump() for s in self._sensors.values()], indent=2)

    def load_json(self, text: str):
        sensors = json.loads(text)
        for s in sensors:
            self.register_sensor(s)
