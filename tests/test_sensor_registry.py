
import pytest
import asyncio
from unittest.mock import MagicMock

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from registry import SensorRegistry3, Sensor  # Assuming the class is in sensor_registry.py

@pytest.fixture
def registry():
    return SensorRegistry3()

@pytest.fixture
def sample_sensor_data():
    return {
        "type": "Tango",
        "address": "addr1",
        "attribute": "attr1",
        "display_name": "Sensor 1",
    }

@pytest.fixture
def sample_sensor_data_tine():
    return {
        "type": "Tine",
        "address": "context/server/device",
        "property": "prop2",
        "display_name": "Sensor 2",
    }


def test_subscribe(registry):
    queue = registry.subscribe()
    assert len(registry.subscribers) == 1
    assert queue in registry.subscribers

def test_unsubscribe(registry):
    queue = registry.subscribe()
    registry.unsubscribe(queue)
    assert len(registry.subscribers) == 0


def test_register_sensor(registry):
    # Initial sensor configuration
    sensor_cfg = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }

    # Register the sensor
    sid = registry.register_sensor(sensor_cfg)
    
    # Check that the sensor is in the registry
    sensor = registry.get_sensor_by_id(sid)
    assert sensor is not None
    assert sensor.id == sid
    assert sensor.display_name == "Sensor 1"
    assert sensor.type == "Tango"
    assert sensor.address == "addr123"

def test_register_sensor_frozen_field_update(registry):
    # Register a sensor
    sensor_cfg = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }
    sid = registry.register_sensor(sensor_cfg)

    # Attempt to update a frozen field (property, attribute should be frozen)
    new_data = {
        "property": "prop2",  # Changing frozen field should raise error
    }

    with pytest.raises(ValueError):
        registry.update_sensor(sid, new_data)

def test_update_groups_tango(registry):
    # Register two Tango sensors
    sensor_cfg1 = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }
    sid1 = registry.register_sensor(sensor_cfg1)

    sensor_cfg2 = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 2",
        "property": "prop1",
        "attribute": "attr2"
    }
    sid2 = registry.register_sensor(sensor_cfg2)

    # Verify the grouping
    groups = registry.get_groups()
    tango_group = groups["Tango"]
    assert "addr123" in tango_group
    assert len(tango_group["addr123"]) == 2
    assert sid1 in tango_group["addr123"]
    assert sid2 in tango_group["addr123"]

def test_update_groups_tine(registry):
    # Register two Tine sensors
    sensor_cfg1 = {
        "type": "Tine",
        "address": "ctx1/srv1/dev1",
        "display_name": "Tine Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }
    sid1 = registry.register_sensor(sensor_cfg1)

    sensor_cfg2 = {
        "type": "Tine",
        "address": "ctx1/srv1/dev1",
        "display_name": "Tine Sensor 2",
        "property": "prop2",
        "attribute": "attr2"
    }
    sid2 = registry.register_sensor(sensor_cfg2)

    # Verify the grouping
    groups = registry.get_groups()
    tine_group = groups["Tine"]
    key = "ctx1/srv1/prop1"
    assert key in tine_group
    assert len(tine_group[key]) == 1  # Only one sensor should be in this group
    assert sid1 in tine_group[key]



def test_register_many(registry):
    # Multiple sensor configurations
    sensor_cfgs = [
        {
            "type": "Tango",
            "address": "addr123",
            "display_name": "Sensor 1",
            "property": "prop1",
            "attribute": "attr1"
        },
        {
            "type": "Tine",
            "address": "ctx1/srv1/dev1",
            "display_name": "Sensor 2",
            "property": "prop1",
            "attribute": "attr1"
        }
    ]

    sensor_ids = registry.register_many(sensor_cfgs)
    
    # Check that both sensors were added correctly
    assert len(sensor_ids) == 2
    sensor1 = registry.get_sensor_by_id(sensor_ids[0])
    sensor2 = registry.get_sensor_by_id(sensor_ids[1])

    assert sensor1 is not None
    assert sensor2 is not None

@pytest.mark.asyncio
async def test_update_sensor(registry, sample_sensor_data):
    sensor_id = await registry.register_sensor(sample_sensor_data)
    updated_data = {"address": "new_addr"}
    
    registry.update_sensor(sensor_id, updated_data)
    
    updated_sensor = registry.get_sensor_by_id(sensor_id)
    assert updated_sensor.address == "new_addr"


@pytest.mark.asyncio
async def test_update_many(registry, sample_sensor_data, sample_sensor_data_tine):
    sensor_id1 = await registry.register_sensor(sample_sensor_data)
    sensor_id2 = await registry.register_sensor(sample_sensor_data_tine)
    
    updates = [
        (sensor_id1, {"address": "updated_addr1"}),
        (sensor_id2, {"address": "updated_addr2"})
    ]
    
    registry.update_many(updates)
    
    updated_sensor1 = registry.get_sensor_by_id(sensor_id1)
    updated_sensor2 = registry.get_sensor_by_id(sensor_id2)
    
    assert updated_sensor1.address == "updated_addr1"
    assert updated_sensor2.address == "updated_addr2"


def test_remove_sensor(registry):
    # Register a sensor to remove
    sensor_cfg = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }
    sid = registry.register_sensor(sensor_cfg)

    # Remove the sensor
    sensor = registry.remove_sensor(sid)
    
    # Ensure the sensor was removed
    assert sensor.id == sid
    assert registry.get_sensor_by_id(sid) is None

def test_remove_sensor_not_found(registry):
    # Try to remove a sensor that doesn't exist
    with pytest.raises(KeyError):
        registry.remove_sensor("nonexistent_id")



@pytest.mark.asyncio
async def test_remove_many(registry, sample_sensor_data, sample_sensor_data_tine):
    sensor_id1 = await registry.register_sensor(sample_sensor_data)
    sensor_id2 = await registry.register_sensor(sample_sensor_data_tine)
    
    removed_sensors = registry.remove_many([sensor_id1, sensor_id2])
    
    assert len(removed_sensors) == 2
    assert len(registry.get_all()) == 0



def test_get_sensor_by_id(registry, sample_sensor_data):
    sensor_id = registry.register_sensor(sample_sensor_data)
    sensor = registry.get_sensor_by_id(sensor_id)
    
    assert sensor.id == sensor_id
    assert sensor.type == "Tango"


def test_get_groups(registry, sample_sensor_data, sample_sensor_data_tine):
    registry.register_sensor(sample_sensor_data)
    registry.register_sensor(sample_sensor_data_tine)
    
    groups = registry.get_groups()
    assert "Tango" in groups
    assert "Tine" in groups
    assert len(groups["Tango"]) == 1
    assert len(groups["Tine"]) == 1



def test_to_json(registry):
    # Register a sensor
    sensor_cfg = {
        "type": "Tango",
        "address": "addr123",
        "display_name": "Sensor 1",
        "property": "prop1",
        "attribute": "attr1"
    }
    sid = registry.register_sensor(sensor_cfg)

    # Convert registry to JSON
    json_data = registry.to_json()
    
    # Ensure the JSON contains the registered sensor's data
    assert '"display_name": "Sensor 1"' in json_data

def test_load_from_json(registry):
    # JSON data representing sensors
    json_data = '''
    [
        {
            "type": "Tango",
            "address": "addr123",
            "display_name": "Sensor 1",
            "property": "prop1",
            "attribute": "attr1"
        }
    ]
    '''
    # Load sensors from JSON
    asyncio.run(registry.load_from_json(json_data))
    
    # Ensure the sensor was added to the registry
    sensor = registry.get_all()
    assert len(sensor) == 1
    assert sensor["Sensor 1"].display_name == "Sensor 1"


def test_load_groups(registry):
    groups_data = {
        "Tango": {"addr1": ["sensor1"]},
        "Tine": {"context/server/prop1": ["sensor2"]}
    }
    registry.load_groups(groups_data)
    
    groups = registry.get_groups()
    assert "Tango" in groups
    assert "Tine" in groups
    assert len(groups["Tango"]["addr1"]) == 1
    assert len(groups["Tine"]["context/server/prop1"]) == 1


