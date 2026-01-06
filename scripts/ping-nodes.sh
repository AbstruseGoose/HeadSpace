#!/bin/bash
# HeadSpace - Ping nodes through Meshtastic device
# Run this script on your LOCAL machine (not in container)

echo "🔍 Pinging Meshtastic nodes..."
echo

# Method 1: Ping all nodes
echo "Method 1: Broadcasting ping to all nodes..."
meshtastic --ping

echo
echo "---"
echo

# Method 2: Get node list
echo "Method 2: Listing all nodes in mesh..."
meshtastic --nodes

echo
echo "---"
echo

# Method 3: Get detailed info
echo "Method 3: Getting device info..."
meshtastic --info

echo
echo "To ping a specific node:"
echo "  meshtastic --ping --dest !12345678"
echo
echo "To send a message:"
echo "  meshtastic --sendtext 'Hello from base station'"
