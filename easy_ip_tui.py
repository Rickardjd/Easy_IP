#!/usr/bin/env python3
"""
i-PRO Camera and Recorder IP Setup Tool - TUI Version
A cross-platform Python TUI for i-PRO's Easy IP Setup Tool.
Uses Textual and Rich for the terminal user interface.
"""

import json
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict, field
from enum import Enum

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Label, Input,
    DataTable, Tree, Select, Checkbox, RadioSet, RadioButton,
    Rule, LoadingIndicator, ProgressBar
)
from textual.widgets.tree import TreeNode
from textual.screen import Screen, ModalScreen
from textual.message import Message
from textual.reactive import reactive
from textual import work
from textual.worker import Worker, get_current_worker

from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

# Import discovery functionality from Easy_IP
# Handle both possible import names for cross-platform compatibility
try:
    from Easy_IP import iPROIPSetup, DeviceInfo, get_network_interfaces
except ImportError:
    from easy_ip import iPROIPSetup, DeviceInfo, get_network_interfaces


class DeviceStatus(Enum):
    """Device status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class TrackedDevice:
    """A device being tracked in a group"""
    mac_address: str
    device_type: str
    model_name: str
    device_name: str
    serial_number: str
    ip_address: str
    subnet_mask: str
    gateway: str
    http_port: int
    firmware_version: str
    network_mode: str
    status: str = "unknown"
    last_seen: Optional[str] = None
    first_seen: Optional[str] = None
    added_manually: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TrackedDevice':
        return cls(**data)

    @classmethod
    def from_device_info(cls, device: DeviceInfo) -> 'TrackedDevice':
        """Create TrackedDevice from DeviceInfo"""
        now = datetime.now().isoformat()
        return cls(
            mac_address=device.mac_address,
            device_type=device.device_type,
            model_name=device.model_name,
            device_name=device.device_name,
            serial_number=device.serial_number,
            ip_address=device.ip_address,
            subnet_mask=device.subnet_mask,
            gateway=device.gateway,
            http_port=device.http_port,
            firmware_version=device.firmware_version,
            network_mode=device.network_mode,
            status="online",
            last_seen=now,
            first_seen=now
        )


@dataclass
class DeviceGroup:
    """A group of devices"""
    name: str
    devices: List[TrackedDevice] = field(default_factory=list)
    expanded: bool = True

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'devices': [d.to_dict() for d in self.devices],
            'expanded': self.expanded
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceGroup':
        devices = [TrackedDevice.from_dict(d) for d in data.get('devices', [])]
        return cls(
            name=data['name'],
            devices=devices,
            expanded=data.get('expanded', True)
        )

    @property
    def device_count(self) -> int:
        return len(self.devices)

    @property
    def online_count(self) -> int:
        return sum(1 for d in self.devices if d.status == "online")

    @property
    def offline_count(self) -> int:
        return sum(1 for d in self.devices if d.status == "offline")

    def get_status_color(self) -> str:
        """Get color based on group status"""
        if not self.devices:
            return "white"
        if self.offline_count == 0:
            return "green"
        elif self.online_count == 0:
            return "red"
        else:
            return "orange1"


@dataclass
class SiteData:
    """Site data containing all groups"""
    name: str = "Untitled Site"
    groups: List[DeviceGroup] = field(default_factory=list)
    scan_frequency: int = 60  # seconds
    last_scan: Optional[str] = None
    # Network interface setting
    network_interface: str = "0.0.0.0"  # Default to all interfaces
    # Column visibility settings
    show_device_type: bool = True
    show_ip_address: bool = True
    show_mac_address: bool = True
    show_model: bool = True
    show_serial: bool = False
    show_status: bool = True
    show_firmware: bool = False
    show_http_port: bool = False

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'groups': [g.to_dict() for g in self.groups],
            'scan_frequency': self.scan_frequency,
            'last_scan': self.last_scan,
            'network_interface': self.network_interface,
            'show_device_type': self.show_device_type,
            'show_ip_address': self.show_ip_address,
            'show_mac_address': self.show_mac_address,
            'show_model': self.show_model,
            'show_serial': self.show_serial,
            'show_status': self.show_status,
            'show_firmware': self.show_firmware,
            'show_http_port': self.show_http_port,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SiteData':
        groups = [DeviceGroup.from_dict(g) for g in data.get('groups', [])]
        return cls(
            name=data.get('name', 'Untitled Site'),
            groups=groups,
            scan_frequency=data.get('scan_frequency', 60),
            last_scan=data.get('last_scan'),
            network_interface=data.get('network_interface', '0.0.0.0'),
            show_device_type=data.get('show_device_type', True),
            show_ip_address=data.get('show_ip_address', True),
            show_mac_address=data.get('show_mac_address', True),
            show_model=data.get('show_model', True),
            show_serial=data.get('show_serial', False),
            show_status=data.get('show_status', True),
            show_firmware=data.get('show_firmware', False),
            show_http_port=data.get('show_http_port', False),
        )

    def save(self, path: Path):
        """Save site data to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> 'SiteData':
        """Load site data from JSON file"""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))

    def get_all_devices(self) -> List[TrackedDevice]:
        """Get all devices across all groups"""
        devices = []
        for group in self.groups:
            devices.extend(group.devices)
        return devices

    def find_device_by_mac(self, mac: str) -> Optional[tuple]:
        """Find device by MAC, returns (group, device) or None"""
        for group in self.groups:
            for device in group.devices:
                if device.mac_address.lower() == mac.lower():
                    return (group, device)
        return None


# CSS styling for the application
APP_CSS = """
Screen {
    background: $surface;
}

#main-container {
    width: 100%;
    height: 100%;
}

#groups-container {
    width: 100%;
    height: 1fr;
    border: solid $primary;
    padding: 1;
}

.group-header {
    width: 100%;
    height: auto;
    padding: 0 1;
    margin-bottom: 1;
}

.group-header-online {
    background: $success 30%;
    color: $text;
}

.group-header-offline {
    background: $error 30%;
    color: $text;
}

.group-header-partial {
    background: $warning 30%;
    color: $text;
}

.group-header-empty {
    background: $surface;
    color: $text-muted;
}

.device-row {
    width: 100%;
    height: auto;
    padding: 0 2;
}

.device-online {
    color: $success;
}

.device-offline {
    color: $error;
}

.device-unknown {
    color: $text-muted;
}

#status-bar {
    height: 1;
    background: $primary;
    color: $text;
    padding: 0 1;
}

#menu-bar {
    dock: top;
    height: 3;
    background: $surface-darken-1;
}

.menu-button {
    margin: 0 1;
    min-width: 10;
}

DataTable {
    height: 100%;
}

.modal-container {
    align: center middle;
    width: 70;
    height: auto;
    max-height: 85%;
    border: thick $primary;
    background: $surface;
    padding: 1 2;
    overflow-y: auto;
}

.modal-title {
    text-align: center;
    text-style: bold;
    margin-bottom: 1;
}

.modal-buttons {
    align: center middle;
    margin-top: 1;
    height: auto;
    min-height: 3;
}

.modal-buttons Button {
    margin: 0 1;
}

Input {
    margin: 1 0;
}

#scan-progress {
    margin: 1 0;
}

.export-options {
    margin: 1 0;
    padding: 0 1;
    border: solid $primary;
    height: auto;
    max-height: 10;
}

#file-list {
    height: 15;
    border: solid $primary;
    margin: 1 0;
}

.file-item {
    width: 100%;
    margin: 0;
    text-align: left;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $primary;
    color: $text;
    padding: 0 1;
}

#status-bar .status-item {
    margin-right: 2;
}

.status-monitoring-on {
    color: $success;
}

.status-monitoring-off {
    color: $text-muted;
}

#monitor-status {
    margin-left: 2;
    padding: 0 2;
    text-style: bold;
}

#monitor-status.monitor-active {
    background: $success;
    color: $text;
}

#monitor-status.monitor-stopped {
    background: $error 50%;
    color: $text;
}
"""


class StatusBar(Horizontal):
    """Custom status bar showing monitoring status and stats"""

    monitoring = reactive(False)
    last_scan = reactive("")
    next_scan = reactive("")
    online_count = reactive(0)
    offline_count = reactive(0)
    total_count = reactive(0)

    def compose(self) -> ComposeResult:
        yield Label("", id="status-monitoring")
        yield Label("", id="status-stats")
        yield Label("", id="status-last-scan")
        yield Label("", id="status-next-scan")

    def watch_monitoring(self, monitoring: bool) -> None:
        label = self.query_one("#status-monitoring", Label)
        if monitoring:
            label.update("[MONITORING: ON]")
            label.set_class(True, "status-monitoring-on")
            label.set_class(False, "status-monitoring-off")
        else:
            label.update("[MONITORING: OFF]")
            label.set_class(False, "status-monitoring-on")
            label.set_class(True, "status-monitoring-off")
        # Clear next scan when monitoring stops
        if not monitoring:
            self.update_next_scan("")

    def update_stats(self, total: int, online: int, offline: int) -> None:
        self.total_count = total
        self.online_count = online
        self.offline_count = offline
        stats_label = self.query_one("#status-stats", Label)
        stats_label.update(f" | Devices: {total} (Online: {online}, Offline: {offline})")

    def update_last_scan(self, timestamp: str) -> None:
        self.last_scan = timestamp
        scan_label = self.query_one("#status-last-scan", Label)
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted = dt.strftime("%H:%M:%S")
                scan_label.update(f" | Last Scan: {formatted}")
            except:
                scan_label.update(f" | Last Scan: {timestamp}")
        else:
            scan_label.update("")

    def update_next_scan(self, timestamp: str) -> None:
        self.next_scan = timestamp
        next_label = self.query_one("#status-next-scan", Label)
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted = dt.strftime("%H:%M:%S")
                next_label.update(f" | Next Scan: {formatted}")
            except:
                next_label.update(f" | Next Scan: {timestamp}")
        else:
            next_label.update("")


class MenuBar(Horizontal):
    """Custom menu bar widget"""

    def compose(self) -> ComposeResult:
        yield Button("File", id="menu-file", classes="menu-button")
        yield Button("Scan", id="menu-scan", classes="menu-button")
        yield Button("Monitor", id="menu-monitor", classes="menu-button")
        yield Button("Groups", id="menu-groups", classes="menu-button")
        yield Button("Setup", id="menu-setup", classes="menu-button")
        yield Label("MONITORING: STOPPED", id="monitor-status", classes="monitor-stopped")


class FileMenuScreen(ModalScreen):
    """File menu modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("File Menu", classes="modal-title")
            yield Rule()
            yield Button("Load Site...", id="btn-load", variant="primary")
            yield Button("Save Site", id="btn-save")
            yield Button("Save Site As...", id="btn-save-as")
            yield Rule()
            yield Button("Exit", id="btn-exit", variant="error")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-load":
            self.dismiss("load")
        elif event.button.id == "btn-save":
            self.dismiss("save")
        elif event.button.id == "btn-save-as":
            self.dismiss("save-as")
        elif event.button.id == "btn-exit":
            self.dismiss("exit")


class SaveAsScreen(ModalScreen):
    """Save As dialog with filename input"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, current_name: str = "site_data"):
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Save Site As", classes="modal-title")
            yield Rule()
            yield Label("Filename:")
            yield Input(value=self.current_name, placeholder="Enter filename", id="save-filename")
            yield Label("(Extension .json will be added automatically)", classes="device-unknown")
            with Horizontal(classes="modal-buttons"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-save":
            filename = self.query_one("#save-filename", Input).value
            if not filename:
                self.notify("Please enter a filename", severity="warning")
                return
            # Add .json extension if not present
            if not filename.endswith('.json'):
                filename = f"{filename}.json"
            self.dismiss(filename)


class FileBrowserScreen(ModalScreen):
    """File browser for loading site files"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, start_path: Optional[Path] = None):
        super().__init__()
        self.current_path = start_path or Path.cwd()
        self._id_to_name: Dict[str, str] = {}  # Map sanitized IDs to real names

    def _sanitize_id(self, name: str, prefix: str) -> str:
        """Create a valid ID from a filename, storing the mapping"""
        import re
        # Replace any non-alphanumeric characters (except hyphen/underscore) with underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        full_id = f"{prefix}-{sanitized}"
        self._id_to_name[full_id] = name
        return full_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Load Site File", classes="modal-title")
            yield Rule()
            yield Label(f"Current directory: {self.current_path}", id="current-dir")
            yield Rule()
            with ScrollableContainer(id="file-list"):
                # Parent directory option
                yield Button(".. (Parent Directory)", id="btn-parent", classes="file-item")
            yield Rule()
            yield Label("Selected file:")
            yield Input(placeholder="Select a file above or enter path", id="selected-file")
            with Horizontal(classes="modal-buttons"):
                yield Button("Load", id="btn-load", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        """Populate files when screen mounts"""
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        """Refresh the file list"""
        file_list = self.query_one("#file-list", ScrollableContainer)
        # Keep only the parent button, remove others
        for child in list(file_list.children):
            if child.id != "btn-parent":
                child.remove()

        # Clear ID mapping
        self._id_to_name = {}

        # Update current directory label
        self.query_one("#current-dir", Label).update(f"Current directory: {self.current_path}")

        try:
            items = sorted(self.current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for item in items:
                if item.is_dir():
                    btn_id = self._sanitize_id(item.name, "dir")
                    btn = Button(f"[Dir] {item.name}", id=btn_id, classes="file-item")
                    file_list.mount(btn)
                elif item.suffix.lower() == '.json':
                    btn_id = self._sanitize_id(item.name, "file")
                    btn = Button(f"      {item.name}", id=btn_id, classes="file-item")
                    file_list.mount(btn)
        except PermissionError:
            self.notify("Permission denied", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.dismiss()
        elif button_id == "btn-load":
            filename = self.query_one("#selected-file", Input).value
            if not filename:
                self.notify("Please select a file", severity="warning")
                return
            filepath = Path(filename)
            if not filepath.is_absolute():
                filepath = self.current_path / filepath
            if not filepath.exists():
                self.notify("File not found", severity="error")
                return
            self.dismiss(filepath)
        elif button_id == "btn-parent":
            parent = self.current_path.parent
            if parent != self.current_path:
                self.current_path = parent
                self._refresh_file_list()
        elif button_id.startswith("dir-"):
            # Look up real name from mapping
            real_name = self._id_to_name.get(button_id)
            if real_name:
                self.current_path = self.current_path / real_name
                self._refresh_file_list()
        elif button_id.startswith("file-"):
            # Look up real name from mapping
            real_name = self._id_to_name.get(button_id)
            if real_name:
                filepath = self.current_path / real_name
                self.query_one("#selected-file", Input).value = str(filepath)


class ScanMenuScreen(ModalScreen):
    """Scan menu modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Scan Options", classes="modal-title")
            yield Rule()
            yield Button("Scan Network (Auto)", id="btn-scan-auto", variant="primary")
            yield Button("Manual Add Device...", id="btn-manual-add")
            yield Rule()
            yield Label("Scan Timeout (seconds):")
            yield Input(value="3", id="scan-timeout", type="number")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-scan-auto":
            timeout = self.query_one("#scan-timeout", Input).value
            self.dismiss(("scan", float(timeout) if timeout else 3.0))
        elif event.button.id == "btn-manual-add":
            self.dismiss("manual-add")


class GroupMenuScreen(ModalScreen):
    """Group management menu modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Group Management", classes="modal-title")
            yield Rule()
            yield Button("Add New Group...", id="btn-add-group", variant="primary")
            yield Button("Remove Group...", id="btn-remove-group", variant="warning")
            yield Button("Move Device...", id="btn-move-device")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-add-group":
            self.dismiss("add-group")
        elif event.button.id == "btn-remove-group":
            self.dismiss("remove-group")
        elif event.button.id == "btn-move-device":
            self.dismiss("move-device")


class SetupMenuScreen(ModalScreen):
    """Setup menu modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, site_data: 'SiteData'):
        super().__init__()
        self.site_data = site_data
        self.network_interfaces = get_network_interfaces()

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Setup Options", classes="modal-title")
            yield Rule()
            yield Label("Site Name:")
            yield Input(value=self.site_data.name, id="site-name")
            yield Rule()
            yield Label("Network Interface:")
            # Build interface options for the dropdown
            interface_options = []
            current_interface_idx = 0
            for i, iface in enumerate(self.network_interfaces):
                label = f"{iface['name']} ({iface['ip']})"
                interface_options.append((label, iface['ip']))
                if iface['ip'] == self.site_data.network_interface:
                    current_interface_idx = i
            yield Select(interface_options, id="network-interface", value=self.site_data.network_interface)
            yield Label("(Select specific interface if auto-detection fails)", classes="device-unknown")
            yield Rule()
            yield Label("Scan Frequency (seconds):")
            yield Input(value=str(self.site_data.scan_frequency), id="scan-frequency", type="number")
            yield Rule()
            yield Label("Display Columns:")
            yield Checkbox("Device Type", value=self.site_data.show_device_type, id="col-type")
            yield Checkbox("IP Address", value=self.site_data.show_ip_address, id="col-ip")
            yield Checkbox("MAC Address", value=self.site_data.show_mac_address, id="col-mac")
            yield Checkbox("Model", value=self.site_data.show_model, id="col-model")
            yield Checkbox("Serial Number", value=self.site_data.show_serial, id="col-serial")
            yield Checkbox("Status", value=self.site_data.show_status, id="col-status")
            yield Checkbox("Firmware", value=self.site_data.show_firmware, id="col-firmware")
            yield Checkbox("HTTP Port", value=self.site_data.show_http_port, id="col-port")
            with Horizontal(classes="modal-buttons"):
                yield Button("Apply", id="btn-apply", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-apply":
            interface_select = self.query_one("#network-interface", Select)
            selected_interface = interface_select.value if interface_select.value != Select.BLANK else "0.0.0.0"
            result = {
                'name': self.query_one("#site-name", Input).value or "Untitled Site",
                'network_interface': selected_interface,
                'frequency': int(self.query_one("#scan-frequency", Input).value or 60),
                'show_device_type': self.query_one("#col-type", Checkbox).value,
                'show_ip_address': self.query_one("#col-ip", Checkbox).value,
                'show_mac_address': self.query_one("#col-mac", Checkbox).value,
                'show_model': self.query_one("#col-model", Checkbox).value,
                'show_serial': self.query_one("#col-serial", Checkbox).value,
                'show_status': self.query_one("#col-status", Checkbox).value,
                'show_firmware': self.query_one("#col-firmware", Checkbox).value,
                'show_http_port': self.query_one("#col-port", Checkbox).value,
            }
            self.dismiss(result)


class AddGroupScreen(ModalScreen):
    """Add new group modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Add New Group", classes="modal-title")
            yield Rule()
            yield Label("Group Name:")
            yield Input(placeholder="Enter group name", id="group-name")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", id="btn-create", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-create":
            name = self.query_one("#group-name", Input).value
            if name:
                self.dismiss(name)
            else:
                self.notify("Please enter a group name", severity="warning")


class RemoveGroupScreen(ModalScreen):
    """Remove group modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, groups: List[str]):
        super().__init__()
        self.groups = groups

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Remove Group", classes="modal-title")
            yield Rule()
            yield Label("Select group to remove:")
            options = [(g, g) for g in self.groups]
            yield Select(options, id="group-select")
            yield Label("Warning: All devices in the group will be removed!",
                       classes="device-offline")
            with Horizontal(classes="modal-buttons"):
                yield Button("Remove", id="btn-remove", variant="error")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-remove":
            select = self.query_one("#group-select", Select)
            if select.value != Select.BLANK:
                self.dismiss(select.value)


class MoveDeviceScreen(ModalScreen):
    """Move device between groups modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, devices: List[tuple], groups: List[str]):
        super().__init__()
        self.devices = devices  # List of (mac, name, current_group)
        self.groups = groups

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Move Device", classes="modal-title")
            yield Rule()
            yield Label("Select device:")
            device_options = [(f"{d[1]} ({d[0]}) - {d[2]}", d[0]) for d in self.devices]
            yield Select(device_options, id="device-select")
            yield Label("Move to group:")
            group_options = [(g, g) for g in self.groups]
            yield Select(group_options, id="target-group")
            with Horizontal(classes="modal-buttons"):
                yield Button("Move", id="btn-move", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-move":
            device_select = self.query_one("#device-select", Select)
            group_select = self.query_one("#target-group", Select)
            if device_select.value != Select.BLANK and group_select.value != Select.BLANK:
                self.dismiss((device_select.value, group_select.value))


class ManualAddScreen(ModalScreen):
    """Manually add device modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, groups: List[str]):
        super().__init__()
        self.groups = groups

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Manual Add Device", classes="modal-title")
            yield Rule()
            yield Label("Device Name:")
            yield Input(placeholder="Camera 1", id="device-name")
            yield Label("MAC Address:")
            yield Input(placeholder="aa:bb:cc:dd:ee:ff", id="mac-address")
            yield Label("IP Address:")
            yield Input(placeholder="192.168.1.100", id="ip-address")
            yield Label("Model:")
            yield Input(placeholder="WV-S1131", id="model")
            yield Label("Add to Group:")
            group_options = [(g, g) for g in self.groups]
            yield Select(group_options, id="target-group")
            with Horizontal(classes="modal-buttons"):
                yield Button("Add", id="btn-add", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-add":
            name = self.query_one("#device-name", Input).value
            mac = self.query_one("#mac-address", Input).value
            ip = self.query_one("#ip-address", Input).value
            model = self.query_one("#model", Input).value
            group_select = self.query_one("#target-group", Select)

            if not all([name, mac, ip]):
                self.notify("Please fill in required fields", severity="warning")
                return

            if group_select.value == Select.BLANK:
                self.notify("Please select a group", severity="warning")
                return

            device = TrackedDevice(
                mac_address=mac,
                device_type="camera",
                model_name=model or "Unknown",
                device_name=name,
                serial_number="",
                ip_address=ip,
                subnet_mask="255.255.255.0",
                gateway="",
                http_port=80,
                firmware_version="",
                network_mode="Manual",
                status="unknown",
                last_seen=datetime.now().isoformat(),
                first_seen=datetime.now().isoformat(),
                added_manually=True
            )
            self.dismiss((device, group_select.value))


class ExportScreen(ModalScreen):
    """Export options modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, groups: List[str]):
        super().__init__()
        self.groups = groups

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Export Devices", classes="modal-title")
            yield Rule()
            yield Label("Filename:")
            yield Input(value="export", placeholder="Enter filename (without extension)", id="export-filename")
            yield Rule()
            yield Label("Export Format:")
            with RadioSet(id="format-select"):
                yield RadioButton("JSON", value=True, id="fmt-json")
                yield RadioButton("CSV", id="fmt-csv")
            yield Rule()
            yield Label("Export Scope:")
            with RadioSet(id="scope-select"):
                yield RadioButton("All Groups", value=True, id="scope-all")
                yield RadioButton("Selected Group", id="scope-group")
            yield Label("Select Group (if applicable):")
            group_options = [(g, g) for g in self.groups]
            yield Select(group_options, id="group-select")
            yield Rule()
            yield Label("Include Fields:")
            with ScrollableContainer(classes="export-options", id="export-fields"):
                yield Checkbox("Device Name", value=True, id="exp-name")
                yield Checkbox("Device Type", value=True, id="exp-type")
                yield Checkbox("IP Address", value=True, id="exp-ip")
                yield Checkbox("Subnet Mask", value=False, id="exp-subnet")
                yield Checkbox("Gateway", value=False, id="exp-gateway")
                yield Checkbox("MAC Address", value=True, id="exp-mac")
                yield Checkbox("Model", value=True, id="exp-model")
                yield Checkbox("Serial Number", value=True, id="exp-serial")
                yield Checkbox("HTTP Port", value=False, id="exp-port")
                yield Checkbox("Firmware", value=False, id="exp-firmware")
                yield Checkbox("Network Mode", value=False, id="exp-netmode")
                yield Checkbox("Status", value=True, id="exp-status")
                yield Checkbox("First Seen", value=False, id="exp-firstseen")
                yield Checkbox("Last Seen", value=True, id="exp-lastseen")
            with Horizontal(classes="modal-buttons"):
                yield Button("Export", id="btn-export", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-export":
            filename = self.query_one("#export-filename", Input).value
            if not filename:
                self.notify("Please enter a filename", severity="warning")
                return

            format_json = self.query_one("#fmt-json", RadioButton).value
            scope_all = self.query_one("#scope-all", RadioButton).value
            group = self.query_one("#group-select", Select).value

            fields = []
            if self.query_one("#exp-name", Checkbox).value:
                fields.append("device_name")
            if self.query_one("#exp-type", Checkbox).value:
                fields.append("device_type")
            if self.query_one("#exp-ip", Checkbox).value:
                fields.append("ip_address")
            if self.query_one("#exp-subnet", Checkbox).value:
                fields.append("subnet_mask")
            if self.query_one("#exp-gateway", Checkbox).value:
                fields.append("gateway")
            if self.query_one("#exp-mac", Checkbox).value:
                fields.append("mac_address")
            if self.query_one("#exp-model", Checkbox).value:
                fields.append("model_name")
            if self.query_one("#exp-serial", Checkbox).value:
                fields.append("serial_number")
            if self.query_one("#exp-port", Checkbox).value:
                fields.append("http_port")
            if self.query_one("#exp-firmware", Checkbox).value:
                fields.append("firmware_version")
            if self.query_one("#exp-netmode", Checkbox).value:
                fields.append("network_mode")
            if self.query_one("#exp-status", Checkbox).value:
                fields.append("status")
            if self.query_one("#exp-firstseen", Checkbox).value:
                fields.append("first_seen")
            if self.query_one("#exp-lastseen", Checkbox).value:
                fields.append("last_seen")

            self.dismiss({
                'filename': filename,
                'format': 'json' if format_json else 'csv',
                'scope': 'all' if scope_all else group,
                'fields': fields
            })


class ScanResultsScreen(ModalScreen):
    """Show scan results and allow adding to groups"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, devices: List[DeviceInfo], groups: List[str], existing_macs: Set[str]):
        super().__init__()
        self.devices = devices
        self.groups = groups
        self.existing_macs = existing_macs

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label(f"Scan Results - {len(self.devices)} devices found", classes="modal-title")
            yield Rule()

            new_devices = [d for d in self.devices if d.mac_address.lower() not in self.existing_macs]
            existing = [d for d in self.devices if d.mac_address.lower() in self.existing_macs]

            yield Label(f"New devices: {len(new_devices)} | Already tracked: {len(existing)}")
            yield Rule()

            if new_devices:
                yield Label("Add new devices to group:")
                group_options = [(g, g) for g in self.groups]
                yield Select(group_options, id="target-group")

                yield Label("Select devices to add:")
                with ScrollableContainer(id="device-list"):
                    for device in new_devices:
                        yield Checkbox(
                            f"{device.device_name} ({device.ip_address}) - {device.model_name}",
                            value=True,
                            id=f"dev-{device.mac_address.replace(':', '-')}"
                        )
            else:
                yield Label("All discovered devices are already tracked.")

            with Horizontal(classes="modal-buttons"):
                if new_devices:
                    yield Button("Add Selected", id="btn-add", variant="primary")
                yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
        elif event.button.id == "btn-add":
            group_select = self.query_one("#target-group", Select)
            if group_select.value == Select.BLANK:
                self.notify("Please select a target group", severity="warning")
                return

            selected_devices = []
            for device in self.devices:
                checkbox_id = f"dev-{device.mac_address.replace(':', '-')}"
                try:
                    checkbox = self.query_one(f"#{checkbox_id}", Checkbox)
                    if checkbox.value:
                        selected_devices.append(device)
                except:
                    pass

            self.dismiss({
                'group': group_select.value,
                'devices': selected_devices
            })


class DeviceDetailsScreen(ModalScreen):
    """Show device details modal"""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, device: TrackedDevice):
        super().__init__()
        self.device = device

    def compose(self) -> ComposeResult:
        d = self.device
        with Vertical(classes="modal-container"):
            yield Label(f"Device Details: {d.device_name}", classes="modal-title")
            yield Rule()
            yield Label(f"Type: {d.device_type.capitalize()}")
            yield Label(f"Model: {d.model_name}")
            yield Label(f"Serial: {d.serial_number}")
            yield Label(f"MAC: {d.mac_address}")
            yield Rule()
            yield Label(f"IP Address: {d.ip_address}")
            yield Label(f"Subnet: {d.subnet_mask}")
            yield Label(f"Gateway: {d.gateway}")
            yield Label(f"HTTP Port: {d.http_port}")
            yield Label(f"Network Mode: {d.network_mode}")
            yield Rule()
            yield Label(f"Firmware: {d.firmware_version}")
            yield Label(f"Status: {d.status}")
            yield Label(f"First Seen: {d.first_seen or 'N/A'}")
            yield Label(f"Last Seen: {d.last_seen or 'N/A'}")
            yield Rule()
            with Horizontal(classes="modal-buttons"):
                yield Button("Open in Browser", id="btn-browser", variant="primary")
                yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
        elif event.button.id == "btn-browser":
            # Return device info so the handler can open browser
            self.dismiss(("browser", self.device))


class ScanningScreen(ModalScreen):
    """Scanning progress modal"""

    def __init__(self, timeout: float = 3.0):
        super().__init__()
        self.timeout = timeout

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Scanning Network...", classes="modal-title")
            yield Rule()
            yield LoadingIndicator()
            yield Label(f"Timeout: {self.timeout} seconds")
            yield Label("Please wait...")


class GroupsView(ScrollableContainer):
    """Main view showing device groups"""

    def __init__(self, site_data: SiteData):
        super().__init__(id="groups-container")
        self.site_data = site_data

    def compose(self) -> ComposeResult:
        if not self.site_data.groups:
            yield Label("No groups defined. Use Groups > Add New Group to create one.")
            return

        for group in self.site_data.groups:
            yield self._create_group_widget(group)

    def _create_group_widget(self, group: DeviceGroup) -> Container:
        """Create a widget for a device group"""
        status_color = group.get_status_color()

        if group.device_count == 0:
            header_class = "group-header group-header-empty"
        elif status_color == "green":
            header_class = "group-header group-header-online"
        elif status_color == "red":
            header_class = "group-header group-header-offline"
        else:
            header_class = "group-header group-header-partial"

        container = Vertical(id=f"group-{group.name.replace(' ', '-')}")
        return container

    def refresh_groups(self):
        """Refresh the groups display"""
        self.remove_children()
        for widget in self.compose():
            self.mount(widget)


class EasyIPTUI(App):
    """Main TUI Application"""

    CSS = APP_CSS
    TITLE = "i-PRO Easy IP Setup"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f1", "show_file_menu", "File"),
        Binding("f2", "show_scan_menu", "Scan"),
        Binding("f3", "toggle_monitor", "Monitor"),
        Binding("f4", "show_group_menu", "Groups"),
        Binding("f5", "show_setup_menu", "Setup"),
        Binding("e", "export", "Export"),
        Binding("r", "refresh", "Refresh"),
        Binding("o", "open_in_browser", "Open Browser"),
        Binding("space", "toggle_group", "Expand/Collapse", show=False),
    ]

    site_data: reactive[SiteData] = reactive(SiteData)
    current_file: reactive[Optional[Path]] = reactive(None)
    monitoring: reactive[bool] = reactive(False)

    def __init__(self):
        super().__init__()
        self.site_data = SiteData()
        self.current_file = None
        self.monitoring = False
        self._monitor_timer = None
        self._is_monitoring_scan = False  # Flag to distinguish monitor scans from manual scans
        self._row_keys: List[str] = []  # Map row index to key

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield MenuBar(id="menu-bar")
            yield self._create_groups_table()
        yield StatusBar(id="status-bar")
        yield Footer()

    def _create_groups_table(self) -> DataTable:
        """Create the main data table"""
        table = DataTable(id="main-table")
        self._add_table_columns(table)
        return table

    def _add_table_columns(self, table: DataTable) -> None:
        """Add columns to table based on visibility settings"""
        columns = ["", "Device"]  # Group indicator and device name always shown
        if self.site_data.show_device_type:
            columns.append("Type")
        if self.site_data.show_ip_address:
            columns.append("IP Address")
        if self.site_data.show_mac_address:
            columns.append("MAC Address")
        if self.site_data.show_model:
            columns.append("Model")
        if self.site_data.show_serial:
            columns.append("Serial")
        if self.site_data.show_http_port:
            columns.append("Port")
        if self.site_data.show_firmware:
            columns.append("Firmware")
        if self.site_data.show_status:
            columns.append("Status")
        table.add_columns(*columns)

    def _rebuild_table_columns(self) -> None:
        """Rebuild table columns when visibility settings change"""
        table = self.query_one("#main-table", DataTable)
        table.clear(columns=True)
        self._add_table_columns(table)

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self._rebuild_table_columns()
        self.refresh_table()
        self.title = f"i-PRO Easy IP Setup - {self.site_data.name}"
        self._update_status_bar()
        self._update_monitor_status_label()

    def _update_status_bar(self) -> None:
        """Update the status bar with current stats"""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.monitoring = self.monitoring

            # Calculate totals
            total = 0
            online = 0
            offline = 0
            for group in self.site_data.groups:
                total += group.device_count
                online += group.online_count
                offline += group.offline_count

            status_bar.update_stats(total, online, offline)
            status_bar.update_last_scan(self.site_data.last_scan or "")
        except:
            pass  # Status bar may not be mounted yet

    def _build_row_data(self, device, is_group_header: bool = False, group_text=None, stats_text=None):
        """Build row data based on column visibility settings"""
        row = []
        # First column: group indicator or indentation
        if is_group_header:
            row.append(group_text)
            row.append(stats_text)
        else:
            row.append("    ")  # Indentation
            row.append(device.device_name)

        if not is_group_header:
            if self.site_data.show_device_type:
                row.append(device.device_type)
            if self.site_data.show_ip_address:
                row.append(device.ip_address)
            if self.site_data.show_mac_address:
                row.append(device.mac_address)
            if self.site_data.show_model:
                row.append(device.model_name)
            if self.site_data.show_serial:
                row.append(device.serial_number)
            if self.site_data.show_http_port:
                row.append(str(device.http_port))
            if self.site_data.show_firmware:
                row.append(device.firmware_version)
            if self.site_data.show_status:
                status_style = {"online": "green", "offline": "red", "unknown": "dim"}.get(device.status, "dim")
                row.append(Text(device.status.upper(), style=status_style))
        else:
            # Fill remaining columns for group header
            col_count = 2  # Already have group text and stats
            if self.site_data.show_device_type:
                col_count += 1
            if self.site_data.show_ip_address:
                col_count += 1
            if self.site_data.show_mac_address:
                col_count += 1
            if self.site_data.show_model:
                col_count += 1
            if self.site_data.show_serial:
                col_count += 1
            if self.site_data.show_http_port:
                col_count += 1
            if self.site_data.show_firmware:
                col_count += 1
            if self.site_data.show_status:
                col_count += 1
            # Add empty strings for remaining columns
            while len(row) < col_count:
                row.append("")

        return row

    def refresh_table(self) -> None:
        """Refresh the data table"""
        table = self.query_one("#main-table", DataTable)
        table.clear()
        self._row_keys = []  # Reset row keys mapping

        for group_idx, group in enumerate(self.site_data.groups):
            status_color = group.get_status_color()

            # Add group header row with expand/collapse indicator
            expand_icon = "[-]" if group.expanded else "[+]"
            group_text = Text(f"{expand_icon} {group.name}", style=f"bold {status_color}")
            stats = Text(f"({group.device_count} devices: {group.online_count} online, {group.offline_count} offline)", style="dim")

            # Use index for key to avoid issues with special characters in names
            group_key = f"group-{group_idx}"
            row_data = self._build_row_data(None, is_group_header=True, group_text=group_text, stats_text=stats)
            table.add_row(*row_data, key=group_key)
            self._row_keys.append(group_key)

            # Add device rows only if group is expanded
            if group.expanded:
                for device in group.devices:
                    # Sanitize MAC address for key (replace colons)
                    mac_key = device.mac_address.replace(":", "-")
                    device_key = f"device-{mac_key}"
                    row_data = self._build_row_data(device)
                    table.add_row(*row_data, key=device_key)
                    self._row_keys.append(device_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu button presses"""
        button_id = event.button.id
        if button_id == "menu-file":
            self.action_show_file_menu()
        elif button_id == "menu-scan":
            self.action_show_scan_menu()
        elif button_id == "menu-monitor":
            self.action_toggle_monitor()
        elif button_id == "menu-groups":
            self.action_show_group_menu()
        elif button_id == "menu-setup":
            self.action_show_setup_menu()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data table"""
        key = event.row_key.value if event.row_key else ""

        if key.startswith("group-"):
            # Toggle group expand/collapse using index
            try:
                group_idx = int(key.replace("group-", ""))
                if 0 <= group_idx < len(self.site_data.groups):
                    self.site_data.groups[group_idx].expanded = not self.site_data.groups[group_idx].expanded
                    self.refresh_table()
                    self._update_status_bar()
            except ValueError:
                pass
        elif key.startswith("device-"):
            # Convert key back to MAC address format
            mac = key.replace("device-", "").replace("-", ":")
            result = self.site_data.find_device_by_mac(mac)
            if result:
                _, device = result
                self.push_screen(DeviceDetailsScreen(device), self._handle_device_details)

    def _handle_device_details(self, result) -> None:
        """Handle device details screen result"""
        if result and isinstance(result, tuple) and result[0] == "browser":
            device = result[1]
            # Build URL and open browser
            port = device.http_port if device.http_port != 80 else ""
            port_str = f":{port}" if port else ""
            url = f"http://{device.ip_address}{port_str}"
            try:
                webbrowser.open(url)
                self.notify(f"Opening {url} in browser")
            except Exception as e:
                self.notify(f"Failed to open browser: {e}", severity="error")

    # File menu actions
    def action_show_file_menu(self) -> None:
        self.push_screen(FileMenuScreen(), self._handle_file_menu)

    def _handle_file_menu(self, result: Optional[str]) -> None:
        if result == "load":
            self._load_site()
        elif result == "save":
            self._save_site()
        elif result == "save-as":
            self._save_site_as()
        elif result == "exit":
            self.exit()

    def _load_site(self) -> None:
        """Load site from file using file browser"""
        self.push_screen(FileBrowserScreen(), self._handle_load_file)

    def _handle_load_file(self, filepath: Optional[Path]) -> None:
        """Handle file selection from browser"""
        if filepath:
            try:
                self.site_data = SiteData.load(filepath)
                self.current_file = filepath
                self.title = f"i-PRO Easy IP Setup - {self.site_data.name}"
                self._rebuild_table_columns()  # Rebuild columns for loaded settings
                self.refresh_table()
                self._update_status_bar()
                self.notify(f"Loaded site from {filepath}")
            except Exception as e:
                self.notify(f"Error loading site: {e}", severity="error")

    def _save_site(self) -> None:
        """Save site to current file"""
        if self.current_file:
            self._save_to_path(self.current_file)
        else:
            self._save_site_as()

    def _save_site_as(self) -> None:
        """Save site to new file with filename dialog"""
        current_name = self.current_file.stem if self.current_file else "site_data"
        self.push_screen(SaveAsScreen(current_name), self._handle_save_as)

    def _handle_save_as(self, filename: Optional[str]) -> None:
        """Handle save as dialog result"""
        if filename:
            path = Path(filename)
            self._save_to_path(path)

    def _save_to_path(self, path: Path) -> None:
        """Save site data to specified path"""
        try:
            self.site_data.save(path)
            self.current_file = path
            self.title = f"i-PRO Easy IP Setup - {self.site_data.name}"
            self.notify(f"Saved site to {path}")
        except Exception as e:
            self.notify(f"Error saving site: {e}", severity="error")

    # Scan menu actions
    def action_show_scan_menu(self) -> None:
        self.push_screen(ScanMenuScreen(), self._handle_scan_menu)

    def _handle_scan_menu(self, result) -> None:
        if isinstance(result, tuple) and result[0] == "scan":
            timeout = result[1]
            self._run_scan(timeout)
        elif result == "manual-add":
            if not self.site_data.groups:
                self.notify("Please create a group first", severity="warning")
                return
            groups = [g.name for g in self.site_data.groups]
            self.push_screen(ManualAddScreen(groups), self._handle_manual_add)

    def _handle_manual_add(self, result) -> None:
        if result:
            device, group_name = result
            for group in self.site_data.groups:
                if group.name == group_name:
                    group.devices.append(device)
                    self.refresh_table()
                    self._update_status_bar()
                    self.notify(f"Added {device.device_name} to {group_name}")
                    break

    @work(exclusive=True, thread=True)
    def _run_scan(self, timeout: float, silent: bool = False) -> None:
        """Run network scan in background thread

        Args:
            timeout: Scan timeout in seconds
            silent: If True, don't show scanning screen or results popup (for monitoring)
        """
        worker = get_current_worker()

        # Show scanning screen only for manual scans
        if not silent:
            self.call_from_thread(self.push_screen, ScanningScreen(timeout))

        # Run discovery using the configured network interface
        interface = self.site_data.network_interface or "0.0.0.0"
        setup = iPROIPSetup(timeout=timeout, interface=interface)
        devices = setup.discover_devices()

        # Hide scanning screen for manual scans
        if not silent:
            self.call_from_thread(self.pop_screen)

        if not worker.is_cancelled:
            self.call_from_thread(self._process_scan_results, devices, silent)

    def _process_scan_results(self, devices: List[DeviceInfo], silent: bool = False) -> None:
        """Process scan results - update device statuses"""
        # Update status of existing devices
        existing_macs = set()
        for group in self.site_data.groups:
            for device in group.devices:
                existing_macs.add(device.mac_address.lower())
                # Update status based on scan
                found = False
                for scanned in devices:
                    if scanned.mac_address.lower() == device.mac_address.lower():
                        device.status = "online"
                        device.last_seen = datetime.now().isoformat()
                        device.ip_address = scanned.ip_address
                        found = True
                        break
                if not found:
                    device.status = "offline"

        self.site_data.last_scan = datetime.now().isoformat()
        self.refresh_table()
        self._update_status_bar()

        # For silent (monitoring) scans, just update and notify briefly
        if silent:
            online = sum(g.online_count for g in self.site_data.groups)
            offline = sum(g.offline_count for g in self.site_data.groups)
            if offline > 0:
                self.notify(f"Monitor scan: {offline} device(s) offline", severity="warning")
            return

        # For manual scans, show full results
        self._show_scan_results(devices, existing_macs)

    def _show_scan_results(self, devices: List[DeviceInfo], existing_macs: Set[str]) -> None:
        """Show scan results screen for manual scans"""
        if not devices:
            self.notify("No devices found on network", severity="warning")
            return

        # Create a default group if none exist
        if not self.site_data.groups:
            default_group = DeviceGroup(name="Default")
            self.site_data.groups.append(default_group)
            self.refresh_table()
            self._update_status_bar()
            self.notify("Created 'Default' group for discovered devices")

        groups = [g.name for g in self.site_data.groups]
        self.push_screen(
            ScanResultsScreen(devices, groups, existing_macs),
            self._handle_scan_results
        )

    def _handle_scan_results(self, result) -> None:
        if result and isinstance(result, dict):
            group_name = result['group']
            devices = result['devices']

            for group in self.site_data.groups:
                if group.name == group_name:
                    for device_info in devices:
                        tracked = TrackedDevice.from_device_info(device_info)
                        group.devices.append(tracked)
                    self.refresh_table()
                    self._update_status_bar()
                    self.notify(f"Added {len(devices)} devices to {group_name}")
                    break

    # Monitor actions
    def action_toggle_monitor(self) -> None:
        self.monitoring = not self.monitoring
        self._update_status_bar()
        self._update_monitor_status_label()

        if self.monitoring:
            self._start_monitoring()
            self.notify("Monitoring started", severity="information")
        else:
            self._stop_monitoring()
            self.notify("Monitoring stopped", severity="information")

    def _update_monitor_status_label(self) -> None:
        """Update the monitoring status label in the menu bar"""
        try:
            label = self.query_one("#monitor-status", Label)
            if self.monitoring:
                label.update("MONITORING: ACTIVE")
                label.remove_class("monitor-stopped")
                label.add_class("monitor-active")
            else:
                label.update("MONITORING: STOPPED")
                label.remove_class("monitor-active")
                label.add_class("monitor-stopped")
        except:
            pass  # Label may not be mounted yet

    def _start_monitoring(self) -> None:
        """Start periodic scanning"""
        # Run an immediate scan when monitoring starts
        self._monitor_scan()
        # Calculate and display next scan time
        self._update_next_scan_time()
        # Then set up the timer for subsequent scans
        self._monitor_timer = self.set_interval(
            self.site_data.scan_frequency,
            self._monitor_scan_with_next_update
        )

    def _update_next_scan_time(self) -> None:
        """Update the next scan time in the status bar"""
        try:
            next_scan = datetime.now() + timedelta(seconds=self.site_data.scan_frequency)
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_next_scan(next_scan.isoformat())
        except:
            pass

    def _monitor_scan_with_next_update(self) -> None:
        """Run a monitoring scan and update the next scan time"""
        self._monitor_scan()
        self._update_next_scan_time()

    def _stop_monitoring(self) -> None:
        """Stop periodic scanning"""
        if self._monitor_timer:
            self._monitor_timer.stop()
            self._monitor_timer = None
        # Clear next scan time display
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_next_scan("")
        except:
            pass

    def _monitor_scan(self) -> None:
        """Run a silent monitoring scan"""
        self._run_scan(3.0, silent=True)

    # Group menu actions
    def action_show_group_menu(self) -> None:
        self.push_screen(GroupMenuScreen(), self._handle_group_menu)

    def _handle_group_menu(self, result: Optional[str]) -> None:
        if result == "add-group":
            self.push_screen(AddGroupScreen(), self._handle_add_group)
        elif result == "remove-group":
            if self.site_data.groups:
                groups = [g.name for g in self.site_data.groups]
                self.push_screen(RemoveGroupScreen(groups), self._handle_remove_group)
            else:
                self.notify("No groups to remove", severity="warning")
        elif result == "move-device":
            self._show_move_device()

    def _handle_add_group(self, name: Optional[str]) -> None:
        if name:
            # Check for duplicate
            if any(g.name == name for g in self.site_data.groups):
                self.notify(f"Group '{name}' already exists", severity="warning")
                return

            self.site_data.groups.append(DeviceGroup(name=name))
            self.refresh_table()
            self._update_status_bar()
            self.notify(f"Created group: {name}")

    def _handle_remove_group(self, name: Optional[str]) -> None:
        if name:
            self.site_data.groups = [g for g in self.site_data.groups if g.name != name]
            self.refresh_table()
            self._update_status_bar()
            self.notify(f"Removed group: {name}")

    def _show_move_device(self) -> None:
        """Show move device screen"""
        devices = []
        for group in self.site_data.groups:
            for device in group.devices:
                devices.append((device.mac_address, device.device_name, group.name))

        if not devices:
            self.notify("No devices to move", severity="warning")
            return

        groups = [g.name for g in self.site_data.groups]
        self.push_screen(MoveDeviceScreen(devices, groups), self._handle_move_device)

    def _handle_move_device(self, result) -> None:
        if result:
            mac, target_group = result

            # Find and remove device from current group
            device_to_move = None
            for group in self.site_data.groups:
                for device in group.devices:
                    if device.mac_address == mac:
                        device_to_move = device
                        group.devices.remove(device)
                        break
                if device_to_move:
                    break

            # Add to target group
            if device_to_move:
                for group in self.site_data.groups:
                    if group.name == target_group:
                        group.devices.append(device_to_move)
                        self.refresh_table()
                        self._update_status_bar()
                        self.notify(f"Moved {device_to_move.device_name} to {target_group}")
                        break

    # Setup menu actions
    def action_show_setup_menu(self) -> None:
        self.push_screen(
            SetupMenuScreen(self.site_data),
            self._handle_setup_menu
        )

    def _handle_setup_menu(self, result) -> None:
        if result and isinstance(result, dict):
            # Update site name
            old_name = self.site_data.name
            self.site_data.name = result['name']

            # Update network interface
            self.site_data.network_interface = result['network_interface']

            # Update scan frequency
            self.site_data.scan_frequency = result['frequency']

            # Update column visibility
            self.site_data.show_device_type = result['show_device_type']
            self.site_data.show_ip_address = result['show_ip_address']
            self.site_data.show_mac_address = result['show_mac_address']
            self.site_data.show_model = result['show_model']
            self.site_data.show_serial = result['show_serial']
            self.site_data.show_status = result['show_status']
            self.site_data.show_firmware = result['show_firmware']
            self.site_data.show_http_port = result['show_http_port']

            # Update title if name changed
            if old_name != self.site_data.name:
                self.title = f"i-PRO Easy IP Setup - {self.site_data.name}"

            # Refresh table with new column settings
            self._rebuild_table_columns()
            self.refresh_table()

            self.notify("Settings applied")

            # Restart monitoring with new frequency if active
            if self.monitoring:
                self._stop_monitoring()
                self._start_monitoring()

    # Export action
    def action_export(self) -> None:
        if not self.site_data.groups:
            self.notify("No data to export", severity="warning")
            return

        groups = [g.name for g in self.site_data.groups]
        self.push_screen(ExportScreen(groups), self._handle_export)

    def _handle_export(self, options) -> None:
        if not options:
            return

        # Determine which devices to export
        if options['scope'] == 'all':
            devices = self.site_data.get_all_devices()
        else:
            devices = []
            for group in self.site_data.groups:
                if group.name == options['scope']:
                    devices = group.devices
                    break

        if not devices:
            self.notify("No devices to export", severity="warning")
            return

        # Build export data
        fields = options['fields']
        export_data = []
        for device in devices:
            device_dict = device.to_dict()
            filtered = {k: v for k, v in device_dict.items() if k in fields}
            export_data.append(filtered)

        # Get filename from options
        base_filename = options.get('filename', 'export')

        # Export to file with appropriate extension
        try:
            if options['format'] == 'json':
                filename = f"{base_filename}.json"
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
            else:
                import csv
                filename = f"{base_filename}.csv"
                with open(filename, 'w', newline='') as f:
                    if export_data:
                        writer = csv.DictWriter(f, fieldnames=fields)
                        writer.writeheader()
                        writer.writerows(export_data)

            self.notify(f"Exported {len(devices)} devices to {filename}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    # Refresh action
    def action_refresh(self) -> None:
        self.refresh_table()
        self._update_status_bar()
        self.notify("Display refreshed")

    def action_open_in_browser(self) -> None:
        """Open the currently selected device in browser"""
        table = self.query_one("#main-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._row_keys):
            row_key = self._row_keys[table.cursor_row]
            if row_key.startswith("device-"):
                mac = row_key.replace("device-", "").replace("-", ":")
                result = self.site_data.find_device_by_mac(mac)
                if result:
                    _, device = result
                    port = device.http_port if device.http_port != 80 else ""
                    port_str = f":{port}" if port else ""
                    url = f"http://{device.ip_address}{port_str}"
                    try:
                        webbrowser.open(url)
                        self.notify(f"Opening {url} in browser")
                    except Exception as e:
                        self.notify(f"Failed to open browser: {e}", severity="error")
            else:
                self.notify("Select a device to open in browser", severity="warning")
        else:
            self.notify("No row selected", severity="warning")

    def action_toggle_group(self) -> None:
        """Toggle expand/collapse for the currently selected group"""
        table = self.query_one("#main-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._row_keys):
            row_key = self._row_keys[table.cursor_row]
            if row_key.startswith("group-"):
                try:
                    group_idx = int(row_key.replace("group-", ""))
                    if 0 <= group_idx < len(self.site_data.groups):
                        self.site_data.groups[group_idx].expanded = not self.site_data.groups[group_idx].expanded
                        self.refresh_table()
                        self._update_status_bar()
                except ValueError:
                    pass


def main():
    """Main entry point"""
    app = EasyIPTUI()
    app.run()


if __name__ == "__main__":
    main()
