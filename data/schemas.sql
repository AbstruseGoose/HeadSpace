-- HeadSpace Database Schema
-- SQLite database for storing Meshtastic tracking data
-- Version: 1.0
-- Last Updated: 2026-01-04

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Table: nodes
-- Stores node metadata and last-known state
-- ============================================================================
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    node_name TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK(node_type IN ('dog', 'team_lead', 'base_station', 'truck', 'repeater', 'unknown')),
    
    -- Node information from Meshtastic
    short_name TEXT,
    long_name TEXT,
    hw_model TEXT,
    role TEXT,
    firmware_version TEXT,
    
    -- Timing
    first_seen_at INTEGER NOT NULL,
    last_heard_at INTEGER NOT NULL,
    
    -- Last known position
    last_position_lat REAL,
    last_position_lon REAL,
    last_position_alt REAL,
    
    -- Last known telemetry
    last_battery_level INTEGER,
    last_voltage REAL,
    last_rssi INTEGER,
    last_snr REAL,
    
    -- Status
    is_active BOOLEAN DEFAULT 1,
    
    -- Metadata
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_nodes_last_heard ON nodes(last_heard_at DESC);
CREATE INDEX idx_nodes_active ON nodes(is_active);
CREATE INDEX idx_nodes_type ON nodes(node_type);

-- ============================================================================
-- Table: gps_points
-- Historical GPS breadcrumb trail for all nodes
-- ============================================================================
CREATE TABLE IF NOT EXISTS gps_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    
    -- Position
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL,
    precision_meters REAL,
    
    -- Telemetry snapshot at this point
    battery_level INTEGER,
    rssi INTEGER,
    snr REAL,
    
    -- Metadata
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

CREATE INDEX idx_gps_node_time ON gps_points(node_id, timestamp DESC);
CREATE INDEX idx_gps_timestamp ON gps_points(timestamp DESC);
CREATE INDEX idx_gps_location ON gps_points(latitude, longitude);

-- ============================================================================
-- Table: dwells
-- Detected dwell events (stationary periods)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dwells (
    dwell_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    
    -- Timing
    start_timestamp INTEGER NOT NULL,
    end_timestamp INTEGER,
    duration_seconds INTEGER,
    
    -- Location (centroid of all points in the dwell)
    center_lat REAL NOT NULL,
    center_lon REAL NOT NULL,
    radius_meters REAL NOT NULL,
    
    -- Statistics
    point_count INTEGER NOT NULL DEFAULT 0,
    
    -- Status: 'ongoing' or 'completed'
    status TEXT NOT NULL CHECK(status IN ('ongoing', 'completed')) DEFAULT 'ongoing',
    
    -- Metadata
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

CREATE INDEX idx_dwells_node_time ON dwells(node_id, start_timestamp DESC);
CREATE INDEX idx_dwells_status ON dwells(status);
CREATE INDEX idx_dwells_node_status ON dwells(node_id, status);

-- ============================================================================
-- Table: telemetry
-- Periodic telemetry snapshots (for trending and analysis)
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    
    -- Power
    battery_level INTEGER,
    voltage REAL,
    
    -- Radio
    channel_utilization REAL,
    air_util_tx REAL,
    rssi INTEGER,
    snr REAL,
    
    -- Metadata
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

CREATE INDEX idx_telemetry_node_time ON telemetry(node_id, timestamp DESC);
CREATE INDEX idx_telemetry_timestamp ON telemetry(timestamp DESC);

-- ============================================================================
-- Table: system_events
-- System-level events for monitoring and debugging
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('debug', 'info', 'warning', 'error')),
    message TEXT NOT NULL,
    details TEXT,  -- JSON string with additional context
    
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_system_events_timestamp ON system_events(timestamp DESC);
CREATE INDEX idx_system_events_type ON system_events(event_type);
CREATE INDEX idx_system_events_severity ON system_events(severity);

-- ============================================================================
-- Views for common queries
-- ============================================================================

-- Active nodes with their latest data
CREATE VIEW IF NOT EXISTS v_active_nodes AS
SELECT 
    n.node_id,
    n.node_name,
    n.node_type,
    n.last_heard_at,
    n.last_position_lat,
    n.last_position_lon,
    n.last_battery_level,
    n.last_rssi,
    n.last_snr,
    -- Calculate age in seconds
    (strftime('%s', 'now') - n.last_heard_at) AS age_seconds,
    -- Determine status
    CASE 
        WHEN (strftime('%s', 'now') - n.last_heard_at) < 300 THEN 'LIVE'
        WHEN (strftime('%s', 'now') - n.last_heard_at) < 900 THEN 'STALE'
        ELSE 'LOST'
    END AS status
FROM nodes n
WHERE n.is_active = 1
ORDER BY n.last_heard_at DESC;

-- Ongoing dwells
CREATE VIEW IF NOT EXISTS v_ongoing_dwells AS
SELECT 
    d.dwell_id,
    d.node_id,
    n.node_name,
    n.node_type,
    d.start_timestamp,
    d.center_lat,
    d.center_lon,
    d.radius_meters,
    d.point_count,
    (strftime('%s', 'now') - d.start_timestamp) AS current_duration_seconds
FROM dwells d
JOIN nodes n ON d.node_id = n.node_id
WHERE d.status = 'ongoing'
ORDER BY d.start_timestamp DESC;

-- ============================================================================
-- Triggers for automatic timestamp updates
-- ============================================================================

-- Update nodes.updated_at on any change
CREATE TRIGGER IF NOT EXISTS trg_nodes_updated_at
AFTER UPDATE ON nodes
FOR EACH ROW
BEGIN
    UPDATE nodes SET updated_at = strftime('%s', 'now')
    WHERE node_id = NEW.node_id;
END;

-- Update dwells.updated_at on any change
CREATE TRIGGER IF NOT EXISTS trg_dwells_updated_at
AFTER UPDATE ON dwells
FOR EACH ROW
BEGIN
    UPDATE dwells SET updated_at = strftime('%s', 'now')
    WHERE dwell_id = NEW.dwell_id;
END;

-- ============================================================================
-- Initial system event
-- ============================================================================
INSERT INTO system_events (event_type, timestamp, severity, message)
VALUES ('schema_initialized', strftime('%s', 'now'), 'info', 'Database schema created successfully');

-- ============================================================================
-- Optimization: Analyze tables for query planning
-- ============================================================================
ANALYZE;
