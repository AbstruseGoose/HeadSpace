#!/bin/bash
# Monitor multi-site HeadSpace deployment

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════╗"
echo "║     HeadSpace Multi-Site Status Monitor       ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"
echo

# Local services
echo -e "${YELLOW}=== Local Services ===${NC}"
for service in headspace-ingest headspace-process headspace-dashboard; do
    if systemctl is-active --quiet $service.service 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $service: running"
    else
        echo -e "  ${RED}✗${NC} $service: stopped"
    fi
done
echo

# Mosquitto
echo -e "${YELLOW}=== MQTT Broker ===${NC}"
if systemctl is-active --quiet mosquitto; then
    echo -e "  ${GREEN}✓${NC} Mosquitto: running"
    
    # Check bridge connections
    BRIDGE_STATUS=$(mosquitto_sub -h localhost -t '$SYS/broker/connection/#' -C 5 -W 1 2>/dev/null || echo "")
    if [ ! -z "$BRIDGE_STATUS" ]; then
        echo "  Bridge status:"
        echo "$BRIDGE_STATUS" | grep -E "state|clients" | sed 's/^/    /'
    fi
else
    echo -e "  ${RED}✗${NC} Mosquitto: stopped"
fi
echo

# Tailscale network
echo -e "${YELLOW}=== VPN Network (Tailscale) ===${NC}"
if command -v tailscale &> /dev/null; then
    if tailscale status &> /dev/null; then
        LOCAL_IP=$(tailscale ip -4 2>/dev/null)
        echo -e "  ${GREEN}✓${NC} Tailscale: connected"
        echo "  Local IP: $LOCAL_IP"
        echo
        echo "  Network peers:"
        tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for peer_id, peer in data.get('Peer', {}).items():
    name = peer.get('HostName', 'Unknown')
    ip = peer.get('TailscaleIPs', [''])[0]
    online = peer.get('Online', False)
    status = '✓' if online else '✗'
    print(f'    {status} {name}: {ip}')
" 2>/dev/null || tailscale status | grep -v "^#" | head -10 | sed 's/^/    /'
    else
        echo -e "  ${YELLOW}⚠${NC} Tailscale: not connected"
        echo "  Run: sudo tailscale up"
    fi
else
    echo -e "  ${RED}✗${NC} Tailscale: not installed"
fi
echo

# Remote site connectivity
echo -e "${YELLOW}=== Remote Sites ===${NC}"
BRIDGE_CONF="/etc/mosquitto/conf.d/bridge.conf"
if [ -f "$BRIDGE_CONF" ]; then
    REMOTE_IPS=$(grep "^address" $BRIDGE_CONF | awk '{print $2}' | cut -d: -f1)
    if [ ! -z "$REMOTE_IPS" ]; then
        for ip in $REMOTE_IPS; do
            if timeout 1 nc -z $ip 1883 2>/dev/null; then
                echo -e "  ${GREEN}✓${NC} $ip:1883 (MQTT reachable)"
            else
                echo -e "  ${RED}✗${NC} $ip:1883 (MQTT not reachable)"
            fi
        done
    else
        echo "  No remote sites configured"
    fi
else
    echo "  No bridge configuration found"
    echo "  Run: sudo ./scripts/setup-multi-site.sh"
fi
echo

# Database stats
echo -e "${YELLOW}=== Database ===${NC}"
DB_PATH="/home/$(logname)/HeadSpace/data/headspace.db"
if [ -f "$DB_PATH" ]; then
    NODE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM nodes" 2>/dev/null)
    GPS_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM gps_points" 2>/dev/null)
    echo "  Nodes tracked: $NODE_COUNT"
    echo "  GPS points: $GPS_COUNT"
else
    echo -e "  ${RED}✗${NC} Database not found"
fi
echo

# Dashboard access
echo -e "${YELLOW}=== Dashboard Access ===${NC}"
LOCAL_IP=$(hostname -I | awk '{print $1}')
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
echo "  Local network: http://$LOCAL_IP:8080"
if [ ! -z "$TAILSCALE_IP" ]; then
    echo "  Tailscale VPN: http://$TAILSCALE_IP:8080"
fi
echo

# Recent activity
echo -e "${YELLOW}=== Recent Activity ===${NC}"
echo "  Last 5 position updates:"
sqlite3 "$DB_PATH" "SELECT datetime(timestamp, 'unixepoch', 'localtime'), node_id FROM gps_points ORDER BY timestamp DESC LIMIT 5" 2>/dev/null | sed 's/^/    /' || echo "    No data"
echo

echo -e "${GREEN}End of status report${NC}"
echo
echo "For live monitoring:"
echo "  journalctl -u headspace-* -f"
echo "  mosquitto_sub -h localhost -t 'headspace/#' -v"
