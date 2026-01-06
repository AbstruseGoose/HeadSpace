# Hardware Setup Guide

**Complete guide for configuring your Meshtastic devices for HeadSpace tracking**

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Your Hardware](#your-hardware)
3. [How It All Works](#how-it-all-works)
4. [Flashing Meshtastic Firmware](#flashing-meshtastic-firmware)
5. [Configuring Each Device Type](#configuring-each-device-type)
6. [Viewing Live Tracking](#viewing-live-tracking)
7. [Step-by-Step Setup](#step-by-step-setup)
8. [Troubleshooting](#troubleshooting)

---

## System Overview

### What HeadSpace Does

**HeadSpace is a tracking server that runs on a computer** (like a laptop in your truck or a Raspberry Pi at base camp). It:

1. **Receives GPS positions** from all your Meshtastic devices over the LoRa mesh
2. **Stores the location history** (breadcrumb trails)
3. **Detects when dogs stop moving** (dwell detection)
4. **Shows everything on a web dashboard** with a live map

### What You'll See

- **Live map** showing all nodes (dogs, trucks, team members, base stations)
- **Breadcrumb trails** showing where dogs have been
- **Node status**: LIVE (recently heard), STALE (few minutes old), LOST (not heard in a while)
- **Battery levels** and signal strength for each device
- **Dwell alerts** when a dog stays in one spot too long

---

## Your Hardware

### What You Have

| Device Type | Hardware | Role | Quantity | GPS? | Screen? |
|------------|----------|------|----------|------|---------|
| **Base Stations** | Heltec V3 | Fixed mesh routers | Multiple | Yes (has GPS) | Yes (OLED) |
| **Team Leaders** | T-Beam Supreme | Handheld tracking | Multiple | Yes | Yes |
| **Vehicles** | T-Beam Supreme | Truck-mounted | Multiple | Yes | Yes |
| **Dogs (with screen)** | T-Beam | Dog collar mounted | Some | Yes | Yes (optional) |
| **Dogs (no screen)** | T-Beam | Dog collar mounted | Some | Yes | No |

**Key Point**: All your devices run the **same Meshtastic firmware** - you just configure them differently!

---

## How It All Works

### The Complete Picture

```
┌─────────────────────────────────────────────────────────────┐
│                    LoRa Mesh Network                         │
│                                                              │
│  🐕 Dog T-Beams  →  📡 Base Stations  →  🚚 Truck/Handhelds │
│     (send GPS)       (route packets)       (receive GPS)     │
│                                                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ USB connection (Serial)
                         │
                         ▼
              ┌─────────────────────┐
              │   Gateway Device    │ ← ONE device connected to computer
              │  (any of yours)     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   HeadSpace Server  │ ← Runs on laptop/computer
              │   (the software we  │
              │    built above)     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Web Dashboard     │ ← View in browser
              │   (live map)        │
              └─────────────────────┘
```

### Two Ways to Track

#### 1. **Direct Viewing (No Computer Needed)**

Any device with a screen (Heltec V3, T-Beam Supreme, T-Beam with screen) can show:
- Last known position of other nodes (on the screen)
- Distance and direction to other nodes
- Battery levels

**Limitations:**
- Only shows data on the small OLED screen
- No map view
- No history/breadcrumbs
- No fancy dashboard

#### 2. **HeadSpace Dashboard (Requires Computer)**

Connect ONE device to a laptop/computer running HeadSpace:
- **Full map** with all nodes
- **Breadcrumb trails** showing paths
- **Historical data**
- **Dwell detection**
- **Multiple people can view** the dashboard at once

**This is what we built above!**

---

## Flashing Meshtastic Firmware

### Important: You DON'T Write Custom Code!

All your devices run **official Meshtastic firmware**. You don't need to write or compile anything!

### How to Flash

#### Option 1: Web Flasher (Easiest)

1. Go to https://flasher.meshtastic.org/
2. Connect device via USB
3. Click "Flash" and select your device type:
   - **Heltec V3** → "HELTEC_WIRELESS_TRACKER_V1_0"
   - **T-Beam Supreme** → "TBEAM_SUPREME"
   - **T-Beam** → "TBEAM" (select version based on your hardware)
4. Choose latest stable firmware
5. Click "Flash"
6. Wait 2-3 minutes

#### Option 2: Meshtastic CLI

```bash
# Install Meshtastic CLI
pip install meshtastic

# Flash device (auto-detects)
meshtastic --flash-only
```

#### Option 3: Using a Phone

1. Install **Meshtastic app** (iOS or Android)
2. Connect to device via Bluetooth
3. Go to Settings → Firmware → Update Firmware

---

## Configuring Each Device Type

After flashing, you need to **configure** each device for its role.

### Configuration Methods

You have 3 ways to configure:

1. **Meshtastic CLI** (command line) - Best for bulk setup
2. **Meshtastic App** (phone) - Best for quick changes
3. **Python API** (scripting) - Best for advanced automation

I'll show CLI examples (works in terminal):

---

### 1. Base Stations (Heltec V3)

**Role**: Permanent, always-on mesh routers that extend coverage.

```bash
# Connect device via USB, then:

# Set node info
meshtastic --set-owner "Base-North"
meshtastic --set-owner-short "BNTH"

# Configure as ROUTER
meshtastic --set device.role ROUTER

# Enable GPS (needed for position beacons)
meshtastic --set position.gps_enabled true
meshtastic --set position.gps_update_interval 300
meshtastic --set position.position_broadcast_secs 900  # Every 15 min

# Power settings (mains powered)
meshtastic --set power.is_power_saving false

# Screen settings
meshtastic --set display.screen_on_secs 0  # Always on
meshtastic --set display.auto_screen_carousel_secs 10

# Optional: Increase transmit power (if you have external antenna)
meshtastic --set lora.tx_power 30  # Max for your region

# Save
meshtastic --set device.is_managed false
```

**Important Settings:**
- `device.role = ROUTER` → Stays awake, routes packets
- GPS broadcasts every 15 minutes (not needed often for fixed stations)
- Screen always on (mains powered)

---

### 2. Team Leader Handhelds (T-Beam Supreme)

**Role**: Mobile tracking displays that show team and dog positions.

```bash
# Set node info
meshtastic --set-owner "TeamLead-Alpha"
meshtastic --set-owner-short "TLA"

# Configure as CLIENT
meshtastic --set device.role CLIENT

# GPS settings - frequent updates
meshtastic --set position.gps_enabled true
meshtastic --set position.gps_update_interval 30
meshtastic --set position.position_broadcast_secs 60  # Every minute

# Smart position for battery saving
meshtastic --set position.position_flags 3  # Smart positioning

# Power settings
meshtastic --set power.is_power_saving false  # Stay awake when needed
meshtastic --set power.on_battery_shutdown_after_secs 3600  # 1 hour

# Screen settings
meshtastic --set display.screen_on_secs 60  # Turn off after 60s
meshtastic --set display.auto_screen_carousel_secs 5
```

**Important Settings:**
- `device.role = CLIENT` → Normal power usage, relays packets
- GPS updates every 30 seconds, broadcasts every minute
- Screen turns off after 60 seconds to save battery

---

### 3. Vehicle/Truck Nodes (T-Beam Supreme)

**Role**: Mobile tracking nodes with external power (vehicle battery).

```bash
# Set node info
meshtastic --set-owner "Truck-1"
meshtastic --set-owner-short "TRK1"

# Configure as ROUTER_CLIENT (helps extend mesh while mobile)
meshtastic --set device.role ROUTER_CLIENT

# GPS settings - very frequent (vehicle powered)
meshtastic --set position.gps_enabled true
meshtastic --set position.gps_update_interval 20
meshtastic --set position.position_broadcast_secs 30  # Every 30 seconds

# Power settings (external power)
meshtastic --set power.is_power_saving false

# Screen settings
meshtastic --set display.screen_on_secs 0  # Always on (vehicle powered)
meshtastic --set display.auto_screen_carousel_secs 5
```

**Important Settings:**
- `device.role = ROUTER_CLIENT` → Acts as mobile router + client
- GPS updates every 20 seconds (externally powered)
- Screen always on

---

### 4. Dog Trackers (T-Beam with/without screen)

**Role**: High-priority tracking nodes that send frequent GPS updates.

```bash
# Set node info
meshtastic --set-owner "Dog-Rex"
meshtastic --set-owner-short "REX"

# Configure as TRACKER (optimized for GPS tracking)
meshtastic --set device.role TRACKER

# GPS settings - VERY frequent updates
meshtastic --set position.gps_enabled true
meshtastic --set position.gps_update_interval 10  # Every 10 seconds
meshtastic --set position.position_broadcast_secs 20  # Broadcast every 20s

# Smart positioning (saves battery)
meshtastic --set position.position_flags 7  # All smart features

# Power settings - aggressive battery saving
meshtastic --set power.is_power_saving true
meshtastic --set power.wait_bluetooth_secs 60  # BT timeout
meshtastic --set power.ls_secs 300  # Light sleep after 5 min idle

# Screen settings (if screen present)
meshtastic --set display.screen_on_secs 30  # Quick timeout
meshtastic --set display.auto_screen_carousel_secs 3

# Optional: Set as high priority node
meshtastic --set telemetry.device_update_interval 900  # Every 15 min
```

**Important Settings:**
- `device.role = TRACKER` → Optimized for GPS tracking
- GPS updates every 10-20 seconds when moving
- Aggressive power saving (battery powered)
- If no screen, display settings are ignored

**For T-Beams WITHOUT screens:**
Same settings, but display config is ignored. The device still works perfectly!

---

## Viewing Live Tracking

### Method 1: On Device Screens (No Computer)

**What you see on the OLED screen:**

On any device with a screen (press button to cycle through screens):

1. **Node List Screen**:
   ```
   📡 Nodes (8)
   🐕 REX    87%  45m ←
   🐕 LUNA   92%  120m ↗
   👤 TLA    78%  5m →
   🚚 TRK1   --   2km ↑
   ```

2. **Map Screen** (if device has GPS):
   - Shows your position
   - Distance/bearing to other nodes
   - Signal strength

3. **Messages Screen**:
   - Text messages from other nodes

**Limitations:**
- Small screen, limited info
- No history
- No fancy map

---

### Method 2: HeadSpace Dashboard (WITH Computer)

This is the **main tracking solution** we built!

#### Setup

1. **Choose ONE gateway device** (any of your devices - a base station works well)
2. **Connect it to your laptop/computer** via USB
3. **Run HeadSpace** (the software we created above)
4. **Open browser** to http://localhost:8080

#### What You See

```
╔════════════════════════════════════════════════════════════╗
║  HeadSpace Dashboard                    [Battery][Time]   ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  🗺️ LIVE MAP (Leaflet/OpenStreetMap)                     ║
║                                                            ║
║    🐕 Dog-Rex (LIVE) ────────┐ (breadcrumb trail)        ║
║                               │                            ║
║    🐕 Dog-Luna (LIVE) ────────┤                           ║
║                               │                            ║
║    🚚 Truck-1 (LIVE)          │                           ║
║                               │                            ║
║    📡 Base-North (LIVE)       │                           ║
║                               │                            ║
║  [+] [-] [⟲] [⊡ Fit All]     │                           ║
║                                                            ║
╠════════════════════════════════════════════════════════════╣
║  NODE LIST                                                 ║
║  🐕 Dog-Rex      LIVE   87%  -89dBm  12s ago   [Trail]   ║
║  🐕 Dog-Luna     LIVE   92%  -76dBm   8s ago   [Trail]   ║
║  👤 TeamLead-A   LIVE   78%  -82dBm  23s ago   [Trail]   ║
║  🚚 Truck-1      LIVE   --   -68dBm  15s ago   [Trail]   ║
║  📡 Base-North   STALE  --   -91dBm  7m ago    [ Off ]   ║
║  📡 Base-South   LOST   --   ---     45m ago   [ Off ]   ║
╚════════════════════════════════════════════════════════════╝
```

**Features:**
- **Live map** with all nodes
- **Breadcrumb trails** (toggle per node)
- **Battery %**, **Signal strength** (RSSI)
- **Time since last update**
- **Status colors**: 🟢 LIVE, 🟡 STALE, 🔴 LOST
- **Dwell markers** (📍 when dog stops)
- **Click node** to zoom to it

---

## Step-by-Step Setup

### Phase 1: Flash All Devices

1. Flash all devices with Meshtastic firmware (web flasher)
2. Test each device powers on and shows Meshtastic screen

### Phase 2: Configure Mesh Settings (All Devices)

**CRITICAL: All devices must use the same channel settings!**

```bash
# On EACH device, set the same channel:

# Default channel (or create custom)
meshtastic --ch-index 0 --ch-set name "MyTeam"
meshtastic --ch-index 0 --ch-set psk random  # Or use same PSK for all

# Regional settings (CRITICAL - set for your region!)
meshtastic --set lora.region US  # Or EU868, AU915, etc.

# LoRa settings (same on all)
meshtastic --set lora.modem_preset LONG_FAST  # Good balance
```

**All devices MUST have:**
- Same `lora.region`
- Same channel name and PSK
- Same `modem_preset`

### Phase 3: Configure Device Roles

Go through each device and configure per the sections above:
- Base stations → ROUTER
- Team leads → CLIENT
- Trucks → ROUTER_CLIENT
- Dogs → TRACKER

### Phase 4: Set Up HeadSpace Server

1. Choose one device as gateway (base station works well)
2. Connect to laptop/computer via USB
3. Edit `/workspaces/HeadSpace/services/ingestion/config.yaml`:
   ```yaml
   meshtastic:
     connection_type: serial
     serial_port: auto  # Or /dev/ttyUSB0, /dev/ttyACM0, COM3, etc.
   ```

4. Start services (see [deployment.md](deployment.md)):
   ```bash
   # Terminal 1
   python services/ingestion/ingest.py
   
   # Terminal 2
   python services/processing/processor.py
   
   # Terminal 3
   python dashboard/server.py
   ```

5. Open browser to http://localhost:8080

### Phase 5: Test the System

1. **Check nodes appear** on dashboard
2. **Walk around with a dog tracker** and verify trail appears
3. **Leave a dog tracker stationary** for 2 minutes and verify dwell alert
4. **Check battery levels** update
5. **Test mesh range** by moving devices apart

---

## Viewing from Trucks and Handhelds

You have **two options**:

### Option 1: Dashboard in Browser (Recommended)

**In the truck:**
1. Run HeadSpace on a laptop or Raspberry Pi in the truck
2. Connect ONE device (truck's T-Beam Supreme) via USB as gateway
3. Open dashboard on laptop screen
4. **Optional**: Set up WiFi hotspot so team members can view dashboard on their phones

**Advantages:**
- Full map view
- Breadcrumb trails
- Multiple people can view at once
- Historical data

### Option 2: Device Screen Only (Basic)

**On handhelds:**
1. Just carry the T-Beam Supreme
2. Press button to cycle through screens
3. View node list showing distances to dogs

**Advantages:**
- No laptop needed
- Works anywhere in mesh range
- Simple and rugged

**Disadvantages:**
- Small screen
- Limited information
- No map

### Option 3: Both! (Best Setup)

- **In truck**: Laptop with HeadSpace dashboard (full tracking)
- **On handhelds**: T-Beam Supreme screens (quick reference)
- Everyone can see tracking data on whatever device they have

---

## Practical Deployment Example

### Scenario: Search Operation with 3 Dogs

**Equipment:**
- 2× Heltec V3 (base stations at command post)
- 3× T-Beam (dogs: Rex, Luna, Max)
- 2× T-Beam Supreme (team leads: Alpha, Bravo)
- 1× T-Beam Supreme (truck)
- 1× Laptop (in truck, running HeadSpace)

**Setup:**

1. **Command Post**:
   - Set up 2× Heltec V3 as base stations (ROUTER role)
   - Power from generator or battery bank
   - Positioned for good coverage

2. **In Truck**:
   - Laptop running HeadSpace
   - Truck's T-Beam Supreme connected via USB (gateway)
   - Dashboard open in browser
   - Power from vehicle 12V

3. **Team Leads**:
   - Each carries T-Beam Supreme (CLIENT role)
   - Can view dog positions on screen
   - Can send messages to each other

4. **Dogs**:
   - Each wears T-Beam (TRACKER role)
   - Broadcasts GPS every 20 seconds
   - Battery lasts 8-12 hours (depends on activity)

**During Operation:**
- Dashboard shows all 3 dogs in real-time
- Team leads can see distances on their screens
- Command post (truck) has full situational awareness
- Breadcrumb trails show where each dog has been
- Dwell alerts if any dog stops moving

---

## Important Meshtastic Concepts

### Mesh Routing

- Packets hop through multiple devices to reach destination
- Each hop adds ~1-3 seconds of latency
- Maximum 3 hops by default (configurable)
- More routers = better coverage

### Update Frequency vs Battery Life

**Faster updates = More battery drain**

| Update Interval | Battery Life (approx) | Use Case |
|----------------|---------------------|----------|
| 10-20 seconds | 6-10 hours | Dogs (critical tracking) |
| 30-60 seconds | 12-24 hours | Team leads (active) |
| 2-5 minutes | 24-48 hours | Team leads (standby) |
| 15+ minutes | Days | Base stations (but use external power!) |

### Position Broadcast vs GPS Update

- **GPS Update Interval**: How often device queries GPS chip
- **Position Broadcast**: How often device sends position over mesh

Set GPS update FASTER than broadcast:
```bash
meshtastic --set position.gps_update_interval 10
meshtastic --set position.position_broadcast_secs 20
# Queries GPS every 10s, broadcasts every 20s
```

---

## Troubleshooting

### Device Won't Flash

- Try different USB cable (many are power-only!)
- Press and hold BOOT button while connecting
- Use USB 2.0 port (USB 3.0 sometimes has issues)
- Try web flasher: https://flasher.meshtastic.org/

### Devices Not Seeing Each Other

1. **Check same channel**:
   ```bash
   meshtastic --info | grep -A 5 "Channels"
   ```
   All devices must have same settings!

2. **Check region**:
   ```bash
   meshtastic --get lora.region
   ```
   All must match your physical location!

3. **Check range**: LoRa range varies:
   - Urban: 1-3 km
   - Suburban: 3-10 km
   - Rural/open: 10-20 km
   - With good antennas: 20-50+ km

### HeadSpace Not Receiving Data

1. **Check gateway connection**:
   ```bash
   meshtastic --info
   # Should show device info
   ```

2. **Check MQTT**:
   ```bash
   mosquitto_sub -h localhost -t 'headspace/#' -v
   # Should see messages when positions arrive
   ```

3. **Check logs**:
   - Ingestion service: Look for "Received position from..."
   - Processing service: Look for "Stored GPS point for..."

### Poor Battery Life

1. **Enable power saving**:
   ```bash
   meshtastic --set power.is_power_saving true
   ```

2. **Reduce GPS frequency**:
   ```bash
   meshtastic --set position.gps_update_interval 30
   meshtastic --set position.position_broadcast_secs 60
   ```

3. **Use smart positioning**:
   ```bash
   meshtastic --set position.position_flags 7
   ```

4. **Reduce screen time**:
   ```bash
   meshtastic --set display.screen_on_secs 10
   ```

---

## Quick Reference Commands

### Get Device Info
```bash
meshtastic --info
```

### See All Settings
```bash
meshtastic --get all
```

### Reset to Factory Defaults
```bash
meshtastic --factory-reset
```

### Set Owner Name
```bash
meshtastic --set-owner "Dog-Rex"
meshtastic --set-owner-short "REX"
```

### Configure GPS
```bash
meshtastic --set position.gps_enabled true
meshtastic --set position.gps_update_interval 20
meshtastic --set position.position_broadcast_secs 30
```

### Set Device Role
```bash
meshtastic --set device.role TRACKER     # Dogs
meshtastic --set device.role CLIENT      # Team leads
meshtastic --set device.role ROUTER      # Base stations
meshtastic --set device.role ROUTER_CLIENT  # Trucks
```

### Check Battery
```bash
meshtastic --info | grep -i battery
```

### Send Test Message
```bash
meshtastic --sendtext "Testing from Rex"
```

---

## Next Steps

1. **Flash all devices** with Meshtastic firmware
2. **Configure mesh settings** (same on all devices!)
3. **Configure device roles** (per device type)
4. **Test mesh connectivity** (all devices should see each other)
5. **Set up HeadSpace server** (in truck or at base)
6. **Deploy and test** in the field!

---

## Additional Resources

- **Meshtastic Documentation**: https://meshtastic.org/docs/
- **Meshtastic Web Flasher**: https://flasher.meshtastic.org/
- **Meshtastic Discord**: https://discord.gg/meshtastic (very helpful community!)
- **Python CLI Guide**: https://meshtastic.org/docs/software/python/cli/

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-04
