#!/bin/bash
# Install HeadSpace as systemd services (auto-start on boot)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Installing HeadSpace systemd services...${NC}"
echo

# Get current user and HeadSpace path
USER=$(whoami)
HEADSPACE_DIR=$(pwd)
VENV_PYTHON="${HEADSPACE_DIR}/venv/bin/python3"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt
fi

# Create ingestion service
echo "Creating headspace-ingest.service..."
sudo tee /etc/systemd/system/headspace-ingest.service > /dev/null <<EOF
[Unit]
Description=HeadSpace Ingestion Service
After=network.target mosquitto.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HEADSPACE_DIR
ExecStart=$VENV_PYTHON $HEADSPACE_DIR/services/ingestion/ingest.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create processing service
echo "Creating headspace-process.service..."
sudo tee /etc/systemd/system/headspace-process.service > /dev/null <<EOF
[Unit]
Description=HeadSpace Processing Service
After=network.target mosquitto.service headspace-ingest.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HEADSPACE_DIR
ExecStart=$VENV_PYTHON $HEADSPACE_DIR/services/processing/processor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create dashboard service
echo "Creating headspace-dashboard.service..."
sudo tee /etc/systemd/system/headspace-dashboard.service > /dev/null <<EOF
[Unit]
Description=HeadSpace Dashboard Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HEADSPACE_DIR
ExecStart=$VENV_PYTHON $HEADSPACE_DIR/dashboard/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable services
echo "Enabling services..."
sudo systemctl enable headspace-ingest.service
sudo systemctl enable headspace-process.service
sudo systemctl enable headspace-dashboard.service

# Start services
echo "Starting services..."
sudo systemctl start headspace-ingest.service
sudo systemctl start headspace-process.service
sudo systemctl start headspace-dashboard.service

echo
echo -e "${GREEN}✅ Services installed and started!${NC}"
echo
echo "Check status:"
echo "  sudo systemctl status headspace-*"
echo
echo "View logs:"
echo "  journalctl -u headspace-ingest.service -f"
echo "  journalctl -u headspace-process.service -f"
echo "  journalctl -u headspace-dashboard.service -f"
echo
echo "Restart services:"
echo "  sudo systemctl restart headspace-*"
echo
echo "Stop services:"
echo "  sudo systemctl stop headspace-*"
echo
echo "Disable auto-start:"
echo "  sudo systemctl disable headspace-*"
