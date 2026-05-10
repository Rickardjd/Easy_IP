# Camera Tracker - User Guide

## Overview

Camera Tracker is a companion application for Easy_IP_3 that maintains a persistent database of discovered Panasonic cameras. It tracks:

- **First Discovery**: When each camera was first seen
- **Last Discovery**: Most recent detection
- **IP Changes**: Complete history of IP address changes
- **Status**: Active, Offline, Missing, or IP Changed
- **Discovery Count**: Total number of times each camera was detected

## Installation

No installation required - just place `camera_tracker.py` in the same directory as `Easy_IP_3.py`.

## Database

The tracker maintains a JSON database file (`camera_database.json` by default) that persists between runs. This file contains:
- Complete camera information
- Timestamps for first and last discovery
- IP address change history
- Total discovery count

## Usage

### 1. Update Database from Discovery (Piped Input)

The most common usage is to pipe the output from Easy_IP_3 directly into the tracker:

```bash
# Discover cameras and update tracker in one command
python Easy_IP_3.py discover --json | python camera_tracker.py update

# Quiet mode (no output, just update database)
python Easy_IP_3.py discover --json | python camera_tracker.py update --quiet
```

### 2. Update from Saved JSON File

If you've saved discovery output to a file:

```bash
# Save discovery to file
python Easy_IP_3.py discover --json > cameras_today.json

# Update tracker from file
python camera_tracker.py update --input cameras_today.json
```

### 3. List All Tracked Cameras

**Table Format (Recommended):**
```bash
# Show all cameras in formatted table
python camera_tracker.py list --table

# Show only active cameras (hide offline/missing)
python camera_tracker.py list --table --active-only

# Sort by different fields
python camera_tracker.py list --table --sort ip
python camera_tracker.py list --table --sort name
python camera_tracker.py list --table --sort first_seen
```

**JSON Format:**
```bash
# Export list as JSON
python camera_tracker.py list --json

# Pipe to other tools
python camera_tracker.py list --json | jq '.cameras[] | select(.current_ip | startswith("192.168.1"))'
```

**Simple List:**
```bash
# Simple text list
python camera_tracker.py list
```

### 4. View Database Statistics

```bash
python camera_tracker.py stats
```

Shows:
- Total cameras tracked
- Total discoveries across all cameras
- Average discoveries per camera
- Cameras with IP changes
- Most/least recently seen cameras

### 5. View IP Change History

```bash
# View complete IP history for a specific camera
python camera_tracker.py history --mac d4:2d:c5:14:c5:70
```

### 6. Export Database

```bash
# Export entire database to JSON file
python camera_tracker.py export --output backup.json
```

### 7. Use Custom Database Location

```bash
# Use a different database file
python camera_tracker.py --database /path/to/my_cameras.json list --table
```

## Table Output Format

```
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+
| MAC Address     | Camera Name | IP Address      | Model         | First Seen          | Last Seen           | Discoveries | Status     |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+
| d4:2d:c5:14:c5  | Camera-01   | 192.168.1.100   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-22 14:15:00 | 5           | Active     |
| d4:2d:c5:14:c6  | Camera-02   | 192.168.1.101   | WV-S1234      | 2024-12-20 09:00:00 | 2024-12-22 14:15:00 | 12          | IP Changed | 🔄 IP CHANGED
| d4:2d:c5:14:c7  | Camera-03   | 192.168.1.102   | WV-S1235      | 2024-12-15 08:00:00 | 2024-12-21 10:00:00 | 8           | Offline    | ⏸️  OFFLINE
| d4:2d:c5:14:c8  | Camera-04   | 192.168.1.103   | WV-S1236      | 2024-11-10 12:00:00 | 2024-12-01 16:00:00 | 3           | MISSING    | ⚠️  MISSING
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+

Total cameras: 4
Active: 1 | IP Changed: 1 | Offline: 1 | Missing: 1
```

## Camera Status Definitions

| Status | Meaning | Criteria |
|--------|---------|----------|
| **Active** | Camera is online and responding | Seen in latest discovery, no recent IP change |
| **IP Changed** | Camera IP address changed | IP address different from previous discovery |
| **Offline** | Camera recently offline but not missing | Not in latest discovery, but seen within threshold (default 24 hours) |
| **MISSING** | Camera hasn't been seen in a long time | Not seen for more than threshold hours (default 24) |

You can adjust the missing threshold:
```bash
python camera_tracker.py list --table --missing-hours 48
```

## Workflow Examples

### Daily Network Monitoring

```bash
#!/bin/bash
# daily_camera_check.sh

# Discover and update tracker
python Easy_IP_3.py discover --json | python camera_tracker.py update

# Show current status
python camera_tracker.py list --table --active-only

# Email if any cameras are missing
MISSING=$(python camera_tracker.py list --json | jq '.cameras[] | select(.status == "MISSING") | length')
if [ "$MISSING" -gt 0 ]; then
    python camera_tracker.py list --table | mail -s "Camera Alert: Missing Devices" admin@example.com
fi
```

### Weekly Status Report

```bash
#!/bin/bash
# weekly_report.sh

echo "Weekly Camera Status Report" > report.txt
echo "============================" >> report.txt
echo "" >> report.txt

python camera_tracker.py stats >> report.txt
echo "" >> report.txt

echo "All Cameras:" >> report.txt
python camera_tracker.py list --table >> report.txt

cat report.txt | mail -s "Weekly Camera Report" admin@example.com
```

### Find Cameras with Changed IPs

```bash
# List all cameras with IP changes
python camera_tracker.py list --json | jq '.cameras[] | select(.ip_history | length > 1)'

# Show IP history for specific camera
python camera_tracker.py history --mac d4:2d:c5:14:c5:70
```

### Continuous Monitoring

```bash
#!/bin/bash
# continuous_monitor.sh

while true; do
    echo "Scanning network at $(date)"
    python Easy_IP_3.py discover --json | python camera_tracker.py update --quiet
    sleep 300  # Check every 5 minutes
done
```

## Integration with Other Tools

### With jq (JSON processing)

```bash
# Find cameras on specific subnet
python camera_tracker.py list --json | jq '.cameras[] | select(.current_ip | startswith("192.168.1"))'

# Count cameras per model
python camera_tracker.py list --json | jq '[.cameras[].model_name] | group_by(.) | map({model: .[0], count: length})'

# Find cameras not seen today
TODAY=$(date +%Y-%m-%d)
python camera_tracker.py list --json | jq --arg today "$TODAY" '.cameras[] | select(.last_seen | startswith($today) | not)'
```

### With Excel/Spreadsheet

```bash
# Export database to CSV-compatible format
python camera_tracker.py list --json | jq -r '.cameras[] | [.mac_address, .camera_name, .current_ip, .model_name, .first_seen, .last_seen, .total_discoveries] | @csv' > cameras.csv
```

### With Monitoring Systems

```bash
# Nagios/Icinga check script
#!/bin/bash
MISSING=$(python camera_tracker.py list --json | jq '[.cameras[] | select(.status == "MISSING")] | length')

if [ "$MISSING" -gt 0 ]; then
    echo "CRITICAL: $MISSING cameras missing"
    exit 2
elif [ "$MISSING" -eq 0 ]; then
    echo "OK: All cameras online"
    exit 0
fi
```

## Command Reference

### Update Command
```bash
python camera_tracker.py update [OPTIONS]

Options:
  --input, -i FILE    Read from JSON file instead of stdin
  --quiet, -q         Suppress output
```

### List Command
```bash
python camera_tracker.py list [OPTIONS]

Options:
  --table             Show formatted table
  --json              Output as JSON
  --sort FIELD        Sort by: last_seen, first_seen, ip, mac, name
  --active-only       Hide offline/missing cameras
  --missing-hours N   Hours before camera considered missing (default: 24)
```

### Export Command
```bash
python camera_tracker.py export --output FILE

Options:
  --output, -o FILE   Output JSON file (required)
```

### Stats Command
```bash
python camera_tracker.py stats

No options
```

### History Command
```bash
python camera_tracker.py history --mac MAC_ADDRESS

Options:
  --mac MAC           MAC address of camera (required)
```

### Global Options
```bash
--database FILE       Path to database file (default: camera_database.json)
```

## Tips and Best Practices

1. **Regular Updates**: Run discovery and update regularly (e.g., every hour) to maintain accurate status
2. **Backup Database**: Periodically export the database for backup
3. **Monitor IP Changes**: Check for IP changes regularly - they might indicate network issues
4. **Adjust Thresholds**: Set `--missing-hours` based on your network maintenance schedule
5. **Combine with Cron**: Use cron jobs for automated monitoring
6. **Version Control**: Keep database backups in version control for historical analysis

## Troubleshooting

### Database File Locked
If you get file locking errors:
- Ensure no other instance is running
- Check file permissions
- Try specifying a different database file

### Invalid JSON Input
If piping fails:
- Ensure Easy_IP_3 is using `--json` flag
- Check for error messages in Easy_IP_3 output
- Test with a saved JSON file first

### Missing Camera Not Detected
- Adjust `--missing-hours` threshold
- Check if camera MAC address changed
- Verify database contains the camera

## Database Schema

The database JSON structure:

```json
{
  "d4:2d:c5:14:c5:70": {
    "mac_address": "d4:2d:c5:14:c5:70",
    "serial_number": "12345678",
    "model_name": "WV-S1234",
    "camera_name": "Camera-01",
    "firmware_version": "2.00",
    "current_ip": "192.168.1.100",
    "current_subnet": "255.255.255.0",
    "current_gateway": "192.168.1.1",
    "current_port": 80,
    "current_network_mode": "Static",
    "first_seen": "2024-12-22T10:30:00.000000",
    "last_seen": "2024-12-22T14:15:00.000000",
    "ip_history": [
      {
        "ip": "192.168.1.50",
        "timestamp": "2024-12-22T10:30:00.000000",
        "previous_ip": null
      },
      {
        "ip": "192.168.1.100",
        "timestamp": "2024-12-22T12:00:00.000000",
        "previous_ip": "192.168.1.50"
      }
    ],
    "total_discoveries": 5
  }
}
```

## License

Same as Easy_IP_3 - use freely for Panasonic camera management.
