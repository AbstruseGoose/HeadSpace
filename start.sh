#!/bin/bash
# HeadSpace - Startup Script
# This script starts all HeadSpace services in the correct order

set -e  # Exit on error

echo "🐕 Starting HeadSpace Dog Tracking System..."
echo

# Color codes for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Mosquitto is running
echo -n "Checking MQTT broker... "
if ! pgrep -x mosquitto > /dev/null; then
    echo -e "${YELLOW}not running${NC}"
    echo "Starting Mosquitto MQTT broker..."
    sudo mkdir -p /run/mosquitto 2>/dev/null
    sudo chown $(whoami) /run/mosquitto 2>/dev/null
    sudo service mosquitto start || {
        echo -e "${RED}Failed to start Mosquitto${NC}"
        echo "Try running: sudo apt install mosquitto mosquitto-clients"
        exit 1
    }
fi
echo -e "${GREEN}running${NC}"

# Check Python dependencies
echo -n "Checking Python dependencies... "
python3 -c "import meshtastic, yaml, paho.mqtt.client, flask" 2>/dev/null && echo -e "${GREEN}OK${NC}" || {
    echo -e "${RED}missing${NC}"
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
}

# Create data directory if it doesn't exist
mkdir -p data logs

# Initialize database if it doesn't exist
if [ ! -f data/headspace.db ]; then
    echo "Initializing database..."
    sqlite3 data/headspace.db < data/schemas.sql
    echo -e "${GREEN}Database created${NC}"
fi

# Create log directory
mkdir -p logs

echo
echo "Starting services..."
echo "Press Ctrl+C to stop all services"
echo

# Function to cleanup background processes on exit
cleanup() {
    echo
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null
    wait
    echo "All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start services with logging
echo -e "${YELLOW}[1/3]${NC} Starting Ingestion Service..."
python3 services/ingestion/ingest.py > logs/ingestion.log 2>&1 &
INGEST_PID=$!
sleep 2

echo -e "${YELLOW}[2/3]${NC} Starting Processing Service..."
python3 services/processing/processor.py > logs/processing.log 2>&1 &
PROC_PID=$!
sleep 2

echo -e "${YELLOW}[3/3]${NC} Starting Dashboard Server..."
python3 dashboard/server.py > logs/dashboard.log 2>&1 &
DASH_PID=$!
sleep 2

echo
echo -e "${GREEN}✅ All services started!${NC}"
echo
echo "📊 Dashboard: http://localhost:8080"
echo "📡 SSE Stream: http://localhost:8081/events"
echo
echo "📝 Logs:"
echo "   - Ingestion:  tail -f logs/ingestion.log"
echo "   - Processing: tail -f logs/processing.log"
echo "   - Dashboard:  tail -f logs/dashboard.log"
echo
echo "Monitoring services (press Ctrl+C to stop)..."
echo

# Wait for all background processes
wait
