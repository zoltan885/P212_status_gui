# P212_status_gui
P212 status GUI

## TODO
- Make sure the snapshot queue always has an entry (could be done with a custom AsyncOverwritingSingleSlotQueue)
- Use asyncio for the whole project, it would work better with the poller as well
- ZMQ stream for internal clients?
- Asynchronous Fan Out for internal message distribution (as a preparation for multiple simultaneous publishers), before publishing them
- Prepare the clients for multiple entries for the same attribute in a single message (if the current_state update frequency is higher than the publisher, this is certainly the case)
### Future
- Implement Grafana metrics (for internal queues and nats messaging as well)
- Implement NTP message delay metrics (measure the relative difference between the server and client time once at startup...)
- 
