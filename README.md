# P212_status_gui
P212 status GUI

## TODO
- Prepare the clients for multiple entries for the same attribute in a single message (if the current_state update frequency is higher than the publisher, this is certainly the case)
- Implement steady sensor heart-beat in the CurrentStateMonitor
- remove case-sensitivity of attributes
- Sensor heart beat should be a collected signal (alphabetically order the sensor IDs and then encode the activity of a sensor in the last period into a binary number, send this number with a timestamp - the beginning of the cycle. This would give a pessimistic approach to the last sensor activity)
### Near Future
- internal NATS server for local clients?
- implement central setting storage as a dataclass: each object should have a reference to this and then live updates are relatively easy. This way we do not need setter methods for all updatable variables.
- split tango and tine registries?
- handle sesor config and views config in a more unified way (handle missing sensor entries in the view config)
- rewrite poller_tango and poller_tine to use the same base class

### Future
- Implement Grafana metrics (for internal queues and nats messaging as well)
- Implement NTP message delay metrics (measure the relative difference between the server and client time once at startup...)
- check if rounding the float values would reduce message size
