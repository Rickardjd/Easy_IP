# Camera Tracker - Quick Start Examples

## Basic Usage

### 1. First Time Setup - Discover and Track
```bash
# Discover cameras and add to database
python Easy_IP_3.py discover --json | python camera_tracker.py update
```

**Output Example:**
```
======================================================================
Camera Discovery Update Summary
======================================================================

✨ New Cameras Discovered: 3
  - Camera-01 (d4:2d:c5:14:c5:70) at 192.168.1.100
  - Camera-02 (d4:2d:c5:14:c5:71) at 192.168.1.101
  - Camera-03 (d4:2d:c5:14:c5:72) at 192.168.1.102

Database updated: camera_database.json
```

### 2. View All Cameras in Table Format
```bash
python camera_tracker.py list --table
```

**Output Example:**
```
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+
| MAC Address     | Camera Name | IP Address      | Model         | First Seen          | Last Seen           | Discoveries | Status |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+
| d4:2d:c5:14:c5  | Camera-01   | 192.168.1.100   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-22 10:30:00 | 1           | Active |
| d4:2d:c5:14:c6  | Camera-02   | 192.168.1.101   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-22 10:30:00 | 1           | Active |
| d4:2d:c5:14:c7  | Camera-03   | 192.168.1.102   | WV-S1235      | 2024-12-22 10:30:00 | 2024-12-22 10:30:00 | 1           | Active |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+

Total cameras: 3
Active: 3 | IP Changed: 0 | Offline: 0 | Missing: 0
```

### 3. Second Discovery - Tracking Changes
```bash
# Run discovery again (e.g., 1 hour later)
python Easy_IP_3.py discover --json | python camera_tracker.py update
```

**If a camera IP changed:**
```
======================================================================
Camera Discovery Update Summary
======================================================================

🔄 IP Address Changes: 1
  - Camera-02 (d4:2d:c5:14:c5:71)
    192.168.1.101 → 192.168.1.150

✓ Updated Cameras: 2
  - Camera-01 (d4:2d:c5:14:c5:70) at 192.168.1.100
  - Camera-03 (d4:2d:c5:14:c5:72) at 192.168.1.102

Database updated: camera_database.json
```

### 4. View Table After Changes
```bash
python camera_tracker.py list --table
```

**Output with IP change indicator:**
```
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+
| MAC Address     | Camera Name | IP Address      | Model         | First Seen          | Last Seen           | Discoveries | Status     |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+
| d4:2d:c5:14:c5  | Camera-01   | 192.168.1.100   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-22 11:30:00 | 2           | Active     |
| d4:2d:c5:14:c6  | Camera-02   | 192.168.1.150   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-22 11:30:00 | 2           | IP Changed | 🔄 IP CHANGED
| d4:2d:c5:14:c7  | Camera-03   | 192.168.1.102   | WV-S1235      | 2024-12-22 10:30:00 | 2024-12-22 11:30:00 | 2           | Active     |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+------------+

Total cameras: 3
Active: 2 | IP Changed: 1 | Offline: 0 | Missing: 0
```

### 5. View IP Change History
```bash
python camera_tracker.py history --mac d4:2d:c5:14:c5:71
```

**Output:**
```
======================================================================
IP Change History: Camera-02 (d4:2d:c5:14:c5:71)
======================================================================
Current IP: 192.168.1.150
First seen: 2024-12-22 10:30:00
Last seen: 2024-12-22 11:30:00
Total discoveries: 2

IP Address History:
  [1] 2024-12-22 10:30:00: 192.168.1.101 (first discovery)
  [2] 2024-12-22 11:30:00: 192.168.1.101 → 192.168.1.150
```

### 6. Detecting Missing Cameras
```bash
# Run discovery but Camera-03 is offline
python Easy_IP_3.py discover --json | python camera_tracker.py update

# Later, check status (if Camera-03 offline for 25+ hours)
python camera_tracker.py list --table --missing-hours 24
```

**Output with missing camera:**
```
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+
| MAC Address     | Camera Name | IP Address      | Model         | First Seen          | Last Seen           | Discoveries | Status |
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+
| d4:2d:c5:14:c5  | Camera-01   | 192.168.1.100   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-23 10:30:00 | 15          | Active |
| d4:2d:c5:14:c6  | Camera-02   | 192.168.1.150   | WV-S1234      | 2024-12-22 10:30:00 | 2024-12-23 10:30:00 | 15          | Active |
| d4:2d:c5:14:c7  | Camera-03   | 192.168.1.102   | WV-S1235      | 2024-12-22 10:30:00 | 2024-12-22 10:30:00 | 1           | MISSING| ⚠️  MISSING
+-----------------+-------------+-----------------+---------------+---------------------+---------------------+-------------+--------+

Total cameras: 3
Active: 2 | IP Changed: 0 | Offline: 0 | Missing: 1
```

### 7. Database Statistics
```bash
python camera_tracker.py stats
```

**Output:**
```
============================================================
Camera Database Statistics
============================================================
Total cameras tracked: 3
Total discoveries: 32
Average discoveries per camera: 10.7
Cameras with IP changes: 1

Most recently seen:
  Camera-01 (d4:2d:c5:14:c5:70) - 2024-12-23 10:30:00
  Camera-02 (d4:2d:c5:14:c5:71) - 2024-12-23 10:30:00
  Camera-03 (d4:2d:c5:14:c5:72) - 2024-12-22 10:30:00
```

### 8. Export and Backup
```bash
# Export database to backup file
python camera_tracker.py export --output backup_2024-12-23.json
```

### 9. Sorting Options
```bash
# Sort by IP address
python camera_tracker.py list --table --sort ip

# Sort by camera name
python camera_tracker.py list --table --sort name

# Sort by first seen (oldest first)
python camera_tracker.py list --table --sort first_seen

# Sort by last seen (most recent first - default)
python camera_tracker.py list --table --sort last_seen
```

### 10. Show Only Active Cameras
```bash
# Hide offline and missing cameras
python camera_tracker.py list --table --active-only
```

## Real-World Workflow

### Daily Morning Check
```bash
#!/bin/bash
# morning_check.sh

echo "=== Daily Camera Check - $(date) ==="
echo ""

# Discover and update
python Easy_IP_3.py discover --json | python camera_tracker.py update

# Show current status
python camera_tracker.py list --table --sort ip
```

### Automated Monitoring (Cron Job)
```bash
# Add to crontab: runs every hour
0 * * * * cd /path/to/scripts && python Easy_IP_3.py discover --json | python camera_tracker.py update --quiet

# Check daily at 8 AM and email if issues found
0 8 * * * cd /path/to/scripts && python camera_tracker.py list --table | mail -s "Daily Camera Status" admin@example.com
```

### Finding Specific Issues
```bash
# Find cameras that changed IP in the last day
python camera_tracker.py list --json | jq '.cameras[] | select(.ip_history | length > 1) | select(.last_seen | . > (now - 86400 | todate))'

# Count cameras per subnet
python camera_tracker.py list --json | jq '[.cameras[].current_ip] | map(split(".")[0:3] | join(".")) | group_by(.) | map({subnet: .[0], count: length})'

# Find cameras not seen in last 48 hours
python camera_tracker.py list --table --missing-hours 48
```

## Pipe Workflow Examples

### Combine Discovery and Reporting
```bash
# One command: discover, update, and show table
python Easy_IP_3.py discover --json | python camera_tracker.py update && python camera_tracker.py list --table
```

### Save Discovery and Process Later
```bash
# Save discovery output
python Easy_IP_3.py discover --json > discovery_$(date +%Y%m%d_%H%M%S).json

# Process later
python camera_tracker.py update --input discovery_20241223_103000.json
```

### Create Daily Reports
```bash
# Generate report
{
    echo "Camera Status Report - $(date)"
    echo "================================"
    echo ""
    python camera_tracker.py stats
    echo ""
    echo "Current Status:"
    python camera_tracker.py list --table
} > daily_report_$(date +%Y%m%d).txt
```

## Integration Examples

### With Telegram Bot
```bash
#!/bin/bash
# Send alert to Telegram if cameras missing

MISSING=$(python camera_tracker.py list --json | jq '[.cameras[] | select(.status == "MISSING")] | length')

if [ "$MISSING" -gt 0 ]; then
    MESSAGE="⚠️ Alert: $MISSING camera(s) missing!"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
         -d chat_id="${CHAT_ID}" \
         -d text="$MESSAGE"
fi
```

### With Slack Webhook
```bash
#!/bin/bash
# Post status to Slack

STATUS=$(python camera_tracker.py stats)
curl -X POST -H 'Content-type: application/json' \
     --data "{\"text\":\"Camera Status:\n\`\`\`$STATUS\`\`\`\"}" \
     $SLACK_WEBHOOK_URL
```

### With Grafana/InfluxDB
```bash
#!/bin/bash
# Send metrics to InfluxDB

python camera_tracker.py list --json | jq -r '.cameras[] | 
  "cameras,mac=\(.mac_address),name=\(.camera_name) discoveries=\(.total_discoveries)i,status=\"\(.status)\""' | \
  curl -i -XPOST "http://localhost:8086/write?db=cameras" --data-binary @-
```

## Tips

1. **Run hourly**: Set up cron job to track changes over time
2. **Review history**: Use `history` command to investigate IP changes
3. **Monitor missing**: Set appropriate `--missing-hours` for your environment
4. **Backup regularly**: Export database weekly
5. **Use JSON output**: Combine with `jq` for powerful filtering
6. **Active-only view**: Use `--active-only` for cleaner daily view
7. **Sort strategically**: Use `--sort ip` to group by subnet

## Common Issues

### "No cameras in database"
- Run `update` command first to populate database
- Check that Easy_IP_3.py is finding cameras

### Database not updating
- Ensure you're using `--json` flag with Easy_IP_3.py
- Check database file permissions
- Verify JSON format is valid

### Status showing as "Offline" when camera is active
- Adjust `--missing-hours` threshold
- Ensure regular discoveries are running
- Camera might have just come back online
