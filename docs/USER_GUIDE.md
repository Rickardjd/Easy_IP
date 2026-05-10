# Easy IP Setup Tool — User Guide

A cross-platform Python TUI (Terminal User Interface) for discovering and managing i-PRO IP cameras and recorders on your network.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Interface](#main-interface)
3. [Scanning for Devices](#scanning-for-devices)
4. [Configuring IP Addresses](#configuring-ip-addresses)
5. [Managing Groups](#managing-groups)
6. [Monitoring Devices](#monitoring-devices)
7. [Setup & Configuration](#setup--configuration)
8. [File Operations](#file-operations)
9. [Exporting Data](#exporting-data)
10. [Keyboard Shortcuts](#keyboard-shortcuts)
11. [Command Line Usage](#command-line-usage)
12. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Requirements

- Python 3.8 or higher
- Required packages (install via `pip install -r requirements.txt`):
  - textual
  - rich

### Running the Application

```
python easy_ip_tui.py
```

Or on Windows, double-click `easy_ip.bat`.

---

## Main Interface

When you launch the application you will see a menu bar at the top, the device table in the centre, and a status bar at the bottom.

### Menu Bar

| Menu | Key | Purpose |
|------|-----|---------|
| File | F1 | Load / save site configurations |
| Scan | F2 | Discover devices on the network |
| Monitor | F3 | Start / stop continuous monitoring |
| Groups | F4 | Manage device groups |
| Setup | F5 | Configure application settings |

### Status Bar

- Monitoring status (ON / OFF)
- Device counts — total, online, offline
- Last scan timestamp
- Next scan timestamp (when monitoring is active)

### Theme

The application supports multiple colour themes. Open the command palette with `Ctrl+P`, type **theme**, and choose from the available options. Your chosen theme is saved automatically and restored on the next launch.

---

## Scanning for Devices

### Automatic Network Scan

1. Click **Scan** or press `F2`
2. Select **Scan Network (Auto)**
3. Adjust the timeout if needed (default: 3 seconds)
4. Wait for the scan to complete

The scan sends a UDP broadcast on port 10670 to discover all i-PRO cameras and recorders on your local network segment.

### First-Time Scanning

If you scan before creating any groups, the application automatically creates a **"Default"** group so discovered devices have somewhere to go immediately.

### Scan Results

After scanning you will see:
- Number of devices found
- New devices not yet tracked
- Devices already in your site

Select which new devices to add and choose a target group.

### Manual Device Addition

If a device is not discovered automatically:

1. Click **Scan** > **Manual Add Device...**
2. Enter the device details:
   - Device Name
   - MAC Address (format: `aa:bb:cc:dd:ee:ff`)
   - IP Address
   - Model (optional)
3. Select a target group
4. Click **Add**

---

## Configuring IP Addresses

The Configure IP dialog lets you change the network settings of one or more tracked cameras in a single operation. Press `I` or use the **Config IP** button to open it.

### Network Mode

Select the addressing mode from the dropdown at the top of the dialog:

| Mode | Description |
|------|-------------|
| **Static IP** | The camera uses the IP address you specify permanently. |
| **DHCP** | The camera requests an IP address from a DHCP server. |
| **Auto (AutoIP)** | DHCP with automatic link-local fallback (169.254.x.x) if no DHCP server responds. |
| **Auto (Advanced)** | DHCP with enhanced auto-negotiation and AutoIP fallback. |

### Shared Network Settings

These values apply to every camera you configure in this session:

- **Subnet Mask** — pre-filled from the first tracked device
- **Gateway** — pre-filled from the first tracked device

### DNS Settings

Choose how each camera resolves hostnames:

- **Auto** — the camera obtains DNS addresses from DHCP or the network automatically.
- **Manual** — enter a Primary DNS and Secondary DNS address explicitly.

### Assigning IP Addresses (Static mode)

**Auto-assign from a base address:**

1. Enter a starting IP (e.g. `192.168.1.100`) in the **Auto-assign** field
2. Click **Auto-assign ▶**
3. Each ticked camera receives the next sequential address (100, 101, 102 …)
4. The base address field advances automatically to the next available address
5. The next time you open the dialog the field is pre-filled with that address, ready for the next batch

**Manual entry:**

Type directly into the **New IP** field beside each camera row.

**Select All / Select None:**

Use these buttons to tick or clear all cameras at once.

### Applying Settings

Click **Apply Selected** to send the new configuration to every ticked camera. A progress bar shows each camera being configured. The application uses the same two-phase broadcast protocol as the original i-PRO EasyIP.exe tool — the config packet is sent three times followed by a commit packet, exactly mirroring the original behaviour.

> **Note:** The camera's current HTTP port must remain unchanged during configuration. The tool auto-discovers the live port before sending if none is specified.

---

## Managing Groups

Groups organise your devices by location, floor, function, or any criteria you choose.

### Creating a Group

1. Click **Groups** or press `F4`
2. Select **Add New Group...**
3. Enter a group name
4. Click **Create**

### Removing a Group

1. Click **Groups** > **Remove Group...**
2. Select the group to remove
3. Click **Remove**

> **Warning:** Removing a group permanently deletes all devices in that group from the site.

### Moving Devices Between Groups

The Move Devices dialog supports moving multiple cameras at once — essential when reorganising a large site.

1. Click **Groups** > **Move Device...**
2. The dialog lists every tracked device with its current group shown in parentheses
3. Tick the devices you want to move — use the helper buttons for speed:

| Button | Effect |
|--------|--------|
| **All** | Selects every device in the list |
| **None** | Clears all selections |
| **Invert** | Flips every checkbox — useful when most cameras need to move and only a few should stay |

4. Choose the target group from the dropdown
5. Click **Move Selected**

A single notification confirms how many devices were moved and to which group.

### Group Status Colours

| Colour | Meaning |
|--------|---------|
| Green | All devices online |
| Red | All devices offline |
| Orange | Mix of online and offline |
| Grey | Group is empty |

### Expanding / Collapsing Groups

- Click a group header to expand or collapse it
- Press `Space` when a group row is focused
- Expanded groups show `[-]`, collapsed groups show `[+]`

---

## Monitoring Devices

Monitoring periodically scans the network and updates each device's online / offline status automatically.

### Starting Monitoring

1. Click **Monitor** or press `F3`
2. The menu bar label changes to **MONITORING: ACTIVE** (green)
3. An immediate scan runs
4. Subsequent scans run at the interval set in Setup

### Status Bar When Monitoring

```
[MONITORING: ON]  |  Devices: 7 (Online: 6, Offline: 1)  |  Last: 14:30:15  |  Next: 14:31:15
```

### Stopping Monitoring

Click **Monitor** or press `F3` again.

### Offline Alerts

When a monitoring scan detects offline devices you receive a notification:

```
Monitor scan: 2 device(s) offline
```

### Deep Check

When **Deep Check** is enabled in Setup, each scan also queries the HTTP webserver on every camera to confirm it is genuinely responding — not just present on the network. This catches cameras that are reachable via ping but have a crashed webserver.

---

## Setup & Configuration

Access settings via **Setup** or press `F5`.

### Site Name

Give your site a descriptive name such as "Main Office" or "Warehouse – Level 2".

### Network Interface

**Important on multi-NIC systems.**

If your PC has multiple adapters (Ethernet, Wi-Fi, VPN), select the one connected to the camera network:

- **All Interfaces (0.0.0.0)** — broadcast on all adapters (default)
- **Specific interface** — select the IP of the adapter on the camera subnet

> **Tip:** If scanning finds no devices, switch from All Interfaces to your specific LAN adapter.

### Deep Check

Queries the webserver on each camera after every scan to confirm it is responding. Adds a small amount of time to each scan cycle.

### Scan Frequency

How often monitoring scans run, in seconds:

| Network size | Recommended interval |
|-------------|----------------------|
| Small (< 20 cameras) | 30 – 60 s |
| Medium (20 – 100) | 60 – 120 s |
| Large (100+) | 120 – 300 s |

### Data Folder

Where site `.json` files are saved. Can be an absolute path or a path relative to the application directory.

### Display Columns

Toggle which columns appear in the device table:

| Column | Description |
|--------|-------------|
| Device Type | Camera or Recorder |
| IP Address | Current IP address |
| MAC Address | Hardware (MAC) address |
| Model | Device model number |
| Serial Number | Device serial number |
| Status | Online / Offline / Unknown |
| Firmware | Firmware version string |
| HTTP Port | Web interface port number |

---

## File Operations

### Saving Your Site

1. Click **File** or press `F1`
2. Select **Save Site** (or **Save Site As...** for a new file)
3. Enter a filename
4. Click **Save**

Site files are saved as `.json` and include all groups, devices, column visibility settings, scan frequency, and the network interface selection.

### Loading a Site

1. Click **File** > **Load Site...**
2. Navigate to your site file
3. Select the `.json` file
4. Click **Load**

> **Tip:** The application does not auto-save. Save before exiting to retain any changes.

---

## Exporting Data

Export device information for reports, spreadsheets, or integration with other tools. Press `E` or use the File menu.

### Export Format

| Format | Best for |
|--------|----------|
| **JSON** | Scripting, APIs, structured data |
| **CSV** | Excel, Google Sheets, reporting tools |

### Export Scope

- **All Groups** — every tracked device
- **Selected Group** — one group only

### Exportable Fields

Device Name, Device Type, IP Address, Subnet Mask, Gateway, MAC Address, Model, Serial Number, HTTP Port, Firmware Version, Network Mode, Status, First Seen, Last Seen.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F1` | File menu |
| `F2` | Scan menu |
| `F3` | Toggle monitoring |
| `F4` | Groups menu |
| `F5` | Setup menu |
| `I` | Configure IP addresses |
| `E` | Export devices |
| `R` | Refresh display |
| `O` | Open selected device in browser |
| `Space` | Expand / collapse group |
| `Enter` | View device details |
| `C` | Copy selected cell value |
| `Ctrl+P` | Command palette (theme, commands) |
| `Q` | Quit application |
| `Esc` | Close current dialog |

---

## Command Line Usage

The underlying engine can also be used without the TUI.

### Discover Devices

```
python Easy_IP.py discover --table
python Easy_IP.py discover --interface 192.168.1.10 --table
python Easy_IP.py discover --json > devices.json
python Easy_IP.py discover --csv  > devices.csv
python Easy_IP.py discover --table --sort type
```

Sort options: `ip` (default), `mac`, `serial`, `type`

### Configure a Device

```
# Static IP with manual DNS
python Easy_IP.py configure \
    --mac d4:2d:c5:2a:8d:13 \
    --ip 192.168.1.54 \
    --subnet 255.255.255.0 \
    --gateway 192.168.1.1 \
    --mode static \
    --dns-mode manual \
    --primary-dns 192.168.1.1 \
    --secondary-dns 8.8.4.4

# DHCP with auto DNS
python Easy_IP.py configure \
    --mac d4:2d:c5:2a:8d:13 \
    --ip 192.168.1.54 \
    --subnet 255.255.255.0 \
    --gateway 192.168.1.1 \
    --mode dhcp \
    --dns-mode auto

# Auto (AutoIP) mode
python Easy_IP.py configure ... --mode auto_autoip

# Auto (Advanced) mode
python Easy_IP.py configure ... --mode auto_advanced
```

### Network Mode Options

| `--mode` value | Description |
|---------------|-------------|
| `static` | Static IP (default) |
| `dhcp` | DHCP |
| `auto_autoip` | Auto with AutoIP fallback |
| `auto_advanced` | Auto Advanced |

### DNS Mode Options

| `--dns-mode` value | Description |
|-------------------|-------------|
| `manual` | Use `--primary-dns` and `--secondary-dns` (default) |
| `auto` | Camera obtains DNS automatically |

### Diagnostics

```
python Easy_IP.py diag
python Easy_IP.py discover -v    # verbose — shows raw protocol detail
```

---

## Troubleshooting

### No Devices Found

**Check the network interface**
Go to Setup > Network Interface. Select your specific LAN adapter instead of All Interfaces. Cameras must be on the same subnet as the selected adapter.

**Check the firewall**
Allow Python through Windows Firewall. UDP ports 10669 and 10670 must be open for broadcast traffic.

**Increase the scan timeout**
In the Scan menu, increase the timeout to 5 – 10 seconds. Large or slow networks may need more time.

**Verify basic connectivity**
Confirm you can ping a camera's IP address from the PC running the tool.

### Devices Show as Offline

- Verify the device is powered on and the network cable is connected
- Check that the IP address has not changed (use a DHCP reservation for stable IPs)
- Run a manual scan to refresh status immediately

### IP Configuration Has No Effect

- The camera's HTTP port in the config packet must match its current port. The tool auto-detects this; if it fails, specify `--port` explicitly on the command line.
- Ensure UDP broadcast is not blocked between the PC and the camera subnet.
- Some managed switches block broadcast traffic between VLANs.

### Application Won't Start

Verify Python 3.8+ is installed:

```
python --version
```

Install required packages:

```
pip install -r requirements.txt
```

### Interface Selection Shows Wrong Adapters

- Ensure the adapter is enabled and has an IP address assigned
- Restart the application after connecting to a new network
- If psutil is installed, interface detection is more accurate:
  ```
  pip install psutil
  ```

---

## Support

For issues and feature requests, visit:
https://github.com/Rickardjd/Easy_IP

---

*Last updated: May 2025*
