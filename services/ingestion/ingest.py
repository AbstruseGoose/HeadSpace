#!/usr/bin/env python3
"""
HeadSpace Ingestion Service
Receives Meshtastic packets and publishes to MQTT

Connects to Meshtastic gateway device via Serial/USB and normalizes
incoming position, telemetry, and node discovery packets into internal
JSON schema, then publishes to local MQTT broker.

Supports simulation mode for testing without hardware.
"""

import sys
import time
import json
import logging
import signal
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

# Colorful logging
try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False

# Meshtastic imports
try:
    import meshtastic
    import meshtastic.serial_interface
    from meshtastic import portnums_pb2
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False
    print("WARNING: Meshtastic library not available. Only simulation mode will work.")


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Configuration loader"""
    
    def __init__(self, config_path: str = "services/ingestion/config.yaml"):
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
        """Get config value with dot notation (e.g., 'mqtt.broker')"""
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
    """Configure logging with optional color output"""
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
# MQTT Client
# ============================================================================

class MQTTPublisher:
    """MQTT client for publishing normalized events"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('MQTT')
        
        # MQTT configuration
        self.broker = config.get('mqtt.broker', 'localhost')
        self.port = config.get('mqtt.port', 1883)
        self.client_id = config.get('mqtt.client_id', 'headspace-ingest')
        self.username = config.get('mqtt.username')
        self.password = config.get('mqtt.password')
        self.qos = config.get('mqtt.qos', 1)
        self.keepalive = config.get('mqtt.keepalive', 60)
        
        # Topic structure
        self.topic_position = config.get('mqtt.topics.position', 'headspace/position')
        self.topic_telemetry = config.get('mqtt.topics.telemetry', 'headspace/telemetry')
        self.topic_discovery = config.get('mqtt.topics.discovery', 'headspace/discovery')
        
        # Create client
        self.client = mqtt.Client(client_id=self.client_id)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        # Set credentials if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        self.connected = False
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            self.connected = True
        else:
            self.logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")
        self.connected = False
    
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
    
    def publish_position(self, node_id: str, event: Dict[str, Any]):
        """Publish position update event"""
        topic = f"{self.topic_position}/{node_id}"
        payload = json.dumps(event)
        result = self.client.publish(topic, payload, qos=self.qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self.logger.debug(f"Published position update for {node_id}")
        else:
            self.logger.error(f"Failed to publish position update for {node_id}")
    
    def publish_telemetry(self, node_id: str, event: Dict[str, Any]):
        """Publish telemetry update event"""
        topic = f"{self.topic_telemetry}/{node_id}"
        payload = json.dumps(event)
        result = self.client.publish(topic, payload, qos=self.qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self.logger.debug(f"Published telemetry update for {node_id}")
        else:
            self.logger.error(f"Failed to publish telemetry update for {node_id}")
    
    def publish_discovery(self, node_id: str, event: Dict[str, Any]):
        """Publish node discovery event"""
        topic = f"{self.topic_discovery}/{node_id}"
        payload = json.dumps(event)
        result = self.client.publish(topic, payload, qos=self.qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self.logger.info(f"Published node discovery for {node_id}")
        else:
            self.logger.error(f"Failed to publish node discovery for {node_id}")


# ============================================================================
# Meshtastic Interface
# ============================================================================

class MeshtasticInterface:
    """Interface to Meshtastic device"""
    
    def __init__(self, config: Config, mqtt_publisher: MQTTPublisher):
        self.config = config
        self.mqtt = mqtt_publisher
        self.logger = logging.getLogger('Meshtastic')
        
        self.interface = None
        self.node_db = {}  # Cache of known nodes
        
        # Node type overrides from config
        self.node_types = config.get('node_types', {})
        self.node_names = config.get('node_names', {})
        
        # Deduplication
        self.last_positions = {}  # node_id -> (lat, lon, timestamp)
        self.dedupe_enabled = config.get('performance.deduplicate_enabled', True)
        self.dedupe_distance = config.get('performance.deduplicate_distance', 1.0)
    
    def connect(self):
        """Connect to Meshtastic device"""
        if not MESHTASTIC_AVAILABLE:
            raise ImportError("Meshtastic library not installed")
        
        connection_type = self.config.get('meshtastic.connection_type', 'serial')
        
        if connection_type == 'serial':
            serial_port = self.config.get('meshtastic.serial_port', 'auto')
            
            try:
                if serial_port == 'auto':
                    self.logger.info("Auto-detecting Meshtastic device...")
                    self.interface = meshtastic.serial_interface.SerialInterface()
                else:
                    self.logger.info(f"Connecting to Meshtastic device on {serial_port}")
                    self.interface = meshtastic.serial_interface.SerialInterface(serial_port)
                
                # Register packet callback
                self.interface.onReceive = self._on_receive
                
                self.logger.info("Connected to Meshtastic device")
                
            except Exception as e:
                self.logger.error(f"Failed to connect to Meshtastic device: {e}")
                raise
        
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")
    
    def disconnect(self):
        """Disconnect from Meshtastic device"""
        if self.interface:
            self.interface.close()
            self.logger.info("Disconnected from Meshtastic device")
    
    def _on_receive(self, packet, interface):
        """Callback when packet is received"""
        try:
            self._handle_packet(packet)
        except Exception as e:
            self.logger.error(f"Error handling packet: {e}", exc_info=True)
    
    def _handle_packet(self, packet: Dict[str, Any]):
        """Process received packet"""
        # Extract basic info
        from_id = packet.get('fromId')
        to_id = packet.get('toId')
        packet_type = packet.get('decoded', {}).get('portnum')
        
        if not from_id:
            return
        
        # Convert numeric ID to hex format
        node_id = self._format_node_id(from_id)
        
        # Update node database
        self._update_node_db(node_id, packet)
        
        # Handle different packet types
        if packet_type == 'POSITION_APP':
            self._handle_position(node_id, packet)
        elif packet_type == 'TELEMETRY_APP':
            self._handle_telemetry(node_id, packet)
        elif packet_type == 'NODEINFO_APP':
            self._handle_node_info(node_id, packet)
    
    def _format_node_id(self, node_id: Any) -> str:
        """Format node ID to hex string with ! prefix"""
        if isinstance(node_id, str):
            if node_id.startswith('!'):
                return node_id
            return f"!{node_id}"
        elif isinstance(node_id, int):
            return f"!{node_id:08x}"
        else:
            return str(node_id)
    
    def _update_node_db(self, node_id: str, packet: Dict[str, Any]):
        """Update internal node database"""
        if node_id not in self.node_db:
            self.node_db[node_id] = {}
        
        # Store basic info
        self.node_db[node_id]['last_heard'] = time.time()
    
    def _get_node_name(self, node_id: str) -> str:
        """Get node name from config or cache"""
        # Check config overrides first
        if node_id in self.node_names:
            return self.node_names[node_id]
        
        # Check node database
        if node_id in self.node_db:
            return self.node_db[node_id].get('long_name', node_id)
        
        return node_id
    
    def _get_node_type(self, node_id: str) -> str:
        """Get node type from config or infer"""
        # Check config overrides first
        if node_id in self.node_types:
            return self.node_types[node_id]
        
        # Try to infer from node info
        if node_id in self.node_db:
            role = self.node_db[node_id].get('role', '').upper()
            if role == 'ROUTER':
                return 'base_station'
            elif role == 'TRACKER':
                return 'dog'
        
        return 'unknown'
    
    def _handle_position(self, node_id: str, packet: Dict[str, Any]):
        """Handle position packet"""
        decoded = packet.get('decoded', {})
        position = decoded.get('position', {})
        
        lat = position.get('latitude')
        lon = position.get('longitude')
        alt = position.get('altitude')
        precision = position.get('precisionBits')
        
        if lat is None or lon is None:
            return
        
        # Deduplication check
        if self.dedupe_enabled:
            last_pos = self.last_positions.get(node_id)
            if last_pos:
                last_lat, last_lon, last_time = last_pos
                # Simple distance check (rough approximation)
                dist = ((lat - last_lat)**2 + (lon - last_lon)**2)**0.5 * 111000  # meters
                if dist < self.dedupe_distance and (time.time() - last_time) < 5:
                    self.logger.debug(f"Skipping duplicate position for {node_id}")
                    return
        
        # Store last position
        self.last_positions[node_id] = (lat, lon, time.time())
        
        # Extract telemetry if present
        telemetry = {}
        if 'rxRssi' in packet:
            telemetry['rssi'] = packet['rxRssi']
        if 'rxSnr' in packet:
            telemetry['snr'] = packet['rxSnr']
        
        # Build event
        event = {
            'event_type': 'position_update',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'node_id': node_id,
            'node_name': self._get_node_name(node_id),
            'node_type': self._get_node_type(node_id),
            'position': {
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'precision': precision,
                'source': 'gps'
            },
            'telemetry': telemetry if telemetry else None,
            'raw_packet': {
                'from': packet.get('from'),
                'to': packet.get('to'),
                'hop_limit': packet.get('hopLimit'),
                'hop_start': packet.get('hopStart'),
                'want_ack': packet.get('wantAck', False)
            }
        }
        
        self.logger.info(f"Position update from {node_id} ({event['node_name']}): {lat:.6f}, {lon:.6f}")
        
        # Publish to MQTT
        self.mqtt.publish_position(node_id, event)
    
    def _handle_telemetry(self, node_id: str, packet: Dict[str, Any]):
        """Handle telemetry packet"""
        decoded = packet.get('decoded', {})
        telemetry_data = decoded.get('telemetry', {})
        
        device_metrics = telemetry_data.get('deviceMetrics', {})
        
        telemetry = {}
        if 'batteryLevel' in device_metrics:
            telemetry['battery_level'] = device_metrics['batteryLevel']
        if 'voltage' in device_metrics:
            telemetry['voltage'] = device_metrics['voltage']
        if 'channelUtilization' in device_metrics:
            telemetry['channel_utilization'] = device_metrics['channelUtilization']
        if 'airUtilTx' in device_metrics:
            telemetry['air_util_tx'] = device_metrics['airUtilTx']
        
        if not telemetry:
            return
        
        event = {
            'event_type': 'telemetry_update',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'node_id': node_id,
            'node_name': self._get_node_name(node_id),
            'telemetry': telemetry
        }
        
        self.logger.info(f"Telemetry from {node_id}: battery={telemetry.get('battery_level')}%")
        
        # Publish to MQTT
        self.mqtt.publish_telemetry(node_id, event)
    
    def _handle_node_info(self, node_id: str, packet: Dict[str, Any]):
        """Handle node info packet"""
        decoded = packet.get('decoded', {})
        user = decoded.get('user', {})
        
        node_info = {}
        if 'shortName' in user:
            node_info['short_name'] = user['shortName']
            self.node_db[node_id]['short_name'] = user['shortName']
        if 'longName' in user:
            node_info['long_name'] = user['longName']
            self.node_db[node_id]['long_name'] = user['longName']
        if 'hwModel' in user:
            node_info['hw_model'] = user['hwModel']
            self.node_db[node_id]['hw_model'] = user['hwModel']
        if 'role' in user:
            node_info['role'] = user['role']
            self.node_db[node_id]['role'] = user['role']
        
        if not node_info:
            return
        
        event = {
            'event_type': 'node_discovered',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'node_id': node_id,
            'node_info': node_info
        }
        
        self.logger.info(f"Node discovered: {node_id} ({node_info.get('long_name', 'Unknown')})")
        
        # Publish to MQTT
        self.mqtt.publish_discovery(node_id, event)


# ============================================================================
# Simulation Mode
# ============================================================================

class SimulationMode:
    """Simulate Meshtastic packets for testing"""
    
    def __init__(self, config: Config, mqtt_publisher: MQTTPublisher):
        self.config = config
        self.mqtt = mqtt_publisher
        self.logger = logging.getLogger('Simulation')
        
        self.interval = config.get('meshtastic.simulation_interval', 10)
        self.nodes = config.get('meshtastic.simulation_nodes', [])
        
        self.running = False
        self.tick = 0
        
        # Node states
        self.node_states = {}
        self._initialize_nodes()
    
    def _initialize_nodes(self):
        """Initialize simulated node states"""
        import random
        
        # Default simulation nodes if none configured
        if not self.nodes:
            self.nodes = [
                {'node_id': '!sim00001', 'name': 'Dog-Rex', 'type': 'dog', 'movement': 'circle'},
                {'node_id': '!sim00002', 'name': 'Dog-Luna', 'type': 'dog', 'movement': 'figure8'},
                {'node_id': '!sim00003', 'name': 'Base-Station-1', 'type': 'base_station', 'movement': 'stationary'},
                {'node_id': '!sim00004', 'name': 'Team-Lead-1', 'type': 'team_lead', 'movement': 'random_walk'},
            ]
        
        # Initialize each node
        for node in self.nodes:
            node_id = node['node_id']
            self.node_states[node_id] = {
                'name': node['name'],
                'type': node['type'],
                'movement': node['movement'],
                'lat': 47.6062 + random.uniform(-0.01, 0.01),
                'lon': -122.3321 + random.uniform(-0.01, 0.01),
                'battery': random.randint(70, 100),
                'angle': 0,
            }
        
        self.logger.info(f"Initialized {len(self.node_states)} simulated nodes")
    
    def start(self):
        """Start simulation loop"""
        self.running = True
        self.logger.info("Starting simulation mode")
        
        # Publish initial discovery events
        for node_id, state in self.node_states.items():
            event = {
                'event_type': 'node_discovered',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'node_id': node_id,
                'node_info': {
                    'short_name': state['name'][:4].upper(),
                    'long_name': state['name'],
                    'hw_model': 'SIMULATED',
                    'role': 'TRACKER' if state['type'] == 'dog' else 'CLIENT',
                }
            }
            self.mqtt.publish_discovery(node_id, event)
        
        # Run simulation loop
        try:
            while self.running:
                self._simulate_tick()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.logger.info("Simulation stopped by user")
    
    def stop(self):
        """Stop simulation"""
        self.running = False
    
    def _simulate_tick(self):
        """Simulate one tick (update all nodes)"""
        import random
        import math
        
        self.tick += 1
        
        for node_id, state in self.node_states.items():
            # Update position based on movement pattern
            if state['movement'] == 'stationary':
                # Small random jitter
                state['lat'] += random.uniform(-0.00001, 0.00001)
                state['lon'] += random.uniform(-0.00001, 0.00001)
            
            elif state['movement'] == 'circle':
                # Move in a circle
                radius = 0.002  # ~200m
                state['angle'] += 0.1
                state['lat'] = 47.6062 + radius * math.cos(state['angle'])
                state['lon'] = -122.3321 + radius * math.sin(state['angle'])
            
            elif state['movement'] == 'figure8':
                # Move in a figure-8
                radius = 0.003
                state['angle'] += 0.15
                state['lat'] = 47.6062 + radius * math.sin(state['angle'])
                state['lon'] = -122.3321 + radius * math.sin(state['angle'] * 2)
            
            elif state['movement'] == 'random_walk':
                # Random walk
                state['lat'] += random.uniform(-0.0002, 0.0002)
                state['lon'] += random.uniform(-0.0002, 0.0002)
            
            # Slowly drain battery
            if state['battery'] > 0:
                state['battery'] -= random.uniform(0, 0.5)
            
            # Build position event
            event = {
                'event_type': 'position_update',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'node_id': node_id,
                'node_name': state['name'],
                'node_type': state['type'],
                'position': {
                    'latitude': state['lat'],
                    'longitude': state['lon'],
                    'altitude': 12.0 + random.uniform(-2, 2),
                    'precision': random.randint(3, 8),
                    'source': 'gps'
                },
                'telemetry': {
                    'battery_level': int(state['battery']),
                    'voltage': 3.3 + (state['battery'] / 100) * 0.9,
                    'rssi': random.randint(-100, -70),
                    'snr': random.uniform(5, 12),
                },
                'raw_packet': {
                    'from': int(node_id.replace('!', ''), 16) if node_id.startswith('!') else 0,
                    'to': 4294967295,  # Broadcast
                    'hop_limit': 3,
                    'hop_start': 3,
                    'want_ack': False
                }
            }
            
            self.logger.info(f"[SIM] Position from {state['name']}: {state['lat']:.6f}, {state['lon']:.6f}")
            
            # Publish position
            self.mqtt.publish_position(node_id, event)
            
            # Occasionally publish telemetry
            if self.tick % 3 == 0:
                telemetry_event = {
                    'event_type': 'telemetry_update',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'node_id': node_id,
                    'node_name': state['name'],
                    'telemetry': {
                        'battery_level': int(state['battery']),
                        'voltage': 3.3 + (state['battery'] / 100) * 0.9,
                    }
                }
                self.mqtt.publish_telemetry(node_id, telemetry_event)


# ============================================================================
# Main Service
# ============================================================================

class IngestionService:
    """Main ingestion service"""
    
    def __init__(self, config_path: str = "services/ingestion/config.yaml"):
        self.config = Config(config_path)
        self.logger = logging.getLogger('Ingestion')
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.mqtt = None
        self.interface = None
        self.simulation = None
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def start(self):
        """Start the ingestion service"""
        self.logger.info("=" * 60)
        self.logger.info("HeadSpace Ingestion Service")
        self.logger.info("=" * 60)
        
        # Connect to MQTT
        self.mqtt = MQTTPublisher(self.config)
        self.mqtt.connect()
        
        # Check if simulation mode
        simulation_mode = self.config.get('meshtastic.simulation_mode', False)
        
        if simulation_mode:
            self.logger.info("Running in SIMULATION mode (no hardware required)")
            self.simulation = SimulationMode(self.config, self.mqtt)
            self.running = True
            self.simulation.start()
        else:
            # Connect to real Meshtastic device
            self.logger.info("Connecting to Meshtastic device...")
            self.interface = MeshtasticInterface(self.config, self.mqtt)
            self.interface.connect()
            
            self.running = True
            self.logger.info("Ingestion service running. Press Ctrl+C to stop.")
            
            # Keep running
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    
    def stop(self):
        """Stop the ingestion service"""
        self.running = False
        
        if self.simulation:
            self.simulation.stop()
        
        if self.interface:
            self.interface.disconnect()
        
        if self.mqtt:
            self.mqtt.disconnect()
        
        self.logger.info("Ingestion service stopped")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    # Determine config path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "services/ingestion/config.yaml"
    
    # Load config and setup logging
    config = Config(config_path)
    setup_logging(config)
    
    # Create and start service
    service = IngestionService(config_path)
    
    try:
        service.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
