#!/bin/bash
# Setup MQTT bridge for multi-site deployment
# Run this on each HeadSpace server

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════╗"
echo "║   HeadSpace Multi-Site MQTT Bridge Setup      ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo -e "${YELLOW}Tailscale not found. Installing...${NC}"
    curl -fsSL https://tailscale.com/install.sh | sh
    echo
    echo -e "${GREEN}Tailscale installed!${NC}"
    echo "Please run: sudo tailscale up"
    echo "Then run this script again."
    exit 0
fi

# Check Tailscale status
if ! tailscale status &> /dev/null; then
    echo -e "${YELLOW}Tailscale not running. Start with:${NC}"
    echo "  sudo tailscale up"
    exit 1
fi

# Get this server's Tailscale IP
LOCAL_IP=$(tailscale ip -4)
echo -e "${GREEN}This server's Tailscale IP: $LOCAL_IP${NC}"
echo

# Get site configuration
echo "Enter configuration for this site:"
echo
read -p "Site ID (e.g., base-a, truck-1): " SITE_ID
read -p "Site Name (e.g., California Base): " SITE_NAME
echo

# Get remote sites to bridge to
echo "Enter remote site Tailscale IPs (one per line, empty line to finish):"
echo "Example: 100.64.0.2"
REMOTE_IPS=()
while true; do
    read -p "Remote IP: " ip
    if [ -z "$ip" ]; then
        break
    fi
    REMOTE_IPS+=("$ip")
done

if [ ${#REMOTE_IPS[@]} -eq 0 ]; then
    echo -e "${YELLOW}No remote sites configured. Exiting.${NC}"
    exit 0
fi

# Create bridge configuration
BRIDGE_CONF="/etc/mosquitto/conf.d/bridge.conf"
echo -e "${GREEN}Creating bridge configuration...${NC}"

cat > $BRIDGE_CONF <<EOF
# HeadSpace Multi-Site MQTT Bridge
# Generated: $(date)
# Site: $SITE_ID ($SITE_NAME)

EOF

# Add bridge for each remote site
for i in "${!REMOTE_IPS[@]}"; do
    REMOTE_IP=${REMOTE_IPS[$i]}
    BRIDGE_NAME="bridge-to-site-$i"
    
    cat >> $BRIDGE_CONF <<EOF
# Bridge to remote site at $REMOTE_IP
connection $BRIDGE_NAME
address $REMOTE_IP:1883
topic headspace/# both 2
bridge_protocol_version mqttv311
try_private false
cleansession true
notifications false
bridge_attempt_unsubscribe false
restart_timeout 30

EOF

    echo -e "  Added bridge to $REMOTE_IP"
done

echo
echo -e "${GREEN}Bridge configuration created at: $BRIDGE_CONF${NC}"
echo

# Update HeadSpace config
PROCESS_CONFIG="/home/$(logname)/HeadSpace/services/processing/config.yaml"
if [ -f "$PROCESS_CONFIG" ]; then
    echo "Updating HeadSpace processing config..."
    
    # Use Python to update YAML properly
    python3 << PYEOF
import yaml

config_file = "$PROCESS_CONFIG"
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

if 'site' not in config:
    config['site'] = {}

config['site']['enabled'] = True
config['site']['id'] = "$SITE_ID"
config['site']['name'] = "$SITE_NAME"

with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print("✓ Updated processing config")
PYEOF

fi

# Restart services
echo
echo -e "${GREEN}Restarting services...${NC}"
systemctl restart mosquitto
sleep 2

if systemctl is-active --quiet headspace-process.service; then
    systemctl restart headspace-process.service
fi

echo
echo -e "${GREEN}✅ Multi-site bridge setup complete!${NC}"
echo
echo "Site Configuration:"
echo "  Site ID: $SITE_ID"
echo "  Site Name: $SITE_NAME"
echo "  Local IP: $LOCAL_IP"
echo "  Remote Sites: ${#REMOTE_IPS[@]}"
echo
echo "Test connectivity:"
echo "  mosquitto_sub -h localhost -t 'headspace/#' -v"
echo
echo "Check bridge status:"
echo "  journalctl -u mosquitto -f | grep bridge"
echo
echo "View Tailscale network:"
echo "  tailscale status"
