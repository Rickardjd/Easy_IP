# Camera Monitor Web Service - Quick Start

## What You Get

A beautiful, real-time web dashboard for monitoring your Panasonic IP cameras:

- 📊 **Live Statistics** - See active, offline, and missing cameras at a glance
- 🔍 **Network Scanning** - One-click camera discovery
- 📹 **Camera Details** - Complete information including IP history
- 🔄 **Auto-Refresh** - Dashboard updates automatically
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- 💾 **Export Data** - Download complete database

## Installation

### Step 1: Install Flask

```bash
# Windows
pip install -r requirements.txt

# Linux/Mac
pip3 install -r requirements.txt
```

### Step 2: File Structure

Ensure you have these files in the same directory:

```
camera-monitor/
├── camera_web_service.py
├── Easy_IP_3.py
├── camera_tracker.py
├── requirements.txt
├── templates/
│   └── index.html
└── start_web_service.bat (Windows) or .sh (Linux/Mac)
```

### Step 3: Start the Service

**Windows:**
```bash
# Double-click start_web_service.bat
# OR run in command prompt:
python camera_web_service.py
```

**Linux/Mac:**
```bash
# Make executable (first time only):
chmod +x start_web_service.sh

# Run:
./start_web_service.sh

# OR:
python3 camera_web_service.py
```

### Step 4: Open Your Browser

Go to: **http://localhost:5000**

## First Use

1. **Click "Scan Network"** - Discovers all cameras on your network
2. **Wait for scan** - Takes a few seconds
3. **View results** - See all discovered cameras in the dashboard
4. **Click "Details"** on any camera for complete information

## Features Overview

### Main Dashboard

**Statistics Cards** (Top of page)
- Total Cameras
- Active (green) - Currently responding
- IP Changed (blue) - IP address changed
- Offline (orange) - Recently offline
- Missing (red) - Not seen for 24+ hours

**Controls**
- **Scan Network** - Run immediate discovery
- **Refresh** - Reload dashboard data
- **Export** - Download database as JSON
- **Auto-scan Toggle** - Enable automatic scanning every 5 minutes

**Filter Buttons**
- All - Show all cameras
- Active - Only active cameras
- IP Changed - Cameras with changed IPs
- Offline - Recently offline cameras
- Missing - Long-term missing cameras

**Camera Table**
- Status badge (color-coded)
- Camera name
- IP address and port
- MAC address
- Model
- Last seen timestamp
- Total discoveries
- Details button

### Camera Details

Click "Details" on any camera to see:
- Complete network configuration
- Serial number and firmware
- First and last seen timestamps
- **IP Address History** - Every IP change with timestamps
- All network settings

### Auto-Scan Mode

Enable auto-scan to:
- Automatically discover cameras every 5 minutes
- Keep database up-to-date
- Detect offline cameras quickly
- Track IP changes automatically

## Common Use Cases

### Daily Monitoring

1. Enable auto-scan
2. Keep browser tab open
3. Dashboard updates automatically
4. Get notified of status changes

### Finding Problem Cameras

1. Click "Missing" or "Offline" filter
2. See which cameras aren't responding
3. Click "Details" for last known configuration
4. Check IP history for recent changes

### Tracking IP Changes

1. Click "IP Changed" filter
2. See cameras with changed IPs
3. Click "Details" to view complete IP history
4. Timestamps show when each change occurred

### Network Documentation

1. Run scan to discover all cameras
2. Click "Export" to download database
3. Use JSON file for documentation
4. Import to Excel/spreadsheet if needed

## Accessing from Other Devices

The web service is accessible from other devices on your network:

1. Find your computer's IP address:
   ```bash
   # Windows
   ipconfig
   
   # Linux/Mac
   ifconfig
   ```

2. On other device, go to:
   ```
   http://YOUR_COMPUTER_IP:5000
   ```

For example: `http://192.168.1.100:5000`

## Tips

- **Run scans regularly** - Keeps database current
- **Enable auto-scan** - For hands-free monitoring
- **Check IP history** - When cameras have connectivity issues
- **Use filters** - To focus on problem cameras
- **Export database** - For backup or reporting

## Troubleshooting

### "No Cameras Found"

1. Ensure cameras are on same network
2. Check firewall allows UDP ports 10669-10670
3. Run manual test: `python Easy_IP_3.py discover -v`

### Cannot Access from Browser

1. Check service is running (look for console output)
2. Verify URL is correct: `http://localhost:5000`
3. Try different browser
4. Check firewall isn't blocking port 5000

### Scan Button Not Working

1. Check console for error messages
2. Verify Easy_IP_3.py is in same directory
3. Try manual scan: `python Easy_IP_3.py discover --json`

### Auto-Scan Not Working

1. Enable the toggle in the dashboard
2. Check console logs for errors
3. Wait 5 minutes for first auto-scan

## Advanced Usage

### Change Auto-Scan Interval

Edit `camera_web_service.py`:
```python
AUTO_SCAN_INTERVAL = 600  # 10 minutes (default is 300)
```

### Run on Different Port

Edit `camera_web_service.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8080)
```

### Custom Database Location

Edit `camera_web_service.py`:
```python
DATABASE_PATH = '/path/to/my_database.json'
```

## File Descriptions

- **camera_web_service.py** - Main Flask web application
- **Easy_IP_3.py** - Camera discovery tool
- **camera_tracker.py** - Database management
- **templates/index.html** - Web interface
- **requirements.txt** - Python dependencies
- **camera_database.json** - Database (auto-created)

## Support

For detailed documentation, see:
- **WEB_SERVICE_GUIDE.md** - Complete web service documentation
- **CAMERA_TRACKER_GUIDE.md** - Database and tracking features
- **ENHANCEMENTS.md** - Easy_IP_3 features

## Screenshots

### Dashboard View
- Real-time statistics cards
- Filter buttons
- Sortable camera table
- Status indicators

### Camera Details
- Complete network configuration
- IP change history
- Firmware and serial info
- Discovery timestamps

### Mobile View
- Responsive design
- Touch-friendly controls
- All features available

Enjoy monitoring your cameras! 📹
