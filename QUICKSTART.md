# Quick Start: Understanding Your Setup

## What You're Building

You have a **dog tracking system** using LoRa mesh radios. Here's what happens:

```
┌─────────────────────────────────────────────────────────────────┐
│                  YOUR PHYSICAL SETUP                             │
└─────────────────────────────────────────────────────────────────┘

STEP 1: Devices talk to each other via LoRa mesh
═════════════════════════════════════════════════

     🐕 Dog T-Beam          🐕 Dog T-Beam          🐕 Dog T-Beam
     "Rex" (TRACKER)        "Luna" (TRACKER)      "Max" (TRACKER)
     GPS broadcasts         GPS broadcasts        GPS broadcasts
     every 20 seconds       every 20 seconds      every 20 seconds
            │                      │                     │
            └──────────┬───────────┴─────────────────────┘
                       │
                       │ LoRa mesh (wireless)
                       │
            ┌──────────┴───────────┬─────────────────────┐
            │                      │                     │
            ▼                      ▼                     ▼
     📡 Base Station        👤 Team Lead         🚚 Truck Node
     Heltec V3 (ROUTER)    T-Beam Supreme       T-Beam Supreme
     Routes packets        Shows distances      Shows distances
     + can view on         on screen           + runs gateway
     screen


STEP 2: One device connects to computer as "gateway"
════════════════════════════════════════════════════

     🚚 Truck's T-Beam Supreme ──[USB cable]──▶ 💻 Laptop in truck
     (gateway device)                            Running HeadSpace


STEP 3: HeadSpace shows everything on a map
═══════════════════════════════════════════

     💻 Laptop Browser: http://localhost:8080
     
     ┌─────────────────────────────────────────┐
     │  🗺️ Live Map                            │
     │                                         │
     │  🐕 Rex    ────┐  (breadcrumb trail)   │
     │               │                         │
     │  🐕 Luna   ────┤                        │
     │               │                         │
     │  🐕 Max    ────┘                        │
     │                                         │
     │  🚚 Truck-1 (you are here)              │
     │                                         │
     │  Battery: 87%  Signal: -89dBm  12s ago │
     └─────────────────────────────────────────┘
```

---

## The Two Parts

### Part 1: Meshtastic Firmware (On Your Devices)

- **What it is**: Open-source firmware you flash onto your T-Beams and Heltecs
- **What it does**: Makes devices talk to each other via LoRa mesh
- **You need to**: Flash it once, then configure each device
- **No coding required**: Use web flasher or command-line tool

### Part 2: HeadSpace Server (On Your Laptop)

- **What it is**: The Python software we're building in this project
- **What it does**: Receives data from ONE gateway device and shows it on a web dashboard
- **You need to**: Run it on a laptop/computer
- **This is what we're creating above!**

---

## Simple Explanation

### Without HeadSpace (Just Meshtastic)

1. Flash Meshtastic on all devices
2. They talk to each other
3. Each screen shows basic info (distance, battery, etc.)
4. **Pro**: No computer needed
5. **Con**: Tiny screen, no map, no history

### With HeadSpace (Meshtastic + HeadSpace)

1. Flash Meshtastic on all devices (same as above)
2. They talk to each other (same as above)
3. Connect ONE to laptop running HeadSpace
4. **Pro**: Full map, breadcrumb trails, history, multiple viewers
5. **Con**: Need laptop/computer

---

## Your Specific Hardware

| What You Have | Meshtastic Role | HeadSpace Config | Screen? |
|---------------|----------------|------------------|---------|
| **Heltec V3** (base stations) | `ROUTER` | `node_type: base_station` | Yes (OLED) |
| **T-Beam Supreme** (team/trucks) | `CLIENT` or `ROUTER_CLIENT` | `node_type: team_lead` or `truck` | Yes |
| **T-Beam** (dogs with screen) | `TRACKER` | `node_type: dog` | Yes |
| **T-Beam** (dogs no screen) | `TRACKER` | `node_type: dog` | No (still works!) |

---

## What "Code to Flash" Means

**You DON'T write custom code!** You flash **Meshtastic firmware** (pre-built by Meshtastic project).

### Firmware for Each Device

All your devices use **the same Meshtastic firmware**, just configured differently:

1. **Heltec V3** → Flash "HELTEC_WIRELESS_TRACKER_V1_0" variant
2. **T-Beam Supreme** → Flash "TBEAM_SUPREME" variant
3. **T-Beam** → Flash "TBEAM" variant (check your version: 0.7, 1.0, 1.1, etc.)

After flashing, you **configure** each device via command line or phone app.

---

## How to Track Dogs from Trucks and Handhelds

### Option 1: Look at the Device Screen (Simple)

Any device with a screen shows:
- List of other nodes
- Distance and direction to each
- Battery levels

**Press button on device to cycle through screens.**

### Option 2: Use HeadSpace Dashboard (Advanced)

1. Run HeadSpace on laptop in truck
2. Connect truck's T-Beam Supreme to laptop via USB
3. Open browser to http://localhost:8080
4. See full map with all dogs, trails, etc.

### Option 3: Both! (Recommended)

- **In truck**: Laptop with dashboard (full tracking)
- **On foot**: Look at handheld screen (quick reference)

---

## Real-World Example

You're in a truck with your laptop. You have 3 dogs in the field (Rex, Luna, Max).

**What happens:**

1. Dog "Rex" has a T-Beam on his collar
2. Rex's T-Beam gets GPS fix and broadcasts position every 20 seconds
3. Position packet travels through mesh (maybe hops through base station)
4. Your truck's T-Beam Supreme receives the packet
5. Truck's T-Beam is connected to laptop via USB
6. HeadSpace software on laptop receives the data
7. Dashboard in browser updates showing Rex's new position
8. You see a dot on the map labeled "🐕 Rex" with a trail showing where he's been

**On your handheld T-Beam Supreme:**
- Screen shows "REX - 450m NE ↗"
- You can walk toward him following the bearing

---

## Next Steps

1. **Read [Hardware Setup Guide](docs/hardware-setup.md)** for detailed flashing and configuration
2. **Flash all devices** using https://flasher.meshtastic.org/
3. **Configure roles** using command line (see hardware guide)
4. **Test mesh** (all devices should see each other)
5. **Set up HeadSpace** (connect gateway, run software)
6. **Go track some dogs!**

---

## Quick Links

- 📖 **[Hardware Setup Guide](docs/hardware-setup.md)** ← START HERE
- 🏗️ **[Architecture](docs/architecture.md)** - How it all works
- 📊 **[Data Model](docs/data-model.md)** - JSON schemas and database
- 🚀 **[Deployment Guide](docs/deployment.md)** - Running the software

---

## Questions?

**Q: Do I need to learn to code?**  
A: No! Just flash firmware and configure devices. HeadSpace is already written.

**Q: Can I track dogs without a laptop?**  
A: Yes, but only on small device screens. HeadSpace adds the nice dashboard.

**Q: How far does LoRa reach?**  
A: 1-3km urban, 10-20km rural, 50km+ with good antennas and line-of-sight.

**Q: How long does battery last?**  
A: Dogs (T-Beam tracking every 20s): ~6-10 hours. Team leads: ~12-24 hours.

**Q: Can multiple people view the dashboard?**  
A: Yes! Set up WiFi hotspot in truck and share the URL.

**Q: What if devices lose connection?**  
A: Dashboard shows "STALE" or "LOST" status. Last known position stays on map.
