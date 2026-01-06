# HeadSpace Truck Deployment Guide

**Portable tracking system for mobile command units**

Deploy HeadSpace on a Raspberry Pi in your truck for a rugged, battery-powered, mobile tracking station.

---

## 🚚 Overview

**What You're Building:**
- Raspberry Pi 4/5 runs HeadSpace
- T-Beam Supreme connects via USB (gateway to LoRa mesh)
- Battery powered (12V truck power or USB battery)
- WiFi hotspot for dashboard access from phones/tablets
- Survives bumps, vibration, and power loss
- Boots automatically when truck starts

**Why Raspberry Pi for Trucks:**
- ✅ Compact and rugged
- ✅ Low power consumption (2.5-3W typical)
- ✅ No moving parts (reliable)
- ✅ Boots in ~30 seconds
- ✅ Can run 8+ hours on battery bank
- ✅ Mounts easily in vehicle

---

## 📦 Hardware Requirements

### Required Components

| Item | Specification | Notes |
|------|--------------|-------|
| **Raspberry Pi** | Pi 4 or Pi 5, 2GB+ RAM | 4GB recommended for multiple trucks |
| **MicroSD Card** | 32GB+ Class 10/A1 | SanDisk High Endurance recommended |
| **Power Supply** | 5V 3A USB-C | Or 12V-to-USB adapter for truck |
| **T-Beam Supreme** | ESP32-based with LoRa | Your gateway device |
| **USB Cable** | USB-C to USB-C | For T-Beam to Pi connection |
| **Case** | Raspberry Pi case | Preferably with fan |

### Optional But Recommended

| Item | Purpose |
|------|---------|
| USB Battery Bank (20,000mAh+) | Backup power when truck is off |
| 12V-to-USB adapter | Power from truck 12V outlet |
| External USB WiFi adapter | Stronger hotspot signal |
| Short external LoRa antenna | Better range when Pi is inside cab |
| Velcro/mounting tape | Secure Pi to dashboard/console |
| Waterproof case | For extreme conditions |

---

## 🔧 Step-by-Step Installation

### Part 1: Prepare the Raspberry Pi

#### 1. Install Raspberry Pi OS

**On your laptop/desktop:**

```bash
# Download Raspberry Pi Imager
# https://www.raspberrypi.com/software/

# Flash SD card with:
# - OS: Raspberry Pi OS (64-bit) Lite (no desktop needed)
# - Configure SSH, WiFi, username in imager settings
# - Username: pi (or your choice)
# - Enable SSH
```

**Important Imager Settings:**
- ✅ Enable SSH
- ✅ Set username and password
- ✅ Configure WiFi (optional, for initial setup)
- ✅ Set hostname: `headspace-truck-1` (or similar)

#### 2. First Boot

```bash
# Insert SD card into Pi
# Power on
# Find Pi on network: ssh pi@headspace-truck-1.local
# Or use: nmap -sn 192.168.1.0/24 | grep -i raspberry

# SSH into Pi
ssh pi@headspace-truck-1.local
```

#### 3. Update System

```bash
# Update everything
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    mosquitto \
    mosquitto-clients \
    sqlite3 \
    net-tools \
    htop \
    screen

# Enable Mosquitto
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

---

### Part 2: Install HeadSpace

#### 1. Clone Repository

```bash
cd ~
git clone https://github.com/AbstruseGoose/HeadSpace.git
cd HeadSpace
```

#### 2. Run Automated Setup

```bash
# Make installation script executable
chmod +x scripts/install-pi.sh

# Run installation
./scripts/install-pi.sh

# This will:
# - Create Python virtual environment
# - Install all dependencies
# - Initialize database
# - Detect USB devices
```

#### 3. Verify Installation

```bash
# Activate virtual environment
source venv/bin/activate

# Test Python packages
python3 -c "import meshtastic, flask, paho.mqtt.client; print('✓ All packages installed')"

# Test database
sqlite3 data/headspace.db "SELECT name FROM sqlite_master WHERE type='table';"
```

---

### Part 3: Connect T-Beam Supreme

#### 1. Configure T-Beam Supreme

**Before connecting to Pi, configure the T-Beam from your laptop:**

```bash
# Install Meshtastic CLI (on your laptop)
pip install meshtastic

# Connect T-Beam to laptop via USB
# Configure as CLIENT device
meshtastic --set device.role CLIENT

# Set node name
meshtastic --set-owner "Truck-1"

# Configure position broadcast
meshtastic --set position.position_broadcast_secs 30

# Set GPS update interval
meshtastic --set position.gps_update_interval 30

# Save and reboot
meshtastic --reboot
```

**Key Settings for Truck Devices:**
- Role: `CLIENT` (not ROUTER - saves power)
- Position broadcast: 30-60 seconds
- TX power: HIGH (you're mobile, need good range)

#### 2. Connect to Raspberry Pi

```bash
# Plug T-Beam Supreme into Pi via USB
# Wait 5 seconds

# Verify connection
ls -la /dev/ttyUSB*
# Should show: /dev/ttyUSB0

# Test Meshtastic connection
meshtastic --info

# Should show node info, battery %, etc.
```

#### 3. Configure HeadSpace

```bash
cd ~/HeadSpace

# Check ingestion config
cat services/ingestion/config.yaml
```

**Should show:**
```yaml
meshtastic:
  connection_type: serial
  serial_port: auto  # Auto-detects /dev/ttyUSB0
  simulation_mode: false
```

**If multi-site, edit to add your truck ID:**
```bash
nano services/processing/config.yaml
```

```yaml
site:
  enabled: true
  id: "truck-1"
  name: "Truck 1"
  location:
    lat: 0.0  # Updated automatically from GPS
    lon: 0.0
```

---

### Part 4: Setup Auto-Start Services

#### Install Systemd Services

```bash
cd ~/HeadSpace

# Install services to start on boot
sudo ./scripts/install-services.sh

# Check status
sudo systemctl status headspace-*
```

#### Enable Read-Only Root (Optional but Recommended)

**Protects SD card from corruption if power is suddenly lost:**

```bash
# Install overlay filesystem
sudo raspi-config
# Navigate to: Performance Options > Overlay File System > Enable
# Reboot

# Note: You'll need to disable overlay to make changes later
# Use: sudo raspi-config -> Disable overlay -> Make changes -> Enable overlay
```

---

### Part 5: Create WiFi Hotspot

**So team members can access dashboard without internet:**

#### Option A: Using NetworkManager (Easier)

```bash
# Install NetworkManager
sudo apt install -y network-manager

# Create hotspot
sudo nmcli device wifi hotspot \
    ifname wlan0 \
    ssid "HeadSpace-Truck-1" \
    password "DogTracking2026"

# Make it start on boot
sudo nmcli connection modify Hotspot connection.autoconnect yes
```

#### Option B: Using hostapd (More Control)

```bash
# Install packages
sudo apt install -y hostapd dnsmasq

# Stop services while configuring
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Configure hostapd
sudo nano /etc/hostapd/hostapd.conf
```

Add:
```
interface=wlan0
driver=nl80211
ssid=HeadSpace-Truck-1
hw_mode=g
channel=6
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
# Configure dnsmasq
sudo nano /etc/dnsmasq.conf
```

Add:
```
interface=wlan0
dhcp-range=10.0.0.2,10.0.0.20,255.255.255.0,24h
domain=headspace.local
address=/headspace.local/10.0.0.1
```

```bash
# Configure static IP
sudo nano /etc/dhcpcd.conf
```

Add:
```
interface wlan0
static ip_address=10.0.0.1/24
nohook wpa_supplicant
```

```bash
# Enable and start
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
sudo reboot
```

**After reboot, you should see WiFi network: "HeadSpace-Truck-1"**

---

### Part 6: Test the System

#### 1. Start HeadSpace

```bash
# If not using systemd services
cd ~/HeadSpace
./start.sh

# If using systemd services
sudo systemctl start headspace-*
```

#### 2. Check Status

```bash
# View logs
journalctl -u headspace-ingest.service -f   # In one terminal
journalctl -u headspace-process.service -f  # In another terminal
journalctl -u headspace-dashboard.service -f # In another terminal

# Or use screen
screen -S headspace
# Ctrl+A, C to create new window
# Ctrl+A, N to switch windows
```

#### 3. Access Dashboard

**From phone/tablet connected to HeadSpace-Truck-1 WiFi:**
```
http://10.0.0.1:8080
```

**From another device on same network:**
```
http://TRUCK_PI_IP:8080
```

---

## 🔋 Power Configuration

### Option 1: USB Battery Bank (Recommended)

**Setup:**
1. Get 20,000mAh+ USB-C battery bank
2. Connect to Pi USB-C power port
3. Expected runtime: 12-16 hours continuous

**Advantages:**
- Survives power loss when truck is off
- Easy to charge/swap
- No vehicle wiring needed

### Option 2: 12V Truck Power

**Setup:**
1. Get 12V-to-USB-C adapter (3A rated)
2. Plug into truck 12V outlet
3. Pi powers on when truck starts

**Considerations:**
- ⚠️ Power loss protection needed (sudden shutdowns can corrupt SD card)
- ✅ Unlimited runtime when truck is running
- ✅ No battery to manage

**Recommended Setup:**
```
12V Outlet → 12V-to-USB converter → Battery Bank → Raspberry Pi
                                     (passthrough)
```
This gives you truck power + battery backup!

### Option 3: Hardwired with UPS

**For permanent installation:**
1. Wire to truck fuse box with inline fuse
2. Add UPS module (like LiFePO4 battery + charge controller)
3. Clean shutdown on power loss

---

## 📍 Mounting in Truck

### Dashboard Mount
- Use phone dashboard mount + Pi case
- Good visibility, easy access
- Can get hot in summer

### Under-Seat Mount
- Velcro Pi to flat surface under seat
- Protected from sun/theft
- Run USB cable to T-Beam on dash

### Console Mount
- Mount inside center console
- T-Beam antenna external
- Very secure, out of sight

### Glove Box Mount
- If glove box has space
- Must allow airflow (Pi generates heat)
- External antenna recommended

**Mounting Tips:**
- ✅ Allow airflow for cooling
- ✅ Secure against vibration (Velcro + zip ties)
- ✅ Keep T-Beam antenna vertical if possible
- ✅ Don't block Pi's SD card slot
- ⚠️ Avoid direct sunlight
- ⚠️ Keep away from heating vents

---

## 🎒 Field Operations

### Daily Startup Routine

1. **Turn on truck** (if using truck power)
2. **Wait ~30 seconds** for Pi to boot
3. **Connect to WiFi**: HeadSpace-Truck-1
4. **Open dashboard**: http://10.0.0.1:8080
5. **Verify nodes**: Check that your truck shows on map
6. **Check T-Beam battery**: Should show on dashboard

### During Operations

- Dashboard auto-updates as dogs move
- No interaction needed
- System logs all positions to database
- Works offline (no internet required)

### End of Day

- **Data persists** on SD card
- **Safe to power off** (especially with read-only root)
- **Backup data** (optional): Copy ~/HeadSpace/data/headspace.db

---

## 🛠️ Troubleshooting

### Pi Won't Boot
```bash
# Check power supply (needs 3A)
# Try different SD card
# Reflash OS
```

### Can't Find T-Beam
```bash
# Check USB connection
ls -la /dev/ttyUSB*

# Check Meshtastic
meshtastic --info

# Restart ingestion service
sudo systemctl restart headspace-ingest.service
```

### Dashboard Not Loading
```bash
# Check dashboard service
sudo systemctl status headspace-dashboard.service

# Check port
netstat -tlnp | grep 8080

# Test locally
curl http://localhost:8080
```

### No Position Updates
```bash
# Check ingestion logs
journalctl -u headspace-ingest.service -f

# Check MQTT
mosquitto_sub -h localhost -t 'headspace/#' -v

# Verify T-Beam GPS lock
meshtastic --info | grep -i gps
```

### WiFi Hotspot Not Working
```bash
# Check hostapd status
sudo systemctl status hostapd

# Check dnsmasq
sudo systemctl status dnsmasq

# View hostapd logs
journalctl -u hostapd -f

# Restart services
sudo systemctl restart hostapd dnsmasq
```

---

## 📊 Performance Optimization

### Reduce Boot Time
```bash
# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable hciuart
sudo systemctl disable avahi-daemon

# Use Lite OS (no desktop)
```

### Reduce Power Consumption
```bash
# Disable WiFi if using Ethernet
sudo iwconfig wlan0 txpower off

# Reduce CPU frequency
echo "arm_freq=1000" | sudo tee -a /boot/config.txt

# Disable HDMI (saves 25mA)
/usr/bin/tvservice -o

# Disable LEDs
echo 0 | sudo tee /sys/class/leds/led0/brightness
```

### Increase Reliability
```bash
# Use quality SD card (SanDisk High Endurance)
# Enable read-only root filesystem
# Add hardware watchdog
echo "dtparam=watchdog=on" | sudo tee -a /boot/config.txt

# Add watchdog daemon
sudo apt install watchdog
sudo systemctl enable watchdog
```

---

## ✅ Truck Deployment Checklist

**Hardware Setup:**
- [ ] Raspberry Pi 4/5 with 32GB+ SD card
- [ ] T-Beam Supreme configured as CLIENT
- [ ] USB cable connecting T-Beam to Pi
- [ ] Power solution (battery bank or 12V adapter)
- [ ] Pi mounted securely in truck
- [ ] T-Beam antenna positioned vertically

**Software Setup:**
- [ ] Raspberry Pi OS installed and updated
- [ ] HeadSpace installed and configured
- [ ] Systemd services enabled (auto-start)
- [ ] WiFi hotspot created and tested
- [ ] Site ID configured (truck-1, truck-2, etc.)
- [ ] Multi-site bridge setup (if applicable)

**Testing:**
- [ ] Dashboard accessible from phone
- [ ] Truck position shows on map
- [ ] Can see other nodes in mesh
- [ ] Survives power cycle
- [ ] Boots automatically
- [ ] Battery lasts expected duration

**Documentation:**
- [ ] WiFi password documented
- [ ] Dashboard URL noted
- [ ] Backup of SD card created
- [ ] Team trained on accessing dashboard

---

## 🚀 Quick Reference Card

**Print and laminate for truck:**

```
╔═══════════════════════════════════════╗
║     HeadSpace Truck System            ║
╠═══════════════════════════════════════╣
║                                       ║
║  WiFi: HeadSpace-Truck-1              ║
║  Password: DogTracking2026            ║
║                                       ║
║  Dashboard: http://10.0.0.1:8080     ║
║                                       ║
║  Startup: 30 seconds after power on   ║
║                                       ║
║  Troubleshooting:                     ║
║    - Reboot: Unplug power 10 seconds ║
║    - Check T-Beam USB connection      ║
║    - Verify WiFi hotspot active       ║
║                                       ║
║  Support: See truck binder            ║
║                                       ║
╚═══════════════════════════════════════╝
```

---

**Your truck is now a mobile tracking command center!** 🚚📡

Drive anywhere, boots automatically, works offline, team accesses dashboard via WiFi hotspot.
