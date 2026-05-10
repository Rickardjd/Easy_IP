# Camera Monitor Web Service

## Overview

A modern, real-time web interface for monitoring Panasonic IP cameras. Combines Easy_IP_3 discovery and camera_tracker database management into a beautiful, responsive dashboard.

## Features

### Real-Time Dashboard
- **Live Statistics**: Active, Offline, Missing, and IP Changed camera counts
- **Auto-Refresh**: Dashboard updates every 30 seconds
- **Status Indicators**: Color-coded status badges for quick identification
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### Camera Management
- **Network Scanning**: One-click discovery of all cameras
- **Auto-Scan Mode**: Automatic periodic scanning (every 5 minutes)
- **Detailed View**: Click any camera for complete information
- **IP History**: Track all IP address changes over time
- **Export Data**: Download complete database as JSON

### Status Tracking
- **Active**: Camera responding in latest scan
- **IP Changed**: IP address changed since last scan
- **Offline**: Not seen recently but within threshold
- **Missing**: Not seen for extended period (24+ hours)

### Filtering
- Filter cameras by status
- Quick access to problem cameras
- Clean, organized table view

## Installation

### Prerequisites

```bash
pip install flask
```

### File Structure

```
camera-monitor/
├── camera_web_service.py      # Main Flask application
├── Easy_IP_3.py                # Camera discovery tool
├── camera_tracker.py           # Database management
├── templates/
│   └── index.html             # Web interface
└── camera_database.json       # Database (auto-created)
```

### Setup

1. Ensure all three Python files are in the same directory:
   - `camera_web_service.py`
   - `Easy_IP_3.py`
   - `camera_tracker.py`

2. Create the `templates` directory and add `index.html`

3. Run the web service:
```bash
python camera_web_service.py
```

4. Open your browser to: `http://localhost:5000`

## Usage

### Starting the Service

```bash
python camera_web_service.py
```

Output:
```
======================================================================
Camera Monitor Web Service
======================================================================
Database: camera_database.json
Auto-scan interval: 300 seconds

Starting web server on http://localhost:5000
Press Ctrl+C to stop
======================================================================
```

### Web Interface

#### Main Dashboard

The dashboard shows:
- **Header**: Application title and description
- **Control Panel**: Scan, refresh, export, and auto-scan controls
- **Statistics Cards**: Real-time counts of camera statuses
- **Filter Buttons**: Quick filter by status
- **Camera Table**: Detailed list of all cameras

#### Controls

**Scan Network**
- Triggers immediate network discovery
- Updates database with findings
- Shows progress indicator during scan

**Refresh**
- Reloads dashboard data from database
- Updates statistics and table

**Export**
- Downloads complete database as JSON
- Filename includes current date

**Auto-scan Toggle**
- Enable/disable automatic periodic scanning
- Scans every 5 minutes when enabled
- Visual indicator shows current state

#### Camera Table

Columns:
- **Status**: Color-coded badge (Active/Offline/Missing/IP Changed)
- **Camera Name**: Device name
- **IP Address**: Current IP and port
- **MAC Address**: Hardware address
- **Model**: Camera model number
- **Last Seen**: Timestamp of last discovery
- **Discoveries**: Total number of times discovered
- **Details Button**: Opens detailed view

#### Camera Details Modal

Click "Details" on any camera to see:
- Complete network configuration
- Serial number and firmware version
- First seen and last seen timestamps
- Complete IP address change history
- All network settings (subnet, gateway, etc.)

### API Endpoints

The web service provides REST API endpoints:

#### GET /api/cameras
Returns all cameras with status information

**Response:**
```json
{
  "cameras": [...],
  "count": 5,
  "last_scan": "2024-12-23T10:30:00",
  "scan_in_progress": false
}
```

#### GET /api/camera/<mac_address>
Returns detailed information for specific camera

**Example:** `/api/camera/d4:2d:c5:14:c5:70`

#### GET /api/stats
Returns database statistics

**Response:**
```json
{
  "total_cameras": 10,
  "active": 8,
  "offline": 1,
  "missing": 1,
  "ip_changed": 2,
  "total_discoveries": 150,
  "cameras_with_ip_changes": 3,
  "last_scan": "2024-12-23T10:30:00",
  "scan_in_progress": false,
  "auto_scan_enabled": true,
  "auto_scan_interval": 300
}
```

#### POST /api/scan
Triggers manual network scan

**Response:**
```json
{
  "success": true,
  "message": "Scan started"
}
```

#### POST /api/auto-scan
Enable/disable automatic scanning

**Request:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "auto_scan_enabled": true,
  "interval": 300
}
```

#### GET /api/export
Export complete database as JSON

## Configuration

### Change Port

Edit `camera_web_service.py`:

```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Changed from 5000
```

### Change Auto-Scan Interval

Edit `camera_web_service.py`:

```python
AUTO_SCAN_INTERVAL = 600  # 10 minutes (default is 300)
```

### Change Database Location

Edit `camera_web_service.py`:

```python
DATABASE_PATH = '/path/to/camera_database.json'
```

### Enable External Access

By default, the server is accessible from other devices on your network.

To restrict to localhost only:
```python
app.run(debug=True, host='127.0.0.1', port=5000)
```

## Production Deployment

### Using Gunicorn (Recommended)

Install:
```bash
pip install gunicorn
```

Run:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 camera_web_service:app
```

### Using systemd (Linux)

Create `/etc/systemd/system/camera-monitor.service`:

```ini
[Unit]
Description=Camera Monitor Web Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/camera-monitor
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/camera-monitor/camera_web_service.py

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable camera-monitor
sudo systemctl start camera-monitor
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "camera_web_service.py"]
```

Create `requirements.txt`:
```
flask==2.3.0
```

Build and run:
```bash
docker build -t camera-monitor .
docker run -p 5000:5000 -v ./camera_database.json:/app/camera_database.json camera-monitor
```

## Monitoring and Maintenance

### View Logs

The web service logs to stdout. Redirect to file:

```bash
python camera_web_service.py > camera_monitor.log 2>&1
```

### Database Backup

The database is stored in `camera_database.json`. Back it up regularly:

```bash
# Manual backup
cp camera_database.json camera_database_backup_$(date +%Y%m%d).json

# Automated daily backup (cron)
0 2 * * * cp /path/to/camera_database.json /path/to/backups/camera_db_$(date +\%Y\%m\%d).json
```

### Check Service Status

```bash
# Check if service is running
curl http://localhost:5000/api/stats

# Check from another machine
curl http://YOUR_SERVER_IP:5000/api/stats
```

## Troubleshooting

### Port Already in Use

Error: `Address already in use`

Solution: Change port or kill existing process:
```bash
# Find process using port 5000
lsof -i :5000

# Kill it
kill -9 <PID>

# Or use a different port
```

### Easy_IP_3.py Not Found

Error: `Easy_IP_3.py not found in current directory`

Solution: Ensure all files are in the same directory:
```bash
ls -la
# Should show:
# camera_web_service.py
# Easy_IP_3.py
# camera_tracker.py
# templates/index.html
```

### No Cameras Discovered

1. Check cameras are on same network
2. Check firewall allows UDP ports 10669-10670
3. Run manual discovery test:
   ```bash
   python Easy_IP_3.py discover -v
   ```

### Cannot Access from Other Devices

1. Check firewall allows port 5000
2. Verify host is set to `0.0.0.0` not `127.0.0.1`
3. Check network connectivity:
   ```bash
   # From other device
   ping YOUR_SERVER_IP
   telnet YOUR_SERVER_IP 5000
   ```

### Auto-Scan Not Working

1. Check auto-scan is enabled (toggle in UI)
2. Check logs for errors
3. Verify Easy_IP_3.py works manually
4. Check scan interval setting

## Security Considerations

### Authentication

The basic version has no authentication. For production:

1. Add Flask-Login for user authentication
2. Use HTTPS (reverse proxy with nginx/Apache)
3. Implement API key authentication
4. Restrict by IP address

### Example: Basic Authentication

```python
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("your-password")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@app.route('/')
@auth.login_required
def index():
    return render_template('index.html')
```

### HTTPS Setup (with nginx)

```nginx
server {
    listen 443 ssl;
    server_name camera-monitor.local;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Advanced Features

### Custom Styling

Edit `templates/index.html` to customize:
- Colors: Modify CSS variables
- Logo: Add image to header
- Layout: Adjust grid/table styling

### Database Cleanup

Remove old cameras not seen in 90+ days:

```python
from datetime import datetime, timedelta

def cleanup_old_cameras():
    cutoff = datetime.now() - timedelta(days=90)
    for mac, camera in list(db.cameras.items()):
        last_seen = datetime.fromisoformat(camera.last_seen)
        if last_seen < cutoff:
            del db.cameras[mac]
    db.save()
```

### Alerting

Send alerts when cameras go missing:

```python
def check_for_alerts():
    missing = [c for c in db.cameras.values() 
               if get_camera_status(c, 24) == "MISSING"]
    
    if missing:
        # Send email, SMS, or webhook
        send_alert(f"{len(missing)} cameras missing!")
```

### Integration with Monitoring Systems

Export metrics for Prometheus, Grafana, etc.:

```python
@app.route('/metrics')
def metrics():
    stats = get_stats()
    return f"""
# HELP cameras_total Total number of cameras
# TYPE cameras_total gauge
cameras_total {stats['total_cameras']}

# HELP cameras_active Number of active cameras
# TYPE cameras_active gauge
cameras_active {stats['active']}

# HELP cameras_missing Number of missing cameras
# TYPE cameras_missing gauge
cameras_missing {stats['missing']}
"""
```

## Support

For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. Check Easy_IP_3 and camera_tracker documentation
4. Verify network configuration

## License

Same as Easy_IP_3 - use freely for Panasonic camera management.
