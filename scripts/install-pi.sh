#!/bin/bash
# HeadSpace - Raspberry Pi Installation Script
# Run this on a fresh Raspberry Pi OS installation

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════╗"
echo "║      HeadSpace - Raspberry Pi Setup           ║"
echo "║      Dog Tracking via Meshtastic LoRa         ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"
echo

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo -e "${GREEN}[1/7] Updating system...${NC}"
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo -e "${GREEN}[2/7] Installing system packages...${NC}"
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    mosquitto \
    mosquitto-clients \
    sqlite3

# Enable Mosquitto
echo -e "${GREEN}[3/7] Configuring Mosquitto MQTT broker...${NC}"
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Create virtual environment
echo -e "${GREEN}[4/7] Setting up Python virtual environment...${NC}"
cd ~/HeadSpace
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${GREEN}[5/7] Installing Python packages...${NC}"
pip3 install -r requirements.txt

# Initialize database
echo -e "${GREEN}[6/7] Initializing database...${NC}"
mkdir -p data logs
sqlite3 data/headspace.db < data/schemas.sql

# Test Meshtastic connection
echo -e "${GREEN}[7/7] Checking for Meshtastic device...${NC}"
if ls /dev/ttyUSB* 1> /dev/null 2>&1; then
    echo -e "${GREEN}Found USB device(s):${NC}"
    ls -la /dev/ttyUSB*
    echo
    echo -e "${GREEN}Testing Meshtastic connection...${NC}"
    timeout 5 meshtastic --info || echo -e "${YELLOW}Note: Device found but no response yet${NC}"
else
    echo -e "${YELLOW}No USB devices found. Connect your Heltec V3 and rerun.${NC}"
fi

echo
echo -e "${GREEN}✅ Installation complete!${NC}"
echo
echo "Next steps:"
echo "  1. Connect your Heltec V3 via USB"
echo "  2. Run: ./start.sh"
echo "  3. Access dashboard at: http://$(hostname -I | awk '{print $1}'):8080"
echo
echo "To enable auto-start on boot:"
echo "  ./scripts/install-services.sh"
echo
echo -e "${GREEN}Happy tracking! 🐕${NC}"
