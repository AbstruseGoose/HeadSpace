# HeadSpace Architecture

Detailed technical architecture for the HeadSpace tracking system.

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Key Design Decisions](#key-design-decisions)
5. [LoRa Constraints & Adaptations](#lora-constraints--adaptations)
6. [Scalability Considerations](#scalability-considerations)
7. [Future Expansion](#future-expansion)

---

## System Overview

HeadSpace is a **latency-tolerant, event-driven tracking system** designed specifically for LoRa mesh networks. It prioritizes mesh health over real-time responsiveness while still providing near-instantaneous UI updates when data arrives.

### Core Principles

1. **Event-Driven Architecture**: No component polls another; all communication is push-based
2. **LoRa-Aware Design**: Respects high latency (seconds to minutes) and low bandwidth
3. **Decoupled Components**: Services communicate via MQTT for independent scaling and restart
4. **Stateful Processing**: In-memory state allows instant response while DB ensures persistence
5. **Offline-First**: No internet required; runs entirely on local infrastructure

### Technology Stack Rationale

| Component | Technology | Why? |
|-----------|-----------|------|
| Gateway Connection | Meshtastic Python API (Serial) | Lower latency than MQTT for single gateway; simpler debugging |
| Message Bus | Mosquitto MQTT | Industry standard; lightweight; reliable delivery; decouples services |
| Storage | SQLite | Sufficient for scale; no separate service; single-file backup; built into Python |
| Processing | Python | Full-featured language; rich ecosystem; easy to maintain |
| Live Updates | Server-Sent Events (SSE) | Simpler than WebSocket for one-way push; browser auto-reconnects |
| Frontend | Vanilla JS + Leaflet | No build step; easy to modify; fast loading; widely supported |

---

## Component Architecture

### 1. Ingestion Service

**Purpose**: Bridge between Meshtastic LoRa gateway and internal MQTT bus.

**Responsibilities**:
- Connect to Meshtastic device via Serial/USB
- Listen for incoming packets (position, telemetry, node info)
- Normalize packet data to internal schema
- Publish normalized events to MQTT
- Handle connection failures and reconnection

**Key Features**:
- **Non-blocking**: Packet handler returns immediately; no I/O in callback
- **Simulation mode**: Generate fake data for testing without hardware
- **Deduplication**: Skip duplicate positions to reduce downstream load
- **Node mapping**: Override node types/names from config

**Interface**:
```
INPUT:  Meshtastic packets (Serial/USB)
OUTPUT: MQTT messages on topics:
        - headspace/position/{node_id}
        - headspace/telemetry/{node_id}
        - headspace/discovery/{node_id}
```

**Failure Modes**:
- Serial disconnect → Auto-reconnect every 5 seconds
- MQTT disconnect → Buffer messages, reconnect, flush buffer
- Invalid packet → Log warning, skip

---

### 2. Processing Service

**Purpose**: Core business logic; maintains state, detects dwells, stores data, broadcasts updates.

**Responsibilities**:
- Subscribe to all MQTT events
- Maintain in-memory state (last known positions, telemetry)
- Store GPS points and telemetry to SQLite
- Detect dwell events using geospatial logic
- Broadcast updates to dashboard via SSE
- Periodic cleanup of old data

**Key Features**:
- **Dual Storage**: In-memory for speed, SQLite for persistence
- **Dwell Detection**: Per-node-type thresholds; handles movement resumption
- **Status Management**: Classifies nodes as LIVE/STALE/LOST based on age
- **Graceful Restart**: Rebuilds in-memory state from DB on startup

**Interface**:
```
INPUT:  MQTT messages from headspace/#
OUTPUT: SQLite database (insert/update operations)
        SSE events on http://localhost:8081/events
```

**Failure Modes**:
- MQTT disconnect → Reconnect, miss messages during outage (acceptable)
- DB locked → Retry with exponential backoff
- Memory overflow → Prune old breadcrumbs, limit buffer size

---

### 3. Dashboard Server

**Purpose**: Serve static files and provide HTTP endpoint for SSE.

**Responsibilities**:
- Serve HTML/CSS/JS assets
- Proxy SSE connection from processing service
- Handle CORS for development

**Key Features**:
- **Lightweight**: Simple Flask app, no complex routing
- **Static Assets**: All UI logic in browser, server is stateless
- **SSE Proxy**: Passes events from processing service to clients

**Interface**:
```
INPUT:  HTTP requests on http://localhost:8080
OUTPUT: Static files (index.html, app.js, styles.css)
        SSE stream on http://localhost:8080/events
```

---

### 4. Web Dashboard (Frontend)

**Purpose**: Live map and node status display.

**Responsibilities**:
- Render Leaflet map with node markers
- Display breadcrumb trails
- Show node list with status indicators
- Consume SSE stream and update UI in real-time
- Handle user interactions (toggle trails, zoom to node, etc.)

**Key Features**:
- **Real-Time Updates**: SSE connection auto-updates map
- **Responsive Design**: Works on desktop and tablet
- **No Page Reload**: Pure JS updates, no full refresh
- **Visual Status**: Color-coded markers for LIVE/STALE/LOST

**Interface**:
```
INPUT:  SSE events from /events endpoint
        User interactions (clicks, toggles)
OUTPUT: Updated DOM (map, node list, overlays)
```

---

## Data Flow

### Normal Operation (Position Update)

```
┌──────────────────┐
│  Meshtastic Node │ (sends GPS packet over LoRa)
└────────┬─────────┘
         │ LoRa mesh (high latency, low bandwidth)
         ▼
┌──────────────────┐
│  Gateway Device  │ (USB connected)
└────────┬─────────┘
         │ Serial
         ▼
┌──────────────────────────────────────────────┐
│  Ingestion Service                           │
│  1. Receive packet via Meshtastic API       │
│  2. Extract position data                    │
│  3. Normalize to internal schema             │
│  4. Publish to MQTT                          │
└────────┬─────────────────────────────────────┘
         │ MQTT (local)
         ▼
┌──────────────────────────────────────────────┐
│  MQTT Broker (Mosquitto)                     │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Processing Service                          │
│  1. Receive MQTT message                     │
│  2. Update in-memory state                   │
│  3. Store GPS point to SQLite                │
│  4. Check dwell conditions                   │
│  5. Determine node status                    │
│  6. Broadcast SSE event                      │
└────────┬────────────┬────────────────────────┘
         │            │
         ▼            ▼
┌──────────────┐  ┌──────────────┐
│  SQLite DB   │  │  SSE Stream  │
└──────────────┘  └──────┬───────┘
                         │ HTTP
                         ▼
                  ┌──────────────┐
                  │  Dashboard   │
                  │  (Browser)   │
                  └──────────────┘
```

**Timing**:
- LoRa transmission: 1-10 seconds (depends on packet size, mesh hops)
- Ingestion processing: <10ms
- MQTT delivery: <5ms (local)
- Processing + DB write: <50ms
- SSE broadcast: <5ms
- UI update: <10ms

**Total latency**: Dominated by LoRa (1-10s), internal processing ~70ms

---

## Key Design Decisions

### 1. Serial vs. MQTT for Meshtastic Connection

**Chosen: Serial (Meshtastic Python API)**

**Pros**:
- Lower latency (no extra broker hop)
- Simpler for single gateway deployment
- Direct access to device metadata
- Easier debugging (can see raw packets)

**Cons**:
- Single point of failure (one gateway only)
- Requires physical USB connection

**Alternative (not chosen)**: Meshtastic MQTT
- Better for multiple gateways
- More complex setup
- **Decision**: Start simple, can add later if needed

---

### 2. SQLite vs. InfluxDB

**Chosen: SQLite**

**Pros**:
- Zero configuration (built into Python)
- Single file = easy backup
- Sufficient performance for this scale (10-50 nodes)
- Lower resource usage
- Perfect for offline deployment

**Cons**:
- Not optimized for time-series queries
- Single writer (but WAL mode helps)

**Alternative (not chosen)**: InfluxDB
- Better for high-frequency time-series
- More complex deployment
- **Decision**: SQLite is sufficient; can migrate later if needed

---

### 3. WebSocket vs. SSE

**Chosen: Server-Sent Events (SSE)**

**Pros**:
- Simpler protocol (HTTP-based)
- Browser auto-reconnects
- One-way push is all we need
- Built-in EventSource API in browsers
- No extra libraries needed

**Cons**:
- Can't send from client to server (not needed here)

**Alternative (not chosen)**: WebSocket
- Bidirectional communication (overkill)
- Requires more complex server handling
- **Decision**: SSE is perfect for this use case

---

### 4. Node-RED vs. Python Processing

**Chosen: Python**

**Pros**:
- Full programming language capabilities
- Better for complex logic (dwell detection)
- Easier to version control
- Easier to test
- More maintainable at scale

**Cons**:
- No visual flow representation

**Alternative (not chosen)**: Node-RED
- Visual programming
- **Decision**: Dwell detection and state management are too complex for visual flows

---

### 5. Polling vs. Event-Driven

**Chosen: Event-Driven**

This is non-negotiable given LoRa constraints.

**Why**:
- LoRa bandwidth is extremely limited
- Polling would spam the mesh with requests
- Position updates are inherently asynchronous
- Nodes may be unreachable for extended periods

**Implementation**:
- Ingestion service passively listens
- Processing service reacts to MQTT events
- Dashboard receives SSE push updates
- **No component ever queries a device**

---

## LoRa Constraints & Adaptations

### Constraint 1: High Latency (1-30+ seconds)

**Adaptation**:
- Don't show "loading" spinners
- Display "last known" position until update arrives
- Show age of data: "Updated 23s ago"
- Accept that UI is always showing historical state

### Constraint 2: Low Bandwidth (~250 bytes/sec)

**Adaptation**:
- Never request data from nodes
- Accept whatever arrives
- Deduplicate positions to reduce internal traffic
- Don't implement features that require frequent updates

### Constraint 3: Packet Loss (5-30% typical)

**Adaptation**:
- No ACKs or retries (would congest mesh)
- UI shows gaps in breadcrumb trails (expected)
- Dwell detection tolerates missing points
- Status thresholds account for missed packets

### Constraint 4: Variable Frequency

**Adaptation**:
- Don't assume update intervals
- Dogs may send frequently when moving, slowly when stationary
- Handle bursts and droughts gracefully
- "Last heard" is more important than "expected next"

### Constraint 5: Mesh Routing Changes

**Adaptation**:
- RSSI/SNR may fluctuate wildly (store but don't over-interpret)
- Latency may spike when routes change
- UI doesn't depend on consistent delivery timing

---

## Scalability Considerations

### Current Design Targets

- **Nodes**: 10-50 active nodes
- **GPS Updates**: 1-10 per node per minute (varies)
- **Data Retention**: 30 days of GPS breadcrumbs
- **Concurrent Users**: 5-10 dashboard viewers

### Bottlenecks

1. **SQLite Write Throughput**
   - Single writer limitation
   - **Mitigation**: WAL mode, batch commits, in-memory buffering

2. **SSE Fan-Out**
   - Broadcasting to many clients
   - **Mitigation**: Async Flask, limit to 20 concurrent connections

3. **In-Memory State Size**
   - 100 points × 50 nodes = 5000 points in RAM
   - **Mitigation**: Circular buffer, prune old data

### Scaling Beyond 50 Nodes

If you exceed 50 nodes, consider:

1. **Multiple Processing Instances**
   - Shard by node ID (mod hash)
   - Each instance handles subset of nodes

2. **PostgreSQL Instead of SQLite**
   - Multiple writers
   - Better concurrency

3. **Redis for In-Memory State**
   - Shared state across processes
   - Pub/sub for SSE distribution

4. **Load Balancer for Dashboard**
   - Distribute SSE connections
   - Nginx with upstream servers

---

## Future Expansion

### 1. Multiple Gateway Support

**Change Required**: Switch ingestion to Meshtastic MQTT

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Gateway1 │  │ Gateway2 │  │ Gateway3 │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     └──────────┬──┘             │
                │ MQTT           │
                ▼                │
         ┌─────────────┐         │
         │  MQTT Broker│◄────────┘
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │ Processing  │
         └─────────────┘
```

**Benefits**:
- Geographic coverage
- Redundancy
- More packet capture (reduces loss)

---

### 2. Geofencing

**Implementation**:
- Add `geofences` table to DB
- Processing service checks if position crosses boundary
- Emit `geofence_enter` / `geofence_exit` events
- Dashboard shows geofence polygons

---

### 3. ATAK Integration

**Implementation**:
- New service: `atak_bridge.py`
- Converts position updates to CoT XML
- Sends multicast UDP to ATAK devices
- **Separate from main system** (doesn't depend on ATAK)

---

### 4. Historical Replay

**Implementation**:
- Dashboard adds time slider control
- New REST API: `GET /api/replay?start={ts}&end={ts}&speed={x}`
- Queries DB for historical points
- Replays them at accelerated speed via SSE

---

### 5. Alert Rules Engine

**Implementation**:
- Add `alert_rules` table (conditions + actions)
- Processing service evaluates rules on each update
- Actions: log event, send notification, trigger webhook
- Example rules:
  - "Dog hasn't moved in 30 minutes → alert"
  - "Battery below 10% → alert"
  - "Node lost for 1 hour → alert"

---

## Security Considerations

### Threat Model

**Assumptions**:
- System runs on trusted local network
- Physical access to devices is controlled
- Users are authenticated (not by HeadSpace itself)

**Risks**:
1. Unauthorized dashboard access
2. MQTT message injection
3. Database tampering
4. LoRa jamming (out of scope for software)

### Mitigations

1. **MQTT Authentication** (optional but recommended)
   ```bash
   mosquitto_passwd -c /etc/mosquitto/passwd headspace
   ```

2. **Dashboard Access Control**
   - Basic HTTP auth
   - Or reverse proxy with SSO (nginx + oauth2_proxy)

3. **File Permissions**
   ```bash
   chmod 600 data/headspace.db
   chmod 600 services/*/config.yaml
   ```

4. **Network Isolation**
   - Don't expose MQTT or SSE ports externally
   - Only dashboard port behind reverse proxy

---

## Performance Benchmarks (Estimated)

### Throughput
- **Ingestion**: 1000 packets/sec (far exceeds LoRa capability)
- **Processing**: 500 events/sec (with DB writes)
- **SSE Broadcast**: 100 events/sec to 10 clients

### Latency
- **MQTT Pub-Sub**: <5ms (local)
- **DB Write**: 10-50ms (depends on disk)
- **SSE Delivery**: <5ms (local network)
- **End-to-End (Internal)**: <100ms

### Resource Usage
- **RAM**: ~100MB per service (total ~300MB)
- **Disk I/O**: <1MB/sec (depends on GPS frequency)
- **CPU**: <5% on modern hardware

---

## Monitoring & Observability

### Health Checks

1. **Service Status**
   ```bash
   systemctl status headspace-*
   ```

2. **MQTT Activity**
   ```bash
   mosquitto_sub -h localhost -t 'headspace/#' -v | head
   ```

3. **Database Size**
   ```bash
   ls -lh data/headspace.db
   ```

4. **Active Nodes**
   ```bash
   sqlite3 data/headspace.db "SELECT COUNT(*) FROM v_active_nodes;"
   ```

### Metrics to Track

- Messages per second (MQTT)
- Database write latency
- SSE connection count
- Node status distribution (LIVE/STALE/LOST)
- Dwell event rate
- GPS point insertion rate

### Future: Prometheus Integration

Export metrics on `/metrics` endpoint:
- `headspace_nodes_active{status="LIVE"}`
- `headspace_gps_points_total`
- `headspace_dwells_active`
- `headspace_sse_clients`

---

## Conclusion

HeadSpace is designed from the ground up for LoRa mesh constraints. Every architectural decision prioritizes mesh health and latency tolerance while still providing a responsive user experience when data arrives. The system is simple, robust, and ready for offline deployment in challenging environments.

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-04
