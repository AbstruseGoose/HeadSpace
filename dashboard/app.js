// HeadSpace Dashboard Application
// Real-time tracking dashboard with Leaflet map and SSE updates

class HeadSpaceDashboard {
    constructor() {
        // Configuration
        this.config = {
            sseUrl: `http://${window.location.hostname}:8081/events`,
            mapCenter: [47.6062, -122.3321],
            mapZoom: 13,
            tileLayer: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            tileAttribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        };
        
        // State
        this.nodes = new Map();
        this.markers = new Map();
        this.trails = new Map();
        this.dwellMarkers = new Map();
        this.selectedNodeId = null;
        this.showTrails = true;
        this.showDwells = true;
        this.gatewayNode = null;
        this.userLocation = null;
        this.userMarker = null;
        
        // SSE
        this.eventSource = null;
        this.reconnectInterval = 3000;
        this.reconnectTimer = null;
        
        // Initialize
        this.initializeMap();
        this.setupEventListeners();
        this.requestGeolocation();
        this.connectSSE();
    }
    
    // ========================================================================
    // Map Initialization
    // ========================================================================
    
    initializeMap() {
        // Create map
        this.map = L.map('map').setView(this.config.mapCenter, this.config.mapZoom);
        
        // Add tile layer
        L.tileLayer(this.config.tileLayer, {
            attribution: this.config.tileAttribution,
            maxZoom: 18
        }).addTo(this.map);
        
        console.log('Map initialized');
    }
    
    // ========================================================================
    // Geolocation
    // ========================================================================
    
    requestGeolocation() {
        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.userLocation = {
                        lat: position.coords.latitude,
                        lon: position.coords.longitude
                    };
                    
                    // Center map on user location
                    this.map.setView([this.userLocation.lat, this.userLocation.lon], 15);
                    
                    // Add user marker
                    const userIcon = L.divIcon({
                        html: '<div class="user-location-marker">📍</div>',
                        className: 'user-marker',
                        iconSize: [24, 24]
                    });
                    
                    this.userMarker = L.marker([this.userLocation.lat, this.userLocation.lon], {
                        icon: userIcon,
                        zIndexOffset: 1000
                    }).addTo(this.map);
                    
                    console.log('User location:', this.userLocation);
                    
                    // Watch position for updates
                    navigator.geolocation.watchPosition(
                        (position) => {
                            this.userLocation = {
                                lat: position.coords.latitude,
                                lon: position.coords.longitude
                            };
                            if (this.userMarker) {
                                this.userMarker.setLatLng([this.userLocation.lat, this.userLocation.lon]);
                            }
                        },
                        (error) => console.warn('Geolocation watch error:', error),
                        { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
                    );
                },
                (error) => {
                    console.warn('Geolocation error:', error);
                },
                { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
            );
        } else {
            console.warn('Geolocation not available');
        }
    }
    
    updateGatewayInfo(node) {
        this.gatewayNode = node;
        const gatewayInfo = document.getElementById('gateway-info');
        const gatewayName = document.getElementById('gateway-name');
        const gatewayBattery = document.getElementById('gateway-battery');
        
        if (node && node.telemetry) {
            gatewayInfo.style.display = 'flex';
            gatewayName.textContent = node.name || node.node_id;
            
            const battery = node.telemetry.battery_level || 0;
            const batteryIcon = battery > 75 ? '█' : battery > 50 ? '▓' : battery > 25 ? '▒' : '░';
            gatewayBattery.textContent = `${batteryIcon} ${battery}%`;
            
            // Color code battery
            if (battery > 50) {
                gatewayBattery.style.color = 'var(--tactical-success)';
            } else if (battery > 20) {
                gatewayBattery.style.color = 'var(--tactical-warning)';
            } else {
                gatewayBattery.style.color = 'var(--tactical-danger)';
            }
        }
    }
    
    // ========================================================================
    // Event Listeners
    // ========================================================================
    
    setupEventListeners() {
        // Fit all button
        document.getElementById('fit-all-btn').addEventListener('click', () => {
            this.fitAllNodes();
        });
        
        // Toggle trails button
        document.getElementById('toggle-trails-btn').addEventListener('click', (e) => {
            this.showTrails = !this.showTrails;
            e.currentTarget.classList.toggle('active', this.showTrails);
            this.updateAllTrails();
        });
        
        // Toggle dwells button
        document.getElementById('toggle-dwells-btn').addEventListener('click', (e) => {
            this.showDwells = !this.showDwells;
            e.currentTarget.classList.toggle('active', this.showDwells);
            this.updateAllDwells();
        });
        
        // Filter checkboxes
        ['live', 'stale', 'lost'].forEach(status => {
            document.getElementById(`filter-${status}`).addEventListener('change', () => {
                this.filterNodes();
            });
        });
        
        // Dwell toast close
        document.querySelector('.toast-close').addEventListener('click', () => {
            this.hideDwellToast();
        });
    }
    
    // ========================================================================
    // SSE Connection
    // ========================================================================
    
    connectSSE() {
        console.log('Connecting to SSE:', this.config.sseUrl);
        
        this.eventSource = new EventSource(this.config.sseUrl);
        
        this.eventSource.addEventListener('open', () => {
            console.log('SSE connected');
            this.updateConnectionStatus(true);
            
            // Clear reconnect timer
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
        });
        
        this.eventSource.addEventListener('error', (e) => {
            console.error('SSE error:', e);
            this.updateConnectionStatus(false);
            
            // Close and attempt reconnect
            this.eventSource.close();
            this.scheduleReconnect();
        });
        
        // Event handlers
        this.eventSource.addEventListener('position', (e) => {
            const data = JSON.parse(e.data);
            this.handlePositionUpdate(data);
        });
        
        this.eventSource.addEventListener('telemetry', (e) => {
            const data = JSON.parse(e.data);
            this.handleTelemetryUpdate(data);
        });
        
        this.eventSource.addEventListener('discovery', (e) => {
            const data = JSON.parse(e.data);
            this.handleNodeDiscovery(data);
        });
        
        this.eventSource.addEventListener('dwell', (e) => {
            const data = JSON.parse(e.data);
            this.handleDwellEvent(data);
        });
        
        this.eventSource.addEventListener('heartbeat', (e) => {
            const data = JSON.parse(e.data);
            this.handleHeartbeat(data);
        });
    }
    
    scheduleReconnect() {
        if (this.reconnectTimer) return;
        
        console.log(`Reconnecting in ${this.reconnectInterval}ms...`);
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connectSSE();
        }, this.reconnectInterval);
    }
    
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        const textEl = statusEl.querySelector('.status-text');
        
        if (connected) {
            statusEl.classList.remove('disconnected');
            statusEl.classList.add('connected');
            textEl.textContent = 'Connected';
        } else {
            statusEl.classList.remove('connected');
            statusEl.classList.add('disconnected');
            textEl.textContent = 'Disconnected';
        }
    }
    
    // ========================================================================
    // Event Handlers
    // ========================================================================
    
    handlePositionUpdate(data) {
        const nodeId = data.node_id;
        const nodeName = data.node_name;
        const nodeType = data.node_type;
        const position = data.position;
        const telemetry = data.telemetry || {};
        const status = data.status;
        
        // Update or create node
        if (!this.nodes.has(nodeId)) {
            this.nodes.set(nodeId, {
                node_id: nodeId,
                node_name: nodeName,
                node_type: nodeType,
                position: position,
                telemetry: telemetry,
                status: status,
                trail: [],
                last_update: Date.now()
            });
        } else {
            const node = this.nodes.get(nodeId);
            node.position = position;
            node.telemetry = { ...node.telemetry, ...telemetry };
            node.status = status;
            node.last_update = Date.now();
            
            // Add to trail
            node.trail.push({
                lat: position.latitude,
                lon: position.longitude,
                timestamp: Date.now()
            });
            
            // Limit trail length
            if (node.trail.length > 100) {
                node.trail = node.trail.slice(-100);
            }
        }
        
        // Update marker
        this.updateMarker(nodeId);
        
        // Update trail if shown
        if (this.showTrails) {
            this.updateTrail(nodeId);
        }
        
        // Update node list
        this.updateNodeList();
        
        // Update stats
        this.updateStats();
        
        // Update last update time
        this.updateLastUpdateTime();
        
        console.log(`Position update: ${nodeName} at ${position.latitude.toFixed(6)}, ${position.longitude.toFixed(6)}`);
    }
    
    handleTelemetryUpdate(data) {
        const nodeId = data.node_id;
        
        if (this.nodes.has(nodeId)) {
            const node = this.nodes.get(nodeId);
            node.telemetry = { ...node.telemetry, ...data.telemetry };
            node.status = data.status;
            node.last_update = Date.now();
            
            // Update gateway info if this is the connected node (first node we see)
            if (!this.gatewayNode || this.gatewayNode.node_id === nodeId) {
                this.updateGatewayInfo(node);
            }
            
            // Update node list item
            this.updateNodeList();
        }
    }
    
    handleNodeDiscovery(data) {
        const nodeId = data.node_id;
        const nodeName = data.node_name;
        const nodeType = data.node_type;
        
        console.log(`Node discovered: ${nodeName} (${nodeId})`);
        
        // Update node if exists, otherwise wait for position
        if (this.nodes.has(nodeId)) {
            const node = this.nodes.get(nodeId);
            node.node_name = nodeName;
            node.node_type = nodeType;
            this.updateNodeList();
        }
    }
    
    handleDwellEvent(data) {
        const eventType = data.event_type;
        const nodeId = data.node_id;
        const nodeName = data.node_name;
        const dwellId = data.dwell_id;
        const location = data.location;
        const duration = data.duration_seconds;
        
        console.log(`Dwell event: ${eventType} for ${nodeName}`);
        
        if (eventType === 'dwell_started') {
            // Show toast
            this.showDwellToast(nodeName, 'started dwelling', location);
            
            // Add dwell marker
            if (this.showDwells) {
                this.addDwellMarker(dwellId, location, nodeName, duration);
            }
        } else if (eventType === 'dwell_ended') {
            // Update dwell marker
            if (this.dwellMarkers.has(dwellId)) {
                const marker = this.dwellMarkers.get(dwellId);
                marker.setPopupContent(this.createDwellPopup(nodeName, duration, 'completed'));
            }
        }
    }
    
    handleHeartbeat(data) {
        // Update connection status silently
        this.updateConnectionStatus(true);
    }
    
    // ========================================================================
    // Map Updates
    // ========================================================================
    
    updateMarker(nodeId) {
        const node = this.nodes.get(nodeId);
        const position = node.position;
        const latlng = [position.latitude, position.longitude];
        
        if (this.markers.has(nodeId)) {
            // Update existing marker
            const marker = this.markers.get(nodeId);
            marker.setLatLng(latlng);
            marker.setPopupContent(this.createPopupContent(node));
        } else {
            // Create new marker
            const icon = this.createMarkerIcon(node);
            const marker = L.marker(latlng, { icon: icon });
            
            marker.bindPopup(this.createPopupContent(node));
            marker.on('click', () => {
                this.selectNode(nodeId);
            });
            
            marker.addTo(this.map);
            this.markers.set(nodeId, marker);
        }
    }
    
    createMarkerIcon(node) {
        const icons = {
            dog: '🐕',
            base_station: '📡',
            team_lead: '👤',
            truck: '🚚',
            repeater: '🔁',
            unknown: '❓'
        };
        
        const colors = {
            dog: '#FF6B6B',
            base_station: '#4ECDC4',
            team_lead: '#45B7D1',
            truck: '#FFA07A',
            repeater: '#98D8C8',
            unknown: '#95A5A6'
        };
        
        const icon = icons[node.node_type] || icons.unknown;
        const color = colors[node.node_type] || colors.unknown;
        
        const html = `
            <div style="
                font-size: 24px;
                text-align: center;
                filter: drop-shadow(0 0 4px ${color});
            ">${icon}</div>
        `;
        
        return L.divIcon({
            html: html,
            className: 'custom-marker',
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
    }
    
    createPopupContent(node) {
        const pos = node.position;
        const tel = node.telemetry;
        
        return `
            <div style="min-width: 200px;">
                <h3 style="margin: 0 0 8px 0;">${node.node_name}</h3>
                <p style="margin: 4px 0; font-size: 0.85rem;">
                    <strong>Type:</strong> ${node.node_type}<br>
                    <strong>Status:</strong> ${node.status}<br>
                    <strong>Lat:</strong> ${pos.latitude.toFixed(6)}<br>
                    <strong>Lon:</strong> ${pos.longitude.toFixed(6)}<br>
                    ${pos.altitude ? `<strong>Alt:</strong> ${pos.altitude.toFixed(1)}m<br>` : ''}
                    ${tel.battery_level ? `<strong>Battery:</strong> ${tel.battery_level}%<br>` : ''}
                    ${tel.rssi ? `<strong>RSSI:</strong> ${tel.rssi} dBm<br>` : ''}
                </p>
            </div>
        `;
    }
    
    updateTrail(nodeId) {
        const node = this.nodes.get(nodeId);
        
        if (!node.trail || node.trail.length < 2) {
            return;
        }
        
        const latlngs = node.trail.map(point => [point.lat, point.lon]);
        
        const colors = {
            dog: '#FF6B6B',
            base_station: '#4ECDC4',
            team_lead: '#45B7D1',
            truck: '#FFA07A',
            repeater: '#98D8C8',
            unknown: '#95A5A6'
        };
        
        const color = colors[node.node_type] || colors.unknown;
        
        if (this.trails.has(nodeId)) {
            // Update existing trail
            const trail = this.trails.get(nodeId);
            trail.setLatLngs(latlngs);
        } else {
            // Create new trail
            const trail = L.polyline(latlngs, {
                color: color,
                weight: 3,
                opacity: 0.7
            }).addTo(this.map);
            
            this.trails.set(nodeId, trail);
        }
    }
    
    updateAllTrails() {
        if (this.showTrails) {
            // Show all trails
            this.nodes.forEach((node, nodeId) => {
                this.updateTrail(nodeId);
            });
        } else {
            // Hide all trails
            this.trails.forEach(trail => {
                trail.remove();
            });
            this.trails.clear();
        }
    }
    
    addDwellMarker(dwellId, location, nodeName, duration) {
        const latlng = [location.center_lat, location.center_lon];
        
        // Create circle for dwell radius
        const circle = L.circle(latlng, {
            radius: location.radius_meters,
            color: '#FF9800',
            fillColor: '#FF9800',
            fillOpacity: 0.2,
            weight: 2,
            dashArray: '5, 5'
        });
        
        circle.bindPopup(this.createDwellPopup(nodeName, duration, 'ongoing'));
        circle.addTo(this.map);
        
        this.dwellMarkers.set(dwellId, circle);
    }
    
    createDwellPopup(nodeName, duration, status) {
        const minutes = Math.floor(duration / 60);
        const seconds = duration % 60;
        
        return `
            <div style="min-width: 150px;">
                <h3 style="margin: 0 0 8px 0;">📍 Dwell Event</h3>
                <p style="margin: 4px 0; font-size: 0.85rem;">
                    <strong>Node:</strong> ${nodeName}<br>
                    <strong>Duration:</strong> ${minutes}m ${seconds}s<br>
                    <strong>Status:</strong> ${status}
                </p>
            </div>
        `;
    }
    
    updateAllDwells() {
        if (this.showDwells) {
            // Dwells are added as they arrive
        } else {
            // Hide all dwells
            this.dwellMarkers.forEach(marker => {
                marker.remove();
            });
            this.dwellMarkers.clear();
        }
    }
    
    fitAllNodes() {
        if (this.markers.size === 0) return;
        
        const bounds = L.latLngBounds();
        this.markers.forEach(marker => {
            bounds.extend(marker.getLatLng());
        });
        
        this.map.fitBounds(bounds, { padding: [50, 50] });
    }
    
    // ========================================================================
    // Node List
    // ========================================================================
    
    updateNodeList() {
        const nodeList = document.getElementById('node-list');
        
        if (this.nodes.size === 0) {
            nodeList.innerHTML = `
                <div class="no-nodes">
                    <p>No nodes detected yet</p>
                    <p class="hint">Waiting for GPS updates...</p>
                </div>
            `;
            return;
        }
        
        // Sort nodes by status and name
        const sortedNodes = Array.from(this.nodes.values()).sort((a, b) => {
            const statusOrder = { LIVE: 0, STALE: 1, LOST: 2 };
            const aOrder = statusOrder[a.status] || 3;
            const bOrder = statusOrder[b.status] || 3;
            
            if (aOrder !== bOrder) return aOrder - bOrder;
            return a.node_name.localeCompare(b.node_name);
        });
        
        nodeList.innerHTML = sortedNodes.map(node => this.createNodeItem(node)).join('');
        
        // Add event listeners
        sortedNodes.forEach(node => {
            const item = document.getElementById(`node-${node.node_id}`);
            if (item) {
                item.addEventListener('click', () => {
                    this.selectNode(node.node_id);
                });
                
                // Trail toggle button
                const trailBtn = item.querySelector('.trail-btn');
                if (trailBtn) {
                    trailBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.toggleNodeTrail(node.node_id);
                    });
                }
                
                // Zoom button
                const zoomBtn = item.querySelector('.zoom-btn');
                if (zoomBtn) {
                    zoomBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.zoomToNode(node.node_id);
                    });
                }
            }
        });
        
        // Apply filters
        this.filterNodes();
    }
    
    createNodeItem(node) {
        const icons = {
            dog: '🐕',
            base_station: '📡',
            team_lead: '👤',
            truck: '🚚',
            repeater: '🔁',
            unknown: '❓'
        };
        
        const icon = icons[node.node_type] || icons.unknown;
        
        const age = Math.floor((Date.now() - node.last_update) / 1000);
        const ageStr = age < 60 ? `${age}s ago` : `${Math.floor(age / 60)}m ago`;
        
        const tel = node.telemetry;
        const battery = tel.battery_level || '--';
        const batteryClass = battery === '--' ? '' : 
                            battery > 50 ? 'good' : 
                            battery > 20 ? 'warning' : 'bad';
        
        const rssi = tel.rssi || '--';
        const rssiClass = rssi === '--' ? '' :
                         rssi > -80 ? 'good' :
                         rssi > -95 ? 'warning' : 'bad';
        
        const hasTrail = this.trails.has(node.node_id);
        
        return `
            <div class="node-item ${this.selectedNodeId === node.node_id ? 'selected' : ''}" 
                 id="node-${node.node_id}"
                 data-status="${node.status.toLowerCase()}">
                <div class="node-header">
                    <div class="node-info-left">
                        <span class="node-icon">${icon}</span>
                        <span class="node-name">${node.node_name}</span>
                    </div>
                    <span class="node-status-badge ${node.status.toLowerCase()}">${node.status}</span>
                </div>
                <div class="node-details">
                    <div class="node-detail">
                        <span class="detail-label">Battery</span>
                        <span class="detail-value ${batteryClass}">${battery}${battery !== '--' ? '%' : ''}</span>
                    </div>
                    <div class="node-detail">
                        <span class="detail-label">Signal</span>
                        <span class="detail-value ${rssiClass}">${rssi}${rssi !== '--' ? ' dBm' : ''}</span>
                    </div>
                    <div class="node-detail">
                        <span class="detail-label">Age</span>
                        <span class="detail-value">${ageStr}</span>
                    </div>
                    <div class="node-detail">
                        <span class="detail-label">Type</span>
                        <span class="detail-value">${node.node_type}</span>
                    </div>
                </div>
                <div class="node-actions">
                    <button class="action-btn trail-btn ${hasTrail ? 'active' : ''}">
                        ${hasTrail ? '✓' : ''} Trail
                    </button>
                    <button class="action-btn zoom-btn">Zoom</button>
                </div>
            </div>
        `;
    }
    
    filterNodes() {
        const showLive = document.getElementById('filter-live').checked;
        const showStale = document.getElementById('filter-stale').checked;
        const showLost = document.getElementById('filter-lost').checked;
        
        document.querySelectorAll('.node-item').forEach(item => {
            const status = item.dataset.status;
            const show = (status === 'live' && showLive) ||
                        (status === 'stale' && showStale) ||
                        (status === 'lost' && showLost);
            
            item.style.display = show ? 'block' : 'none';
        });
    }
    
    // ========================================================================
    // Node Actions
    // ========================================================================
    
    selectNode(nodeId) {
        this.selectedNodeId = nodeId;
        
        // Update selection in list
        document.querySelectorAll('.node-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        const item = document.getElementById(`node-${nodeId}`);
        if (item) {
            item.classList.add('selected');
        }
        
        // Open marker popup
        const marker = this.markers.get(nodeId);
        if (marker) {
            marker.openPopup();
        }
    }
    
    zoomToNode(nodeId) {
        const marker = this.markers.get(nodeId);
        if (marker) {
            this.map.setView(marker.getLatLng(), 15, { animate: true });
            marker.openPopup();
        }
    }
    
    toggleNodeTrail(nodeId) {
        if (this.trails.has(nodeId)) {
            // Remove trail
            this.trails.get(nodeId).remove();
            this.trails.delete(nodeId);
        } else {
            // Add trail
            this.updateTrail(nodeId);
        }
        
        // Update node list
        this.updateNodeList();
    }
    
    // ========================================================================
    // UI Updates
    // ========================================================================
    
    updateStats() {
        const activeCount = Array.from(this.nodes.values())
            .filter(node => node.status === 'LIVE').length;
        
        document.getElementById('active-nodes-count').textContent = activeCount;
    }
    
    updateLastUpdateTime() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        document.getElementById('last-update').textContent = timeStr;
    }
    
    showDwellToast(nodeName, message, location) {
        const toast = document.getElementById('dwell-toast');
        const messageEl = toast.querySelector('.toast-message');
        
        messageEl.textContent = `${nodeName} ${message} at ${location.center_lat.toFixed(6)}, ${location.center_lon.toFixed(6)}`;
        
        toast.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.hideDwellToast();
        }, 5000);
    }
    
    hideDwellToast() {
        document.getElementById('dwell-toast').classList.add('hidden');
    }
}

// ============================================================================
// Initialize Dashboard
// ============================================================================

let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing HeadSpace Dashboard...');
    dashboard = new HeadSpaceDashboard();
});
