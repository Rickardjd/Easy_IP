#!/usr/bin/env python3
"""
i-PRO Camera and Recorder IP Setup Tool
A cross-platform Python alternative to i-PRO's Easy IP Setup Tool.
Discovers and configures network settings for i-PRO IP cameras and recorders.
"""

import socket
import struct
import sys
import argparse
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from enum import IntEnum
from collections import Counter

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MessageType(IntEnum):
    """i-PRO Easy IP Setup protocol message types"""
    SEARCH_REQUEST = 0x0011
    SEARCH_RESPONSE = 0x0012
    CONFIG_REQUEST = 0x0021
    CONFIG_RESPONSE = 0x0022


@dataclass
class DeviceInfo:
    """Information about a discovered i-PRO device (camera or recorder)"""
    device_type: str  # "camera" or "recorder"
    mac_address: str
    model_name: str
    ip_address: str
    subnet_mask: str
    gateway: str
    http_port: int
    firmware_version: str
    device_name: str
    serial_number: str
    network_mode: str
    device_type_code: Optional[int] = None  # Raw device type code from tag 0xa6
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_csv_row(self) -> List[str]:
        """Return data as CSV row"""
        return [
            self.device_type,
            self.device_name,
            self.model_name,
            self.serial_number,
            self.mac_address,
            self.ip_address,
            self.subnet_mask,
            self.gateway,
            str(self.http_port),
            self.network_mode,
            self.firmware_version
        ]
    
    @staticmethod
    def csv_headers() -> List[str]:
        """Return CSV headers"""
        return [
            "Device Type",
            "Device Name",
            "Model",
            "Serial Number",
            "MAC Address",
            "IP Address",
            "Subnet Mask",
            "Gateway",
            "HTTP Port",
            "Network Mode",
            "Firmware"
        ]
    
    def __str__(self) -> str:
        """Human-readable representation"""
        device_label = "Recorder" if self.device_type == "recorder" else "Camera"
        return (
            f"{device_label}: {self.device_name}\n"
            f"  Model: {self.model_name}\n"
            f"  Serial: {self.serial_number}\n"
            f"  MAC: {self.mac_address}\n"
            f"  IP: {self.ip_address}\n"
            f"  Subnet: {self.subnet_mask}\n"
            f"  Gateway: {self.gateway}\n"
            f"  HTTP Port: {self.http_port}\n"
            f"  Network Mode: {self.network_mode}\n"
            f"  Firmware: {self.firmware_version}"
        )


def sort_devices(devices: List[DeviceInfo], sort_by: str = 'ip') -> List[DeviceInfo]:
    """
    Sort devices by specified field
    
    Args:
        devices: List of DeviceInfo objects to sort
        sort_by: Field to sort by ('ip', 'mac', 'serial', 'type')
    
    Returns:
        Sorted list of DeviceInfo objects
    """
    sort_by = sort_by.lower()
    
    if sort_by == 'ip':
        # Sort by IP address (convert to tuple of ints for proper numeric sorting)
        def ip_key(device):
            try:
                return tuple(int(part) for part in device.ip_address.split('.'))
            except:
                return (255, 255, 255, 255)  # Put invalid IPs at end
        return sorted(devices, key=ip_key)
    
    elif sort_by == 'mac':
        # Sort by MAC address
        def mac_key(device):
            # Remove separators and convert to uppercase for consistent sorting
            return device.mac_address.replace(':', '').replace('-', '').upper()
        return sorted(devices, key=mac_key)
    
    elif sort_by == 'serial':
        # Sort by serial number
        return sorted(devices, key=lambda d: d.serial_number)
    
    elif sort_by == 'type':
        # Sort by device type (cameras first, then recorders), then by IP
        def type_ip_key(device):
            type_priority = 0 if device.device_type == 'camera' else 1
            try:
                ip_tuple = tuple(int(part) for part in device.ip_address.split('.'))
            except:
                ip_tuple = (255, 255, 255, 255)
            return (type_priority, ip_tuple)
        return sorted(devices, key=type_ip_key)
    
    else:
        # Default to IP sorting if invalid sort option
        return sort_devices(devices, 'ip')


def detect_ip_overlaps(devices: List[DeviceInfo]) -> Dict[str, List[str]]:
    """
    Detect duplicate IP addresses
    
    Args:
        devices: List of DeviceInfo objects
    
    Returns:
        Dictionary mapping IP addresses to list of device identifiers (serial or MAC)
    """
    ip_map = {}
    for device in devices:
        if device.ip_address not in ip_map:
            ip_map[device.ip_address] = []
        identifier = device.serial_number if device.serial_number else device.mac_address
        ip_map[device.ip_address].append(identifier)
    
    # Return only IPs with multiple devices
    return {ip: devices for ip, devices in ip_map.items() if len(devices) > 1}


def print_table(devices: List[DeviceInfo], show_warnings: bool = True):
    """
    Print devices in a formatted table
    
    Args:
        devices: List of DeviceInfo objects
        show_warnings: Whether to show IP overlap warnings
    """
    if not devices:
        print("No devices discovered.")
        return
    
    # Separate cameras and recorders
    cameras = [d for d in devices if d.device_type == 'camera']
    recorders = [d for d in devices if d.device_type == 'recorder']
    
    # Detect IP overlaps
    overlaps = detect_ip_overlaps(devices)
    
    # Define column headers and widths
    headers = ['Type', 'MAC Address', 'IP Address', 'Port', 'Device Name', 'Model', 'Serial Number']
    
    # Calculate column widths based on content
    col_widths = {
        'Type': 8,
        'MAC Address': max(17, max((len(d.mac_address) for d in devices), default=17)),
        'IP Address': max(15, max((len(d.ip_address) for d in devices), default=15)),
        'Port': 6,
        'Device Name': max(11, max((len(d.device_name) for d in devices), default=11)),
        'Model': max(15, max((len(d.model_name) for d in devices), default=15)),
        'Serial Number': max(13, max((len(d.serial_number) for d in devices), default=13))
    }
    
    # Build separator line
    separator = '+-' + '-+-'.join('-' * col_widths[h] for h in headers) + '-+'
    
    # Print header
    print(separator)
    header_row = '| ' + ' | '.join(h.ljust(col_widths[h]) for h in headers) + ' |'
    print(header_row)
    print(separator)
    
    # Print each device
    for device in devices:
        device_type = device.device_type.capitalize()[:col_widths['Type']].ljust(col_widths['Type'])
        mac = device.mac_address.ljust(col_widths['MAC Address'])
        ip = device.ip_address.ljust(col_widths['IP Address'])
        port = str(device.http_port).ljust(col_widths['Port'])
        name = device.device_name[:col_widths['Device Name']].ljust(col_widths['Device Name'])
        model = device.model_name[:col_widths['Model']].ljust(col_widths['Model'])
        serial = device.serial_number.ljust(col_widths['Serial Number'])
        
        # Check if this device has an overlapping IP
        has_overlap = device.ip_address in overlaps
        
        row = f"| {device_type} | {mac} | {ip} | {port} | {name} | {model} | {serial} |"
        
        if has_overlap and show_warnings:
            # Print row with warning marker
            print(row + " ⚠️  IP CONFLICT")
        else:
            print(row)
    
    print(separator)
    
    # Print summary
    print(f"\nTotal devices discovered: {len(devices)}")
    if cameras:
        print(f"  Cameras: {len(cameras)}")
    if recorders:
        print(f"  Recorders: {len(recorders)}")
    
    # Print warnings if IP overlaps detected
    if overlaps and show_warnings:
        print("\n⚠️  WARNING: IP ADDRESS CONFLICTS DETECTED!")
        print("=" * 60)
        for ip, device_list in overlaps.items():
            print(f"  IP {ip} is assigned to {len(device_list)} devices:")
            for device in device_list:
                print(f"    - {device}")
        print("\nPlease reconfigure devices to use unique IP addresses.")


class iPROIPSetup:
    """Main class for discovering and configuring i-PRO cameras and recorders"""
    
    # Correct ports based on packet capture
    BROADCAST_PORT = 10670  # 0x29ae - destination port
    SOURCE_PORT = 10669     # 0x29ad - source port  
    BUFFER_SIZE = 4096
    BROADCAST_ADDR = "255.255.255.255"
    
    def __init__(self, timeout: float = 3.0, interface: str = "0.0.0.0", verbose: bool = False):
        """
        Initialize the setup tool
        
        Args:
            timeout: Socket timeout in seconds
            interface: Network interface IP to bind to
            verbose: Enable verbose diagnostic output
        """
        self.timeout = timeout
        self.interface = interface
        self.verbose = verbose
        self.sock = None
        
        if verbose:
            # Enable console logging for diagnostics
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    
    def _create_socket(self) -> socket.socket:
        """Create and configure UDP broadcast socket"""
        logger.info("Creating UDP broadcast socket...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.timeout)
        
        # Bind to the source port used by i-PRO protocol
        bind_addr = (self.interface, self.SOURCE_PORT)
        logger.info(f"Binding socket to {bind_addr}")
        try:
            sock.bind(bind_addr)
        except OSError as e:
            if e.errno == 48 or e.errno == 98:  # Address already in use
                logger.warning(f"Port {self.SOURCE_PORT} in use, binding to any port")
                sock.bind((self.interface, 0))
            else:
                raise
        
        # Get actual bound address
        actual_addr = sock.getsockname()
        logger.info(f"Socket bound to {actual_addr}")
        
        return sock
    
    def _build_search_packet(self) -> bytes:
        """
        Build search request packet for i-PRO protocol
        Based on actual packet capture from i-PRO Easy IP Setup Tool
        
        Packet structure from capture (starting at UDP payload):
        00 01 00 2a - Header
        00 0d 00 00 00 00 00 00 - Command/flags
        [MAC address - 6 bytes]
        [IP address - 4 bytes]
        00 00 - Padding
        [Additional data...]
        """
        packet = bytearray()
        
        # Get local MAC and IP for the packet
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            local_ip_bytes = bytes(map(int, local_ip.split('.')))
        except:
            local_ip_bytes = bytes([192, 168, 1, 100])  # Fallback
        
        # Try to get MAC address (platform-specific, may not work everywhere)
        import uuid
        try:
            mac = uuid.getnode()
            mac_bytes = mac.to_bytes(6, 'big')
        except:
            mac_bytes = bytes([0xa0, 0x29, 0x19, 0x3e, 0xab, 0x91])  # Fallback
        
        # Build packet based on capture
        # Header: 00 01 00 2a
        packet.extend([0x00, 0x01, 0x00, 0x2a])
        
        # Command: 00 0d 00 00 00 00 00 00
        packet.extend([0x00, 0x0d, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        # Source MAC address (6 bytes)
        packet.extend(mac_bytes)
        
        # Source IP address (4 bytes)
        packet.extend(local_ip_bytes)
        
        # Padding/flags: 00 00 20 11 1e 11 23 1f 1e 19 13
        packet.extend([0x00, 0x00, 0x20, 0x11, 0x1e, 0x11, 0x23, 0x1f, 0x1e, 0x19, 0x13])
        
        # More data: 00 00 02 01 00 00 00 00 00 00 00 00 00 00 00
        # Bytes 33-36: 00 00 02 01
        # Bytes 37-47: 11 zeros (not 12!)
        # NOTE: Byte at position 35 (value 0x02) is CRITICAL for recorder discovery!
        packet.extend([0x00, 0x00, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 
                      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        # Category flags: ff f0
        packet.extend([0xff, 0xf0])
        
        # Supported models/types: 00 26 00 20 00 21 00 22 00 23 00 25 00 28 
        # 00 40 00 41 00 42 00 44 00 a5 00 a6 00 a7 00 a8 00 ad 00 b3 00 b4
        # 00 b7 00 b8 ff ff
        model_types = [
            0x00, 0x26, 0x00, 0x20, 0x00, 0x21, 0x00, 0x22, 0x00, 0x23, 
            0x00, 0x25, 0x00, 0x28, 0x00, 0x40, 0x00, 0x41, 0x00, 0x42, 
            0x00, 0x44, 0x00, 0xa5, 0x00, 0xa6, 0x00, 0xa7, 0x00, 0xa8, 
            0x00, 0xad, 0x00, 0xb3, 0x00, 0xb4, 0x00, 0xb7, 0x00, 0xb8, 
            0xff, 0xff
        ]
        packet.extend(model_types)
        
        # Trailer bytes (required for recorder discovery)
        # These appear in Panasonic Easy IP broadcast but were missing
        packet.extend([0x11, 0x70])
        
        logger.debug(f"Built search packet: {len(packet)} bytes")
        if self.verbose:
            logger.debug(f"Packet hex: {packet.hex()}")
        
        return bytes(packet)
    
    def _parse_response(self, data: bytes, addr: tuple) -> Optional[DeviceInfo]:
        """
        Parse device response packet using TLV (Type-Length-Value) format
        
        Response format:
        - Header: 00 01 [response_type] [command]
        - Device MAC: 6 bytes at offset 6
        - TLV fields starting around offset 0x30:
          0x00 = Network mode (1 byte: 0=DHCP, 2=Static, 4=Auto(AutoIP), 5=Auto Advanced)
          0x20 = IP address (4 bytes)
          0x21 = Subnet mask (4 bytes)
          0x22 = Gateway (4 bytes)
          0x25 = HTTP port (2 bytes)
          0xa6 = Device type (1 byte: 0x91=Camera, 0x92=Recorder) *** KEY FOR RECORDER DETECTION ***
          0xa7 = Device name (string)
          0xa8 = Model name (string)
          0xa9 = Firmware version (string)
          0xc0 = Channels (2 bytes - for recorders)
          0xc1 = Capacity (2 bytes - for recorders)
          0xd1 = Serial number (string)
        
        Args:
            data: Raw packet data
            addr: Source address tuple
            
        Returns:
            DeviceInfo object if valid response, None otherwise
        """
        logger.debug(f"Received {len(data)} bytes from {addr}")
        
        if len(data) < 20:
            logger.warning(f"Packet too short: {len(data)} bytes")
            return None
        
        try:
            # Check header - should start with 00 01
            if data[0] != 0x00 or data[1] != 0x01:
                logger.warning(f"Invalid header: expected 00 01, got {data[0]:02x} {data[1]:02x}")
                return None
            
            # Response type in bytes 2-3
            response_type = struct.unpack(">H", data[2:4])[0]
            logger.debug(f"Response type: 0x{response_type:04x}")
            
            # Extract MAC address at offset 6
            mac_bytes = data[6:12]
            mac_address = ":".join(f"{b:02x}" for b in mac_bytes)
            logger.debug(f"Device MAC: {mac_address}")
            
            # Parse TLV fields
            tlv_data = {}
            offset = 0x30  # TLV data starts around here
            
            while offset + 4 < len(data):
                # Check for end marker (ff ff)
                if data[offset:offset+2] == b'\xff\xff':
                    break
                
                # Read tag (2 bytes) and length (2 bytes)
                tag = struct.unpack(">H", data[offset:offset+2])[0]
                length = struct.unpack(">H", data[offset+2:offset+4])[0]
                
                if offset + 4 + length > len(data):
                    break
                
                # Read value
                value = data[offset+4:offset+4+length]
                tlv_data[tag] = value
                
                logger.debug(f"TLV: tag=0x{tag:02x}, len={length}, value={value.hex()}")
                
                offset += 4 + length
            
            # Extract fields from TLV data
            
            # First, extract model name as we'll need it for device type detection
            # 0xa8 = Model name (null-terminated string)
            model_name = "Unknown"
            if 0xa8 in tlv_data:
                model_name = tlv_data[0xa8].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                if not model_name:
                    model_name = "Unknown"
                logger.debug(f"Model from TLV 0xa8: {model_name}")
            
            # *** Device Type Detection ***
            # Tag 0xa6 is NOT a reliable device type indicator (it's 0x92 for all i-PRO cameras)
            # Instead, we detect recorders by:
            # 1. Presence of tag 0xc0 (channels) - only recorders have this
            # 2. Model name starting with "NX" or "WJ" (i-PRO recorder series)
            device_type = "camera"  # Default to camera
            device_type_code = None
            
            # Check for recorder-specific tags
            has_channels_tag = 0xc0 in tlv_data
            is_recorder_model = model_name.startswith(('NX', 'WJ'))  # i-PRO recorder model prefixes
            
            if has_channels_tag or is_recorder_model:
                device_type = "recorder"
                logger.debug(f"Device identified as RECORDER (channels_tag={has_channels_tag}, model_prefix={is_recorder_model})")
            else:
                device_type = "camera"
                logger.debug(f"Device identified as CAMERA")
            
            # Store the 0xa6 value for reference (but it's not the device type)
            if 0xa6 in tlv_data and len(tlv_data[0xa6]) >= 1:
                device_type_code = tlv_data[0xa6][0]
                logger.debug(f"Tag 0xa6 value: 0x{device_type_code:02x} (not device type indicator)")
            
            # 0x00 = Network mode (NOT 0x01)
            network_mode = "Unknown"
            network_mode_value = None
            
            # Check tag 0x00 for network mode (0x01 is something else)
            if 0x00 in tlv_data and len(tlv_data[0x00]) >= 1:
                network_mode_value = tlv_data[0x00][0]
            
            # Also check in early packet data (sometimes at specific offsets)
            if network_mode_value is None and len(data) > 0x32:
                # Check offset 0x32 which sometimes contains network settings
                network_mode_value = data[0x32]
            
            if network_mode_value is not None:
                network_modes = {
                    0: "DHCP",
                    2: "Static",
                    4: "Auto (AutoIP)",
                    5: "Auto Advanced"
                }
                network_mode = network_modes.get(network_mode_value, f"Unknown ({network_mode_value})")
                logger.debug(f"Network mode: {network_mode} (value={network_mode_value})")
            
            # 0x20 = IP address
            ip_address = addr[0]  # Default to source address
            if 0x20 in tlv_data and len(tlv_data[0x20]) == 4:
                ip_address = ".".join(str(b) for b in tlv_data[0x20])
                logger.debug(f"IP from TLV 0x20: {ip_address}")
            
            # 0x21 = Subnet mask
            subnet_mask = "255.255.255.0"
            if 0x21 in tlv_data and len(tlv_data[0x21]) == 4:
                subnet_mask = ".".join(str(b) for b in tlv_data[0x21])
                logger.debug(f"Subnet from TLV 0x21: {subnet_mask}")
            
            # 0x22 = Gateway
            gateway = "0.0.0.0"
            if 0x22 in tlv_data and len(tlv_data[0x22]) == 4:
                gateway = ".".join(str(b) for b in tlv_data[0x22])
                logger.debug(f"Gateway from TLV 0x22: {gateway}")
            
            # 0x25 = HTTP port
            http_port = 80
            if 0x25 in tlv_data and len(tlv_data[0x25]) == 2:
                http_port = struct.unpack(">H", tlv_data[0x25])[0]
                logger.debug(f"HTTP port from TLV 0x25: {http_port}")
            
            # 0xa7 = Device name (null-terminated string)
            device_name = "Device"
            if 0xa7 in tlv_data:
                device_name = tlv_data[0xa7].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                if not device_name:  # If empty after stripping
                    device_name = "Device"
                logger.debug(f"Device name from TLV 0xa7: {device_name}")
            
            # Model name was already extracted above for device type detection
            
            # 0xa9 = Firmware version (null-terminated string)
            firmware_version = "Unknown"
            if 0xa9 in tlv_data:
                firmware_version = tlv_data[0xa9].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                if not firmware_version:
                    firmware_version = "Unknown"
                logger.debug(f"Firmware from TLV 0xa9: {firmware_version}")
            
            # 0xd1 = Serial number (null-terminated string)
            serial_number = "Unknown"
            if 0xd1 in tlv_data:
                serial_number = tlv_data[0xd1].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                if not serial_number:
                    serial_number = "Unknown"
                logger.debug(f"Serial from TLV 0xd1: {serial_number}")
            
            device_label = "recorder" if device_type == "recorder" else "camera"
            logger.info(f"✓ Parsed {device_label}: {model_name} ({device_name}) at {ip_address} [{network_mode}]")
            
            return DeviceInfo(
                device_type=device_type,
                mac_address=mac_address,
                model_name=model_name,
                ip_address=ip_address,
                subnet_mask=subnet_mask,
                gateway=gateway,
                http_port=http_port,
                firmware_version=firmware_version,
                device_name=device_name,
                serial_number=serial_number,
                network_mode=network_mode,
                device_type_code=device_type_code
            )
        
        except Exception as e:
            logger.error(f"Error parsing response: {e}", exc_info=True)
            return None
    
    def discover_devices(self) -> List[DeviceInfo]:
        """
        Discover all i-PRO devices (cameras and recorders) on the network
        
        Returns:
            List of discovered devices
        """
        devices = []
        seen_macs = set()
        
        logger.info("=" * 60)
        logger.info("Starting device discovery...")
        logger.info(f"Timeout: {self.timeout}s")
        logger.info(f"Broadcast address: {self.BROADCAST_ADDR}:{self.BROADCAST_PORT}")
        logger.info("=" * 60)
        
        try:
            self.sock = self._create_socket()
            search_packet = self._build_search_packet()
            
            # Send broadcast search
            dest = (self.BROADCAST_ADDR, self.BROADCAST_PORT)
            logger.info(f"Sending search packet to {dest}")
            bytes_sent = self.sock.sendto(search_packet, dest)
            logger.info(f"Sent {bytes_sent} bytes")
            
            # Collect responses
            logger.info(f"Listening for responses (timeout: {self.timeout}s)...")
            start_time = time.time()
            response_count = 0
            
            while time.time() - start_time < self.timeout:
                remaining = self.timeout - (time.time() - start_time)
                logger.debug(f"Time remaining: {remaining:.2f}s")
                
                try:
                    data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                    response_count += 1
                    logger.info(f"Response #{response_count} from {addr}")
                    
                    device = self._parse_response(data, addr)
                    
                    if device and device.mac_address not in seen_macs:
                        device_label = "recorder" if device.device_type == "recorder" else "camera"
                        logger.info(f"✓ Valid {device_label} found: {device.model_name} ({device.mac_address})")
                        devices.append(device)
                        seen_macs.add(device.mac_address)
                    elif device:
                        logger.debug(f"Duplicate device response from {device.mac_address}")
                
                except socket.timeout:
                    logger.debug("Socket timeout - no more responses")
                    break
                except Exception as e:
                    logger.error(f"Error receiving data: {e}", exc_info=True)
                    continue
            
            elapsed = time.time() - start_time
            cameras = [d for d in devices if d.device_type == 'camera']
            recorders = [d for d in devices if d.device_type == 'recorder']
            
            logger.info("=" * 60)
            logger.info(f"Discovery complete in {elapsed:.2f}s")
            logger.info(f"Total responses received: {response_count}")
            logger.info(f"Valid devices found: {len(devices)}")
            if cameras:
                logger.info(f"  Cameras: {len(cameras)}")
            if recorders:
                logger.info(f"  Recorders: {len(recorders)}")
            logger.info("=" * 60)
        
        except Exception as e:
            logger.error(f"Discovery error: {e}", exc_info=True)
        finally:
            if self.sock:
                logger.debug("Closing socket")
                self.sock.close()
        
        return devices
    
    # Keep old method name for backward compatibility
    def discover_cameras(self) -> List[DeviceInfo]:
        """Alias for discover_devices() for backward compatibility"""
        return self.discover_devices()
    
    def configure_camera(self, mac_address: str, ip: str, subnet: str, 
                        gateway: str, port: int = 80) -> bool:
        """
        Configure network settings for a specific camera
        
        Args:
            mac_address: Target camera MAC address (format: "aa:bb:cc:dd:ee:ff")
            ip: New IP address
            subnet: New subnet mask
            gateway: New gateway address
            port: HTTP port (default: 80)
        
        Returns:
            True if configuration successful, False otherwise
        """
        logger.info(f"Configuring device {mac_address}")
        logger.info(f"  New IP: {ip}")
        logger.info(f"  Subnet: {subnet}")
        logger.info(f"  Gateway: {gateway}")
        logger.info(f"  Port: {port}")
        
        try:
            self.sock = self._create_socket()
            
            # Parse MAC address
            mac_parts = mac_address.replace('-', ':').split(':')
            if len(mac_parts) != 6:
                logger.error(f"Invalid MAC address format: {mac_address}")
                return False
            
            mac_bytes = bytes([int(x, 16) for x in mac_parts])
            
            # Parse IP addresses
            ip_bytes = bytes([int(x) for x in ip.split('.')])
            subnet_bytes = bytes([int(x) for x in subnet.split('.')])
            gateway_bytes = bytes([int(x) for x in gateway.split('.')])
            
            # Build configuration packet
            packet = bytearray()
            
            # Header: 00 01 00 21 (config request)
            packet.extend([0x00, 0x01, 0x00, 0x21])
            
            # Command: 00 0e (configure command)
            packet.extend([0x00, 0x0e])
            
            # MAC address (6 bytes)
            packet.extend(mac_bytes)
            
            # Network configuration TLV fields
            # Tag 0x20: IP Address
            packet.extend([0x00, 0x20, 0x00, 0x04])
            packet.extend(ip_bytes)
            
            # Tag 0x21: Subnet Mask
            packet.extend([0x00, 0x21, 0x00, 0x04])
            packet.extend(subnet_bytes)
            
            # Tag 0x22: Gateway
            packet.extend([0x00, 0x22, 0x00, 0x04])
            packet.extend(gateway_bytes)
            
            # Tag 0x25: HTTP Port
            packet.extend([0x00, 0x25, 0x00, 0x02])
            packet.extend(struct.pack(">H", port))
            
            # End marker
            packet.extend([0xff, 0xff])
            
            logger.debug(f"Sending configuration packet ({len(packet)} bytes)")
            
            # Send to broadcast address
            dest = (self.BROADCAST_ADDR, self.BROADCAST_PORT)
            self.sock.sendto(bytes(packet), dest)
            
            # Wait for confirmation response
            try:
                data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                logger.info(f"Received response from {addr}")
                
                # Check if response is success (0x0022)
                if len(data) >= 4 and data[2:4] == b'\x00\x22':
                    logger.info("Configuration successful!")
                    return True
                else:
                    logger.warning(f"Unexpected response type: {data[2:4].hex()}")
                    return False
            except socket.timeout:
                logger.warning("No response received (timeout)")
                return False
        
        except Exception as e:
            logger.error(f"Error configuring device: {e}", exc_info=True)
            return False
        
        finally:
            if self.sock:
                self.sock.close()


def get_network_info():
    """Get information about available network interfaces"""
    import platform

    info = {
        'platform': platform.system(),
        'hostname': socket.gethostname(),
        'interfaces': []
    }

    try:
        # Get local IP addresses
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        info['local_ips'] = local_ips
    except Exception as e:
        logger.warning(f"Could not get local IPs: {e}")
        info['local_ips'] = []

    return info


def get_network_interfaces() -> List[Dict[str, str]]:
    """
    Get list of available network interfaces with their IP addresses.

    Returns:
        List of dictionaries with 'name' and 'ip' keys.
        Always includes "All Interfaces (0.0.0.0)" as first option.
    """
    interfaces = [{"name": "All Interfaces", "ip": "0.0.0.0"}]

    try:
        # Try using psutil if available (most reliable cross-platform method)
        import psutil
        addrs = psutil.net_if_addrs()
        for iface_name, iface_addrs in addrs.items():
            for addr in iface_addrs:
                # Only include IPv4 addresses
                if addr.family == socket.AF_INET and addr.address != '127.0.0.1':
                    interfaces.append({
                        "name": f"{iface_name}",
                        "ip": addr.address
                    })
    except ImportError:
        # Fallback: use socket to get local IPs
        try:
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            for i, ip in enumerate(local_ips):
                if ip != '127.0.0.1':
                    interfaces.append({
                        "name": f"Interface {i+1}",
                        "ip": ip
                    })
        except Exception as e:
            logger.warning(f"Could not enumerate interfaces: {e}")

        # Also try connecting to external address to find primary interface
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            s.close()
            # Check if this IP is already in the list
            if not any(iface['ip'] == primary_ip for iface in interfaces):
                interfaces.append({
                    "name": "Primary Interface",
                    "ip": primary_ip
                })
        except Exception:
            pass

    return interfaces


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description="i-PRO Camera and Recorder IP Setup Tool - Discover and configure i-PRO IP cameras and recorders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover all devices with table output
  %(prog)s discover --table
  
  # Discover and sort by device type (cameras first, then recorders)
  %(prog)s discover --table --sort type
  
  # Discover and sort by MAC address
  %(prog)s discover --table --sort mac
  
  # Discover and sort by serial number
  %(prog)s discover --table --sort serial
  
  # Discover with JSON output
  %(prog)s discover --json
  
  # Discover with CSV output (for Excel/spreadsheets)
  %(prog)s discover --csv > devices.csv
  
  # Configure a camera
  %(prog)s configure --mac 01:23:45:67:89:ab --ip 192.168.1.100 --subnet 255.255.255.0 --gateway 192.168.1.1
  
  # Pipe output to another tool
  %(prog)s discover --json | jq .
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover cameras and recorders on network')
    discover_parser.add_argument('--timeout', type=float, default=3.0,
                                help='Discovery timeout in seconds (default: 3.0)')
    discover_parser.add_argument('--interface', default='0.0.0.0',
                                help='Network interface IP to bind to (default: 0.0.0.0)')
    discover_parser.add_argument('--json', action='store_true',
                                help='Output in JSON format')
    discover_parser.add_argument('--csv', action='store_true',
                                help='Output in CSV format')
    discover_parser.add_argument('--table', action='store_true',
                                help='Output in formatted table (default for terminal)')
    discover_parser.add_argument('--sort', choices=['ip', 'mac', 'serial', 'type'], default='ip',
                                help='Sort output by field (default: ip)')
    discover_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose diagnostic output')
    
    # Configure command
    config_parser = subparsers.add_parser('configure', help='Configure camera/recorder network settings')
    config_parser.add_argument('--mac', required=True,
                              help='Device MAC address (e.g., 01:23:45:67:89:ab)')
    config_parser.add_argument('--ip', required=True,
                              help='New IP address')
    config_parser.add_argument('--subnet', required=True,
                              help='New subnet mask')
    config_parser.add_argument('--gateway', required=True,
                              help='New gateway address')
    config_parser.add_argument('--port', type=int, default=80,
                              help='HTTP port (default: 80)')
    config_parser.add_argument('--timeout', type=float, default=3.0,
                              help='Configuration timeout in seconds (default: 3.0)')
    config_parser.add_argument('-v', '--verbose', action='store_true',
                              help='Enable verbose diagnostic output')
    
    # Diagnostic command
    diag_parser = subparsers.add_parser('diag', help='Run network diagnostics')
    diag_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == 'diag':
        # Run diagnostics
        print("Network Diagnostics")
        print("=" * 60)
        
        net_info = get_network_info()
        print(f"Platform: {net_info['platform']}")
        print(f"Hostname: {net_info['hostname']}")
        print(f"Local IPs: {', '.join(net_info['local_ips']) if net_info['local_ips'] else 'None found'}")
        print()
        
        print("Testing UDP broadcast capability...")
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            test_sock.bind(('0.0.0.0', 0))
            bound_addr = test_sock.getsockname()
            print(f"✓ UDP socket created and bound to {bound_addr}")
            test_sock.close()
        except Exception as e:
            print(f"✗ Failed to create UDP socket: {e}")
        
        print()
        print("Testing broadcast send to port 10670...")
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            test_packet = b'\x01\x00\x00\x11\x00\x04\x00\x00\x00\x00'
            test_sock.sendto(test_packet, ('255.255.255.255', 10670))
            print("✓ Broadcast packet sent successfully")
            test_sock.close()
        except Exception as e:
            print(f"✗ Failed to send broadcast: {e}")
        
        print()
        print("Firewall/Network Notes:")
        print("- UDP ports 10669-10670 must be open for broadcast")
        print("- Devices must be on the same subnet")
        print("- Some corporate networks block broadcasts")
        print("- Windows Firewall may block Python")
        print()
        print("Try running discovery with -v flag for detailed logs:")
        print("  python Easy_IP_3.py discover -v")
        sys.exit(0)
    
    elif args.command == 'discover':
        setup = iPROIPSetup(
            timeout=args.timeout, 
            interface=args.interface,
            verbose=args.verbose
        )
        devices = setup.discover_devices()
        
        # Sort devices based on user preference
        devices = sort_devices(devices, args.sort)
        
        if args.csv:
            # CSV output for spreadsheet import
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(DeviceInfo.csv_headers())
            
            for device in devices:
                writer.writerow(device.to_csv_row())
            
            print(output.getvalue().strip())
            
        elif args.json:
            # JSON output for piping
            output = {
                'count': len(devices),
                'cameras': len([d for d in devices if d.device_type == 'camera']),
                'recorders': len([d for d in devices if d.device_type == 'recorder']),
                'devices': [dev.to_dict() for dev in devices]
            }
            print(json.dumps(output, indent=2))
            
        elif args.table:
            # Formatted table output (only when explicitly requested)
            print_table(devices, show_warnings=True)
            
        else:
            # Human-readable output (default)
            if not devices:
                print("No devices discovered.", file=sys.stderr)
                sys.exit(1)
            
            cameras = [d for d in devices if d.device_type == 'camera']
            recorders = [d for d in devices if d.device_type == 'recorder']
            
            print(f"Discovered {len(devices)} device(s):")
            if cameras:
                print(f"  Cameras: {len(cameras)}")
            if recorders:
                print(f"  Recorders: {len(recorders)}")
            print()
            
            for i, device in enumerate(devices, 1):
                print(f"[{i}] {device}\n")
        
        sys.exit(0)
    
    elif args.command == 'configure':
        setup = iPROIPSetup(timeout=args.timeout, verbose=args.verbose)
        success = setup.configure_camera(
            mac_address=args.mac,
            ip=args.ip,
            subnet=args.subnet,
            gateway=args.gateway,
            port=args.port
        )
        
        if success:
            print(f"Successfully configured device {args.mac}")
            print(f"  IP: {args.ip}")
            print(f"  Subnet: {args.subnet}")
            print(f"  Gateway: {args.gateway}")
            print(f"  Port: {args.port}")
            sys.exit(0)
        else:
            print(f"Failed to configure device {args.mac}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
