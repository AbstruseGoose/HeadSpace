# HeadSpace - Meshtastic Tracking System

**Latency-tolerant, offline-capable tracking system for Meshtastic LoRa mesh networks**

## Architecture Overview

### Design Principles
- **Event-driven, not polled**: Updates trigger actions, never query devices
- **LoRa-aware**: Designed for high-latency, low-bandwidth, lossy mesh
- **Offline-first**: No internet required, runs entirely on local machine
- **Mesh-safe**: No aggressive polling or request spam
- **Resilient**: Tolerates packet loss, delays, and service restarts

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Meshtastic Gateway (USB Serial)                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Ingestion Service (Python)                                  │
│  - meshtastic Python API (Serial)                           │
│  - Normalizes packets                                        │
│  - Emits to local MQTT                                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  MQTT Broker (Mosquitto - local)                            │
│  - Decouples components                                      │
│  - Allows multiple consumers                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Processing Service (Python)                                 │
│  - Subscribes to MQTT events                                 │
│  - Maintains in-memory state (last known positions)          │
│  - Detects dwell events                                      │
│  - Stores to SQLite                                          │
│  - Broadcasts via SSE to dashboard                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    ┌───────────────┐      ┌────────────────┐
    │  SQLite DB    │      │  Web Dashboard │
    │  - GPS points │      │  - Leaflet map │
    │  - Dwells     │      │  - SSE live    │
    │  - Telemetry  │      │  - Node status │
    └───────────────┘      └────────────────┘
```

### Why This Stack?

**Meshtastic Python API (Serial) over MQTT:**
- Direct connection = lower latency for single gateway
- Simpler to debug and deploy
- We still emit to MQTT internally for decoupling
- Can add Meshtastic MQTT later if multiple gateways needed

**SQLite over InfluxDB:**
- Lighter weight, easier in Codespaces
- No separate service to manage
- Sufficient for this scale (dozens of nodes)
- Built-in with Python
- Easier backup (single file)

**Python Processing over Node-RED:**
- More maintainable for complex logic (dwell detection)
- Better for version control
- Easier to test
- Full language capabilities

**SSE over WebSocket:**
- Simpler for one-way push (server → client)
- Auto-reconnection built into browser
- No need for bidirectional communication

## Features

### Core Tracking
- **Live location updates**: Event-driven when packets arrive
- **Breadcrumb trails**: Historical GPS path for each node
- **Node status**: LIVE / STALE / LOST based on last heard time
- **Telemetry**: Battery %, RSSI, SNR when available

### Dwell Detection
- Detects when a node stays in ~10-20m radius for 60-180 seconds
- Tracks dwell duration and location
- Useful for dog behavior monitoring
- Configurable thresholds per node type

### Dashboard
- Live updating map (Leaflet.js)
- Real-time node list with status indicators
- Breadcrumb trails toggle per node
- Dwell markers on map
- No page refresh needed - SSE pushes updates

## Directory Structure

```
HeadSpace/
├── README.md                 # This file
├── services/
│   ├── ingestion/
│   │   ├── ingest.py         # Meshtastic → MQTT
│   │   ├── requirements.txt
│   │   └── config.yaml
│   └── processing/
│       ├── processor.py      # MQTT → DB + SSE
│       ├── dwell_detector.py # Dwell time logic
│       ├── requirements.txt
│       └── config.yaml
├── dashboard/
│   ├── index.html           # Main UI
│   ├── app.js               # Dashboard logic
│   ├── styles.css
│   └── server.py            # Simple HTTP + SSE server
├── data/
│   ├── headspace.db         # SQLite database
│   └── schemas.sql          # DB schema
├── docs/
│   ├── data-model.md        # JSON schemas
│   ├── deployment.md        # Setup instructions
│   └── architecture.md      # Detailed design
└── docker-compose.yml       # Optional: containerized setup
```

## Quick Start

*Detailed instructions coming in `/docs/deployment.md`*

```bash
# 1. Install dependencies
pip install -r services/ingestion/requirements.txt
pip install -r services/processing/requirements.txt

# 2. Start Mosquitto
sudo systemctl start mosquitto

# 3. Initialize database
sqlite3 data/headspace.db < data/schemas.sql

# 4. Start ingestion service (in terminal 1)
python services/ingestion/ingest.py

# 5. Start processing service (in terminal 2)
python services/processing/processor.py

# 6. Start dashboard (in terminal 3)
python dashboard/server.py

# 7. Open browser to http://localhost:8080
```

## Network Topology Support

- **Fixed base stations**: Always-on routers
- **Rogue repeaters**: Temporary mesh extenders
- **Team lead handhelds**: Client nodes
- **Truck nodes**: Variable (router/client with larger antennas)
- **Dog nodes**: High-priority GPS, frequent updates when moving

## Data Flow

1. **Meshtastic packet arrives** at gateway via LoRa mesh
2. **Ingestion service** receives via Serial, normalizes, publishes to MQTT
3. **Processing service** receives MQTT event:
   - Updates in-memory state (last known position)
   - Stores GPS point to SQLite with timestamp
   - Checks dwell conditions
   - Broadcasts update via SSE
4. **Dashboard** receives SSE event, updates map immediately
5. **No polling occurs** - system is entirely event-driven

## Status Thresholds

- **LIVE**: Last heard < 5 minutes
- **STALE**: Last heard 5-15 minutes
- **LOST**: Last heard > 15 minutes

*(Configurable per deployment)*

## Future Expansion

- Geofencing (not in initial implementation)
- Multiple gateway support (via Meshtastic MQTT)
- Historical replay
- ATAK CoT feed (separate integration)
- Alert rules engine

## License

TBD

## Contributing

TBD

---

**Current Status**: 🏗️ Initial design phase