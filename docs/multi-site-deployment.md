# HeadSpace Multi-Site Deployment

**Track dogs across multiple locations separated by hundreds of miles!**

Connect multiple HeadSpace servers securely over the internet to create a unified tracking system across distant bases.

---

## 🌐 Architecture Overview

```
Base A (California)          Base B (Nevada)           Base C (Arizona)
┌─────────────────┐         ┌─────────────────┐       ┌─────────────────┐
│ Local LoRa Mesh │         │ Local LoRa Mesh │       │ Local LoRa Mesh │
│  Dogs, Trucks   │         │  Dogs, Trucks   │       │  Dogs, Trucks   │
│       ↓         │         │       ↓         │       │       ↓         │
│  HeadSpace      │         │  HeadSpace      │       │  HeadSpace      │
│  Server A       │         │  Server B       │       │  Server C       │
└────────┬────────┘         └────────┬────────┘       └────────┬────────┘
         │                           │                          │
         └───────────────────────────┼──────────────────────────┘
                        Secure VPN (WireGuard/Tailscale)
                                     │
                        MQTT Bridge (Port 1883)
                                     │
                    All servers exchange position data
                                     │
         ┌───────────────────────────┼──────────────────────────┐
         ▼                           ▼                          ▼
    Dashboard A                  Dashboard B               Dashboard C
    (sees all sites)            (sees all sites)          (sees all sites)
```

**Key Features:**
- ✅ Each site operates independently (offline capable)
- ✅ Data syncs automatically when internet available
- ✅ View dogs from ALL sites on any dashboard
- ✅ Secure VPN tunnel between sites
- ✅ MQTT bridge forwards position updates
- ✅ No single point of failure

---

## 🔐 Security Architecture

### VPN Layer (Choose One)

#### Option 1: Tailscale (Easiest)
- Zero-config mesh VPN
- Works through NAT/firewalls automatically
- Free for personal use (100 devices)
- Install on each Raspberry Pi

#### Option 2: WireGuard (Most Secure)
- Lightweight, fast
- Full control
- Requires port forwarding or static IPs

---

## 🚀 Setup Guide

### Step 1: Install Tailscale (Recommended)

**On each Raspberry Pi:**

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Start and authenticate
sudo tailscale up

# Get your Tailscale IP
tailscale ip -4
```

**Result:** All Raspberry Pis can now reach each other via private IPs like `100.x.x.x`

---

### Step 2: Configure Multi-Site MQTT Bridge

Each server needs to know about the other servers' MQTT brokers.

**Create bridge configuration on Server A:**

```bash
sudo nano /etc/mosquitto/conf.d/bridge.conf
```

Add:
```conf
# Bridge to Server B (Nevada)
connection bridge-to-server-b
address 100.64.0.2:1883  # Server B's Tailscale IP
topic headspace/# both 2
bridge_protocol_version mqttv311
try_private false
cleansession true
notifications false
bridge_attempt_unsubscribe false

# Bridge to Server C (Arizona)  
connection bridge-to-server-c
address 100.64.0.3:1883  # Server C's Tailscale IP
topic headspace/# both 2
bridge_protocol_version mqttv311
try_private false
cleansession true
notifications false
bridge_attempt_unsubscribe false
```

**Restart Mosquitto:**
```bash
sudo systemctl restart mosquitto
```

**Repeat on Server B and Server C** with their respective bridge configs.

---

### Step 3: Update HeadSpace Config for Multi-Site

**On each server, edit `services/processing/config.yaml`:**

```yaml
# Add site identifier
site:
  id: "base-a"  # Unique ID: base-a, base-b, truck-1, etc.
  name: "California Base"
  location:
    lat: 37.7749
    lon: -122.4194

# Existing config...
mqtt:
  broker: localhost
  port: 1883
  # ... rest of config
```

**This adds site context to all position updates.**

---

### Step 4: Update Dashboard to Show Multi-Site

**Edit `dashboard/config.json`:**

```json
{
  "multi_site": {
    "enabled": true,
    "show_site_labels": true,
    "site_colors": {
      "base-a": "#FF6B6B",
      "base-b": "#4ECDC4", 
      "base-c": "#45B7D1",
      "truck-1": "#FFA07A"
    }
  },
  "map": {
    "default_center": [39.8283, -98.5795],  # Center of USA
    "default_zoom": 5  # Zoomed out to see multiple states
  }
  // ... rest of config
}
```

---

### Step 5: Restart All Services

**On each server:**
```bash
sudo systemctl restart mosquitto
sudo systemctl restart headspace-*
```

---

## 🎯 How It Works

### When Dog at Base A Moves:

1. **Dog's T-Beam** broadcasts position to local LoRa mesh
2. **Server A** receives via Heltec V3 gateway
3. **Server A** publishes to local MQTT: `headspace/position`
4. **MQTT bridge** forwards to Server B and Server C
5. **All servers** receive and store the position
6. **All dashboards** show the dog (labeled "Base A")

### Result:
- **Dashboard at Base A**: Shows dogs from A, B, and C
- **Dashboard at Base B**: Shows dogs from A, B, and C  
- **Dashboard at Base C**: Shows dogs from A, B, and C
- **Truck E in Nevada**: Connects to any server, sees everything

---

## 📊 Data Flow Example

```
Base A Dog "Rex" moves:
  
  T-Beam (Rex) → LoRa Mesh → Server A
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
               MQTT Local   MQTT Bridge  Local Dashboard
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
               Server B                 Server C
                    │                       │
                    ▼                       ▼
             Dashboard B              Dashboard C
             
All dashboards now show Rex at his new position!
```

---

## 🔧 Advanced Configuration

### MQTT Authentication (Recommended for Production)

**Create password file:**
```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd headspace
# Enter password when prompted
```

**Update `/etc/mosquitto/mosquitto.conf`:**
```conf
allow_anonymous false
password_file /etc/mosquitto/passwd
```

**Update bridge config:**
```conf
connection bridge-to-server-b
address 100.64.0.2:1883
remote_username headspace
remote_password YOUR_PASSWORD
topic headspace/# both 2
```

---

### SSL/TLS Encryption (Maximum Security)

**Generate certificates:**
```bash
# On central server
openssl req -new -x509 -days 3650 -extensions v3_ca -keyout ca.key -out ca.crt
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3650
```

**Configure Mosquitto for TLS:**
```conf
listener 8883
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
require_certificate false
```

**Update HeadSpace config:**
```yaml
mqtt:
  broker: 100.64.0.2
  port: 8883
  use_tls: true
  ca_certs: /path/to/ca.crt
```

---

## 🏗️ Deployment Scenarios

### Scenario 1: Multi-State Search Operation
```
Nevada HQ:     Central server + dashboard
California:    Forward base + local server
Arizona:       Forward base + local server
Trucks:        T-Beam Supreme (connect to nearest server)
```

### Scenario 2: Redundant Backup
```
Primary Base:  Main HeadSpace server
Backup Base:   Redundant server (receives all data)
Mobile Truck:  Portable server (can operate standalone)
```

### Scenario 3: Hub and Spoke
```
Central Hub:   Master server (combines all data)
Spoke 1-N:     Field servers (send data to hub)
              ↓
        Centralized monitoring
```

---

## 🔍 Monitoring Multi-Site Status

**Create monitoring script:**

```bash
#!/bin/bash
# multi-site-status.sh

echo "=== HeadSpace Multi-Site Status ==="
echo

echo "Local Services:"
systemctl status headspace-* --no-pager | grep Active

echo
echo "Tailscale Status:"
tailscale status | grep -E "base-|truck-"

echo
echo "MQTT Bridge Status:"
mosquitto_sub -h localhost -t '$SYS/broker/connection/#' -C 10

echo
echo "Remote Sites Reachable:"
for ip in 100.64.0.2 100.64.0.3; do
    if timeout 1 nc -z $ip 1883; then
        echo "  ✅ $ip:1883 (MQTT reachable)"
    else
        echo "  ❌ $ip:1883 (MQTT not reachable)"
    fi
done
```

---

## 📱 Mobile Access

Team members can access ANY server's dashboard:

```
Via Tailscale:
  http://100.64.0.1:8080  (Server A)
  http://100.64.0.2:8080  (Server B)
  http://100.64.0.3:8080  (Server C)

All show the same unified view!
```

---

## 🛠️ Troubleshooting

### Check Bridge Status
```bash
mosquitto_sub -h localhost -t '$SYS/broker/clients/#' -v
```

### Test Remote MQTT
```bash
mosquitto_sub -h 100.64.0.2 -t 'headspace/#' -v
```

### View Bridge Logs
```bash
journalctl -u mosquitto -f | grep bridge
```

### Force MQTT Reconnect
```bash
sudo systemctl restart mosquitto
```

---

## 💡 Best Practices

1. **Each site has unique ID** - Prevents node ID conflicts
2. **Tailscale for simplicity** - Handles NAT/firewalls automatically
3. **MQTT authentication** - Even on VPN, add passwords
4. **Monitor bandwidth** - Position updates are small but add up
5. **Test offline mode** - Each site should work independently
6. **Regular database syncs** - Backup critical position data
7. **Site-aware alerts** - Know which base sent an alert

---

## 📊 Performance Considerations

**Network Usage:**
- Position update: ~200 bytes
- Update every 10s = 20 bytes/s per node
- 50 nodes × 3 sites = 3 KB/s total
- Very minimal bandwidth!

**Latency:**
- Local: < 1 second
- Cross-site: 2-5 seconds (VPN + internet)
- Still real-time for search operations

---

## ✅ Multi-Site Checklist

- [ ] Install Tailscale on all Raspberry Pis
- [ ] Configure MQTT bridges between sites
- [ ] Add site ID to each server config
- [ ] Update dashboard for multi-site view
- [ ] Test connectivity between sites
- [ ] Configure MQTT authentication
- [ ] Setup monitoring/alerts
- [ ] Test offline fallback mode
- [ ] Document site-specific IPs/configs
- [ ] Train team on multi-site dashboard

---

**With this setup, you can track dogs from Base A in California while sitting in Truck E in Nevada!**

The mesh is distributed, resilient, and secure. Each site operates independently but shares data globally.
