#!/usr/bin/env python3
"""
Camera Monitor Web Service
Web interface for Panasonic camera discovery and tracking
"""

from flask import Flask, render_template, jsonify, request, send_file
import subprocess
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import threading
import time

# Add current directory to path to import camera_tracker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camera_tracker import CameraDatabase, format_timestamp, get_camera_status

app = Flask(__name__)
app.config['SECRET_KEY'] = 'panasonic-camera-monitor-secret-key'

# Configuration
DATABASE_PATH = 'camera_database.json'
AUTO_SCAN_INTERVAL = 300  # 5 minutes
auto_scan_enabled = False
last_scan_time = None
scan_in_progress = False

db = CameraDatabase(DATABASE_PATH)


def run_discovery():
    """Run Easy_IP_3 discovery and update database"""
    global last_scan_time, scan_in_progress
    
    try:
        scan_in_progress = True
        
        # Run discovery
        result = subprocess.run(
            [sys.executable, 'Easy_IP_3.py', 'discover', '--json'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            # Parse JSON output
            discovery_data = json.loads(result.stdout)
            
            # Update database
            results = db.update_from_discovery(discovery_data)
            db.save()
            
            last_scan_time = datetime.now()
            
            return {
                'success': True,
                'results': results,
                'timestamp': last_scan_time.isoformat()
            }
        else:
            return {
                'success': False,
                'error': result.stderr or 'Discovery failed'
            }
    
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Discovery timeout - cameras may not be responding'
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f'Invalid JSON from discovery: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        scan_in_progress = False


def auto_scan_worker():
    """Background worker for automatic scanning"""
    global auto_scan_enabled
    
    while True:
        if auto_scan_enabled:
            run_discovery()
        time.sleep(AUTO_SCAN_INTERVAL)


# Start auto-scan worker thread
scan_thread = threading.Thread(target=auto_scan_worker, daemon=True)
scan_thread.start()


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/cameras')
def get_cameras():
    """Get all cameras from database"""
    cameras = db.get_all_cameras_sorted('last_seen')
    
    camera_list = []
    for camera in cameras:
        status = get_camera_status(camera, 24)
        camera_list.append({
            'mac_address': camera.mac_address,
            'serial_number': camera.serial_number,
            'camera_name': camera.camera_name,
            'model_name': camera.model_name,
            'current_ip': camera.current_ip,
            'current_port': camera.current_port,
            'current_subnet': camera.current_subnet,
            'current_gateway': camera.current_gateway,
            'firmware_version': camera.firmware_version,
            'network_mode': camera.current_network_mode,
            'first_seen': camera.first_seen,
            'first_seen_formatted': format_timestamp(camera.first_seen),
            'last_seen': camera.last_seen,
            'last_seen_formatted': format_timestamp(camera.last_seen),
            'total_discoveries': camera.total_discoveries,
            'status': status,
            'ip_changes': len(camera.ip_history) - 1 if len(camera.ip_history) > 0 else 0,
            'seen_in_last_discovery': camera.seen_in_last_discovery
        })
    
    return jsonify({
        'cameras': camera_list,
        'count': len(camera_list),
        'last_scan': last_scan_time.isoformat() if last_scan_time else None,
        'scan_in_progress': scan_in_progress
    })


@app.route('/api/camera/<mac_address>')
def get_camera_detail(mac_address):
    """Get detailed information for a specific camera"""
    mac = mac_address.lower()
    
    if mac not in db.cameras:
        return jsonify({'error': 'Camera not found'}), 404
    
    camera = db.cameras[mac]
    status = get_camera_status(camera, 24)
    
    return jsonify({
        'mac_address': camera.mac_address,
        'serial_number': camera.serial_number,
        'camera_name': camera.camera_name,
        'model_name': camera.model_name,
        'current_ip': camera.current_ip,
        'current_port': camera.current_port,
        'current_subnet': camera.current_subnet,
        'current_gateway': camera.current_gateway,
        'firmware_version': camera.firmware_version,
        'network_mode': camera.current_network_mode,
        'first_seen': camera.first_seen,
        'first_seen_formatted': format_timestamp(camera.first_seen),
        'last_seen': camera.last_seen,
        'last_seen_formatted': format_timestamp(camera.last_seen),
        'total_discoveries': camera.total_discoveries,
        'status': status,
        'ip_history': camera.ip_history,
        'seen_in_last_discovery': camera.seen_in_last_discovery
    })


@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    total = len(db.cameras)
    
    if total == 0:
        return jsonify({
            'total_cameras': 0,
            'active': 0,
            'offline': 0,
            'missing': 0,
            'ip_changed': 0
        })
    
    cameras = list(db.cameras.values())
    
    stats = {
        'total_cameras': total,
        'active': sum(1 for c in cameras if get_camera_status(c, 24) == "Active"),
        'offline': sum(1 for c in cameras if get_camera_status(c, 24) == "Offline"),
        'missing': sum(1 for c in cameras if get_camera_status(c, 24) == "MISSING"),
        'ip_changed': sum(1 for c in cameras if get_camera_status(c, 24) == "IP Changed"),
        'total_discoveries': sum(c.total_discoveries for c in cameras),
        'cameras_with_ip_changes': sum(1 for c in cameras if len(c.ip_history) > 1),
        'last_scan': last_scan_time.isoformat() if last_scan_time else None,
        'scan_in_progress': scan_in_progress,
        'auto_scan_enabled': auto_scan_enabled,
        'auto_scan_interval': AUTO_SCAN_INTERVAL
    }
    
    return jsonify(stats)


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Trigger a manual discovery scan"""
    global scan_in_progress
    
    if scan_in_progress:
        return jsonify({
            'success': False,
            'error': 'Scan already in progress'
        }), 409
    
    # Run discovery in background
    def run_scan():
        result = run_discovery()
        # Result will be available on next API call
    
    thread = threading.Thread(target=run_scan)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Scan started'
    })


@app.route('/api/auto-scan', methods=['POST'])
def toggle_auto_scan():
    """Enable or disable automatic scanning"""
    global auto_scan_enabled
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    auto_scan_enabled = enabled
    
    return jsonify({
        'success': True,
        'auto_scan_enabled': auto_scan_enabled,
        'interval': AUTO_SCAN_INTERVAL
    })


@app.route('/api/export')
def export_database():
    """Export database as JSON"""
    return jsonify({
        mac: cam.to_dict()
        for mac, cam in db.cameras.items()
    })


if __name__ == '__main__':
    # Check if Easy_IP_3.py exists
    if not os.path.exists('Easy_IP_3.py'):
        print("Error: Easy_IP_3.py not found in current directory", file=sys.stderr)
        print("Please ensure Easy_IP_3.py is in the same directory as this script", file=sys.stderr)
        sys.exit(1)
    
    # Check if camera_tracker.py exists
    if not os.path.exists('camera_tracker.py'):
        print("Error: camera_tracker.py not found in current directory", file=sys.stderr)
        print("Please ensure camera_tracker.py is in the same directory as this script", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 70)
    print("Camera Monitor Web Service")
    print("=" * 70)
    print(f"Database: {DATABASE_PATH}")
    print(f"Auto-scan interval: {AUTO_SCAN_INTERVAL} seconds")
    print()
    print("Starting web server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
