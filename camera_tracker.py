#!/usr/bin/env python3
"""
Camera Tracker - Track Panasonic Camera Discovery History
Maintains a database of discovered cameras with timestamps and change tracking.
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import os


@dataclass
class CameraHistory:
    """Historical tracking information for a camera"""
    mac_address: str
    serial_number: str
    model_name: str
    camera_name: str
    firmware_version: str
    current_ip: str
    current_subnet: str
    current_gateway: str
    current_port: int
    current_network_mode: str
    first_seen: str  # ISO format timestamp
    last_seen: str  # ISO format timestamp
    ip_history: List[Dict[str, str]] = field(default_factory=list)  # List of {ip, timestamp}
    total_discoveries: int = 1
    seen_in_last_discovery: bool = True  # Track if seen in most recent discovery
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CameraHistory':
        """Create from dictionary"""
        return cls(**data)
    
    def update_from_discovery(self, camera_data: Dict, timestamp: str) -> Dict[str, any]:
        """
        Update camera history with new discovery data
        
        Returns:
            Dict with status information about what changed
        """
        changes = {
            'ip_changed': False,
            'name_changed': False,
            'firmware_changed': False,
            'was_missing': False,
            'old_ip': None,
            'new_ip': None
        }
        
        # Check if IP changed
        new_ip = camera_data.get('ip_address', '')
        if new_ip != self.current_ip:
            changes['ip_changed'] = True
            changes['old_ip'] = self.current_ip
            changes['new_ip'] = new_ip
            
            # Add to IP history
            self.ip_history.append({
                'ip': new_ip,
                'timestamp': timestamp,
                'previous_ip': self.current_ip
            })
            
            self.current_ip = new_ip
        
        # Check if camera name changed
        new_name = camera_data.get('camera_name', '')
        if new_name != self.camera_name and new_name:
            changes['name_changed'] = True
            self.camera_name = new_name
        
        # Check if firmware changed
        new_firmware = camera_data.get('firmware_version', '')
        if new_firmware != self.firmware_version and new_firmware:
            changes['firmware_changed'] = True
            self.firmware_version = new_firmware
        
        # Update other fields
        self.current_subnet = camera_data.get('subnet_mask', self.current_subnet)
        self.current_gateway = camera_data.get('gateway', self.current_gateway)
        self.current_port = camera_data.get('http_port', self.current_port)
        self.current_network_mode = camera_data.get('network_mode', self.current_network_mode)
        self.model_name = camera_data.get('model_name', self.model_name)
        
        # Update timestamps
        self.last_seen = timestamp
        self.total_discoveries += 1
        
        return changes
    
    @classmethod
    def from_discovery(cls, camera_data: Dict, timestamp: str) -> 'CameraHistory':
        """Create new camera history from discovery data"""
        return cls(
            mac_address=camera_data.get('mac_address', ''),
            serial_number=camera_data.get('serial_number', ''),
            model_name=camera_data.get('model_name', ''),
            camera_name=camera_data.get('camera_name', ''),
            firmware_version=camera_data.get('firmware_version', ''),
            current_ip=camera_data.get('ip_address', ''),
            current_subnet=camera_data.get('subnet_mask', ''),
            current_gateway=camera_data.get('gateway', ''),
            current_port=camera_data.get('http_port', 80),
            current_network_mode=camera_data.get('network_mode', ''),
            first_seen=timestamp,
            last_seen=timestamp,
            ip_history=[{
                'ip': camera_data.get('ip_address', ''),
                'timestamp': timestamp,
                'previous_ip': None
            }]
        )


class CameraDatabase:
    """Database for tracking camera history"""
    
    def __init__(self, db_path: str = 'camera_database.json'):
        self.db_path = Path(db_path)
        self.cameras: Dict[str, CameraHistory] = {}
        self.load()
    
    def load(self):
        """Load database from file"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.cameras = {
                        mac: CameraHistory.from_dict(cam_data)
                        for mac, cam_data in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load database: {e}", file=sys.stderr)
                self.cameras = {}
        else:
            self.cameras = {}
    
    def save(self):
        """Save database to file"""
        try:
            data = {
                mac: cam.to_dict()
                for mac, cam in self.cameras.items()
            }
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error: Could not save database: {e}", file=sys.stderr)
    
    def update_from_discovery(self, discovery_data: Dict) -> Dict[str, List]:
        """
        Update database with new discovery data
        
        Returns:
            Dict with lists of new, updated, and changed cameras
        """
        timestamp = datetime.now().isoformat()
        
        results = {
            'new_cameras': [],
            'updated_cameras': [],
            'ip_changed': [],
            'seen_macs': set()
        }
        
        cameras_list = discovery_data.get('cameras', [])
        
        # First, mark all cameras as NOT seen in this discovery
        for mac in self.cameras:
            self.cameras[mac].seen_in_last_discovery = False
        
        # Now process discovered cameras
        for camera_data in cameras_list:
            mac = camera_data.get('mac_address', '')
            if not mac:
                continue
            
            results['seen_macs'].add(mac)
            
            if mac in self.cameras:
                # Update existing camera
                self.cameras[mac].seen_in_last_discovery = True
                changes = self.cameras[mac].update_from_discovery(camera_data, timestamp)
                results['updated_cameras'].append({
                    'mac': mac,
                    'camera': self.cameras[mac],
                    'changes': changes
                })
                
                if changes['ip_changed']:
                    results['ip_changed'].append({
                        'mac': mac,
                        'camera': self.cameras[mac],
                        'old_ip': changes['old_ip'],
                        'new_ip': changes['new_ip']
                    })
            else:
                # New camera
                self.cameras[mac] = CameraHistory.from_discovery(camera_data, timestamp)
                self.cameras[mac].seen_in_last_discovery = True
                results['new_cameras'].append({
                    'mac': mac,
                    'camera': self.cameras[mac]
                })
        
        return results
    
    def get_missing_cameras(self, hours: int = 24) -> List[CameraHistory]:
        """Get cameras that haven't been seen recently"""
        from datetime import timedelta
        
        missing = []
        cutoff = datetime.now() - timedelta(hours=hours)
        
        for mac, camera in self.cameras.items():
            if not camera.seen_in_last_discovery:
                last_seen = datetime.fromisoformat(camera.last_seen)
                if last_seen < cutoff:
                    missing.append(camera)
        
        return missing
    
    def get_all_cameras_sorted(self, sort_by: str = 'last_seen') -> List[CameraHistory]:
        """Get all cameras sorted by specified field"""
        cameras = list(self.cameras.values())
        
        if sort_by == 'last_seen':
            cameras.sort(key=lambda c: c.last_seen, reverse=True)
        elif sort_by == 'first_seen':
            cameras.sort(key=lambda c: c.first_seen, reverse=True)
        elif sort_by == 'ip':
            def ip_key(camera):
                try:
                    return tuple(int(part) for part in camera.current_ip.split('.'))
                except:
                    return (255, 255, 255, 255)
            cameras.sort(key=ip_key)
        elif sort_by == 'mac':
            cameras.sort(key=lambda c: c.mac_address)
        elif sort_by == 'name':
            cameras.sort(key=lambda c: c.camera_name.lower())
        
        return cameras


def format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp to human-readable string"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_timestamp


def get_camera_status(camera: CameraHistory, hours: int = 24) -> str:
    """Determine camera status based on last discovery and time"""
    from datetime import timedelta
    
    # If camera was seen in last discovery, it's active (unless IP changed)
    if camera.seen_in_last_discovery:
        # Check if IP changed recently (within last discovery)
        if len(camera.ip_history) > 1:
            latest = camera.ip_history[-1]
            if latest.get('previous_ip'):
                return "IP Changed"
        return "Active"
    
    # Camera was NOT in last discovery - check how long it's been
    last_seen = datetime.fromisoformat(camera.last_seen)
    time_since = datetime.now() - last_seen
    
    if time_since > timedelta(hours=hours):
        return "MISSING"
    else:
        return "Offline"


def print_table(cameras: List[CameraHistory], show_all: bool = False, missing_hours: int = 24):
    """Print cameras in a formatted table"""
    if not cameras:
        print("No cameras in database.")
        return
    
    # Define columns
    headers = ['MAC Address', 'Camera Name', 'IP Address', 'Model', 
               'First Seen', 'Last Seen', 'Discoveries', 'Status']
    
    # Calculate column widths
    col_widths = {
        'MAC Address': max(17, max((len(c.mac_address) for c in cameras), default=17)),
        'Camera Name': max(11, max((len(c.camera_name) for c in cameras), default=11)),
        'IP Address': max(15, max((len(c.current_ip) for c in cameras), default=15)),
        'Model': max(15, max((len(c.model_name) for c in cameras), default=15)),
        'First Seen': 19,  # YYYY-MM-DD HH:MM:SS
        'Last Seen': 19,
        'Discoveries': 11,
        'Status': 12
    }
    
    # Build separator
    separator = '+-' + '-+-'.join('-' * col_widths[h] for h in headers) + '-+'
    
    # Print header
    print(separator)
    header_row = '| ' + ' | '.join(h.ljust(col_widths[h]) for h in headers) + ' |'
    print(header_row)
    print(separator)
    
    # Print each camera
    for camera in cameras:
        status = get_camera_status(camera, missing_hours)
        
        # Skip offline/missing if not showing all
        if not show_all and status in ['MISSING', 'Offline']:
            continue
        
        mac = camera.mac_address.ljust(col_widths['MAC Address'])
        name = camera.camera_name[:col_widths['Camera Name']].ljust(col_widths['Camera Name'])
        ip = camera.current_ip.ljust(col_widths['IP Address'])
        model = camera.model_name[:col_widths['Model']].ljust(col_widths['Model'])
        first = format_timestamp(camera.first_seen).ljust(col_widths['First Seen'])
        last = format_timestamp(camera.last_seen).ljust(col_widths['Last Seen'])
        discoveries = str(camera.total_discoveries).ljust(col_widths['Discoveries'])
        status_str = status.ljust(col_widths['Status'])
        
        row = f"| {mac} | {name} | {ip} | {model} | {first} | {last} | {discoveries} | {status_str} |"
        
        # Add status indicator
        if status == "MISSING":
            print(row + " ⚠️  MISSING")
        elif status == "IP Changed":
            print(row + " 🔄 IP CHANGED")
        elif status == "Offline":
            print(row + " ⏸️  OFFLINE")
        else:
            print(row)
    
    print(separator)
    
    # Print summary
    total = len(cameras)
    active = sum(1 for c in cameras if get_camera_status(c, missing_hours) == "Active")
    ip_changed = sum(1 for c in cameras if get_camera_status(c, missing_hours) == "IP Changed")
    offline = sum(1 for c in cameras if get_camera_status(c, missing_hours) == "Offline")
    missing = sum(1 for c in cameras if get_camera_status(c, missing_hours) == "MISSING")
    
    print(f"\nTotal cameras: {total}")
    print(f"Active: {active} | IP Changed: {ip_changed} | Offline: {offline} | Missing: {missing}")


def print_changes_summary(results: Dict):
    """Print summary of changes from update"""
    new_count = len(results['new_cameras'])
    updated_count = len(results['updated_cameras'])
    ip_changed_count = len(results['ip_changed'])
    
    print("=" * 70)
    print("Camera Discovery Update Summary")
    print("=" * 70)
    
    if new_count > 0:
        print(f"\n✨ New Cameras Discovered: {new_count}")
        for item in results['new_cameras']:
            camera = item['camera']
            print(f"  - {camera.camera_name} ({camera.mac_address}) at {camera.current_ip}")
    
    if ip_changed_count > 0:
        print(f"\n🔄 IP Address Changes: {ip_changed_count}")
        for item in results['ip_changed']:
            camera = item['camera']
            old_ip = item['old_ip']
            new_ip = item['new_ip']
            print(f"  - {camera.camera_name} ({camera.mac_address})")
            print(f"    {old_ip} → {new_ip}")
    
    if updated_count > 0 and ip_changed_count == 0:
        print(f"\n✓ Updated Cameras: {updated_count}")
        for item in results['updated_cameras']:
            camera = item['camera']
            print(f"  - {camera.camera_name} ({camera.mac_address}) at {camera.current_ip}")
    
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Camera Tracker - Track Panasonic camera discovery history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pipe discovery output directly into tracker
  python Easy_IP_3.py discover --json | python camera_tracker.py update
  
  # Update from saved JSON file
  python camera_tracker.py update --input cameras.json
  
  # Show all tracked cameras
  python camera_tracker.py list --table
  
  # Show only active cameras
  python camera_tracker.py list --table --active-only
  
  # Export database to JSON
  python camera_tracker.py export --output cameras_db.json
  
  # Show cameras with IP changes
  python camera_tracker.py list --table --sort last_seen
        """
    )
    
    parser.add_argument('--database', default='camera_database.json',
                       help='Path to camera database file (default: camera_database.json)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update database with new discovery data')
    update_parser.add_argument('--input', '-i', 
                              help='Input JSON file (if not provided, reads from stdin)')
    update_parser.add_argument('--quiet', '-q', action='store_true',
                              help='Suppress output, only update database')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List tracked cameras')
    list_parser.add_argument('--table', action='store_true',
                            help='Output in formatted table')
    list_parser.add_argument('--json', action='store_true',
                            help='Output in JSON format')
    list_parser.add_argument('--sort', choices=['last_seen', 'first_seen', 'ip', 'mac', 'name'],
                            default='last_seen',
                            help='Sort order (default: last_seen)')
    list_parser.add_argument('--active-only', action='store_true',
                            help='Show only active cameras (hide offline/missing)')
    list_parser.add_argument('--missing-hours', type=int, default=24,
                            help='Hours before camera considered missing (default: 24)')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export database to JSON')
    export_parser.add_argument('--output', '-o', required=True,
                              help='Output JSON file')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # History command
    history_parser = subparsers.add_parser('history', help='Show IP change history for a camera')
    history_parser.add_argument('--mac', required=True,
                               help='MAC address of camera')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize database
    db = CameraDatabase(args.database)
    
    # Execute command
    if args.command == 'update':
        # Read input JSON
        if args.input:
            with open(args.input, 'r') as f:
                discovery_data = json.load(f)
        else:
            # Read from stdin
            try:
                discovery_data = json.load(sys.stdin)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
                sys.exit(1)
        
        # Update database
        results = db.update_from_discovery(discovery_data)
        db.save()
        
        if not args.quiet:
            print_changes_summary(results)
            print(f"Database updated: {db.db_path}")
    
    elif args.command == 'list':
        cameras = db.get_all_cameras_sorted(args.sort)
        
        if not cameras:
            print("No cameras in database.")
            sys.exit(0)
        
        if args.json:
            output = {
                'count': len(cameras),
                'cameras': [cam.to_dict() for cam in cameras]
            }
            print(json.dumps(output, indent=2))
        elif args.table:
            # Get recently seen MACs for status determination
            print_table(cameras, show_all=not args.active_only, 
                       missing_hours=args.missing_hours)
        else:
            # Simple list
            for camera in cameras:
                print(f"{camera.camera_name} ({camera.mac_address}) - {camera.current_ip}")
                print(f"  First seen: {format_timestamp(camera.first_seen)}")
                print(f"  Last seen: {format_timestamp(camera.last_seen)}")
                print(f"  Discoveries: {camera.total_discoveries}")
                print()
    
    elif args.command == 'export':
        data = {
            mac: cam.to_dict()
            for mac, cam in db.cameras.items()
        }
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Database exported to {args.output}")
    
    elif args.command == 'stats':
        total = len(db.cameras)
        
        if total == 0:
            print("No cameras in database.")
            sys.exit(0)
        
        # Calculate stats
        total_discoveries = sum(cam.total_discoveries for cam in db.cameras.values())
        avg_discoveries = total_discoveries / total if total > 0 else 0
        
        cameras_with_ip_changes = sum(
            1 for cam in db.cameras.values() if len(cam.ip_history) > 1
        )
        
        print("=" * 60)
        print("Camera Database Statistics")
        print("=" * 60)
        print(f"Total cameras tracked: {total}")
        print(f"Total discoveries: {total_discoveries}")
        print(f"Average discoveries per camera: {avg_discoveries:.1f}")
        print(f"Cameras with IP changes: {cameras_with_ip_changes}")
        print()
        
        # Most/least recently seen
        cameras = list(db.cameras.values())
        cameras.sort(key=lambda c: c.last_seen, reverse=True)
        
        print("Most recently seen:")
        for cam in cameras[:5]:
            print(f"  {cam.camera_name} ({cam.mac_address}) - {format_timestamp(cam.last_seen)}")
        
        if len(cameras) > 5:
            print("\nLeast recently seen:")
            for cam in cameras[-5:]:
                print(f"  {cam.camera_name} ({cam.mac_address}) - {format_timestamp(cam.last_seen)}")
    
    elif args.command == 'history':
        mac = args.mac.lower()
        
        if mac not in db.cameras:
            print(f"Error: Camera with MAC {mac} not found in database.", file=sys.stderr)
            sys.exit(1)
        
        camera = db.cameras[mac]
        
        print("=" * 70)
        print(f"IP Change History: {camera.camera_name} ({camera.mac_address})")
        print("=" * 70)
        print(f"Current IP: {camera.current_ip}")
        print(f"First seen: {format_timestamp(camera.first_seen)}")
        print(f"Last seen: {format_timestamp(camera.last_seen)}")
        print(f"Total discoveries: {camera.total_discoveries}")
        print()
        
        if len(camera.ip_history) > 0:
            print("IP Address History:")
            for i, entry in enumerate(camera.ip_history, 1):
                timestamp = format_timestamp(entry['timestamp'])
                ip = entry['ip']
                prev_ip = entry.get('previous_ip')
                
                if prev_ip:
                    print(f"  [{i}] {timestamp}: {prev_ip} → {ip}")
                else:
                    print(f"  [{i}] {timestamp}: {ip} (first discovery)")
        else:
            print("No IP history available.")


if __name__ == '__main__':
    main()
