#!/usr/bin/env python3
"""
HeadSpace Processing Service
Consumes MQTT events, maintains state, detects dwells, stores data, broadcasts SSE

This is the core business logic service that:
1. Subscribes to MQTT events from ingestion
2. Maintains in-memory state (last known positions)
3. Stores GPS points and telemetry to SQLite
4. Detects dwell events
5. Broadcasts updates to dashboard via Server-Sent Events
6. Performs periodic cleanup
"""

import sys
import time
import json
import logging
import signal
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
from pathlib import Path
from queue import Queue

import yaml
import paho.mqtt.client as mqtt
from flask import Flask, Response, request
from flask_cors import CORS

# Import dwell detector
from dwell_detector import (
    DwellDetector, 
    create_dwell_detector_from_config,
    dwell_event_to_mqtt_event
)

# Colorful logging
try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Configuration loader"""
    
    def __init__(self, config_path: str = "services/processing/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"Config file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logging.error(f"Error parsing config file: {e}")
            sys.exit(1)
    
    def get(self, key: str, default=None):
        """Get config value with dot notation"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(config: Config):
    """Configure logging"""
    log_level = getattr(logging, config.get('logging.level', 'INFO'))
    log_format = config.get('logging.format', '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    log_file = config.get('logging.file')
    
    if COLORLOG_AVAILABLE and not log_file:
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
    else:
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                level=log_level,
                format=log_format,
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(level=log_level, format=log_format)
    
    logging.root.setLevel(log_level)


# ============================================================================
# Database Manager
# ============================================================================

class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('Database')
        
        self.db_path = config.get('database.path', 'data/headspace.db')
        self.wal_mode = config.get('database.wal_mode', True)
        self.cache_size = config.get('database.cache_size', -10000)
        self.timeout = config.get('database.timeout', 5000)
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        self._ensure_database()
    
    def _ensure_database(self):
        """Ensure database exists and is initialized"""
        db_file = Path(self.db_path)
        if not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not db_file.exists():
            self.logger.warning(f"Database not found at {self.db_path}")
            self.logger.info("Please run: sqlite3 data/headspace.db < data/schemas.sql")
            # Create empty database
            conn = sqlite3.connect(self.db_path)
            conn.close()
        
        # Configure database
        conn = self.get_connection()
        if self.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA cache_size={self.cache_size}")
        conn.execute(f"PRAGMA busy_timeout={self.timeout}")
        conn.commit()
        
        self.logger.info(f"Database initialized at {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                timeout=self.timeout / 1000.0,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def upsert_node(self, node_id: str, node_name: str, node_type: str, 
                   timestamp: float, node_info: Optional[Dict] = None):
        """Insert or update node record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if node exists
            cursor.execute("SELECT node_id FROM nodes WHERE node_id = ?", (node_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing node
                cursor.execute("""
                    UPDATE nodes 
                    SET node_name = ?, 
                        node_type = ?,
                        last_heard_at = ?,
                        is_active = 1,
                        updated_at = ?
                    WHERE node_id = ?
                """, (node_name, node_type, int(timestamp), int(timestamp), node_id))
                
                # Update node info if provided
                if node_info:
                    updates = []
                    values = []
                    if 'short_name' in node_info:
                        updates.append("short_name = ?")
                        values.append(node_info['short_name'])
                    if 'long_name' in node_info:
                        updates.append("long_name = ?")
                        values.append(node_info['long_name'])
                    if 'hw_model' in node_info:
                        updates.append("hw_model = ?")
                        values.append(node_info['hw_model'])
                    if 'role' in node_info:
                        updates.append("role = ?")
                        values.append(node_info['role'])
                    
                    if updates:
                        values.append(node_id)
                        cursor.execute(f"UPDATE nodes SET {', '.join(updates)} WHERE node_id = ?", values)
            else:
                # Insert new node
                cursor.execute("""
                    INSERT INTO nodes (
                        node_id, node_name, node_type,
                        first_seen_at, last_heard_at,
                        short_name, long_name, hw_model, role,
                        is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    node_id, node_name, node_type,
                    int(timestamp), int(timestamp),
                    node_info.get('short_name') if node_info else None,
                    node_info.get('long_name') if node_info else None,
                    node_info.get('hw_model') if node_info else None,
                    node_info.get('role') if node_info else None,
                    int(timestamp), int(timestamp)
                ))
                
                self.logger.info(f"New node added: {node_id} ({node_name})")
            
            conn.commit()
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in upsert_node: {e}")
            conn.rollback()
    
    def update_node_position(self, node_id: str, lat: float, lon: float, 
                            alt: Optional[float] = None, timestamp: Optional[float] = None):
        """Update last known position for a node"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE nodes 
                SET last_position_lat = ?,
                    last_position_lon = ?,
                    last_position_alt = ?,
                    last_heard_at = ?,
                    updated_at = ?
                WHERE node_id = ?
            """, (lat, lon, alt, int(timestamp or time.time()), int(time.time()), node_id))
            
            conn.commit()
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in update_node_position: {e}")
            conn.rollback()
    
    def update_node_telemetry(self, node_id: str, telemetry: Dict[str, Any]):
        """Update last known telemetry for a node"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            updates = []
            values = []
            
            if 'battery_level' in telemetry:
                updates.append("last_battery_level = ?")
                values.append(telemetry['battery_level'])
            if 'voltage' in telemetry:
                updates.append("last_voltage = ?")
                values.append(telemetry['voltage'])
            if 'rssi' in telemetry:
                updates.append("last_rssi = ?")
                values.append(telemetry['rssi'])
            if 'snr' in telemetry:
                updates.append("last_snr = ?")
                values.append(telemetry['snr'])
            
            if updates:
                updates.append("updated_at = ?")
                values.append(int(time.time()))
                values.append(node_id)
                
                cursor.execute(
                    f"UPDATE nodes SET {', '.join(updates)} WHERE node_id = ?",
                    values
                )
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error in update_node_telemetry: {e}")
            conn.rollback()
    
    def insert_gps_point(self, node_id: str, timestamp: float, 
                        lat: float, lon: float, alt: Optional[float] = None,
                        precision: Optional[float] = None,
                        telemetry: Optional[Dict[str, Any]] = None):
        """Insert GPS point into history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO gps_points (
                    node_id, timestamp, latitude, longitude, altitude, 
                    precision_meters, battery_level, rssi, snr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id, int(timestamp), lat, lon, alt, precision,
                telemetry.get('battery_level') if telemetry else None,
                telemetry.get('rssi') if telemetry else None,
                telemetry.get('snr') if telemetry else None
            ))
            
            conn.commit()
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in insert_gps_point: {e}")
            conn.rollback()
    
    def insert_telemetry(self, node_id: str, timestamp: float, telemetry: Dict[str, Any]):
        """Insert telemetry record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO telemetry (
                    node_id, timestamp, battery_level, voltage,
                    channel_utilization, air_util_tx, rssi, snr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id, int(timestamp),
                telemetry.get('battery_level'),
                telemetry.get('voltage'),
                telemetry.get('channel_utilization'),
                telemetry.get('air_util_tx'),
                telemetry.get('rssi'),
                telemetry.get('snr')
            ))
            
            conn.commit()
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in insert_telemetry: {e}")
            conn.rollback()
    
    def upsert_dwell(self, dwell_dict: Dict[str, Any]):
        """Insert or update dwell record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT dwell_id FROM dwells WHERE dwell_id = ?", (dwell_dict['dwell_id'],))
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute("""
                    UPDATE dwells
                    SET end_timestamp = ?,
                        duration_seconds = ?,
                        center_lat = ?,
                        center_lon = ?,
                        radius_meters = ?,
                        point_count = ?,
                        status = ?,
                        updated_at = ?
                    WHERE dwell_id = ?
                """, (
                    dwell_dict.get('end_timestamp'),
                    dwell_dict.get('duration_seconds'),
                    dwell_dict['center_lat'],
                    dwell_dict['center_lon'],
                    dwell_dict['radius_meters'],
                    dwell_dict['point_count'],
                    dwell_dict['status'],
                    int(time.time()),
                    dwell_dict['dwell_id']
                ))
            else:
                cursor.execute("""
                    INSERT INTO dwells (
                        dwell_id, node_id, start_timestamp, end_timestamp,
                        duration_seconds, center_lat, center_lon, radius_meters,
                        point_count, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dwell_dict['dwell_id'],
                    dwell_dict['node_id'],
                    int(dwell_dict['start_timestamp']),
                    int(dwell_dict['end_timestamp']) if dwell_dict.get('end_timestamp') else None,
                    dwell_dict.get('duration_seconds'),
                    dwell_dict['center_lat'],
                    dwell_dict['center_lon'],
                    dwell_dict['radius_meters'],
                    dwell_dict['point_count'],
                    dwell_dict['status']
                ))
            
            conn.commit()
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in upsert_dwell: {e}")
            conn.rollback()
    
    def get_active_nodes(self) -> List[Dict[str, Any]]:
        """Get all active nodes with their last known state"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM v_active_nodes")
            rows = cursor.fetchall()
            
            nodes = []
            for row in rows:
                nodes.append(dict(row))
            
            return nodes
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error in get_active_nodes: {e}")
            return []


# ============================================================================
# State Manager
# ============================================================================

class StateManager:
    """Maintains in-memory state for fast access"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('State')
        
        # In-memory node state
        self.nodes: Dict[str, Dict[str, Any]] = {}
        
        # Breadcrumb buffer size
        self.breadcrumb_buffer_size = config.get('state.breadcrumb_buffer_size', 100)
        
        # Status thresholds (seconds)
        self.threshold_live = config.get('status_thresholds.live_seconds', 300)
        self.threshold_stale = config.get('status_thresholds.stale_seconds', 900)
    
    def update_position(self, node_id: str, node_name: str, node_type: str,
                       lat: float, lon: float, alt: Optional[float],
                       timestamp: float, telemetry: Optional[Dict] = None):
        """Update node position in memory"""
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                'node_id': node_id,
                'node_name': node_name,
                'node_type': node_type,
                'last_position': None,
                'last_telemetry': {},
                'last_heard_at': 0,
                'breadcrumbs': []
            }
        
        node = self.nodes[node_id]
        node['node_name'] = node_name
        node['node_type'] = node_type
        node['last_position'] = {
            'latitude': lat,
            'longitude': lon,
            'altitude': alt,
            'timestamp': timestamp
        }
        node['last_heard_at'] = timestamp
        
        if telemetry:
            node['last_telemetry'].update(telemetry)
        
        # Add to breadcrumb buffer
        breadcrumb = {
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'ts': timestamp
        }
        node['breadcrumbs'].append(breadcrumb)
        
        # Trim breadcrumbs
        if len(node['breadcrumbs']) > self.breadcrumb_buffer_size:
            node['breadcrumbs'] = node['breadcrumbs'][-self.breadcrumb_buffer_size:]
    
    def update_telemetry(self, node_id: str, telemetry: Dict[str, Any]):
        """Update node telemetry in memory"""
        if node_id in self.nodes:
            self.nodes[node_id]['last_telemetry'].update(telemetry)
    
    def get_node_status(self, node_id: str) -> str:
        """Determine node status based on last heard time"""
        if node_id not in self.nodes:
            return 'UNKNOWN'
        
        age = time.time() - self.nodes[node_id]['last_heard_at']
        
        if age < self.threshold_live:
            return 'LIVE'
        elif age < self.threshold_stale:
            return 'STALE'
        else:
            return 'LOST'
    
    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Get all nodes with current status"""
        nodes = []
        for node_id, node in self.nodes.items():
            node_copy = node.copy()
            node_copy['status'] = self.get_node_status(node_id)
            node_copy['age_seconds'] = int(time.time() - node['last_heard_at'])
            nodes.append(node_copy)
        
        return nodes


# ============================================================================
# SSE Broadcaster
# ============================================================================

class SSEBroadcaster:
    """Server-Sent Events broadcaster for dashboard updates"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('SSE')
        
        # Queue for broadcasting events
        self.event_queue = Queue()
        
        # Connected clients
        self.clients: List[Queue] = []
        self.clients_lock = threading.Lock()
        
        # Heartbeat interval
        self.heartbeat_interval = config.get('sse.heartbeat_interval', 30)
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def add_client(self) -> Queue:
        """Add a new SSE client"""
        client_queue = Queue(maxsize=50)
        with self.clients_lock:
            self.clients.append(client_queue)
        self.logger.info(f"Client connected. Total clients: {len(self.clients)}")
        return client_queue
    
    def remove_client(self, client_queue: Queue):
        """Remove an SSE client"""
        with self.clients_lock:
            if client_queue in self.clients:
                self.clients.remove(client_queue)
        self.logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected clients"""
        message = {
            'event': event_type,
            'data': json.dumps(data)
        }
        
        with self.clients_lock:
            for client_queue in self.clients:
                try:
                    client_queue.put_nowait(message)
                except:
                    pass  # Queue full, skip
    
    def _heartbeat_loop(self):
        """Send periodic heartbeat to keep connections alive"""
        while True:
            time.sleep(self.heartbeat_interval)
            
            heartbeat_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'active_nodes': 0  # Will be updated by main service
            }
            
            self.broadcast('heartbeat', heartbeat_data)


# ============================================================================
# MQTT Consumer
# ============================================================================

class MQTTConsumer:
    """Consumes events from MQTT broker"""
    
    def __init__(self, config: Config, on_message_callback):
        self.config = config
        self.logger = logging.getLogger('MQTT')
        self.on_message_callback = on_message_callback
        
        # MQTT configuration
        self.broker = config.get('mqtt.broker', 'localhost')
        self.port = config.get('mqtt.port', 1883)
        self.client_id = config.get('mqtt.client_id', 'headspace-process')
        self.username = config.get('mqtt.username')
        self.password = config.get('mqtt.password')
        self.qos = config.get('mqtt.qos', 1)
        self.keepalive = config.get('mqtt.keepalive', 60)
        
        # Topics to subscribe to
        self.topics = config.get('mqtt.topics', [])
        
        # Create client
        self.client = mqtt.Client(client_id=self.client_id)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Set credentials if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            self.connected = True
            
            # Subscribe to topics
            for topic in self.topics:
                self.logger.info(f"Subscribing to {topic}")
                client.subscribe(topic, qos=self.qos)
        else:
            self.logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")
        self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback when message is received"""
        try:
            self.on_message_callback(msg.topic, msg.payload)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, self.keepalive)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 5
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                raise ConnectionError("Failed to connect to MQTT broker within timeout")
                
        except Exception as e:
            self.logger.error(f"Error connecting to MQTT broker: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Disconnected from MQTT broker")


# ============================================================================
# Main Processing Service
# ============================================================================

class ProcessingService:
    """Main processing service orchestrator"""
    
    def __init__(self, config_path: str = "services/processing/config.yaml"):
        self.config = Config(config_path)
        self.logger = logging.getLogger('Processing')
        
        # Initialize components
        self.db = DatabaseManager(self.config)
        self.state = StateManager(self.config)
        self.sse = SSEBroadcaster(self.config)
        
        # Initialize dwell detector
        dwell_config = self.config.get('dwell_detection', {})
        # Remove top-level 'enabled' key before passing to detector
        dwell_config_clean = {k: v for k, v in dwell_config.items() if k != 'enabled'}
        self.dwell_detector = create_dwell_detector_from_config(dwell_config_clean)
        
        # MQTT consumer
        self.mqtt = MQTTConsumer(self.config, self._handle_mqtt_message)
        
        # Flask app for SSE
        self.flask_app = None
        self.flask_thread = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def _handle_mqtt_message(self, topic: str, payload: bytes):
        """Handle incoming MQTT message"""
        try:
            # Parse JSON payload
            event = json.loads(payload.decode('utf-8'))
            event_type = event.get('event_type')
            
            if event_type == 'position_update':
                self._handle_position_update(event)
            elif event_type == 'telemetry_update':
                self._handle_telemetry_update(event)
            elif event_type == 'node_discovered':
                self._handle_node_discovery(event)
            else:
                self.logger.warning(f"Unknown event type: {event_type}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from {topic}: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message from {topic}: {e}", exc_info=True)
    
    def _handle_position_update(self, event: Dict[str, Any]):
        """Handle position update event"""
        node_id = event['node_id']
        node_name = event['node_name']
        node_type = event['node_type']
        position = event['position']
        telemetry = event.get('telemetry', {})
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).timestamp()
        
        lat = position['latitude']
        lon = position['longitude']
        alt = position.get('altitude')
        precision = position.get('precision')
        
        self.logger.debug(f"Position update: {node_name} at {lat:.6f}, {lon:.6f}")
        
        # Update database
        self.db.upsert_node(node_id, node_name, node_type, timestamp)
        self.db.update_node_position(node_id, lat, lon, alt, timestamp)
        self.db.insert_gps_point(node_id, timestamp, lat, lon, alt, precision, telemetry)
        
        if telemetry:
            self.db.update_node_telemetry(node_id, telemetry)
        
        # Update in-memory state
        self.state.update_position(node_id, node_name, node_type, lat, lon, alt, timestamp, telemetry)
        
        # Check for dwell
        dwell_result = self.dwell_detector.process_position(
            node_id, node_name, node_type, lat, lon, timestamp, alt
        )
        
        # Handle dwell events
        if dwell_result['dwell_started']:
            dwell = dwell_result['dwell_started']
            self.logger.info(f"Dwell STARTED for {node_name}")
            
            # Store to database
            from dwell_detector import dwell_event_to_dict
            self.db.upsert_dwell(dwell_event_to_dict(dwell))
            
            # Broadcast to dashboard
            dwell_event = dwell_event_to_mqtt_event(dwell, 'dwell_started')
            self.sse.broadcast('dwell', dwell_event)
        
        elif dwell_result['dwell_ended']:
            dwell = dwell_result['dwell_ended']
            self.logger.info(f"Dwell ENDED for {node_name}")
            
            # Update database
            from dwell_detector import dwell_event_to_dict
            self.db.upsert_dwell(dwell_event_to_dict(dwell))
            
            # Broadcast to dashboard
            dwell_event = dwell_event_to_mqtt_event(dwell, 'dwell_ended')
            self.sse.broadcast('dwell', dwell_event)
        
        # Broadcast position update to dashboard
        status = self.state.get_node_status(node_id)
        sse_event = {
            'node_id': node_id,
            'node_name': node_name,
            'node_type': node_type,
            'timestamp': event['timestamp'],
            'position': position,
            'telemetry': telemetry,
            'status': status
        }
        self.sse.broadcast('position', sse_event)
    
    def _handle_telemetry_update(self, event: Dict[str, Any]):
        """Handle telemetry update event"""
        node_id = event['node_id']
        node_name = event['node_name']
        telemetry = event['telemetry']
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).timestamp()
        
        self.logger.debug(f"Telemetry update: {node_name}")
        
        # Update database
        self.db.upsert_node(node_id, node_name, 'unknown', timestamp)
        self.db.update_node_telemetry(node_id, telemetry)
        self.db.insert_telemetry(node_id, timestamp, telemetry)
        
        # Update in-memory state
        self.state.update_telemetry(node_id, telemetry)
        
        # Broadcast to dashboard
        status = self.state.get_node_status(node_id)
        sse_event = {
            'node_id': node_id,
            'node_name': node_name,
            'telemetry': telemetry,
            'status': status
        }
        self.sse.broadcast('telemetry', sse_event)
    
    def _handle_node_discovery(self, event: Dict[str, Any]):
        """Handle node discovery event"""
        node_id = event['node_id']
        node_info = event['node_info']
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).timestamp()
        
        node_name = node_info.get('long_name', node_id)
        node_type = 'unknown'  # Will be updated on first position
        
        self.logger.info(f"Node discovered: {node_name} ({node_id})")
        
        # Update database
        self.db.upsert_node(node_id, node_name, node_type, timestamp, node_info)
        
        # Broadcast to dashboard
        sse_event = {
            'node_id': node_id,
            'node_name': node_name,
            'node_type': node_type,
            'node_info': node_info
        }
        self.sse.broadcast('discovery', sse_event)
    
    def _create_flask_app(self):
        """Create Flask app for SSE endpoint"""
        app = Flask(__name__)
        CORS(app, origins=self.config.get('sse.cors_origins', ['*']))
        
        @app.route('/events')
        def sse_stream():
            """SSE endpoint for dashboard updates"""
            def generate():
                client_queue = self.sse.add_client()
                try:
                    while True:
                        try:
                            message = client_queue.get(timeout=30)
                            yield f"event: {message['event']}\ndata: {message['data']}\n\n"
                        except:
                            # Timeout, send comment to keep alive
                            yield ": keepalive\n\n"
                except GeneratorExit:
                    pass
                finally:
                    self.sse.remove_client(client_queue)
            
            return Response(generate(), mimetype='text/event-stream')
        
        @app.route('/health')
        def health():
            """Health check endpoint"""
            return {'status': 'ok', 'service': 'headspace-processing'}
        
        return app
    
    def _run_flask(self):
        """Run Flask app in separate thread"""
        host = self.config.get('sse.host', '0.0.0.0')
        port = self.config.get('sse.port', 8081)
        
        self.logger.info(f"Starting SSE server on {host}:{port}")
        
        # Disable Flask logging to avoid clutter
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.ERROR)
        
        self.flask_app.run(host=host, port=port, threaded=True)
    
    def start(self):
        """Start the processing service"""
        self.logger.info("=" * 60)
        self.logger.info("HeadSpace Processing Service")
        self.logger.info("=" * 60)
        
        # Connect to MQTT
        self.mqtt.connect()
        
        # Create and start Flask app
        self.flask_app = self._create_flask_app()
        self.flask_thread = threading.Thread(target=self._run_flask, daemon=True)
        self.flask_thread.start()
        
        self.running = True
        self.logger.info("Processing service running. Press Ctrl+C to stop.")
        
        # Main loop
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    def stop(self):
        """Stop the processing service"""
        self.running = False
        
        if self.mqtt:
            self.mqtt.disconnect()
        
        self.logger.info("Processing service stopped")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    # Determine config path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "services/processing/config.yaml"
    
    # Load config and setup logging
    config = Config(config_path)
    setup_logging(config)
    
    # Create and start service
    service = ProcessingService(config_path)
    
    try:
        service.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
