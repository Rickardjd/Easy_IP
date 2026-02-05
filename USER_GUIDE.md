# Easy IP Setup Tool - User Guide

A cross-platform Python TUI (Terminal User Interface) for discovering and managing i-PRO IP cameras and recorders on your network.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Interface](#main-interface)
3. [Scanning for Devices](#scanning-for-devices)
4. [Managing Groups](#managing-groups)
5. [Monitoring Devices](#monitoring-devices)
6. [Setup & Configuration](#setup--configuration)
7. [File Operations](#file-operations)
8. [Exporting Data](#exporting-data)
9. [Keyboard Shortcuts](#keyboard-shortcuts)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Requirements

- Python 3.8 or higher
- Required packages (install via `pip install -r requirements.txt`):
  - textual
  - rich

### Running the Application

```bash
python easy_ip_tui.py
```

Or on Windows, double-click `easy_ip.bat`.

---

## Main Interface

When you launch the application, you'll see:

```
+------------------------------------------------------------------+
|  i-PRO Easy IP Setup - Untitled Site                             |
+------------------------------------------------------------------+
| [File] [Scan] [Monitor] [Groups] [Setup]  MONITORING: STOPPED    |
+------------------------------------------------------------------+
|                                                                  |
|  No groups defined. Use Groups > Add New Group to create one.    |
|                                                                  |
+------------------------------------------------------------------+
| [MONITORING: OFF] | Devices: 0 (Online: 0, Offline: 0)           |
+------------------------------------------------------------------+
```

### Menu Bar
- **File** - Load/save site configurations
- **Scan** - Discover devices on the network
- **Monitor** - Start/stop continuous monitoring
- **Groups** - Manage device groups
- **Setup** - Configure application settings

### Status Bar (Bottom)
- Monitoring status (ON/OFF)
- Device counts (total, online, offline)
- Last scan timestamp
- Next scan timestamp (when monitoring is active)

---

## Scanning for Devices

### Automatic Network Scan

1. Click **Scan** or press `F2`
2. Select **Scan Network (Auto)**
3. Adjust the timeout if needed (default: 3 seconds)
4. Wait for the scan to complete

The scan sends a broadcast packet to discover all i-PRO cameras and recorders on your local network.

### First-Time Scanning

If you scan before creating any groups, the application will automatically create a **"Default"** group for you. This ensures you can immediately add discovered devices.

### Scan Results

After scanning, you'll see:
- Number of devices found
- New devices (not yet tracked)
- Already tracked devices

Select which devices to add and choose a target group.

### Manual Device Addition

If a device isn't discovered automatically:

1. Click **Scan** > **Manual Add Device...**
2. Enter device details:
   - Device Name
   - MAC Address (format: aa:bb:cc:dd:ee:ff)
   - IP Address
   - Model (optional)
3. Select target group
4. Click **Add**

---

## Managing Groups

Groups help organize your devices by location, function, or any criteria you choose.

### Creating a Group

1. Click **Groups** or press `F4`
2. Select **Add New Group...**
3. Enter a group name
4. Click **Create**

### Removing a Group

1. Click **Groups** > **Remove Group...**
2. Select the group to remove
3. Click **Remove**

> **Warning**: Removing a group deletes all devices in that group!

### Moving Devices Between Groups

1. Click **Groups** > **Move Device...**
2. Select the device to move
3. Select the target group
4. Click **Move**

### Group Status Colors

Groups are color-coded based on device status:
- **Green** - All devices online
- **Red** - All devices offline
- **Orange** - Some devices online, some offline
- **Gray** - Empty group

### Expanding/Collapsing Groups

- Click on a group header to expand/collapse
- Press `Space` when a group is selected
- Groups show `[-]` when expanded, `[+]` when collapsed

---

## Monitoring Devices

Monitoring periodically scans the network to update device status.

### Starting Monitoring

1. Click **Monitor** or press `F3`
2. The status changes to "MONITORING: ACTIVE" (green)
3. An immediate scan runs
4. Subsequent scans run at the configured interval

### Monitoring Status Display

When monitoring is active, the status bar shows:
```
[MONITORING: ON] | Devices: 7 (Online: 6, Offline: 1) | Last Scan: 14:30:15 | Next Scan: 14:31:15
```

- **Last Scan** - When the most recent scan completed
- **Next Scan** - When the next automatic scan will run

### Stopping Monitoring

Click **Monitor** or press `F3` again to stop.

### Offline Alerts

When monitoring detects offline devices, you'll receive a notification:
```
Monitor scan: 2 device(s) offline
```

---

## Setup & Configuration

Access settings via **Setup** or press `F5`.

### Site Name

Give your site a descriptive name (e.g., "Office Building", "Warehouse").

### Network Interface

**Important for multi-NIC systems!**

If you have multiple network adapters (e.g., Ethernet + WiFi + VPN), select the correct interface for scanning:

- **All Interfaces (0.0.0.0)** - Broadcast on all adapters (default)
- **Specific Interface** - Select your LAN adapter's IP

> **Tip**: If scanning doesn't find devices, try selecting a specific interface instead of "All Interfaces".

### Scan Frequency

Set how often monitoring scans run (in seconds):
- Default: 60 seconds
- Minimum recommended: 30 seconds
- For large networks: 120+ seconds

### Display Columns

Choose which columns appear in the device table:

| Column | Description |
|--------|-------------|
| Device Type | Camera or Recorder |
| IP Address | Current IP address |
| MAC Address | Hardware address |
| Model | Device model number |
| Serial Number | Device serial |
| Status | Online/Offline/Unknown |
| Firmware | Firmware version |
| HTTP Port | Web interface port |

---

## File Operations

### Saving Your Site

1. Click **File** or press `F1`
2. Select **Save Site** (or **Save Site As...** for a new file)
3. Enter a filename
4. Click **Save**

Site files are saved as `.json` and include:
- All groups and devices
- Column visibility settings
- Scan frequency
- Network interface setting

### Loading a Site

1. Click **File** > **Load Site...**
2. Navigate to your site file
3. Select the `.json` file
4. Click **Load**

### Auto-Save Tip

The application doesn't auto-save. Remember to save before exiting!

---

## Exporting Data

Export device information for reports or other tools.

1. Press `E` or use File menu
2. Configure export options:

### Export Format
- **JSON** - Structured data for programming/APIs
- **CSV** - Spreadsheet-compatible (Excel, Google Sheets)

### Export Scope
- **All Groups** - Export every device
- **Selected Group** - Export one group's devices

### Export Fields

Select which fields to include:
- Device Name, Type, IP Address
- Subnet Mask, Gateway
- MAC Address, Model, Serial Number
- HTTP Port, Firmware, Network Mode
- Status, First Seen, Last Seen

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F1` | File menu |
| `F2` | Scan menu |
| `F3` | Toggle monitoring |
| `F4` | Groups menu |
| `F5` | Setup menu |
| `E` | Export devices |
| `R` | Refresh display |
| `O` | Open selected device in browser |
| `Space` | Expand/collapse group |
| `Enter` | View device details |
| `Q` | Quit application |
| `Esc` | Close current dialog |

---

## Troubleshooting

### No Devices Found

1. **Check Network Interface**
   - Go to Setup > Network Interface
   - Select your specific LAN adapter instead of "All Interfaces"
   - Your cameras must be on the same subnet

2. **Firewall Issues**
   - Allow Python through Windows Firewall
   - UDP ports 10669-10670 must be open

3. **Increase Timeout**
   - In Scan menu, increase timeout to 5-10 seconds
   - Large networks may need more time

4. **Verify Network Connectivity**
   - Ensure you can ping camera IP addresses
   - Check that cameras are powered on

### Devices Show as Offline

- Verify the device is powered on
- Check network cable connections
- Ensure device IP hasn't changed (use DHCP reservation)
- Try a manual scan to refresh status

### Application Won't Start

1. Verify Python 3.8+ is installed:
   ```bash
   python --version
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Check for error messages in the terminal

### Interface Selection Shows Wrong Adapters

The application detects interfaces automatically. If your adapter isn't listed:
- Ensure the adapter is enabled
- Check that it has an IP address assigned
- Try restarting the application after connecting

---

## Command Line Usage

The underlying discovery tool can also be used directly:

```bash
# Discover devices with table output
python Easy_IP.py discover --table

# Discover with specific interface
python Easy_IP.py discover --interface 192.168.1.99 --table

# Export to JSON
python Easy_IP.py discover --json > devices.json

# Export to CSV
python Easy_IP.py discover --csv > devices.csv

# Run diagnostics
python Easy_IP.py diag
```

---

## Support

For issues and feature requests, visit:
https://github.com/Rickardjd/Easy_IP

---

*Last updated: February 2025*
