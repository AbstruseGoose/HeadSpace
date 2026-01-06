# HeadSpace Testing Guide

This guide explains how to test the HeadSpace dog tracking system.

## Quick Test (Simulation Mode)

The fastest way to test HeadSpace is using simulation mode - no hardware required!

### Prerequisites

```bash
# Install dependencies
sudo apt install mosquitto mosquitto-clients sqlite3
pip3 install -r requirements.txt
```

### Running the System

#### Option 1: Using the Startup Script (Recommended)

```bash
cd /workspaces/HeadSpace
./start.sh
```

This will:
- Start Mosquitto MQTT broker (if not running)
- Initialize the database (if needed)
- Start all three services (ingestion, processing, dashboard)
- Display service logs

Press `Ctrl+C` to stop all services.

#### Option 2: Manual Start (For Debugging)

Open three terminal windows and run:

**Terminal 1: Ingestion Service**
```bash
cd /workspaces/HeadSpace
python3 services/ingestion/ingest.py
```

**Terminal 2: Processing Service**
```bash
cd /workspaces/HeadSpace
python3 services/processing/processor.py
```

**Terminal 3: Dashboard Server**
```bash
cd /workspaces/HeadSpace
python3 dashboard/server.py
```

### Accessing the Dashboard

Open your browser to: **http://localhost:8080**

You should see:
- A live map centered on Seattle (default location)
- 4 simulated nodes in the node panel:
  - **Dog-Rex** (moving in circles)
  - **Dog-Luna** (moving in figure-8 pattern)
  - **Base-Station-1** (stationary)
  - **Team-Lead-1** (random walk)
- Live position updates every 10 seconds
- Breadcrumb trails showing movement history
- Connection status indicator (green = connected)

### What to Look For

#### 1. Position Updates
- Node markers should appear on the map
- Node panel should show "LIVE" status (green)
- Last seen timestamps should update every ~10 seconds
- Breadcrumb trails should extend as nodes move

#### 2. Telemetry
- Battery levels should appear in node cards
- RSSI/SNR values should update periodically
- Watch the browser console (F12) for SSE events

#### 3. Dwell Detection
- Leave the simulation running for 2-3 minutes
- "Dog-Rex" and "Dog-Luna" should generate dwell events as they revisit areas
- Dwell toast notifications should appear in top-right corner
- Dwell markers (orange circles) should appear on the map

#### 4. Map Controls
- **Fit All**: Click to zoom to show all nodes
- **Toggle Trails**: Show/hide breadcrumb paths
- **Toggle Dwells**: Show/hide dwell circles
- **Filter Nodes**: Type in the search box to filter node list

### Verifying Data Storage

#### Check Database
```bash
# Count GPS points
sqlite3 data/headspace.db "SELECT COUNT(*) FROM gps_points"

# List nodes
sqlite3 data/headspace.db "SELECT node_id, long_name, node_type FROM nodes"

# Check recent positions
sqlite3 data/headspace.db "SELECT node_id, latitude, longitude, timestamp FROM gps_points ORDER BY timestamp DESC LIMIT 10"

# Check dwell events (after a few minutes)
sqlite3 data/headspace.db "SELECT * FROM dwells"
```

#### Check Logs
```bash
# Ingestion log (simulation activity)
tail -f logs/ingestion.log

# Processing log (MQTT consumption, dwell detection)
tail -f logs/processing.log

# Dashboard log (HTTP requests)
tail -f logs/dashboard.log
```

#### Test MQTT Directly
```bash
# Subscribe to all topics
mosquitto_sub -h localhost -t 'headspace/#' -v

# You should see messages like:
# headspace/position/!12345001 {"event_type":"position_update",...}
# headspace/telemetry/!12345001 {"battery_level":85,...}
```

#### Test SSE Stream
```bash
# Connect to SSE endpoint
curl -N http://localhost:8081/events

# You should see:
# data: {"event":"position_update",...}
# data: {"event":"telemetry_update",...}
```

---

## Hardware Test (Real Devices)

Once you have Meshtastic devices configured (see [hardware-setup.md](docs/hardware-setup.md)), test with real hardware.

### Configuration

1. **Disable simulation mode:**

Edit `services/ingestion/config.yaml`:
```yaml
meshtastic:
  connection_type: serial
  serial_port: auto  # or /dev/ttyUSB0
  simulation_mode: false  # <- Change this
```

2. **Connect gateway device:**
```bash
# Plug in Heltec V3 or other gateway via USB

# Verify it's detected
ls -la /dev/ttyUSB* /dev/ttyACM*

# Should see /dev/ttyUSB0 or similar
```

3. **Start services:**
```bash
./start.sh
```

### Expected Behavior

- Ingestion service connects to `/dev/ttyUSB0` (or detected port)
- Log shows: `Connected to Meshtastic device`
- Node discovery messages appear as devices transmit
- Dog tracker nodes appear on map when they send GPS updates
- Base stations and team leads appear when they transmit

### Troubleshooting

#### No devices detected
```bash
# Check USB connection
lsusb

# Check permissions
sudo usermod -a -G dialout $USER
# Logout and login again

# Check for ttyUSB device
sudo dmesg | grep tty
```

#### Cannot connect to Meshtastic
```bash
# Test with meshtastic CLI
python3 -m meshtastic --info

# If that works, HeadSpace should too
```

#### Nodes not appearing
- Check that devices are configured with correct roles (see hardware-setup.md)
- Verify GPS lock on tracker devices (LED indicators)
- Check position broadcast intervals (should be 30-120s for trackers)
- Increase `position_broadcast_secs` in device config if testing indoors

---

## Performance Testing

### Stress Test (Many Nodes)

Edit `services/ingestion/config.yaml` to add more simulated nodes:

```yaml
simulation_nodes:
  - node_id: "!12345001"
    name: "Dog-01"
    type: dog
    movement: circle
  - node_id: "!12345002"
    name: "Dog-02"
    type: dog
    movement: figure8
  # Add up to 20-30 nodes...
```

Dashboard should handle 20+ nodes smoothly.

### Network Latency Test

Simulate LoRa latency by adjusting `simulation_interval` in config:
```yaml
simulation_interval: 30  # 30 seconds between updates
```

Dashboard should gracefully handle stale data (nodes turn orange → red).

### Database Load Test

```bash
# Generate large dataset
sqlite3 data/headspace.db "SELECT COUNT(*) FROM gps_points"

# After running overnight, you should have thousands of points
# Dashboard should still load quickly due to breadcrumb buffering
```

---

## ATAK Integration Test

*Note: ATAK integration is planned for future release*

1. Install ATAK on Android device
2. Configure ATAK to connect to HeadSpace ATAK bridge (port 8088)
3. Dog nodes should appear as icons on ATAK map
4. Test bidirectional messaging

---

## Automated Tests

### Unit Tests (Future)
```bash
# Run all tests
python3 -m pytest tests/

# Run specific test
python3 -m pytest tests/test_dwell_detector.py
```

### Integration Tests (Future)
```bash
# Test end-to-end flow
./scripts/run_integration_tests.sh
```

---

## Success Criteria

✅ All three services start without errors
✅ Dashboard loads and shows map
✅ Simulated nodes appear on map
✅ Position updates occur every 10 seconds
✅ Breadcrumb trails render correctly
✅ Dwell detection triggers after 60s+ in area
✅ SSE connection indicator shows green
✅ Database accumulates GPS points
✅ Node status changes (LIVE → STALE → LOST) work
✅ Map controls (fit, toggle trails/dwells) function
✅ Node filtering works

---

## Common Issues

### Port Already in Use
```bash
# Find process using port 8080 or 8081
sudo lsof -i :8080
sudo lsof -i :8081

# Kill the process
sudo kill -9 <PID>
```

### Mosquitto Not Running
```bash
# Start manually
sudo service mosquitto start

# Or in dev container:
mosquitto -c /etc/mosquitto/mosquitto.conf
```

### Database Locked
```bash
# Stop all services
pkill -f ingest.py
pkill -f processor.py
pkill -f "python.*dashboard"

# Wait 2 seconds for WAL cleanup
sleep 2

# Restart
./start.sh
```

### SSE Not Connecting
- Check browser console (F12) for errors
- Verify processor.py is running on port 8081
- Try curl: `curl -N http://localhost:8081/events`
- Check CORS settings if accessing from different origin

---

## Next Steps

Once basic testing is complete:

1. **Configure Real Devices**: Follow [hardware-setup.md](docs/hardware-setup.md)
2. **Field Test**: Take system + devices outdoors for GPS lock
3. **Tune Parameters**: Adjust dwell thresholds based on dog behavior
4. **Deploy**: Run on Raspberry Pi or similar for portable operation
5. **ATAK Integration**: Enable tactical coordination

---

## Support

If you encounter issues:

1. Check logs in `logs/` directory
2. Review configuration files in service directories
3. Verify Mosquitto is running: `pgrep mosquitto`
4. Test MQTT: `mosquitto_sub -h localhost -t 'headspace/#' -v`
5. Check database: `sqlite3 data/headspace.db .tables`

For more help, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (future)
