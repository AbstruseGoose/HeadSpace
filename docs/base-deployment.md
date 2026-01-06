# HeadSpace Base Station Deployment Guide

**Command post installation for laptops**

Deploy HeadSpace on a laptop at your base camp for a full-featured, high-performance tracking command center.

---

## 💻 Overview

**What You're Building:**
- Laptop runs HeadSpace (Windows, Mac, or Linux)
- Heltec V3 connects via USB (gateway to LoRa mesh)
- AC or battery powered (laptop battery = backup power)
- Large screen for detailed map view
- WiFi for multiple operators simultaneously
- Central command and control station

**Why Laptop for Base Stations:**
- ✅ More processing power (handle 100+ nodes)
- ✅ Larger screen for detailed operations
- ✅ Easier to configure and troubleshoot
- ✅ Built-in UPS (laptop battery)
- ✅ Multiple USB ports for expansion
- ✅ Can run additional software (mapping, comms)

---

## 💻 Hardware Requirements

### Required Components

| Item | Specification | Notes |
|------|--------------|-------|
| **Laptop** | Any with USB-A/C port | Windows 10+, macOS 10.15+, or Linux |
| **RAM** | 4GB minimum, 8GB+ recommended | More for large operations |
| **Storage** | 10GB+ free space | SSD preferred |
| **Heltec V3** | ESP32-based with LoRa | Your gateway device |
| **USB Cable** | USB-A to USB-C | For Heltec to laptop |

### Recommended Setup

| Item | Purpose |
|------|---------|
| External monitor | Dual-screen for map + logs |
| USB hub | Connect multiple Heltec devices (redundancy) |
| Ethernet adapter | More reliable than WiFi for multi-site |
| UPS or power bank | Extended runtime if AC power fails |
| External WiFi adapter | Stronger hotspot for field teams |
| Waterproof case | For field deployment in weather |

---

## 🔧 Installation by Operating System

Choose your operating system:

---

## 🐧 Linux Installation (Recommended)

**Best for: Ubuntu 22.04+, Debian 12+, Raspberry Pi OS**

### Step 1: Install System Dependencies

```bash
# Update package list
sudo apt update

# Install required packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    mosquitto \
    mosquitto-clients \
    sqlite3 \
    curl
```

### Step 2: Clone and Install HeadSpace

```bash
# Clone repository
cd ~
git clone https://github.com/AbstruseGoose/HeadSpace.git
cd HeadSpace

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
mkdir -p data logs
sqlite3 data/headspace.db < data/schemas.sql
```

### Step 3: Start Mosquitto

```bash
# Start MQTT broker
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Verify it's running
systemctl status mosquitto
```

### Step 4: Connect Heltec V3

```bash
# Plug in Heltec V3 via USB
# Wait a few seconds

# Find device
ls -la /dev/ttyUSB* /dev/ttyACM*
# Should show: /dev/ttyUSB0

# Test connection
pip install meshtastic
meshtastic --info
```

### Step 5: Start HeadSpace

```bash
cd ~/HeadSpace

# Make startup script executable
chmod +x start.sh

# Start all services
./start.sh
```

### Step 6: Access Dashboard

Open browser to:
```
http://localhost:8080
```

---

## 🍎 macOS Installation

### Step 1: Install Homebrew (if not installed)

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Dependencies

```bash
# Install required packages
brew install python3 mosquitto sqlite3

# Start Mosquitto
brew services start mosquitto
```

### Step 3: Clone and Install HeadSpace

```bash
# Clone repository
cd ~
git clone https://github.com/AbstruseGoose/HeadSpace.git
cd HeadSpace

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
mkdir -p data logs
sqlite3 data/headspace.db < data/schemas.sql
```

### Step 4: Connect Heltec V3

```bash
# Plug in Heltec V3 via USB
# macOS may prompt for driver - allow it

# Find device
ls -la /dev/cu.* | grep usb
# Should show: /dev/cu.usbserial-XXXXX

# Test connection
pip install meshtastic
meshtastic --info
```

### Step 5: Configure Serial Port (if needed)

```bash
# Edit ingestion config
nano services/ingestion/config.yaml
```

Update serial port:
```yaml
meshtastic:
  serial_port: /dev/cu.usbserial-XXXXX  # Use your actual port
```

### Step 6: Start HeadSpace

```bash
cd ~/HeadSpace
chmod +x start.sh
./start.sh
```

### Step 7: Access Dashboard

Open browser to:
```
http://localhost:8080
```

---

## 🪟 Windows Installation

### Step 1: Install Python

1. Download Python 3.11+ from https://www.python.org/downloads/
2. **Important:** Check "Add Python to PATH" during installation
3. Verify installation:
```cmd
python --version
```

### Step 2: Install Mosquitto

1. Download from: https://mosquitto.org/download/
2. Install to default location: `C:\Program Files\mosquitto`
3. Start Mosquitto:
```cmd
cd "C:\Program Files\mosquitto"
mosquitto.exe
```

**Or as a service:**
```cmd
# Run as administrator
cd "C:\Program Files\mosquitto"
mosquitto.exe install
net start mosquitto
```

### Step 3: Install Git (if not installed)

Download from: https://git-scm.com/download/win

### Step 4: Clone and Install HeadSpace

```cmd
# Open Command Prompt or PowerShell
cd %USERPROFILE%

# Clone repository
git clone https://github.com/AbstruseGoose/HeadSpace.git
cd HeadSpace

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database (requires SQLite)
# Download sqlite3.exe from https://www.sqlite.org/download.html
# Or use Python:
python -c "import sqlite3; exec(open('data/schemas.sql').read())"
```

### Step 5: Install USB Driver

1. Plug in Heltec V3
2. Windows should detect it automatically
3. If not, install CP210x driver from: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers

### Step 6: Find COM Port

```cmd
# Open Device Manager
# Look under "Ports (COM & LPT)"
# Note the COM port (e.g., COM3)
```

### Step 7: Configure Serial Port

Edit `services/ingestion/config.yaml`:
```yaml
meshtastic:
  serial_port: COM3  # Use your actual COM port
```

### Step 8: Start HeadSpace

```cmd
cd %USERPROFILE%\HeadSpace
venv\Scripts\activate
python services/ingestion/ingest.py
# In another terminal:
python services/processing/processor.py
# In another terminal:
python dashboard/server.py
```

**Or use the startup script:**
```cmd
# Create start.bat file:
@echo off
cd %USERPROFILE%\HeadSpace
call venv\Scripts\activate
start python services/ingestion/ingest.py
start python services/processing/processor.py
start python dashboard/server.py
```

### Step 9: Access Dashboard

Open browser to:
```
http://localhost:8080
```

---

## 🎛️ Base Station Configuration

### Configure as ROUTER (Important!)

**Base station Heltec V3 should be ROUTER for best mesh performance:**

```bash
# Connect Heltec to laptop
meshtastic --set device.role ROUTER

# Set node name
meshtastic --set-owner "Base-Station-Alpha"

# Enable position broadcast (so you see base on map)
meshtastic --set position.position_broadcast_secs 300  # Every 5 min

# Set high transmit power (base has AC power)
meshtastic --set lora.tx_power 22  # Maximum

# Optional: Set fixed position if GPS isn't working
meshtastic --set position.fixed_position true
meshtastic --setlat 47.6062
meshtastic --setlon -122.3321
meshtastic --setalt 100

# Save and reboot
meshtastic --reboot
```

**Key Settings for Base Stations:**
- Role: `ROUTER` (acts as mesh router for other nodes)
- TX Power: Maximum (22 dBm) - you have AC power
- Position broadcast: Every 5 minutes (not critical for stationary base)
- Fixed position: Set if GPS isn't available indoors

---

## 🌐 Multi-Site Setup

**If connecting multiple bases across the internet:**

### Install Tailscale

**Linux/macOS:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4  # Note your VPN IP
```

**Windows:**
1. Download from: https://tailscale.com/download/windows
2. Install and sign in
3. Note your Tailscale IP (e.g., 100.64.0.1)

### Configure Multi-Site Bridge

**Linux/macOS:**
```bash
cd ~/HeadSpace
sudo ./scripts/setup-multi-site.sh
```

**Windows:**
Manually edit `C:\Program Files\mosquitto\mosquitto.conf`:
```conf
# Add bridge to remote site
connection bridge-to-base-b
address 100.64.0.2:1883  # Remote base Tailscale IP
topic headspace/# both 2
```

Restart Mosquitto service.

### Update HeadSpace Config

Edit `services/processing/config.yaml`:
```yaml
site:
  enabled: true
  id: "base-alpha"
  name: "Main Base Station"
  location:
    lat: 47.6062
    lon: -122.3321
```

---

## 📺 Dual Monitor Setup

**Recommended layout for command center:**

### Monitor 1 (Primary): Dashboard
- Open `http://localhost:8080`
- Full-screen mode (F11)
- Focus on live map view

### Monitor 2 (Secondary): Logs & Terminal
```bash
# Terminal 1: Ingestion logs
journalctl -u headspace-ingest -f  # Linux
tail -f logs/ingestion.log  # All platforms

# Terminal 2: Processing logs
journalctl -u headspace-process -f
tail -f logs/processing.log

# Terminal 3: System monitor
htop  # Linux/macOS
# Task Manager (Windows)

# Terminal 4: MQTT monitor
mosquitto_sub -h localhost -t 'headspace/#' -v
```

---

## 🔒 Security Hardening

### Enable MQTT Authentication

**Linux/macOS:**
```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd headspace
# Enter password when prompted

# Edit /etc/mosquitto/mosquitto.conf
echo "password_file /etc/mosquitto/passwd" | sudo tee -a /etc/mosquitto/mosquitto.conf
echo "allow_anonymous false" | sudo tee -a /etc/mosquitto/mosquitto.conf

sudo systemctl restart mosquitto
```

Update HeadSpace config:
```yaml
mqtt:
  username: headspace
  password: YOUR_PASSWORD
```

### Firewall Configuration

**Linux:**
```bash
# Allow only local connections
sudo ufw allow from 192.168.1.0/24 to any port 8080
sudo ufw allow from 192.168.1.0/24 to any port 8081
sudo ufw enable
```

**macOS:**
```bash
# System Preferences → Security & Privacy → Firewall
# Enable and configure to allow HeadSpace
```

**Windows:**
```cmd
# Windows Defender Firewall
# Add inbound rules for ports 8080, 8081
netsh advfirewall firewall add rule name="HeadSpace Dashboard" dir=in action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="HeadSpace SSE" dir=in action=allow protocol=TCP localport=8081
```

---

## 📊 Performance Optimization

### Increase Database Performance

Edit `services/processing/config.yaml`:
```yaml
database:
  cache_size: -50000  # 50MB cache (increase for more nodes)
  wal_mode: true
  synchronous: NORMAL  # Faster than FULL, safe enough
```

### Handle Many Nodes

**For operations with 50+ nodes:**

```yaml
# Increase breadcrumb buffer
state:
  breadcrumb_buffer_size: 200  # More points in memory

# Adjust dwell detection
dwell_detection:
  dog:
    radius_meters: 20  # Larger radius = fewer false positives
    min_duration_seconds: 120  # Longer duration = fewer events
```

### Reduce Latency

```yaml
# Faster position updates
mqtt:
  qos: 0  # Faster but less reliable (good for local network)

# Shorter SSE keepalive
sse:
  keepalive_interval: 15  # Seconds
```

---

## 🛠️ Troubleshooting

### Can't Connect to Heltec V3

**Linux:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in

# Check permissions
ls -la /dev/ttyUSB0
sudo chmod 666 /dev/ttyUSB0  # Temporary fix
```

**macOS:**
```bash
# Check if driver installed
ls -la /dev/cu.*
# Install driver from Silabs if needed
```

**Windows:**
```cmd
# Check Device Manager for yellow exclamation marks
# Reinstall CP210x driver if needed
```

### Mosquitto Won't Start

**Linux:**
```bash
sudo systemctl status mosquitto
# Check logs
journalctl -u mosquitto -n 50
```

**macOS:**
```bash
brew services restart mosquitto
# Check logs
tail -f /usr/local/var/log/mosquitto/mosquitto.log
```

**Windows:**
```cmd
# Check service status
sc query mosquitto

# Start manually
cd "C:\Program Files\mosquitto"
mosquitto.exe -v
```

### Dashboard Not Loading

```bash
# Check if port is already in use
# Linux/macOS:
lsof -i :8080
# Windows:
netstat -ano | findstr :8080

# Kill process using port
# Linux/macOS:
sudo kill -9 <PID>
# Windows:
taskkill /PID <PID> /F
```

---

## 📋 Base Station Operations

### Daily Startup Procedure

1. **Power on laptop**
2. **Connect Heltec V3** via USB
3. **Start HeadSpace**:
   ```bash
   cd ~/HeadSpace
   ./start.sh
   ```
4. **Open dashboard**: http://localhost:8080
5. **Verify base station** appears on map
6. **Check node list** for active devices
7. **Monitor logs** for any errors

### During Operations

- **Map view**: Monitor all nodes in real-time
- **Node list**: Track battery levels, signal strength
- **Dwell alerts**: Watch for dogs staying in one place
- **Database queries**: Extract historical data as needed

### End of Day

- **Backup database**:
  ```bash
  cp data/headspace.db backups/headspace-$(date +%Y%m%d).db
  ```
- **Export tracks** (if needed)
- **Generate reports** from database
- **Safe to shutdown** (data persists)

---

## 💾 Data Management

### Backup Strategy

**Automated daily backup:**
```bash
# Create backup script
nano ~/backup-headspace.sh
```

Add:
```bash
#!/bin/bash
BACKUP_DIR=~/HeadSpace/backups
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d-%H%M)
cp ~/HeadSpace/data/headspace.db $BACKUP_DIR/headspace-$DATE.db
# Keep only last 30 days
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
```

```bash
chmod +x ~/backup-headspace.sh

# Add to crontab (run daily at 2am)
crontab -e
# Add: 0 2 * * * /home/USER/backup-headspace.sh
```

### Export Data

**Export all positions to CSV:**
```bash
sqlite3 data/headspace.db <<EOF
.headers on
.mode csv
.output positions.csv
SELECT datetime(timestamp, 'unixepoch') as time, node_id, latitude, longitude, altitude
FROM gps_points
ORDER BY timestamp;
.quit
EOF
```

**Export dwells:**
```bash
sqlite3 data/headspace.db <<EOF
.headers on
.mode csv
.output dwells.csv
SELECT * FROM dwells;
.quit
EOF
```

---

## ✅ Base Station Deployment Checklist

**Hardware:**
- [ ] Laptop with adequate specs
- [ ] Heltec V3 with LoRa antenna
- [ ] USB cable
- [ ] Power adapter and backup battery
- [ ] External monitor (optional)
- [ ] Ethernet connection (optional, for stability)

**Software:**
- [ ] Operating system updated
- [ ] HeadSpace installed and configured
- [ ] Mosquitto MQTT broker running
- [ ] Heltec V3 configured as ROUTER
- [ ] Site ID configured (for multi-site)
- [ ] Tailscale installed (for multi-site)

**Configuration:**
- [ ] Dashboard accessible
- [ ] Base station shows on map
- [ ] Can see other nodes
- [ ] Multi-site bridge configured (if applicable)
- [ ] MQTT authentication enabled
- [ ] Firewall configured

**Operations:**
- [ ] Team trained on dashboard
- [ ] Backup procedure established
- [ ] Log monitoring setup
- [ ] Contact info for troubleshooting

---

## 🎯 Quick Reference

### Start HeadSpace
```bash
cd ~/HeadSpace
./start.sh
```

### Stop HeadSpace
```bash
pkill -f "ingest.py|processor.py|server.py"
```

### Check Status
```bash
ps aux | grep -E "(ingest|processor|server)" | grep -v grep
```

### View Logs
```bash
tail -f logs/ingestion.log
tail -f logs/processing.log
tail -f logs/dashboard.log
```

### Access Dashboard
```
http://localhost:8080
```

### Backup Database
```bash
cp data/headspace.db backups/headspace-$(date +%Y%m%d).db
```

---

**Your base station is now the command center for tracking operations!** 💻📡

Large screen, powerful processing, reliable connection to the mesh.
