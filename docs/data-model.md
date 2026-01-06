# Data Model & JSON Schemas

This document defines all data structures used in the HeadSpace system.

## 1. MQTT Message Schemas

All messages published to MQTT follow these schemas.

### 1.1 Position Update Event

**Topic**: `headspace/position/{node_id}`

```json
{
  "event_type": "position_update",
  "timestamp": "2026-01-04T14:23:45.123Z",
  "node_id": "!a1b2c3d4",
  "node_name": "Dog-Rex",
  "node_type": "dog",
  "position": {
    "latitude": 47.6062,
    "longitude": -122.3321,
    "altitude": 12.5,
    "precision": 5,
    "source": "gps"
  },
  "telemetry": {
    "battery_level": 87,
    "voltage": 4.12,
    "rssi": -89,
    "snr": 8.5
  },
  "raw_packet": {
    "from": 2757453012,
    "to": 4294967295,
    "hop_limit": 3,
    "hop_start": 3,
    "want_ack": false
  }
}
```

**Fields:**
- `event_type`: Always "position_update"
- `timestamp`: ISO 8601 format with milliseconds (UTC)
- `node_id`: Meshtastic node ID (hex format with `!` prefix)
- `node_name`: Human-readable name (from node DB or config)
- `node_type`: One of: `dog`, `team_lead`, `base_station`, `truck`, `repeater`, `unknown`
- `position.latitude`: Decimal degrees
- `position.longitude`: Decimal degrees
- `position.altitude`: Meters above sea level (optional)
- `position.precision`: GPS precision/HDOP (optional)
- `position.source`: Always "gps" for now (future: "manual", "estimated")
- `telemetry.*`: Optional fields, null if not available
- `raw_packet`: Original Meshtastic packet metadata (for debugging)

### 1.2 Telemetry Update Event

**Topic**: `headspace/telemetry/{node_id}`

```json
{
  "event_type": "telemetry_update",
  "timestamp": "2026-01-04T14:23:45.123Z",
  "node_id": "!a1b2c3d4",
  "node_name": "Dog-Rex",
  "telemetry": {
    "battery_level": 87,
    "voltage": 4.12,
    "channel_utilization": 12.5,
    "air_util_tx": 2.3
  }
}
```

**Note**: Telemetry can arrive independently of position updates.

### 1.3 Node Discovery Event

**Topic**: `headspace/discovery/{node_id}`

```json
{
  "event_type": "node_discovered",
  "timestamp": "2026-01-04T14:23:45.123Z",
  "node_id": "!a1b2c3d4",
  "node_info": {
    "short_name": "REX",
    "long_name": "Dog-Rex",
    "hw_model": "TBEAM",
    "role": "CLIENT",
    "firmware_version": "2.2.15.abc123"
  }
}
```

**Triggered**: When a new node is first seen or requests node info.

### 1.4 Dwell Event

**Topic**: `headspace/dwell/{node_id}`

```json
{
  "event_type": "dwell_started",
  "timestamp": "2026-01-04T14:25:00.000Z",
  "node_id": "!a1b2c3d4",
  "node_name": "Dog-Rex",
  "dwell_id": "dwell_a1b2c3d4_1704377100",
  "location": {
    "center_lat": 47.6062,
    "center_lon": -122.3321,
    "radius_meters": 15.2
  },
  "duration_seconds": 120,
  "point_count": 8,
  "status": "ongoing"
}
```

**Dwell End:**
```json
{
  "event_type": "dwell_ended",
  "timestamp": "2026-01-04T14:30:00.000Z",
  "node_id": "!a1b2c3d4",
  "node_name": "Dog-Rex",
  "dwell_id": "dwell_a1b2c3d4_1704377100",
  "location": {
    "center_lat": 47.6062,
    "center_lon": -122.3321,
    "radius_meters": 15.2
  },
  "duration_seconds": 300,
  "point_count": 15,
  "status": "completed"
}
```

**Fields:**
- `dwell_id`: Unique identifier for this dwell event
- `location.center_lat/lon`: Centroid of all points in the dwell
- `location.radius_meters`: Maximum distance from center
- `duration_seconds`: Time from first to last point
- `point_count`: Number of GPS updates in the dwell
- `status`: `ongoing` or `completed`

---

## 2. SQLite Database Schema

### 2.1 Table: `nodes`

Stores node metadata and last-known state.

```sql
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    node_name TEXT NOT NULL,
    node_type TEXT NOT NULL,
    short_name TEXT,
    long_name TEXT,
    hw_model TEXT,
    role TEXT,
    firmware_version TEXT,
    first_seen_at INTEGER NOT NULL,
    last_heard_at INTEGER NOT NULL,
    last_position_lat REAL,
    last_position_lon REAL,
    last_position_alt REAL,
    last_battery_level INTEGER,
    last_voltage REAL,
    last_rssi INTEGER,
    last_snr REAL,
    is_active BOOLEAN DEFAULT 1,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_nodes_last_heard ON nodes(last_heard_at);
CREATE INDEX idx_nodes_active ON nodes(is_active);
```

**Notes:**
- Timestamps are Unix epoch (seconds)
- `last_heard_at` updates on ANY packet from node
- `is_active` = 0 if node hasn't been heard for > 24 hours

### 2.2 Table: `gps_points`

Historical GPS breadcrumb trail.

```sql
CREATE TABLE gps_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL,
    precision_meters REAL,
    battery_level INTEGER,
    rssi INTEGER,
    snr REAL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_gps_node_time ON gps_points(node_id, timestamp DESC);
CREATE INDEX idx_gps_timestamp ON gps_points(timestamp DESC);
```

**Usage:**
- One row per GPS update
- Query with time range for breadcrumb trails
- Prune old data periodically (keep last 30 days?)

### 2.3 Table: `dwells`

Detected dwell events.

```sql
CREATE TABLE dwells (
    dwell_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    start_timestamp INTEGER NOT NULL,
    end_timestamp INTEGER,
    duration_seconds INTEGER,
    center_lat REAL NOT NULL,
    center_lon REAL NOT NULL,
    radius_meters REAL NOT NULL,
    point_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ongoing', 'completed')),
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_dwells_node_time ON dwells(node_id, start_timestamp DESC);
CREATE INDEX idx_dwells_status ON dwells(status);
```

**Status:**
- `ongoing`: Dwell in progress, `end_timestamp` is NULL
- `completed`: Dwell finished, all fields populated

### 2.4 Table: `telemetry`

Periodic telemetry snapshots (for trending).

```sql
CREATE TABLE telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    battery_level INTEGER,
    voltage REAL,
    channel_utilization REAL,
    air_util_tx REAL,
    rssi INTEGER,
    snr REAL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_telemetry_node_time ON telemetry(node_id, timestamp DESC);
```

**Note:** This is optional - for trending battery drain, signal strength over time.

---

## 3. Server-Sent Events (SSE) Schema

Dashboard receives updates via SSE on `/events` endpoint.

### 3.1 Position Update

```
event: position
data: {"node_id":"!a1b2c3d4","node_name":"Dog-Rex","timestamp":"2026-01-04T14:23:45.123Z","position":{"latitude":47.6062,"longitude":-122.3321,"altitude":12.5},"telemetry":{"battery_level":87,"rssi":-89,"snr":8.5},"status":"LIVE"}
```

### 3.2 Node Status Change

```
event: status
data: {"node_id":"!a1b2c3d4","node_name":"Dog-Rex","status":"STALE","last_heard_seconds_ago":320}
```

**Status values:**
- `LIVE`: Last heard < 5 minutes (300 seconds)
- `STALE`: Last heard 5-15 minutes (300-900 seconds)
- `LOST`: Last heard > 15 minutes (900+ seconds)

### 3.3 Dwell Alert

```
event: dwell
data: {"event_type":"dwell_started","node_id":"!a1b2c3d4","node_name":"Dog-Rex","dwell_id":"dwell_a1b2c3d4_1704377100","location":{"center_lat":47.6062,"center_lon":-122.3321,"radius_meters":15.2},"duration_seconds":120,"status":"ongoing"}
```

### 3.4 Node Discovery

```
event: discovery
data: {"node_id":"!a1b2c3d4","node_name":"Dog-Rex","node_type":"dog","hw_model":"TBEAM"}
```

### 3.5 Heartbeat

```
event: heartbeat
data: {"timestamp":"2026-01-04T14:23:45.123Z","active_nodes":12}
```

**Sent every 30 seconds** to keep connection alive and verify server health.

---

## 4. Configuration Files Schema

### 4.1 Ingestion Config (`services/ingestion/config.yaml`)

```yaml
meshtastic:
  connection_type: serial
  serial_port: /dev/ttyUSB0  # Auto-detect if not specified
  baud_rate: 115200
  
mqtt:
  broker: localhost
  port: 1883
  client_id: headspace-ingest
  topics:
    position: headspace/position
    telemetry: headspace/telemetry
    discovery: headspace/discovery
  qos: 1
  
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  file: /var/log/headspace/ingest.log

node_types:
  # Map node IDs to types (if not in NodeDB)
  "!a1b2c3d4": dog
  "!e5f6g7h8": base_station
  "!i9j0k1l2": team_lead
```

### 4.2 Processing Config (`services/processing/config.yaml`)

```yaml
mqtt:
  broker: localhost
  port: 1883
  client_id: headspace-process
  topics:
    - headspace/position/#
    - headspace/telemetry/#
    - headspace/discovery/#
  qos: 1

database:
  path: /workspaces/HeadSpace/data/headspace.db
  
dwell_detection:
  enabled: true
  # Node type specific settings
  dog:
    radius_meters: 15
    min_duration_seconds: 60
    max_duration_seconds: 7200
  team_lead:
    radius_meters: 20
    min_duration_seconds: 180
    max_duration_seconds: 14400
  default:
    radius_meters: 20
    min_duration_seconds: 120
    max_duration_seconds: 3600

status_thresholds:
  live_seconds: 300      # 5 minutes
  stale_seconds: 900     # 15 minutes
  lost_seconds: 3600     # 1 hour (for UI display, doesn't affect "active")
  inactive_seconds: 86400  # 24 hours (mark node inactive in DB)

sse:
  port: 8081
  heartbeat_interval: 30

logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  file: /var/log/headspace/process.log

cleanup:
  # Prune old data periodically
  enabled: true
  interval_hours: 24
  keep_gps_days: 30
  keep_telemetry_days: 7
```

### 4.3 Dashboard Config (`dashboard/config.json`)

```json
{
  "map": {
    "default_center": [47.6062, -122.3321],
    "default_zoom": 13,
    "tile_layer": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "tile_attribution": "&copy; OpenStreetMap contributors",
    "max_zoom": 18
  },
  "sse": {
    "url": "http://localhost:8081/events",
    "reconnect_interval": 3000
  },
  "ui": {
    "auto_center_on_update": true,
    "breadcrumb_max_points": 100,
    "show_dwell_radius": true,
    "node_icon_size": [32, 32]
  },
  "node_types": {
    "dog": {
      "icon": "🐕",
      "color": "#FF6B6B",
      "show_breadcrumbs": true
    },
    "base_station": {
      "icon": "📡",
      "color": "#4ECDC4",
      "show_breadcrumbs": false
    },
    "team_lead": {
      "icon": "👤",
      "color": "#45B7D1",
      "show_breadcrumbs": true
    },
    "truck": {
      "icon": "🚚",
      "color": "#FFA07A",
      "show_breadcrumbs": true
    },
    "repeater": {
      "icon": "🔁",
      "color": "#98D8C8",
      "show_breadcrumbs": false
    },
    "unknown": {
      "icon": "❓",
      "color": "#95A5A6",
      "show_breadcrumbs": false
    }
  }
}
```

---

## 5. In-Memory State Structure

The processing service maintains this in-memory state:

```python
{
    "nodes": {
        "!a1b2c3d4": {
            "node_id": "!a1b2c3d4",
            "node_name": "Dog-Rex",
            "node_type": "dog",
            "last_position": {
                "latitude": 47.6062,
                "longitude": -122.3321,
                "altitude": 12.5,
                "timestamp": 1704377025
            },
            "last_telemetry": {
                "battery_level": 87,
                "voltage": 4.12,
                "rssi": -89,
                "snr": 8.5,
                "timestamp": 1704377025
            },
            "status": "LIVE",
            "last_heard_at": 1704377025,
            "breadcrumb_buffer": [
                # Last 50-100 points for quick access
                {"lat": 47.6062, "lon": -122.3321, "ts": 1704377025},
                {"lat": 47.6063, "lon": -122.3320, "ts": 1704377010}
            ],
            "active_dwell": {
                "dwell_id": "dwell_a1b2c3d4_1704377100",
                "start_timestamp": 1704377100,
                "points": [
                    {"lat": 47.6062, "lon": -122.3321, "ts": 1704377100},
                    {"lat": 47.6062, "lon": -122.3322, "ts": 1704377160}
                ]
            }
        }
    }
}
```

**Purpose:**
- Fast lookups for status checks
- Avoid DB queries for every SSE broadcast
- Maintain dwell detection state
- Reconstruct on service restart from DB

---

## 6. API Endpoints (Future)

Not implemented initially, but reserved for future REST API:

- `GET /api/nodes` - List all nodes
- `GET /api/nodes/{node_id}` - Node details
- `GET /api/nodes/{node_id}/trail?since={timestamp}` - GPS breadcrumb trail
- `GET /api/nodes/{node_id}/dwells` - Dwell history
- `GET /api/dwells?active=true` - All active dwells
- `GET /api/telemetry/{node_id}?since={timestamp}` - Telemetry history

---

## Design Notes

### Timestamp Handling
- **All timestamps are UTC**
- Stored as Unix epoch (seconds) in SQLite for efficiency
- Transmitted as ISO 8601 strings in JSON for readability
- JavaScript converts to local time for display

### Node ID Format
- Meshtastic uses `!` prefix for hex IDs (e.g., `!a1b2c3d4`)
- Always use this format consistently
- Internal numeric IDs not exposed to user

### Coordinate Precision
- Latitude/Longitude stored as `REAL` (float64 in SQLite)
- Sufficient precision for ~1cm accuracy
- Don't round coordinates during processing

### Event-Driven Flow
- MQTT decouples ingestion from processing
- Processing service is stateless (can restart)
- SSE allows dashboard to be stateless (can refresh)
- No component polls or queries other components

### Scalability Considerations
- Current design targets 10-50 nodes
- For 100+ nodes, consider:
  - Partitioning `gps_points` table by month
  - Using Redis for in-memory state
  - Multiple processing service instances
  - Geographic sharding

---

**Version**: 1.0  
**Last Updated**: 2026-01-04
