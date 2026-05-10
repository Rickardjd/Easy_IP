#!/usr/bin/env python3
"""
Panasonic Camera IP Setup Tool
A cross-platform Python alternative to Panasonic's Easy IP Setup Tool.
Discovers and configures network settings for Panasonic IP cameras.
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
    """Panasonic Easy IP Setup protocol message types"""
    SEARCH_REQUEST = 0x0011
    SEARCH_RESPONSE = 0x0012
    CONFIG_REQUEST = 0x0021
    CONFIG_RESPONSE = 0x0022


@dataclass
class CameraInfo:
    """Information about a discovered Panasonic camera"""
    mac_address: str
    model_name: str
    ip_address: str
    subnet_mask: str
    gateway: str
    http_port: int
    firmware_version: str
    camera_name: str
    serial_number: str
    network_mode: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_csv_row(self) -> List[str]:
        """Return data as CSV row"""
        return [
            self.camera_name,
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
            "Camera Name",
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
        return (
            f"Camera: {self.camera_name}\n"
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


def sort_cameras(cameras: List[CameraInfo], sort_by: str = 'ip') -> List[CameraInfo]:
    """
    Sort cameras by specified field
    
    Args:
        cameras: List of CameraInfo objects to sort
        sort_by: Field to sort by ('ip', 'mac', 'serial')
    
    Returns:
        Sorted list of CameraInfo objects
    """
    sort_by = sort_by.lower()
    
    if sort_by == 'ip':
        # Sort by IP address (convert to tuple of ints for proper numeric sorting)
        def ip_key(camera):
            try:
                return tuple(int(part) for part in camera.ip_address.split('.'))
            except:
                return (255, 255, 255, 255)  # Put invalid IPs at end
        return sorted(cameras, key=ip_key)
    
    elif sort_by == 'mac':
        # Sort by MAC address
        def mac_key(camera):
            # Remove separators and convert to uppercase for consistent sorting
            return camera.mac_address.replace(':', '').replace('-', '').upper()
        return sorted(cameras, key=mac_key)
    
    elif sort_by == 'serial':
        # Sort by serial number
        return sorted(cameras, key=lambda c: c.serial_number)
    
    else:
        # Default to IP sorting if invalid sort option
        return sort_cameras(cameras, 'ip')


def detect_ip_overlaps(cameras: List[CameraInfo]) -> Dict[str, List[str]]:
    """
    Detect duplicate IP addresses
    
    Args:
        cameras: List of CameraInfo objects
    
    Returns:
        Dictionary mapping IP addresses to list of device identifiers (serial or MAC)
    """
    ip_map = {}
    for camera in cameras:
        if camera.ip_address not in ip_map:
            ip_map[camera.ip_address] = []
        identifier = camera.serial_number if camera.serial_number else camera.mac_address
        ip_map[camera.ip_address].append(identifier)
    
    # Return only IPs with multiple devices
    return {ip: devices for ip, devices in ip_map.items() if len(devices) > 1}


def print_table(cameras: List[CameraInfo], show_warnings: bool = True):
    """
    Print cameras in a formatted table
    
    Args:
        cameras: List of CameraInfo objects
        show_warnings: Whether to show IP overlap warnings
    """
    if not cameras:
        print("No cameras discovered.")
        return
    
    # Detect IP overlaps
    overlaps = detect_ip_overlaps(cameras)
    
    # Define column headers and widths
    headers = ['MAC Address', 'IP Address', 'Port', 'Device Name', 'Model', 'Serial Number']
    
    # Calculate column widths based on content
    col_widths = {
        'MAC Address': max(17, max((len(c.mac_address) for c in cameras), default=17)),
        'IP Address': max(15, max((len(c.ip_address) for c in cameras), default=15)),
        'Port': 6,
        'Device Name': max(11, max((len(c.camera_name) for c in cameras), default=11)),
        'Model': max(15, max((len(c.model_name) for c in cameras), default=15)),
        'Serial Number': max(13, max((len(c.serial_number) for c in cameras), default=13))
    }
    
    # Build separator line
    separator = '+-' + '-+-'.join('-' * col_widths[h] for h in headers) + '-+'
    
    # Print header
    print(separator)
    header_row = '| ' + ' | '.join(h.ljust(col_widths[h]) for h in headers) + ' |'
    print(header_row)
    print(separator)
    
    # Print each camera
    for camera in cameras:
        mac = camera.mac_address.ljust(col_widths['MAC Address'])
        ip = camera.ip_address.ljust(col_widths['IP Address'])
        port = str(camera.http_port).ljust(col_widths['Port'])
        name = camera.camera_name[:col_widths['Device Name']].ljust(col_widths['Device Name'])
        model = camera.model_name[:col_widths['Model']].ljust(col_widths['Model'])
        serial = camera.serial_number.ljust(col_widths['Serial Number'])
        
        # Check if this camera has an overlapping IP
        has_overlap = camera.ip_address in overlaps
        
        row = f"| {mac} | {ip} | {port} | {name} | {model} | {serial} |"
        
        if has_overlap and show_warnings:
            # Print row with warning marker
            print(row + " ⚠️  IP CONFLICT")
        else:
            print(row)
    
    print(separator)
    
    # Print summary
    print(f"\nTotal cameras discovered: {len(cameras)}")
    
    # Print warnings if IP overlaps detected
    if overlaps and show_warnings:
        print("\n⚠️  WARNING: IP ADDRESS CONFLICTS DETECTED!")
        print("=" * 60)
        for ip, devices in overlaps.items():
            print(f"  IP {ip} is assigned to {len(devices)} devices:")
            for device in devices:
                print(f"    - {device}")
        print("\nPlease reconfigure devices to use unique IP addresses.")


class PanasonicIPSetup:
    """Main class for discovering and configuring Panasonic cameras"""
    
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
        
        # Bind to the source port used by Panasonic protocol
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
        Build search request packet for Panasonic protocol
        Based on actual packet capture from Panasonic Easy IP Setup Tool
        
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
        
        # More data: 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00
        packet.extend([0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 
                      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
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
        
        logger.debug(f"Built search packet: {len(packet)} bytes")
        if self.verbose:
            logger.debug(f"Packet hex: {packet.hex()}")
        
        return bytes(packet)
    
    def _parse_response(self, data: bytes, addr: tuple) -> Optional[CameraInfo]:
        """
        Parse camera response packet using TLV (Type-Length-Value) format
        
        Response format:
        - Header: 00 01 [response_type] [command]
        - Camera MAC: 6 bytes at offset 6
        - TLV fields starting around offset 0x30:
          0x00 = Network mode (1 byte: 0=DHCP, 3=Static, 4=Auto(AutoIP), 5=Auto Advanced)
          0x20 = IP address (4 bytes)
          0x21 = Subnet mask (4 bytes)
          0x22 = Gateway (4 bytes)
          0x25 = HTTP port (2 bytes)
          0xd1 = Serial number (string)
          0xa7 = Camera name (string)
          0xa8 = Model name (string)
          0xa9 = Firmware version (string)
        
        Args:
            data: Raw packet data
            addr: Source address tuple
            
        Returns:
            CameraInfo object if valid response, None otherwise
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
            logger.debug(f"Camera MAC: {mac_address}")
            
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
            
            # 0x00 = Network mode (appears as tag 0x0001 in some cases, check both)
            network_mode = "Unknown"
            network_mode_value = None
            
            # Check for network mode in different possible locations
            if 0x01 in tlv_data and len(tlv_data[0x00]) >= 1:
                network_mode_value = tlv_data[0x00][0]
            elif 0x00 in tlv_data and len(tlv_data[0x00]) >= 1:
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
            
            # 0xa7 = Camera name (null-terminated string)
            camera_name = "Camera"
            if 0xa7 in tlv_data:
                camera_name = tlv_data[0xa7].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                logger.debug(f"Camera name from TLV 0xa7: {camera_name}")
            
            # 0xa8 = Model name (null-terminated string)
            model_name = "Unknown"
            if 0xa8 in tlv_data:
                model_name = tlv_data[0xa8].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                logger.debug(f"Model from TLV 0xa8: {model_name}")
            
            # 0xa9 = Firmware version (null-terminated string)
            firmware_version = "Unknown"
            if 0xa9 in tlv_data:
                firmware_version = tlv_data[0xa9].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                logger.debug(f"Firmware from TLV 0xa9: {firmware_version}")
            
            # 0xd1 = Serial number (null-terminated string)
            serial_number = "Unknown"
            if 0xd1 in tlv_data:
                serial_number = tlv_data[0xd1].rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                logger.debug(f"Serial from TLV 0xd1: {serial_number}")
            
            logger.info(f"✓ Parsed camera: {model_name} ({camera_name}) at {ip_address} [{network_mode}]")
            
            return CameraInfo(
                mac_address=mac_address,
                model_name=model_name,
                ip_address=ip_address,
                subnet_mask=subnet_mask,
                gateway=gateway,
                http_port=http_port,
                firmware_version=firmware_version,
                camera_name=camera_name,
                serial_number=serial_number,
                network_mode=network_mode
            )
        
        except Exception as e:
            logger.error(f"Error parsing response: {e}", exc_info=True)
            return None
    
    def discover_cameras(self) -> List[CameraInfo]:
        """
        Discover all Panasonic cameras on the network
        
        Returns:
            List of discovered cameras
        """
        cameras = []
        seen_macs = set()
        
        logger.info("=" * 60)
        logger.info("Starting camera discovery...")
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
                    
                    camera = self._parse_response(data, addr)
                    
                    if camera and camera.mac_address not in seen_macs:
                        logger.info(f"✓ Valid camera found: {camera.model_name} ({camera.mac_address})")
                        cameras.append(camera)
                        seen_macs.add(camera.mac_address)
                    elif camera:
                        logger.debug(f"Duplicate camera response from {camera.mac_address}")
                
                except socket.timeout:
                    logger.debug("Socket timeout - no more responses")
                    break
                except Exception as e:
                    logger.error(f"Error receiving data: {e}", exc_info=True)
                    continue
            
            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info(f"Discovery complete in {elapsed:.2f}s")
            logger.info(f"Total responses received: {response_count}")
            logger.info(f"Valid cameras found: {len(cameras)}")
            logger.info("=" * 60)
        
        except Exception as e:
            logger.error(f"Discovery error: {e}", exc_info=True)
        finally:
            if self.sock:
                logger.debug("Closing socket")
                self.sock.close()
        
        return cameras
    
def configure_camera(self, mac_address: str, ip: str, subnet: str, 
                    gateway: str, port: int = 80) -> bool:
    """
    Configure network settings for a specific camera
    
    Args:
        mac_address: Target camera MAC address
        ip: New IP address
        subnet: New subnet mask
        gateway: New gateway address
        port: HTTP port (default 80)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        self.sock = self._create_socket()
        
        # Get source MAC and IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            source_ip = s.getsockname()[0]
            s.close()
            source_ip_bytes = bytes(map(int, source_ip.split('.')))
        except:
            source_ip_bytes = bytes([192, 168, 1, 100])
        
        import uuid
        try:
            mac = uuid.getnode()
            source_mac_bytes = mac.to_bytes(6, 'big')
        except:
            source_mac_bytes = bytes([0xa0, 0x29, 0x19, 0x3e, 0xab, 0x91])
        
        # Parse target MAC address
        target_mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
        
        # Parse IP configuration
        ip_bytes = bytes(map(int, ip.split('.')))
        subnet_bytes = bytes(map(int, subnet.split('.')))
        gateway_bytes = bytes(map(int, gateway.split('.')))
        
        # Build configuration packet using TLV format
        packet = bytearray()
        
        # Header: 00 01 00 af 00 02
        packet.extend([0x00, 0x01])  # Protocol marker
        packet.extend([0x00, 0xaf])  # Total length placeholder (will update later)
        packet.extend([0x00, 0x02])  # Command type
        
        # Target camera MAC (6 bytes)
        packet.extend(target_mac_bytes)
        
        # Source MAC (6 bytes)
        packet.extend(source_mac_bytes)
        
        # Source IP (4 bytes)
        packet.extend(source_ip_bytes)
        
        # Fixed sequence matching Panasonic packet
        packet.extend([0x00, 0x01, 0x20, 0x11, 0x1e, 0x11, 0x23, 0x1f, 0x1e, 0x19, 0x13])
        
        # Padding/flags section
        packet.extend([0x00, 0x00, 0x02, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
                      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        # TLV section starts here
        # Tag 0x0000, Length 1, Value 0x03
        packet.extend([0x00, 0x00, 0x00, 0x01, 0x03])
        
        # Tag 0x0001, Length 1, Value 0x00 (Network mode: 0 = DHCP-like, but we want static)
        packet.extend([0x00, 0x01, 0x00, 0x01, 0x00])
        
        # Tag 0x0020, Length 4, Value = new IP address
        packet.extend([0x00, 0x20, 0x00, 0x04])
        packet.extend(ip_bytes)
        
        # Tag 0x0021, Length 4, Value = subnet mask
        packet.extend([0x00, 0x21, 0x00, 0x04])
        packet.extend(subnet_bytes)
        
        # Tag 0x0022, Length 4, Value = gateway
        packet.extend([0x00, 0x22, 0x00, 0x04])
        packet.extend(gateway_bytes)
        
        # Tag 0x0023, Length 8, Value = DNS servers (gateway as DNS1, zeros for DNS2)
        packet.extend([0x00, 0x23, 0x00, 0x08])
        packet.extend(gateway_bytes)
        packet.extend([0x00, 0x00, 0x00, 0x00])
        
        # Tag 0x0025, Length 2, Value = HTTP port
        packet.extend([0x00, 0x25, 0x00, 0x02])
        packet.extend(struct.pack(">H", port))
        
        # Tag 0x0040, Length 16, Value = IPv6 link-local address (derived from MAC)
        packet.extend([0x00, 0x40, 0x00, 0x10])
        # Generate IPv6 link-local from MAC: fe80::MAC_with_ff:fe_inserted
        packet.extend([0xfe, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        # EUI-64 format: flip 7th bit and insert ff:fe
        mac_bytes_list = list(target_mac_bytes)
        mac_bytes_list[0] ^= 0x02  # Flip universal/local bit
        packet.extend(mac_bytes_list[:3])
        packet.extend([0xff, 0xfe])
        packet.extend(mac_bytes_list[3:])
        
        # Tag 0x0041, Length 16, Value = IPv6 address (all zeros for none)
        packet.extend([0x00, 0x41, 0x00, 0x10])
        packet.extend([0x00] * 16)
        
        # Tag 0x0042, Length 32, Value = IPv6 gateway (all zeros)
        packet.extend([0x00, 0x42, 0x00, 0x20])
        packet.extend([0x00] * 32)
        
        # Tag 0x0044, Length 2, Value = HTTPS port
        packet.extend([0x00, 0x44, 0x00, 0x02])
        packet.extend(struct.pack(">H", port))
        
        # Tag 0x00a0, Length 4, Value = Alt IPv4 (same as main)
        packet.extend([0x00, 0xa0, 0x00, 0x04])
        packet.extend(ip_bytes)
        
        # Tag 0x00a1, Length 4, Value = Alt subnet (same as main)
        packet.extend([0x00, 0xa1, 0x00, 0x04])
        packet.extend(subnet_bytes)
        
        # Tag 0x00a2, Length 4, Value = Alt gateway (same as main)
        packet.extend([0x00, 0xa2, 0x00, 0x04])
        packet.extend(gateway_bytes)
        
        # Tag 0x00a3, Length 8, Value = Alt DNS
        packet.extend([0x00, 0xa3, 0x00, 0x08])
        packet.extend(gateway_bytes)
        packet.extend([0x00, 0x00, 0x00, 0x00])
        
        # Tag 0x00a6, Length 1, Value = 0x92 (network setting flag)
        packet.extend([0x00, 0xa6, 0x00, 0x01, 0x92])
        
        # End marker
        packet.extend([0xff, 0xff])
        
        # Update total length in header (bytes 2-3)
        # Length is from byte 4 to end (excluding first 4 bytes)
        total_length = len(packet) - 4
        packet[2:4] = struct.pack(">H", total_length)
        
        logger.info(f"Sending configuration packet ({len(packet)} bytes)")
        if self.verbose:
            logger.debug(f"Packet hex: {packet.hex()}")
        
        # Send configuration
        dest = (self.BROADCAST_ADDR, self.BROADCAST_PORT)
        self.sock.sendto(bytes(packet), dest)
        logger.info(f"Configuration sent to {dest}")
        
        # Wait for confirmation
        try:
            data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
            logger.info(f"Received response from {addr}")
            if len(data) >= 4:
                msg_type = struct.unpack(">H", data[2:4])[0]
                logger.debug(f"Response type: 0x{msg_type:04x}")
                # Response type might be 0x0022 or similar
                return True  # If we got any response, consider it successful
            return False
        except socket.timeout:
            logger.warning("No response received (timeout)")
            return False
    
    except Exception as e:
        logger.error(f"Error configuring camera: {e}", exc_info=True)
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


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description="Panasonic Camera IP Setup Tool - Discover and configure Panasonic IP cameras",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover all cameras with table output
  %(prog)s discover --table
  
  # Discover and sort by MAC address
  %(prog)s discover --table --sort mac
  
  # Discover and sort by serial number
  %(prog)s discover --table --sort serial
  
  # Discover with JSON output
  %(prog)s discover --json
  
  # Discover with CSV output (for Excel/spreadsheets)
  %(prog)s discover --csv > cameras.csv
  
  # Configure a camera
  %(prog)s configure --mac 01:23:45:67:89:ab --ip 192.168.1.100 --subnet 255.255.255.0 --gateway 192.168.1.1
  
  # Pipe output to another tool
  %(prog)s discover --json | jq .
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover cameras on network')
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
    discover_parser.add_argument('--sort', choices=['ip', 'mac', 'serial'], default='ip',
                                help='Sort output by field (default: ip)')
    discover_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose diagnostic output')
    
    # Configure command
    config_parser = subparsers.add_parser('configure', help='Configure camera network settings')
    config_parser.add_argument('--mac', required=True,
                              help='Camera MAC address (e.g., 01:23:45:67:89:ab)')
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
        print("- Cameras must be on the same subnet")
        print("- Some corporate networks block broadcasts")
        print("- Windows Firewall may block Python")
        print()
        print("Try running discovery with -v flag for detailed logs:")
        print("  python Easy_IP.py discover -v")
        sys.exit(0)
    
    elif args.command == 'discover':
        setup = PanasonicIPSetup(
            timeout=args.timeout, 
            interface=args.interface,
            verbose=args.verbose
        )
        cameras = setup.discover_cameras()
        
        # Sort cameras based on user preference
        cameras = sort_cameras(cameras, args.sort)
        
        if args.csv:
            # CSV output for spreadsheet import
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(CameraInfo.csv_headers())
            
            for camera in cameras:
                writer.writerow(camera.to_csv_row())
            
            print(output.getvalue().strip())
            
        elif args.json:
            # JSON output for piping
            output = {
                'count': len(cameras),
                'cameras': [cam.to_dict() for cam in cameras]
            }
            print(json.dumps(output, indent=2))
            
        elif args.table or (sys.stdout.isatty() and not args.json and not args.csv):
            # Formatted table output (default for interactive terminal)
            print_table(cameras, show_warnings=True)
            
        else:
            # Human-readable output
            if not cameras:
                print("No cameras discovered.", file=sys.stderr)
                sys.exit(1)
            
            print(f"Discovered {len(cameras)} camera(s):\n")
            for i, camera in enumerate(cameras, 1):
                print(f"[{i}] {camera}\n")
        
        sys.exit(0)
    
    elif args.command == 'configure':
        setup = PanasonicIPSetup(timeout=args.timeout, verbose=args.verbose)
        success = setup.configure_camera(
            mac_address=args.mac,
            ip=args.ip,
            subnet=args.subnet,
            gateway=args.gateway,
            port=args.port
        )
        
        if success:
            print(f"Successfully configured camera {args.mac}")
            print(f"  IP: {args.ip}")
            print(f"  Subnet: {args.subnet}")
            print(f"  Gateway: {args.gateway}")
            print(f"  Port: {args.port}")
            sys.exit(0)
        else:
            print(f"Failed to configure camera {args.mac}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()