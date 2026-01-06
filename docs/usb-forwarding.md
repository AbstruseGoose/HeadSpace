# Instructions for TCP Connection Method

## On Your Local PC (where Heltec V3 is connected):

### 1. Install socat (if not installed)
```bash
# Linux
sudo apt install socat

# macOS
brew install socat

# Windows (use WSL or install from https://sourceforge.net/projects/unix-utils/)
```

### 2. Forward USB serial to TCP
```bash
# Find your device (usually /dev/ttyUSB0 on Linux, /dev/cu.usbserial-* on macOS)
ls /dev/tty* | grep -i usb

# Forward to TCP port 4403 (default Meshtastic port)
socat TCP-LISTEN:4403,reuseaddr,fork FILE:/dev/ttyUSB0,b115200,raw,echo=0
```

### 3. Find your PC's IP address
```bash
# Linux/macOS
ip addr show | grep inet

# Or
ifconfig | grep inet
```

## Then in HeadSpace Config:

Edit `services/ingestion/config.yaml`:
```yaml
meshtastic:
  connection_type: tcp
  tcp_host: YOUR_PC_IP_ADDRESS  # e.g., 192.168.1.100
  tcp_port: 4403
  simulation_mode: false
```

Then restart the ingestion service!
