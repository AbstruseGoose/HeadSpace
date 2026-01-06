# Deployment Guide

Complete instructions for running HeadSpace in GitHub Codespaces or on a Linux machine.

## Prerequisites

### Hardware
- Linux machine (Ubuntu 20.04+ recommended) or GitHub Codespaces
- Meshtastic-compatible device connected via USB (for real deployment)
- Minimum 2GB RAM, 5GB disk space

### Software
- Python 3.9+
- Mosquitto MQTT broker
- SQLite3 (usually pre-installed)
- Modern web browser with JavaScript enabled

---

## Installation Steps

### 1. Clone the Repository

```bash
# If not already in the workspace
cd /workspaces/HeadSpace
```

### 2. Install Mosquitto MQTT Broker

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

# Start and enable Mosquitto
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Verify it's running
sudo systemctl status mosquitto

# Test with a simple pub/sub
mosquitto_sub -h localhost -t test &
mosquitto_pub -h localhost -t test -m "Hello MQTT"
# You should see "Hello MQTT" printed
```

### 3. Install Python Dependencies

```bash
# Install for ingestion service
pip install -r services/ingestion/requirements.txt

# Install for processing service
pip install -r services/processing/requirements.txt

# Install for dashboard server
pip install -r dashboard/requirements.txt
```

### 4. Initialize the Database

```bash
# Create the database
sqlite3 data/headspace.db < data/schemas.sql

# Verify tables were created
sqlite3 data/headspace.db "SELECT name FROM sqlite_master WHERE type='table';"
# Should show: nodes, gps_points, dwells, telemetry, system_events
```

### 5. Configure Services

#### Ingestion Service Config

Create `services/ingestion/config.yaml`:

```bash
cp services/ingestion/config.yaml.example services/ingestion/config.yaml
# Edit to match your setup
nano services/ingestion/config.yaml
```

**For testing without hardware**, set `simulation_mode: true` in the config.

#### Processing Service Config

Create `services/processing/config.yaml`:

```bash
cp services/processing/config.yaml.example services/processing/config.yaml
# Edit to match your setup
nano services/processing/config.yaml
```

---

## Running the System

You'll need **3 terminal sessions** (or use `tmux`/`screen`).

### Terminal 1: Ingestion Service

```bash
cd /workspaces/HeadSpace
python services/ingestion/ingest.py
```

**Expected output:**
```
2026-01-04 14:30:00 [INFO] Ingestion: Starting HeadSpace Ingestion Service
2026-01-04 14:30:01 [INFO] Ingestion: Connected to Meshtastic device on /dev/ttyUSB0
2026-01-04 14:30:01 [INFO] Ingestion: Connected to MQTT broker at localhost:1883
2026-01-04 14:30:01 [INFO] Ingestion: Waiting for Meshtastic packets...
```

### Terminal 2: Processing Service

```bash
cd /workspaces/HeadSpace
python services/processing/processor.py
```

**Expected output:**
```
2026-01-04 14:30:05 [INFO] Processing: Starting HeadSpace Processing Service
2026-01-04 14:30:05 [INFO] Processing: Connected to MQTT broker at localhost:1883
2026-01-04 14:30:05 [INFO] Processing: Database initialized at data/headspace.db
2026-01-04 14:30:05 [INFO] Processing: SSE server started on port 8081
2026-01-04 14:30:05 [INFO] Processing: Subscribed to headspace/#
```

### Terminal 3: Dashboard Server

```bash
cd /workspaces/HeadSpace
python dashboard/server.py
```

**Expected output:**
```
2026-01-04 14:30:10 [INFO] Dashboard: Starting HeadSpace Dashboard Server
2026-01-04 14:30:10 [INFO] Dashboard: Serving static files from /workspaces/HeadSpace/dashboard
2026-01-04 14:30:10 [INFO] Dashboard: Dashboard available at http://localhost:8080
```

### Access the Dashboard

Open your browser to: **http://localhost:8080**

In Codespaces, VSCode will prompt you to forward port 8080 - click "Open in Browser".

---

## Testing Without Hardware

If you don't have a Meshtastic device connected, you can run in **simulation mode**.

### 1. Enable Simulation Mode

Edit `services/ingestion/config.yaml`:

```yaml
meshtastic:
  simulation_mode: true
  simulation_interval: 10  # Seconds between simulated updates
```

### 2. Run as Normal

The ingestion service will generate fake GPS updates for several simulated nodes:
- Dog-Rex (moving in a circle)
- Dog-Luna (moving in a figure-8)
- Base-Station-1 (stationary)
- Team-Lead-1 (random walk)

This allows you to see the system working without hardware.

---

## Troubleshooting

### Issue: "Permission denied" on `/dev/ttyUSB0`

```bash
# Add your user to the dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, or use:
newgrp dialout

# Or run with sudo (not recommended for production)
sudo python services/ingestion/ingest.py
```

### Issue: Mosquitto won't start

```bash
# Check if another service is using port 1883
sudo lsof -i :1883

# Check Mosquitto logs
sudo journalctl -u mosquitto -n 50

# Try restarting
sudo systemctl restart mosquitto
```

### Issue: "Module not found" errors

```bash
# Make sure you're using the right Python
which python
python --version  # Should be 3.9+

# Reinstall dependencies
pip install --force-reinstall -r services/ingestion/requirements.txt
```

### Issue: Database locked

```bash
# Check if another process is using the database
lsof data/headspace.db

# If stuck, stop all services and restart
pkill -f ingest.py
pkill -f processor.py
```

### Issue: Dashboard won't load

```bash
# Check if port 8080 is in use
sudo lsof -i :8080

# Try a different port
python dashboard/server.py --port 8090
```

### Issue: No data appearing on dashboard

1. Check that all 3 services are running
2. Check MQTT is working:
   ```bash
   # In one terminal
   mosquitto_sub -h localhost -t 'headspace/#' -v
   
   # Should see messages when data arrives
   ```
3. Check processing service logs for errors
4. Open browser console (F12) and check for JavaScript errors

---

## Production Deployment

### Using systemd Services

Create service files for automatic startup:

#### `/etc/systemd/system/headspace-ingest.service`

```ini
[Unit]
Description=HeadSpace Ingestion Service
After=network.target mosquitto.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/headspace
ExecStart=/usr/bin/python3 /opt/headspace/services/ingestion/ingest.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Similar for `headspace-processor.service` and `headspace-dashboard.service`

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable headspace-ingest headspace-processor headspace-dashboard
sudo systemctl start headspace-ingest headspace-processor headspace-dashboard

# Check status
sudo systemctl status headspace-*
```

### Using Docker Compose (Optional)

A `docker-compose.yml` file will be provided for containerized deployment.

---

## Maintenance

### Database Cleanup

The processing service automatically prunes old data based on `config.yaml` settings:

```yaml
cleanup:
  enabled: true
  interval_hours: 24
  keep_gps_days: 30
  keep_telemetry_days: 7
```

Manual cleanup:

```bash
# Remove GPS points older than 30 days
sqlite3 data/headspace.db "DELETE FROM gps_points WHERE timestamp < strftime('%s', 'now', '-30 days');"

# Vacuum to reclaim space
sqlite3 data/headspace.db "VACUUM;"
```

### Backup

```bash
# Backup database (while running - SQLite supports hot backups)
sqlite3 data/headspace.db ".backup /backups/headspace-$(date +%Y%m%d).db"

# Or simply copy the file
cp data/headspace.db /backups/headspace-$(date +%Y%m%d).db
```

### Logs

```bash
# View real-time logs
tail -f /var/log/headspace/ingest.log
tail -f /var/log/headspace/process.log

# Or if running in foreground, just check the terminal output
```

### Monitoring

Check service health:

```bash
# Node count
sqlite3 data/headspace.db "SELECT COUNT(*) FROM nodes WHERE is_active = 1;"

# Recent activity
sqlite3 data/headspace.db "SELECT * FROM v_active_nodes LIMIT 10;"

# Ongoing dwells
sqlite3 data/headspace.db "SELECT * FROM v_ongoing_dwells;"
```

---

## Performance Tuning

### For High Node Count (50+)

Edit `services/processing/config.yaml`:

```yaml
database:
  # Use WAL mode for better concurrency
  wal_mode: true
  
  # Increase cache
  cache_size: 10000

# Limit in-memory breadcrumb buffer
breadcrumb_buffer_size: 50  # Per node
```

### For Low Resource Environments

```yaml
# Reduce SSE heartbeat frequency
sse:
  heartbeat_interval: 60

# Reduce telemetry storage
telemetry:
  store_interval: 300  # Only store every 5 minutes
```

---

## Security Considerations

### For Production Use:

1. **MQTT Authentication**: Enable username/password on Mosquitto
   ```bash
   sudo mosquitto_passwd -c /etc/mosquitto/passwd headspace
   ```

2. **Dashboard Access Control**: Add basic auth to dashboard server
   ```python
   # In dashboard/server.py, use Flask-HTTPAuth
   ```

3. **Firewall**: Only expose necessary ports
   ```bash
   sudo ufw allow 8080/tcp  # Dashboard (if remote access needed)
   # Do NOT expose 1883 (MQTT) or 8081 (SSE) externally
   ```

4. **HTTPS**: Use reverse proxy (nginx) with SSL for dashboard

---

## Next Steps

Once the system is running:

1. Configure node types in `services/ingestion/config.yaml`
2. Adjust dwell detection thresholds in `services/processing/config.yaml`
3. Customize dashboard appearance in `dashboard/config.json`
4. Monitor the system for a few hours to verify stability
5. Set up systemd services for automatic startup
6. Configure backups

---

## Getting Help

- Check logs first: All services log errors with details
- Test MQTT manually: Use `mosquitto_sub` to verify messages
- Verify database: Use `sqlite3` to check data is being stored
- Browser console: Check for JavaScript errors (F12)

For issues specific to Meshtastic connectivity, refer to:
- https://meshtastic.org/docs/software/python/cli

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-04
