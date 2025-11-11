# registry.py
import json
import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Tuple, List
import asyncio

class Sensor(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str = Field(frozen=True)
    address: str = Field(frozen=True)
    display_name: str
    property: str | None = Field(default=None, frozen=True)
    attribute: str | None = Field(default=None, frozen=True)
    model_config = ConfigDict(extra="allow")  # Allow extra fields
    
    def model_copy(self, *, update=None, deep=False):
        """Prevent updating frozen fields via model_copy()."""
        update = update or {}
        frozen_fields = {
            name for name, field in self.__class__.model_fields.items()
            if getattr(field, "frozen", False)
        }
        illegal = frozen_fields.intersection(update)
        if illegal:
            raise ValueError(f"Cannot update frozen fields via model_copy(): {illegal}")
        return super().model_copy(update=update, deep=deep)


class SensorRegistry:
    """Smart registry that groups Tango and Tine sensors and avoids duplicates."""

    def __init__(self):
        self._sensors: Dict[str, Sensor] = {}
        self._by_key: Dict[Tuple, str] = {}
        # group maps by sensor type
        self._groups: Dict[str, Dict[Any, List[str]]] = {"Tango": {}, "Tine": {}}
        self._version = 1
        self.subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Create and return a subscription queue for sensor updates."""
        q = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscription queue."""
        try:
            self.subscribers.remove(q)
        except ValueError:
            pass
    
    async def _notify(self, event_type: str, sensor: Sensor):
        """Notify all subscribers about a sensor event."""
        for q in self.subscribers:
            await q.put((event_type, sensor))

    @property
    def version(self):
        return self._version

    # ---------------------
    # Internal helpers
    # ---------------------
    def _inject_tine_fields(self, cfg: dict) -> dict:
        """If sensor is Tine, parse address into Context, Server, Device."""
        stype = cfg.get("type", "").capitalize()
        if stype == "Tine":
            addr = cfg.get("address", "")
            parts = addr.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid Tine address format: '{addr}'")
            context, server, device = parts
            cfg = {**cfg, "context": context, "server": server, "device": device}
        return cfg

    def _make_key(self, cfg: dict | Sensor) -> Tuple:
        """Create a unique key for identifying sensors."""
        if isinstance(cfg, Sensor):
            cfg = cfg.model_dump()

        stype = cfg.get("type", "").capitalize()
        addr = cfg.get("address")
        prop = cfg.get("property")
        attr = cfg.get("attribute")

        if stype == "Tine":
            # Expect address like CONTEXT/SERVER/DEVICE
            parts = addr.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid Tine address format: '{addr}'")
            context, server, device = parts
            return (stype, context, server, device, prop)
        elif stype == "Tango":
            return (stype, addr, prop, attr)
        else:
            return (stype, addr, prop, attr)

    def _update_groups(self, sensor: Sensor):
        """Maintain grouping maps for Tango and Tine sensors."""
        stype = sensor.type.capitalize()

        if stype == "Tango":
            addr = sensor.address
            group_map = self._groups["Tango"]
            group_map.setdefault(addr, [])
            if sensor.id not in group_map[addr]:
                group_map[addr].append(sensor.id)

        elif stype == "Tine":
            # Group by (context, server, property)
            try:
                context, server, device = sensor.address.split("/")
            except ValueError:
                raise ValueError(f"Invalid Tine address format: '{sensor.address}'")

            key = (context, server, sensor.property)
            group_map = self._groups["Tine"]
            group_map.setdefault(key, [])
            if sensor.id not in group_map[key]:
                group_map[key].append(sensor.id)

    # ---------------------
    # Public API
    # ---------------------
    async def register_sensor(self, cfg: dict) -> str:
        """Register or update a sensor, grouping by type rules."""
        cfg = self._inject_tine_fields(cfg)
        key = self._make_key(cfg)

        # If sensor already exists
        if key in self._by_key:
            sid = self._by_key[key]
            existing = self._sensors[sid]
            new_data = Sensor(**{**existing.model_dump(), **cfg})

            if existing != new_data:
                self._sensors[sid] = new_data
                self._update_groups(new_data)
            return sid

        # Otherwise create new
        sensor = Sensor(**cfg)
        await self._notify("added", sensor)
        sid = sensor.id
        self._sensors[sid] = sensor
        self._by_key[key] = sid
        self._update_groups(sensor)
        self._version += 1
        return sid

    async def register_many(self, cfgs: List[dict]) -> List[str]:
        """Register or update multiple sensors."""
        ids = []
        for cfg in cfgs:
            sid = await self.register_sensor(cfg)
            ids.append(sid)
        return ids

    def update_sensor(self, sid: str, updates: dict):
        """Update an existing sensor."""
        if sid not in self._sensors:
            raise KeyError(f"Sensor ID not found: {sid}")

        updates = self._inject_tine_fields(updates)
        sensor = self._sensors[sid].model_copy(update=updates)
        self._sensors[sid] = sensor

        # Update uniqueness key
        old_keys = [k for k, v in self._by_key.items() if v == sid]
        for k in old_keys:
            del self._by_key[k]
        self._by_key[self._make_key(sensor)] = sid
        self._update_groups(sensor)
        self._version += 1
    
    def update_many(self, updates_list: List[Tuple[str, dict]]):
        """Update multiple sensors given a list of (sensor_id, updates) tuples."""
        for sid, updates in updates_list:
            self.update_sensor(sid, updates)

    async def remove_sensor(self, sid: str) -> Sensor:
        """Remove a sensor and update groups."""
        try:
            sensor = self._sensors.pop(sid)
        except KeyError:
            raise KeyError(f"Sensor ID not found: {sid}")

        key = self._make_key(sensor)
        self._by_key.pop(key, None)

        stype = sensor.type.capitalize()
        if stype == "Tango":
            addr = sensor.address
            if addr in self._groups["Tango"]:
                self._groups["Tango"][addr] = [i for i in self._groups["Tango"][addr] if i != sid]
                if not self._groups["Tango"][addr]:
                    del self._groups["Tango"][addr]

        elif stype == "Tine":
            context, server, device = sensor.address.split("/")
            key_group = (context, server, sensor.property)
            if key_group in self._groups["Tine"]:
                self._groups["Tine"][key_group] = [
                    i for i in self._groups["Tine"][key_group] if i != sid
                ]
                if not self._groups["Tine"][key_group]:
                    del self._groups["Tine"][key_group]
        self._version += 1
        await self._notify("removed", sensor)
        return sensor

    def remove_many(self, sids: List[str]) -> List[Sensor]:
        """Remove multiple sensors and return them."""
        removed = []
        for sid in sids:
            sensor = self.remove_sensor(sid)
            removed.append(sensor)
        return removed

    def get_sensor_by_id(self, sid: str) -> Sensor | None:
        return self._sensors.get(sid)

    def get_all(self) -> Dict[str, Sensor]:
        return dict(self._sensors)

    def get_groups(self) -> Dict[str, Dict[str, List[str]]]:
        """Return grouped sensors with JSON-safe keys."""
        safe_groups: Dict[str, Dict[str, List[str]]] = {"Tango": {}, "Tine": {}}

        # Tango groups: address → sensor IDs
        for addr, ids in self._groups["Tango"].items():
            safe_groups["Tango"][str(addr)] = ids

        # Tine groups: (context, server, property) → sensor IDs
        for key, ids in self._groups["Tine"].items():
            # Convert tuple keys to readable strings
            if isinstance(key, tuple):
                key_str = "/".join(key)
            else:
                key_str = str(key)
            safe_groups["Tine"][key_str] = ids

        return safe_groups

    @property
    def groups(self):
        return self.get_groups()

    @property
    def tine_groups(self):
        return self.get_groups()['Tine']

    @property
    def tango_groups(self):
        return self.get_groups()['Tango']

    def get_tango_group_sensors(self, address: str) -> List[Sensor]:
        """Return list of Sensor objects in the specified Tango group."""
        sensor_ids = self._groups["Tango"].get(address, [])
        return [self._sensors[sid] for sid in sensor_ids if sid in self._sensors]

    def get_tango_group_attributes(self, address: str) -> List[str]:
        """Return list of attribute names in the specified Tango group."""
        sensors = self.get_tango_group_sensors(address)
        attributes = [getattr(s, 'attribute') for s in sensors if hasattr(s, 'attribute')]
        return attributes

    def get_tine_group_sensors(self, group_key: str | Tuple[str, str, str]) -> List[Sensor]:
        """Return list of Sensor objects in the specified Tine group."""
        if isinstance(group_key, str):
            parts = group_key.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid Tine group key format: '{group_key}'")
            context, server, prop = parts
            key = (context, server, prop)
        else:
            key = group_key

        sensor_ids = self._groups["Tine"].get(key, [])
        return [self._sensors[sid] for sid in sensor_ids if sid in self._sensors]
    
    def get_tine_group_devices(self, group_key: str | Tuple[str, str, str]) -> List[str]:
        """Return list of device names in the specified Tine group."""
        sensors = self.get_tine_group_sensors(group_key)
        devices = [getattr(s, 'Device') for s in sensors if hasattr(s, 'Device')]
        return devices

    def to_json(self) -> str:
        return json.dumps([s.model_dump() for s in self._sensors.values()], indent=2)

    async def load_from_json(self, json_data: str):
        """Load sensors from JSON export and rebuild internal structures."""
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        if not isinstance(data, list):
            raise ValueError("Expected a list of sensor objects")

        for cfg in data:
            if not isinstance(cfg, dict):
                continue  # skip invalid entries

            # Ensure correct type normalization and auto field injection
            cfg = self._inject_tine_fields(cfg)

            # If ID already exists, update existing sensor
            sid = cfg.get("id")
            if sid and sid in self._sensors:
                self.update_sensor(sid, cfg)
                continue

            # Otherwise register a new sensor
            await self.register_sensor(cfg)
        self._version += 1

    def load_groups(self, data: dict):
        """Rebuild group dictionaries from JSON-safe form."""
        self._groups = {"Tango": {}, "Tine": {}}
        for addr, ids in data.get("Tango", {}).items():
            self._groups["Tango"][addr] = ids
        for key, ids in data.get("Tine", {}).items():
            self._groups["Tine"][tuple(key.split("|"))] = ids





async def main():
    registry = SensorRegistry()
    sensor_cfg = {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/PU21b',
        'property': 'Undulator.Gap',
        'display_name': 'PU21b Gap'
    }
    sid = await registry.register_sensor(sensor_cfg)
    print(f"Registered sensor ID: {sid}")
    print("Current sensors in registry:")
    for s in registry.get_all().values():
        print(s)

    # register a list of sensors
    sensors = [
        {
            'type': 'Tine',
            'address': 'PETRA/HISTORY/PU21b',
            'property': 'Undulator.Gap',
            'display_name': 'PU21b Gap'
        },
        {
            'type': 'Tango',
            'address': 'sys/tg_test/1',
            'attribute': 'temperature',
            'display_name': 'TG Test Temperature'
        }
    ]
    sids = await registry.register_many(sensors)
    print("After registering multiple sensors:")
    for s in registry.get_all().values():
        print(s)

    # register more tine sensors to see grouping
    more_sensors = [
        {
            'type': 'Tine',
            'address': 'PETRA/HISTORY/PU21b',
            'property': 'Undulator.Current',
            'display_name': 'PU21b Current'
        },
        {
            'type': 'Tine',
            'address': 'PETRA/HISTORY/PU22a',
            'property': 'Undulator.Gap',
            'display_name': 'PU22a Gap'
        }
    ]
    await registry.register_many(more_sensors)
    print("After registering more Tine sensors:")
    for s in registry.get_all().values():
        print(s)
    print("Tine Groups:")
    for key, ids in registry.tine_groups.items():
        print(f"Group {key}: Sensor IDs {ids}")
    
    # Look at the tine group sensors
    group_key = 'PETRA/HISTORY/Undulator.Gap'
    devices = registry.get_tine_group_sensors(group_key)
    print(f"Devices in Tine group {group_key}:")
    for d in devices:
        print(d)
    
    # Look at the tine group device names
    device_names = registry.get_tine_group_devices(group_key)
    print(f"Device names in Tine group {group_key}: {device_names}")

    # adding more tango sensors
    tango_sensors = [
        {
            'type': 'Tango',
            'address': 'sys/tg_test/2',
            'attribute': 'pressure',
            'display_name': 'TG Test Pressure'
        },
        {
            'type': 'Tango',
            'address': 'sys/tg_test/1',
            'attribute': 'humidity',
            'display_name': 'TG Test Humidity'
        },
        {
            'type': 'Tango',
            'address': 'sys/tg_test/2',
            'attribute': 'temperature',
            'display_name': 'TG Test 2 Temperature'
        },
        {
            'type': 'Tango',
            'address': 'sys/tg_test/1',
            'attribute': 'humanity',
            'display_name': 'Humanity Sensor'
        },
    ]
    await registry.register_many(tango_sensors)
    print("After registering more Tango sensors:")
    for s in registry.get_all().values():
        print(s)
    print("Tango Groups:")
    for addr, ids in registry.tango_groups.items():
        print(f"Address {addr}: Sensor IDs {ids}")
    
    print('Tango group sensors for sys/tg_test/1:')
    tango_group_sensors = registry.get_tango_group_sensors('sys/tg_test/1')
    for s in tango_group_sensors:
        print(s)
    print('Tango group attributes for sys/tg_test/2:')
    tango_group_attrs = registry.get_tango_group_attributes('sys/tg_test/2')
    print(tango_group_attrs)


if __name__ == "__main__":
    asyncio.run(main())
    
    
