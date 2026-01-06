# HeadSpace on Raspberry Pi

**Perfect for portable, field-deployable dog tracking systems!**

---

## 🎯 Why Raspberry Pi?

- **Portable**: Battery-powered operation
- **USB Direct**: Connect Heltec V3 directly via USB
- **Offline**: No internet required
- **WiFi Hotspot**: Create local network for dashboard access
- **Rugged**: Can be weatherproofed for field use

---

## 📋 Requirements

### Hardware
- **Raspberry Pi 4 or 5** (4GB+ RAM recommended, 2GB works)
- **MicroSD Card** (32GB+ recommended, 16GB minimum)
- **Power Supply** or portable battery bank
- **Heltec V3** (or any Meshtastic device) connected via USB

### Software
- **Raspberry Pi OS** (64-bit recommended, Lite or Desktop)
- **Python 3.9+** (included in recent Pi OS)

---

## 🚀 Installation Steps

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    mosquitto \
    mosquitto-clients \
    sqlite3

# Enable Mosquitto at boot
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 2. Clone HeadSpace

```bash
cd ~
git clone https://github.com/AbstruseGoose/HeadSpace.git
cd HeadSpace
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt
```

### 4. Connect Meshtastic Device

```bash
# Plug in your Heltec V3 via USB
# Find the device (usually /dev/ttyUSB0)
ls -la /dev/ttyUSB*

# Test connection
meshtastic --info
```

### 5. Configure HeadSpace

The default config should work! It auto-detects USB devices.

```bash
# Verify ingestion config
cat services/ingestion/config.yaml
```

Should show:
```yaml
meshtastic:
  connection_type: serial
  serial_port: auto  # Auto-detects /dev/ttyUSB0
  simulation_mode: false
```

### 6. Initialize Database

```bash
# Create database
mkdir -p data
sqlite3 data/headspace.db < data/schemas.sql
```

### 7. Start Services

```bash
# Option A: Use startup script
./start.sh

# Option B: Manual start
python3 services/ingestion/ingest.py &
python3 services/processing/processor.py &
python3 dashboard/server.py &
```

### 8. Access Dashboard

From any device on the same network:
```
http://RASPBERRY_PI_IP:8080
```

Find Pi's IP:
```bash
hostname -I
```

---

## 🔧 Auto-Start on Boot

Create systemd services to start HeadSpace automatically:

### Create Service Files

```bash
# Create ingestion service
sudo nano /etc/systemd/system/headspace-ingest.service
```

Paste:
```ini
[Unit]
Description=HeadSpace Ingestion Service
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HeadSpace
ExecStart=/home/pi/HeadSpace/venv/bin/python3 /home/pi/HeadSpace/services/ingestion/ingest.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create processing service
sudo nano /etc/systemd/system/headspace-process.service
```

Paste:
```ini
[Unit]
Description=HeadSpace Processing Service
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HeadSpace
ExecStart=/home/pi/HeadSpace/venv/bin/python3 /home/pi/HeadSpace/services/processing/processor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create dashboard service
sudo nano /etc/systemd/system/headspace-dashboard.service
```

Paste:
```ini
[Unit]
Description=HeadSpace Dashboard Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HeadSpace
ExecStart=/home/pi/HeadSpace/venv/bin/python3 /home/pi/HeadSpace/dashboard/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable headspace-ingest.service
sudo systemctl enable headspace-process.service
sudo systemctl enable headspace-dashboard.service

# Start services
sudo systemctl start headspace-ingest.service
sudo systemctl start headspace-process.service
sudo systemctl start headspace-dashboard.service

# Check status
sudo systemctl status headspace-*
```

---

## 📡 Setup WiFi Access Point (Optional)

Create a WiFi hotspot so team members can access the dashboard from phones/tablets without internet:

```bash
# Install hostapd and dnsmasq
sudo apt install -y hostapd dnsmasq

# Configure access point
sudo nano /etc/hostapd/hostapd.conf
```

Add:
```
interface=wlan0
ssid=HeadSpace
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=DogTracking2026
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

```bash
# Enable and start
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd
```

Now team members can:
1. Connect to **HeadSpace** WiFi (password: DogTracking2026)
2. Open browser to http://10.0.0.1:8080

---

## 🔋 Power Options

### Option 1: USB Battery Bank
- Use any 5V USB battery bank
- 10,000mAh = ~6-8 hours runtime
- 20,000mAh = ~12-16 hours runtime

### Option 2: Power over Ethernet (PoE)
- Use PoE HAT for Raspberry Pi
- Power via Ethernet cable
- Good for fixed base stations

### Option 3: Solar + Battery
- Solar panel (10W+)
- LiPo battery + charge controller
- For extended field operations

---

## 📊 Performance

**Raspberry Pi 4/5 can easily handle:**
- 50+ nodes simultaneously
- Real-time position updates
- Dwell detection for all nodes
- Multiple dashboard clients
- Weeks of GPS data storage

**Resource Usage (typical):**
- CPU: 5-15%
- RAM: ~200MB
- Disk: ~50MB per day (varies by update frequency)

---

## 🧰 Troubleshooting

### Check Services
```bash
sudo systemctl status headspace-*
```

### View Logs
```bash
journalctl -u headspace-ingest.service -f
journalctl -u headspace-process.service -f
journalctl -u headspace-dashboard.service -f
```

### Check USB Device
```bash
# List USB devices
lsusb

# Check serial ports
ls -la /dev/ttyUSB*

# Test Meshtastic connection
meshtastic --info
```

### Restart Services
```bash
sudo systemctl restart headspace-ingest.service
sudo systemctl restart headspace-process.service
sudo systemctl restart headspace-dashboard.service
```

---

## 🎒 Field Deployment Setup

### Waterproof Case
1. Pelican case or similar
2. USB pass-through for Heltec antenna
3. Power bank inside
4. Optional: external antenna mount

### Mounting
- Vehicle mount: Dashboard or console
- Backpack mount: In top pocket with antenna out
- Tripod mount: For base station setup

### Network Access
- Create WiFi hotspot (see above)
- Team members connect via phones/tablets
- No internet required!

---

## 🚁 Advanced: Multiple Base Stations

Deploy multiple Raspberry Pis as base stations:
1. Each Pi runs HeadSpace independently
2. Each collects data from its Meshtastic gateway
3. Later: Sync databases or use central server

---

## ✅ Quick Start Checklist

- [ ] Raspberry Pi 4/5 with Pi OS installed
- [ ] Install mosquitto, sqlite3, python3-pip
- [ ] Clone HeadSpace repo
- [ ] Install Python dependencies
- [ ] Connect Heltec V3 via USB
- [ ] Run `./start.sh`
- [ ] Access dashboard at http://PI_IP:8080
- [ ] Optional: Setup systemd services for auto-start
- [ ] Optional: Create WiFi hotspot for field access

---

## 💡 Tips

1. **Use a high-quality SD card** - Industrial/endurance cards for reliability
2. **Enable read-only root** - Protects against sudden power loss
3. **Regular backups** - Copy `/home/pi/HeadSpace/data/` directory
4. **Monitor battery** - Low voltage can cause corruption
5. **Test before field deployment** - Run for 24 hours indoors first

---

**Ready to deploy? HeadSpace on Raspberry Pi gives you a portable, offline dog tracking system!**
