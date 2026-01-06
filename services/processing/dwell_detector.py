#!/usr/bin/env python3
"""
Dwell Detection Module
Detects when nodes remain stationary within a radius for a period of time

Uses geospatial calculations to determine if a node is dwelling (staying
in approximately the same location) and tracks dwell duration.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class GPSPoint:
    """Single GPS point"""
    latitude: float
    longitude: float
    timestamp: float  # Unix epoch seconds
    altitude: Optional[float] = None


@dataclass
class DwellEvent:
    """A detected dwell event"""
    dwell_id: str
    node_id: str
    node_name: str
    start_timestamp: float
    end_timestamp: Optional[float] = None
    points: List[GPSPoint] = field(default_factory=list)
    center_lat: float = 0.0
    center_lon: float = 0.0
    radius_meters: float = 0.0
    status: str = 'ongoing'  # 'ongoing' or 'completed'
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds"""
        if self.end_timestamp:
            return self.end_timestamp - self.start_timestamp
        else:
            # Ongoing dwell, use current time
            import time
            return time.time() - self.start_timestamp
    
    @property
    def point_count(self) -> int:
        """Number of GPS points in this dwell"""
        return len(self.points)
    
    def update_center(self):
        """Recalculate center point and radius"""
        if not self.points:
            return
        
        # Calculate centroid
        total_lat = sum(p.latitude for p in self.points)
        total_lon = sum(p.longitude for p in self.points)
        self.center_lat = total_lat / len(self.points)
        self.center_lon = total_lon / len(self.points)
        
        # Calculate maximum distance from center
        max_dist = 0.0
        for point in self.points:
            dist = haversine_distance(
                self.center_lat, self.center_lon,
                point.latitude, point.longitude
            )
            if dist > max_dist:
                max_dist = dist
        
        self.radius_meters = max_dist


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula
    Returns distance in meters
    """
    # Earth radius in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance


class DwellDetectorConfig:
    """Configuration for dwell detection per node type"""
    
    def __init__(self, 
                 radius_meters: float = 20.0,
                 min_duration_seconds: float = 120.0,
                 max_duration_seconds: float = 3600.0,
                 enabled: bool = True):
        self.radius_meters = radius_meters
        self.min_duration_seconds = min_duration_seconds
        self.max_duration_seconds = max_duration_seconds
        self.enabled = enabled


class DwellDetector:
    """
    Detects dwell events for tracked nodes
    
    A dwell occurs when a node stays within a defined radius for a minimum duration.
    The detector tracks ongoing dwells and emits events when dwells start and end.
    """
    
    def __init__(self, config_by_type: Dict[str, DwellDetectorConfig]):
        """
        Initialize dwell detector
        
        Args:
            config_by_type: Dict mapping node_type to DwellDetectorConfig
        """
        self.logger = logging.getLogger('DwellDetector')
        self.config_by_type = config_by_type
        
        # Track active dwells: node_id -> DwellEvent
        self.active_dwells: Dict[str, DwellEvent] = {}
        
        # Track recent points for each node (for dwell detection)
        # node_id -> List[GPSPoint]
        self.recent_points: Dict[str, List[GPSPoint]] = {}
        
        # Maximum points to keep in buffer per node
        self.max_recent_points = 50
    
    def get_config(self, node_type: str) -> Optional[DwellDetectorConfig]:
        """Get configuration for a node type"""
        return self.config_by_type.get(node_type, self.config_by_type.get('default'))
    
    def process_position(self, 
                        node_id: str, 
                        node_name: str,
                        node_type: str,
                        latitude: float, 
                        longitude: float, 
                        timestamp: float,
                        altitude: Optional[float] = None) -> Dict[str, any]:
        """
        Process a new position update and detect dwells
        
        Args:
            node_id: Node identifier
            node_name: Human-readable node name
            node_type: Node type (dog, team_lead, etc.)
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timestamp: Unix timestamp in seconds
            altitude: Optional altitude in meters
        
        Returns:
            Dict with keys:
                - dwell_started: Optional[DwellEvent] if new dwell detected
                - dwell_updated: Optional[DwellEvent] if existing dwell updated
                - dwell_ended: Optional[DwellEvent] if dwell ended
        """
        result = {
            'dwell_started': None,
            'dwell_updated': None,
            'dwell_ended': None
        }
        
        # Get configuration for this node type
        config = self.get_config(node_type)
        if not config or not config.enabled:
            return result
        
        # Create GPS point
        point = GPSPoint(latitude, longitude, timestamp, altitude)
        
        # Initialize recent points list for this node if needed
        if node_id not in self.recent_points:
            self.recent_points[node_id] = []
        
        # Add point to recent history
        self.recent_points[node_id].append(point)
        
        # Trim old points (keep last N)
        if len(self.recent_points[node_id]) > self.max_recent_points:
            self.recent_points[node_id] = self.recent_points[node_id][-self.max_recent_points:]
        
        # Check if node is currently dwelling
        if node_id in self.active_dwells:
            result = self._update_existing_dwell(node_id, node_name, node_type, point, config)
        else:
            result = self._check_new_dwell(node_id, node_name, node_type, point, config)
        
        return result
    
    def _check_new_dwell(self, 
                        node_id: str, 
                        node_name: str,
                        node_type: str,
                        new_point: GPSPoint, 
                        config: DwellDetectorConfig) -> Dict[str, any]:
        """Check if a new dwell is starting"""
        result = {
            'dwell_started': None,
            'dwell_updated': None,
            'dwell_ended': None
        }
        
        recent = self.recent_points[node_id]
        
        # Need at least 3 points to detect a dwell
        if len(recent) < 3:
            return result
        
        # Check if all recent points are within radius
        # Use the oldest point as reference
        reference_point = recent[0]
        
        all_within_radius = True
        for point in recent:
            dist = haversine_distance(
                reference_point.latitude, reference_point.longitude,
                point.latitude, point.longitude
            )
            if dist > config.radius_meters:
                all_within_radius = False
                break
        
        if not all_within_radius:
            return result
        
        # Check duration
        duration = new_point.timestamp - reference_point.timestamp
        
        if duration >= config.min_duration_seconds:
            # New dwell detected!
            dwell_id = f"dwell_{node_id}_{int(reference_point.timestamp)}"
            
            dwell = DwellEvent(
                dwell_id=dwell_id,
                node_id=node_id,
                node_name=node_name,
                start_timestamp=reference_point.timestamp,
                points=recent.copy(),
                status='ongoing'
            )
            dwell.update_center()
            
            self.active_dwells[node_id] = dwell
            result['dwell_started'] = dwell
            
            self.logger.info(
                f"Dwell STARTED for {node_name} ({node_id}): "
                f"{dwell.center_lat:.6f}, {dwell.center_lon:.6f}, "
                f"radius={dwell.radius_meters:.1f}m, duration={duration:.0f}s"
            )
        
        return result
    
    def _update_existing_dwell(self, 
                               node_id: str, 
                               node_name: str,
                               node_type: str,
                               new_point: GPSPoint, 
                               config: DwellDetectorConfig) -> Dict[str, any]:
        """Update an existing dwell or end it if node moved"""
        result = {
            'dwell_started': None,
            'dwell_updated': None,
            'dwell_ended': None
        }
        
        dwell = self.active_dwells[node_id]
        
        # Calculate distance from dwell center
        dist = haversine_distance(
            dwell.center_lat, dwell.center_lon,
            new_point.latitude, new_point.longitude
        )
        
        # Check if node moved outside the radius
        if dist > config.radius_meters:
            # Dwell ended - node moved
            dwell.end_timestamp = new_point.timestamp
            dwell.status = 'completed'
            dwell.update_center()
            
            result['dwell_ended'] = dwell
            
            self.logger.info(
                f"Dwell ENDED for {node_name} ({node_id}): "
                f"duration={dwell.duration_seconds:.0f}s, "
                f"points={dwell.point_count}, "
                f"moved {dist:.1f}m from center"
            )
            
            # Remove from active dwells
            del self.active_dwells[node_id]
            
            # Clear recent points to start fresh
            self.recent_points[node_id] = []
        
        else:
            # Still dwelling - update
            dwell.points.append(new_point)
            dwell.update_center()
            
            # Check if dwell exceeded maximum duration
            if dwell.duration_seconds > config.max_duration_seconds:
                # Split into a new dwell (prevents infinitely growing dwells)
                self.logger.info(
                    f"Dwell for {node_name} exceeded max duration, splitting"
                )
                
                # End current dwell
                dwell.end_timestamp = new_point.timestamp
                dwell.status = 'completed'
                result['dwell_ended'] = dwell
                
                # Start new dwell
                new_dwell_id = f"dwell_{node_id}_{int(new_point.timestamp)}"
                new_dwell = DwellEvent(
                    dwell_id=new_dwell_id,
                    node_id=node_id,
                    node_name=node_name,
                    start_timestamp=new_point.timestamp,
                    points=[new_point],
                    status='ongoing'
                )
                new_dwell.update_center()
                
                self.active_dwells[node_id] = new_dwell
                result['dwell_started'] = new_dwell
                
                # Keep only recent points
                self.recent_points[node_id] = [new_point]
            
            else:
                # Just update
                result['dwell_updated'] = dwell
        
        return result
    
    def get_active_dwells(self) -> List[DwellEvent]:
        """Get all currently active dwells"""
        return list(self.active_dwells.values())
    
    def get_active_dwell(self, node_id: str) -> Optional[DwellEvent]:
        """Get active dwell for a specific node"""
        return self.active_dwells.get(node_id)
    
    def force_end_dwell(self, node_id: str) -> Optional[DwellEvent]:
        """Force end a dwell (e.g., when node goes offline)"""
        if node_id not in self.active_dwells:
            return None
        
        dwell = self.active_dwells[node_id]
        dwell.end_timestamp = dwell.points[-1].timestamp if dwell.points else dwell.start_timestamp
        dwell.status = 'completed'
        dwell.update_center()
        
        del self.active_dwells[node_id]
        
        self.logger.info(f"Dwell force-ended for {node_id}")
        
        return dwell
    
    def clear_node_history(self, node_id: str):
        """Clear tracking history for a node"""
        if node_id in self.active_dwells:
            del self.active_dwells[node_id]
        if node_id in self.recent_points:
            del self.recent_points[node_id]


# ============================================================================
# Helper Functions
# ============================================================================

def create_dwell_detector_from_config(config_dict: Dict[str, any]) -> DwellDetector:
    """
    Create a DwellDetector from a configuration dictionary
    
    Args:
        config_dict: Configuration dict with node type settings
        
    Returns:
        Configured DwellDetector instance
    """
    configs = {}
    
    for node_type, settings in config_dict.items():
        configs[node_type] = DwellDetectorConfig(
            radius_meters=settings.get('radius_meters', 20.0),
            min_duration_seconds=settings.get('min_duration_seconds', 120.0),
            max_duration_seconds=settings.get('max_duration_seconds', 3600.0),
            enabled=settings.get('enabled', True)
        )
    
    return DwellDetector(configs)


def dwell_event_to_dict(dwell: DwellEvent) -> Dict[str, any]:
    """Convert DwellEvent to dictionary for serialization"""
    return {
        'dwell_id': dwell.dwell_id,
        'node_id': dwell.node_id,
        'node_name': dwell.node_name,
        'start_timestamp': dwell.start_timestamp,
        'end_timestamp': dwell.end_timestamp,
        'duration_seconds': dwell.duration_seconds,
        'center_lat': dwell.center_lat,
        'center_lon': dwell.center_lon,
        'radius_meters': dwell.radius_meters,
        'point_count': dwell.point_count,
        'status': dwell.status
    }


def dwell_event_to_mqtt_event(dwell: DwellEvent, event_type: str) -> Dict[str, any]:
    """
    Convert DwellEvent to MQTT event format
    
    Args:
        dwell: The dwell event
        event_type: 'dwell_started', 'dwell_updated', or 'dwell_ended'
    
    Returns:
        Dict in MQTT event format
    """
    return {
        'event_type': event_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'node_id': dwell.node_id,
        'node_name': dwell.node_name,
        'dwell_id': dwell.dwell_id,
        'location': {
            'center_lat': dwell.center_lat,
            'center_lon': dwell.center_lon,
            'radius_meters': round(dwell.radius_meters, 2)
        },
        'duration_seconds': int(dwell.duration_seconds),
        'point_count': dwell.point_count,
        'status': dwell.status
    }
