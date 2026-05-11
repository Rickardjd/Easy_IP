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


_APP_CONFIG_PATH = Path(__file__).parent / "app_config.json"


@dataclass
class AppConfig:
    """Application-level settings, persisted independently of site data."""
    data_folder: str = "data"
    theme: str = "textual-dark"

    def save(self) -> None:
        with open(_APP_CONFIG_PATH, 'w') as f:
            json.dump({'data_folder': self.data_folder, 'theme': self.theme}, f, indent=2)

    @classmethod
    def load(cls) -> 'AppConfig':
        try:
            with open(_APP_CONFIG_PATH, 'r') as f:
                data = json.load(f)
                return cls(
                    data_folder=data.get('data_folder', 'data'),
                    theme=data.get('theme', 'textual-dark'),
                )
        except Exception:
            return cls()

    @property
    def data_path(self) -> Path:
        p = Path(self.data_folder)
        if not p.is_absolute():
            p = Path(__file__).parent / p
        return p

    def ensure_data_folder(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)


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
    # Deep check setting
    deep_check_enabled: bool = False
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
            'deep_check_enabled': self.deep_check_enabled,
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
            deep_check_enabled=data.get('deep_check_enabled', False),
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
    height: 4;
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

/* ── Configure IP dialog ─────────────────────────────────── */
#configure-ip-modal {
    width: 84;
}

#configure-ip-list {
    height: 10;
    border: solid $primary;
    margin: 1 0;
}

.configure-device-row {
    height: auto;
    padding: 0 0;
    align: left middle;
}

.configure-device-row Checkbox {
    width: 1fr;
}

.configure-device-row Input {
    width: 20;
    margin: 0;
}

.conf-base-row {
    height: auto;
    align: left middle;
}

.conf-base-row Input {
    width: 1fr;
    margin-right: 1;
}

.conf-base-row Button {
    min-width: 14;
}

#configure-progress {
    margin: 1 0;
}

.conf-result-ok  { color: $success; }
.conf-result-fail { color: $error; }

#dns-manual-fields {
    height: auto;
    margin: 0 0 1 0;
}

#auto-assign-section {
    height: auto;
}

.conf-mode-label {
    margin: 1 0 0 0;
}

#net-mode-select {
    margin: 0 0 1 0;
}

#dns-mode-select {
    margin: 0 0 0 0;
}

/* ── Move devices dialog ─────────────────────────────────── */
#move-device-modal {
    width: 72;
}

#move-device-list {
    height: 14;
    border: solid $primary;
    margin: 1 0;
}

.move-device-row {
    height: auto;
    padding: 0 1;
}

.move-device-row Checkbox {
    width: 1fr;
}

.move-sel-buttons {
    height: auto;
    align: left middle;
    margin-bottom: 1;
}

.move-sel-buttons Button {
    min-width: 10;
    margin-right: 1;
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

#monitor-info {
    margin-left: 2;
    padding: 0 2;
    align: left middle;
}

#monitor-status {
    text-style: bold;
}

#monitor-last-scan-label {
    color: $text-muted;
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
        yield Button("File",      id="menu-file",      classes="menu-button")
        yield Button("Scan",      id="menu-scan",      classes="menu-button")
        yield Button("Monitor",   id="menu-monitor",   classes="menu-button")
        yield Button("Groups",    id="menu-groups",    classes="menu-button")
        yield Button("Setup",     id="menu-setup",     classes="menu-button")
        yield Button("Config IP", id="menu-config-ip", classes="menu-button")
        with Vertical(id="monitor-info"):
            yield Label("MONITORING: STOPPED", id="monitor-status", classes="monitor-stopped")
            yield Label("", id="monitor-last-scan-label")


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

    def __init__(self, current_name: str = "site_data", data_folder: str = "data"):
        super().__init__()
        self.current_name = current_name
        self.data_folder = data_folder

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Save Site As", classes="modal-title")
            yield Rule()
            yield Label("Filename:")
            yield Input(value=self.current_name, placeholder="Enter filename", id="save-filename")
            yield Label("(Extension .ezip will be added automatically)", classes="device-unknown")
            yield Label(f"Save location: {self.data_folder}", classes="device-unknown")
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
            # Add .ezip extension if not present
            if not filename.endswith('.ezip'):
                filename = f"{filename}.ezip"
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
                elif item.suffix.lower() == '.ezip':
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

    def __init__(self, site_data: 'SiteData', app_config: 'AppConfig'):
        super().__init__()
        self.site_data = site_data
        self.app_config = app_config
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
            yield Checkbox("Deep Check", value=self.site_data.deep_check_enabled, id="deep-check")
            yield Label("Query the webserver on each camera to confirm it is responding.", classes="device-unknown")
            yield Rule()
            yield Label("Scan Frequency (seconds):")
            yield Input(value=str(self.site_data.scan_frequency), id="scan-frequency", type="number")
            yield Rule()
            yield Label("Data Folder:")
            yield Input(value=self.app_config.data_folder, placeholder="e.g. data or C:\\MyData", id="data-folder")
            yield Label("(Relative paths are resolved from the application directory)", classes="device-unknown")
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
                'deep_check_enabled': self.query_one("#deep-check", Checkbox).value,
                'frequency': int(self.query_one("#scan-frequency", Input).value or 60),
                'data_folder': self.query_one("#data-folder", Input).value.strip() or "data",
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
    """Move one or more devices to a group."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, devices: List[tuple], groups: List[str]):
        super().__init__()
        self.devices = devices  # List of (mac, name, current_group)
        self.groups = groups

    def _mid(self, mac: str) -> str:
        return mac.replace(":", "")

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container", id="move-device-modal"):
            yield Label("Move Devices to Group", classes="modal-title")
            yield Rule()

            yield Label(f"Select devices to move ({len(self.devices)} total):")
            with ScrollableContainer(id="move-device-list"):
                for mac, name, group in self.devices:
                    with Horizontal(classes="move-device-row"):
                        yield Checkbox(
                            f"{name}  ({group})",
                            value=False,
                            id=f"dev-{self._mid(mac)}",
                        )

            with Horizontal(classes="move-sel-buttons"):
                yield Button("All",    id="btn-sel-all",    variant="default")
                yield Button("None",   id="btn-sel-none",   variant="default")
                yield Button("Invert", id="btn-sel-invert", variant="default")

            yield Rule()
            yield Label("Move selected devices to:")
            group_options = [(g, g) for g in self.groups]
            yield Select(group_options, id="target-group")

            with Horizontal(classes="modal-buttons"):
                yield Button("Move Selected", id="btn-move", variant="primary")
                yield Button("Cancel",        id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-sel-all":
            for mac, _, _ in self.devices:
                try:
                    self.query_one(f"#dev-{self._mid(mac)}", Checkbox).value = True
                except Exception:
                    pass
        elif bid == "btn-sel-none":
            for mac, _, _ in self.devices:
                try:
                    self.query_one(f"#dev-{self._mid(mac)}", Checkbox).value = False
                except Exception:
                    pass
        elif bid == "btn-sel-invert":
            for mac, _, _ in self.devices:
                try:
                    cb = self.query_one(f"#dev-{self._mid(mac)}", Checkbox)
                    cb.value = not cb.value
                except Exception:
                    pass
        elif bid == "btn-move":
            self._do_move()

    def _do_move(self) -> None:
        target = self.query_one("#target-group", Select)
        if target.value == Select.BLANK:
            self.notify("Select a target group first", severity="warning")
            return
        selected = [
            (mac, str(target.value))
            for mac, _, _ in self.devices
            if self.query_one(f"#dev-{self._mid(mac)}", Checkbox).value
        ]
        if not selected:
            self.notify("No devices selected", severity="warning")
            return
        self.dismiss(selected)


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


class ConfigureIPScreen(ModalScreen):
    """Configure IP addresses for one or more tracked cameras."""

    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, devices: List['TrackedDevice'], preselected_mac: Optional[str] = None,
                 base_ip: Optional[str] = None):
        super().__init__()
        self.devices = devices
        self.preselected_mac = preselected_mac
        first = devices[0] if devices else None
        self._default_subnet  = first.subnet_mask if first else "255.255.255.0"
        self._default_gateway = first.gateway    if first else ""
        self._net_mode = "static"
        self._dns_mode = "auto"
        self._initial_base_ip = base_ip

    def _mid(self, mac: str) -> str:
        return mac.replace(":", "")

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container", id="configure-ip-modal"):
            yield Label("Configure IP Addresses", classes="modal-title")
            yield Rule()

            # ── Network mode ──────────────────────────────────────────
            yield Label("Network Mode:")
            yield Select(
                options=[
                    ("Static IP",        "static"),
                    ("DHCP",             "dhcp"),
                    ("Auto (AutoIP)",    "auto_autoip"),
                    ("Auto (Advanced)",  "auto_advanced"),
                ],
                value="static",
                id="net-mode-select",
            )
            yield Rule()

            # ── Shared network settings ───────────────────────────────
            yield Label("Shared Network Settings:")
            yield Label("Subnet Mask:")
            yield Input(value=self._default_subnet, placeholder="255.255.255.0", id="shared-subnet")
            yield Label("Gateway:")
            yield Input(value=self._default_gateway, placeholder="192.168.1.1", id="shared-gateway")

            # ── DNS ───────────────────────────────────────────────────
            yield Label("DNS Mode:", classes="conf-mode-label")
            yield Select(
                options=[("Auto", "auto"), ("Manual", "manual")],
                value="auto",
                id="dns-mode-select",
            )
            with Vertical(id="dns-manual-fields"):
                yield Label("Primary DNS:")
                yield Input(value="8.8.8.8", placeholder="8.8.8.8", id="primary-dns")
                yield Label("Secondary DNS:")
                yield Input(value="8.8.4.4", placeholder="8.8.4.4", id="secondary-dns")
            yield Rule()

            # ── Auto-assign (static mode only) ───────────────────────
            with Vertical(id="auto-assign-section"):
                yield Label("Auto-assign from base address:")
                with Horizontal(classes="conf-base-row"):
                    yield Input(placeholder="e.g. 192.168.1.100", id="base-ip")
                    yield Button("Auto-assign ▶", id="btn-auto-assign")
                with Horizontal(classes="conf-base-row"):
                    yield Button("Select All",  id="btn-sel-all",  variant="default")
                    yield Button("Select None", id="btn-sel-none", variant="default")
                yield Rule()

            # ── Device list ───────────────────────────────────────────
            yield Label(f"Devices ({len(self.devices)}) — tick to configure:")
            with ScrollableContainer(id="configure-ip-list"):
                for device in self.devices:
                    mid = self._mid(device.mac_address)
                    is_pre = (
                        self.preselected_mac is None
                        or device.mac_address.lower() == (self.preselected_mac or "").lower()
                    )
                    with Horizontal(classes="configure-device-row"):
                        yield Checkbox(
                            f"{device.device_name} ({device.ip_address})",
                            value=is_pre,
                            id=f"chk-{mid}",
                        )
                        yield Input(placeholder="New IP", id=f"new-ip-{mid}")

            yield Rule()
            with Horizontal(classes="modal-buttons"):
                yield Button("Apply Selected", id="btn-apply", variant="primary")
                yield Button("Cancel",         id="btn-cancel")

    # ------------------------------------------------------------------ lifecycle

    def on_mount(self) -> None:
        self.query_one("#dns-manual-fields").display = False
        if self._initial_base_ip:
            self.query_one("#base-ip", Input).value = self._initial_base_ip

    # ------------------------------------------------------------------ events

    def on_select_changed(self, event: Select.Changed) -> None:
        widget_id = event.control.id
        value = event.value

        if widget_id == "net-mode-select":
            self._net_mode = str(value) if value != Select.BLANK else "static"
            is_static = (self._net_mode == "static")
            for device in self.devices:
                mid = self._mid(device.mac_address)
                try:
                    self.query_one(f"#new-ip-{mid}", Input).display = is_static
                except Exception:
                    pass
            self.query_one("#auto-assign-section").display = is_static

        elif widget_id == "dns-mode-select":
            self._dns_mode = str(value) if value != Select.BLANK else "auto"
            self.query_one("#dns-manual-fields").display = (self._dns_mode == "manual")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-auto-assign":
            self._do_auto_assign()
        elif bid == "btn-sel-all":
            for device in self.devices:
                try:
                    self.query_one(f"#chk-{self._mid(device.mac_address)}", Checkbox).value = True
                except Exception:
                    pass
        elif bid == "btn-sel-none":
            for device in self.devices:
                try:
                    self.query_one(f"#chk-{self._mid(device.mac_address)}", Checkbox).value = False
                except Exception:
                    pass
        elif bid == "btn-apply":
            self._do_apply()

    def _do_auto_assign(self) -> None:
        base = self.query_one("#base-ip", Input).value.strip()
        if not base:
            self.notify("Enter a base IP address first", severity="warning")
            return
        try:
            parts = [int(x) for x in base.split('.')]
            if len(parts) != 4 or not all(0 <= p <= 255 for p in parts):
                raise ValueError
        except ValueError:
            self.notify("Invalid base IP address", severity="error")
            return

        counter = 0
        for device in self.devices:
            mid = self._mid(device.mac_address)
            try:
                if not self.query_one(f"#chk-{mid}", Checkbox).value:
                    continue
                last = parts[3] + counter
                if last > 255:
                    self.notify(f"Overflow at {device.device_name} — stopped", severity="warning")
                    break
                self.query_one(f"#new-ip-{mid}", Input).value = (
                    f"{parts[0]}.{parts[1]}.{parts[2]}.{last}"
                )
                counter += 1
            except Exception:
                pass
        if counter:
            self.notify(f"Auto-assigned {counter} IP addresses")
            next_last = parts[3] + counter
            if next_last <= 255:
                self.query_one("#base-ip", Input).value = (
                    f"{parts[0]}.{parts[1]}.{parts[2]}.{next_last}"
                )

    def _do_apply(self) -> None:
        subnet  = self.query_one("#shared-subnet",  Input).value.strip()
        gateway = self.query_one("#shared-gateway", Input).value.strip()
        if not subnet:
            self.notify("Subnet mask is required", severity="warning")
            return

        net_mode = self._net_mode
        dns_mode = self._dns_mode
        primary_dns   = self.query_one("#primary-dns",   Input).value.strip() or "8.8.8.8"
        secondary_dns = self.query_one("#secondary-dns", Input).value.strip() or "8.8.4.4"
        is_static = (net_mode == "static")

        configs = []
        for device in self.devices:
            mid = self._mid(device.mac_address)
            try:
                if not self.query_one(f"#chk-{mid}", Checkbox).value:
                    continue

                if is_static:
                    new_ip = self.query_one(f"#new-ip-{mid}", Input).value.strip()
                    if not new_ip:
                        continue
                    parts = new_ip.split('.')
                    if len(parts) != 4 or not all(0 <= int(p) <= 255 for p in parts):
                        self.notify(f"Invalid IP for {device.device_name}: {new_ip}", severity="error")
                        return
                else:
                    new_ip = device.ip_address  # device keeps its current IP; DHCP/auto assigns later

                configs.append({
                    'device':        device,
                    'new_ip':        new_ip,
                    'subnet':        subnet,
                    'gateway':       gateway,
                    'mode':          net_mode,
                    'dns_mode':      dns_mode,
                    'primary_dns':   primary_dns,
                    'secondary_dns': secondary_dns,
                })
            except Exception:
                pass

        if not configs:
            if is_static:
                self.notify("No devices selected with a new IP entered", severity="warning")
            else:
                self.notify("No devices selected", severity="warning")
            return
        self.dismiss(configs)


class ConfiguringScreen(ModalScreen):
    """Progress screen shown while configure_camera commands are in flight."""

    def __init__(self, total: int):
        super().__init__()
        self._total = total

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Configuring Devices…", classes="modal-title")
            yield Rule()
            yield Label("Starting…", id="conf-current")
            yield ProgressBar(total=self._total, show_eta=False, id="configure-progress")
            yield Label("", id="conf-done")

    def set_progress(self, current: int, device_name: str) -> None:
        try:
            self.query_one("#conf-current", Label).update(
                f"({current}/{self._total})  {device_name}"
            )
            self.query_one("#configure-progress", ProgressBar).progress = current
        except Exception:
            pass

    def set_done(self, ok: int, fail: int, expired: int = 0) -> None:
        try:
            parts = []
            if ok:
                parts.append(f"{ok} succeeded")
            if expired:
                parts.append(f"{expired} setup window expired")
            other_fail = fail - expired
            if other_fail:
                parts.append(f"{other_fail} failed")
            if not parts:
                parts.append("nothing to do")
            msg = "Done — " + ", ".join(parts)
            self.query_one("#conf-done", Label).update(msg)
        except Exception:
            pass


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
        Binding("i", "configure_ip", "Config IP"),
        Binding("r", "refresh", "Refresh"),
        Binding("o", "open_in_browser", "Open Browser"),
        Binding("space", "toggle_group", "Expand/Collapse", show=False),
        Binding("c", "copy_cell", "Copy Cell"),
    ]

    site_data: reactive[SiteData] = reactive(SiteData)
    current_file: reactive[Optional[Path]] = reactive(None)
    monitoring: reactive[bool] = reactive(False)

    def __init__(self):
        super().__init__()
        self.site_data = SiteData()
        self.current_file = None
        self.monitoring = False
        self.app_config = AppConfig.load()
        self.app_config.ensure_data_folder()
        self._monitor_timer = None
        self._is_monitoring_scan = False  # Flag to distinguish monitor scans from manual scans
        self._row_keys: List[str] = []  # Map row index to key
        # Sorting state
        self._sort_column: Optional[str] = None  # field name to sort by, or None
        self._sort_ascending: bool = True
        self._column_fields: List[Optional[str]] = []  # maps column index to sortable field name
        # Persists the next available base IP between Configure IP dialog sessions
        self._next_base_ip: Optional[str] = None

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

    def _make_col_label(self, name: str, field: Optional[str]) -> str:
        """Return column label with sort indicator when this column is the active sort."""
        if field and field == self._sort_column:
            indicator = " \u25b2" if self._sort_ascending else " \u25bc"
            return f"{name}{indicator}"
        return name

    def _add_table_columns(self, table: DataTable) -> None:
        """Add columns to table based on visibility settings, tracking sortable fields."""
        self._column_fields = []
        columns = []

        # Group indicator column – not sortable
        columns.append("")
        self._column_fields.append(None)

        # Device name – always shown, sortable
        columns.append(self._make_col_label("Device", "device_name"))
        self._column_fields.append("device_name")

        if self.site_data.show_device_type:
            columns.append(self._make_col_label("Type", "device_type"))
            self._column_fields.append("device_type")
        if self.site_data.show_ip_address:
            columns.append(self._make_col_label("IP Address", "ip_address"))
            self._column_fields.append("ip_address")
        if self.site_data.show_mac_address:
            columns.append(self._make_col_label("MAC Address", "mac_address"))
            self._column_fields.append("mac_address")
        if self.site_data.show_model:
            columns.append(self._make_col_label("Model", "model_name"))
            self._column_fields.append("model_name")
        if self.site_data.show_serial:
            columns.append(self._make_col_label("Serial", "serial_number"))
            self._column_fields.append("serial_number")
        if self.site_data.show_http_port:
            columns.append(self._make_col_label("Port", "http_port"))
            self._column_fields.append("http_port")
        if self.site_data.show_firmware:
            columns.append(self._make_col_label("Firmware", "firmware_version"))
            self._column_fields.append("firmware_version")
        if self.site_data.show_status:
            columns.append(self._make_col_label("Status", "status"))
            self._column_fields.append("status")

        table.add_columns(*columns)

    def _rebuild_table_columns(self) -> None:
        """Rebuild table columns when visibility settings change"""
        table = self.query_one("#main-table", DataTable)
        table.clear(columns=True)
        self._add_table_columns(table)

    def watch_theme(self, theme: str) -> None:
        """Persist theme choice whenever it changes."""
        if hasattr(self, 'app_config'):
            self.app_config.theme = theme
            self.app_config.save()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        # Restore saved theme before rendering
        self.theme = self.app_config.theme
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
        try:
            label = self.query_one("#monitor-last-scan-label", Label)
            last_scan = self.site_data.last_scan
            if last_scan:
                dt = datetime.fromisoformat(last_scan)
                label.update(f"Last scan: {dt.strftime('%H:%M:%S')}")
            else:
                label.update("")
        except:
            pass

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

    # ------------------------------------------------------------------ sorting

    _FIELD_DISPLAY_NAMES = {
        "device_name": "Device",
        "device_type": "Type",
        "ip_address": "IP Address",
        "mac_address": "MAC Address",
        "model_name": "Model",
        "serial_number": "Serial",
        "http_port": "Port",
        "firmware_version": "Firmware",
        "status": "Status",
    }

    def _ip_sort_key(self, ip_str: str) -> tuple:
        """Convert an IP address string to a tuple of ints for correct numeric ordering."""
        try:
            return tuple(int(x) for x in ip_str.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0, 0)

    def _get_sorted_devices(self, devices: List[TrackedDevice]) -> List[TrackedDevice]:
        """Return a sorted copy of *devices* according to the current sort state."""
        if not self._sort_column:
            return list(devices)

        def sort_key(device: TrackedDevice):
            val = getattr(device, self._sort_column, "")
            if self._sort_column == "ip_address":
                return self._ip_sort_key(str(val))
            if isinstance(val, int):
                return (val,)
            return (str(val).lower(),)

        return sorted(devices, key=sort_key, reverse=not self._sort_ascending)

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
                for device in self._get_sorted_devices(group.devices):
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
        elif button_id == "menu-config-ip":
            self.action_configure_ip()

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

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Cycle sort state when a column header is clicked.

        Click 1 on a column  → sort ascending  (▲)
        Click 2 on same col  → sort descending (▼)
        Click 3 on same col  → clear sort (back to insertion order)
        """
        col_idx = event.column_index
        if col_idx >= len(self._column_fields):
            return

        field = self._column_fields[col_idx]
        if field is None:
            return  # Group-indicator column is not sortable

        if self._sort_column == field:
            if self._sort_ascending:
                # ascending → descending
                self._sort_ascending = False
            else:
                # descending → clear
                self._sort_column = None
                self._sort_ascending = True
        else:
            # New column → ascending
            self._sort_column = field
            self._sort_ascending = True

        self._rebuild_table_columns()
        self.refresh_table()

        if self._sort_column:
            direction = "\u25b2 Ascending" if self._sort_ascending else "\u25bc Descending"
            col_name = self._FIELD_DISPLAY_NAMES.get(self._sort_column, self._sort_column)
            self.notify(f"Sorted by {col_name} {direction}")
        else:
            self.notify("Sort cleared \u2014 default order restored")

    def _handle_device_details(self, result) -> None:
        """Handle device details screen result"""
        if result and isinstance(result, tuple) and result[0] == "browser":
            device = result[1]
            # Build URL and open browser
            scheme = "https" if device.http_port == 443 else "http"
            port = device.http_port if device.http_port not in (80, 443) else ""
            port_str = f":{port}" if port else ""
            url = f"{scheme}://{device.ip_address}{port_str}"
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
        self.push_screen(FileBrowserScreen(start_path=self.app_config.data_path), self._handle_load_file)

    def _handle_load_file(self, filepath: Optional[Path]) -> None:
        """Handle file selection from browser"""
        if filepath:
            try:
                self.site_data = SiteData.load(filepath)
                for group in self.site_data.groups:
                    for device in group.devices:
                        device.status = "unknown"
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
        self.push_screen(
            SaveAsScreen(current_name, data_folder=str(self.app_config.data_path)),
            self._handle_save_as
        )

    def _handle_save_as(self, filename: Optional[str]) -> None:
        """Handle save as dialog result"""
        if filename:
            path = Path(filename)
            if not path.is_absolute():
                self.app_config.ensure_data_folder()
                path = self.app_config.data_path / path
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

    def _run_http_checks(self, discovered: List[DeviceInfo]) -> Set[str]:
        """HTTP-verify each tracked device. Returns set of MACs that responded.

        Any HTTP response (including 401/403) counts as reachable; only
        connection errors and timeouts count as unreachable.
        """
        import ssl
        import urllib.request
        import urllib.error

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Build MAC→IP map from UDP discovery so we use the freshest IP
        discovered_ips: Dict[str, str] = {d.mac_address.lower(): d.ip_address for d in discovered}

        verified: Set[str] = set()
        for group in self.site_data.groups:
            for device in group.devices:
                mac = device.mac_address.lower()
                ip = discovered_ips.get(mac, device.ip_address)
                if not ip:
                    continue
                port = device.http_port or 80
                scheme = "https" if port == 443 else "http"
                url = f"{scheme}://{ip}:{port}/cgi-bin/getinfo?FILE=1"
                try:
                    urllib.request.urlopen(url, timeout=3, context=ctx)
                    verified.add(mac)
                except urllib.error.HTTPError:
                    # Camera responded with an HTTP error — it is still up
                    verified.add(mac)
                except Exception:
                    pass  # Timeout or connection refused — camera not verified
        return verified

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

        http_verified: Optional[Set[str]] = None
        if self.site_data.deep_check_enabled and not worker.is_cancelled:
            http_verified = self._run_http_checks(devices)

        if not worker.is_cancelled:
            self.call_from_thread(self._process_scan_results, devices, silent, http_verified)

    def _process_scan_results(self, devices: List[DeviceInfo], silent: bool = False, http_verified: Optional[Set[str]] = None) -> None:
        """Process scan results - update device statuses"""
        # Update status of existing devices
        existing_macs = set()
        for group in self.site_data.groups:
            for device in group.devices:
                mac = device.mac_address.lower()
                existing_macs.add(mac)
                found = False
                for scanned in devices:
                    if scanned.mac_address.lower() == mac:
                        device.last_seen = datetime.now().isoformat()
                        device.ip_address = scanned.ip_address
                        found = True
                        break
                if http_verified is not None:
                    # Deep check mode: HTTP response is the source of truth
                    device.status = "online" if mac in http_verified else "offline"
                else:
                    device.status = "online" if found else "offline"

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
        if not result:
            return
        moved = 0
        target_group_name = result[0][1] if result else ""
        for mac, target_group in result:
            # Remove from current group
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
                        moved += 1
                        break
        if moved:
            self.refresh_table()
            self._update_status_bar()
            self.notify(f"Moved {moved} device(s) to '{target_group_name}'")

    # ── Configure IP actions ──────────────────────────────────────────────────

    def action_configure_ip(self) -> None:
        """Open the Configure IP dialog for tracked devices."""
        all_devices = self.site_data.get_all_devices()
        if not all_devices:
            self.notify("No tracked devices — scan the network first", severity="warning")
            return

        # Pre-select the device under the cursor (if any)
        preselected_mac: Optional[str] = None
        table = self.query_one("#main-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._row_keys):
            row_key = self._row_keys[table.cursor_row]
            if row_key.startswith("device-"):
                preselected_mac = row_key.replace("device-", "").replace("-", ":")

        self.push_screen(
            ConfigureIPScreen(all_devices, preselected_mac=preselected_mac,
                              base_ip=self._next_base_ip),
            self._handle_configure_ip,
        )

    def _handle_configure_ip(self, configs) -> None:
        if configs:
            # Advance the stored base IP to the address after the highest static IP applied.
            # This pre-fills the base IP field the next time the dialog is opened.
            static_ips = [cfg['new_ip'] for cfg in configs if cfg.get('mode', 'static') == 'static']
            if static_ips:
                try:
                    octets_list = [list(map(int, ip.split('.'))) for ip in static_ips]
                    max_last = max(o[3] for o in octets_list)
                    prefix = '.'.join(map(str, octets_list[0][:3]))
                    if max_last + 1 <= 255:
                        self._next_base_ip = f"{prefix}.{max_last + 1}"
                except Exception:
                    pass
            self._run_configure(configs)

    @work(exclusive=True, thread=True)
    def _run_configure(self, configs: List[dict]) -> None:
        """Background worker: send configure_camera for each entry in configs."""
        worker    = get_current_worker()
        total     = len(configs)
        interface = self.site_data.network_interface or "0.0.0.0"

        conf_screen = ConfiguringScreen(total)
        self.call_from_thread(self.push_screen, conf_screen)

        # One upfront discovery scan to get each camera's current setup-window
        # state.  Using a shorter timeout (2 s) since we only need one response
        # per device and they reply within milliseconds on a local LAN.
        self.call_from_thread(conf_screen.set_progress, 0, "Checking camera state…")
        live: dict = {}
        try:
            scanner = iPROIPSetup(timeout=2.0, interface=interface)
            for d in scanner.discover_devices():
                live[d.mac_address.lower()] = d
        except Exception:
            pass

        # results are (device, new_ip, success, reason)
        # reason is None for normal outcomes, "expired" when setup window is closed
        results = []
        for idx, cfg in enumerate(configs):
            if worker.is_cancelled:
                break
            device        = cfg['device']
            new_ip        = cfg['new_ip']
            subnet        = cfg['subnet']
            gateway       = cfg['gateway']
            mode          = cfg.get('mode', 'static')
            dns_mode      = cfg.get('dns_mode', 'manual')
            primary_dns   = cfg.get('primary_dns', '8.8.8.8')
            secondary_dns = cfg.get('secondary_dns', '8.8.4.4')

            self.call_from_thread(conf_screen.set_progress, idx + 1, device.device_name)

            # Refuse if the camera itself has reported its setup window is closed.
            live_dev = live.get(device.mac_address.lower())
            if live_dev is not None and live_dev.setup_window_open is False:
                results.append((device, new_ip, False, "expired"))
                continue

            # Use the freshly discovered port when available (more accurate than
            # the value stored from the last scan).
            live_port = live_dev.http_port if live_dev else None
            port = live_port or device.http_port or 443

            try:
                setup = iPROIPSetup(timeout=5.0, interface=interface)
                success = setup.configure_camera(
                    mac_address=device.mac_address,
                    ip=new_ip,
                    subnet=subnet,
                    gateway=gateway,
                    port=port,
                    mode=mode,
                    dns_mode=dns_mode,
                    primary_dns=primary_dns,
                    secondary_dns=secondary_dns,
                )
                results.append((device, new_ip, success, None))
            except Exception:
                results.append((device, new_ip, False, None))

        ok      = sum(1 for r in results if r[2])
        expired = sum(1 for r in results if r[3] == "expired")
        fail    = len(results) - ok
        self.call_from_thread(conf_screen.set_progress, total, "Complete")
        self.call_from_thread(conf_screen.set_done, ok, fail, expired)

        import time as _time
        _time.sleep(1.5)  # Let the user read the result

        self.call_from_thread(self.pop_screen)
        if not worker.is_cancelled:
            self.call_from_thread(self._process_configure_results, results)

    def _process_configure_results(self, results: List[tuple]) -> None:
        """Update tracked device IPs and refresh the table after configuration."""
        ok = fail = expired = 0
        expired_names = []
        for result in results:
            device, new_ip, success = result[0], result[1], result[2]
            reason = result[3] if len(result) > 3 else None
            if success:
                found = self.site_data.find_device_by_mac(device.mac_address)
                if found:
                    _, tracked = found
                    tracked.ip_address = new_ip
                ok += 1
            elif reason == "expired":
                expired += 1
                expired_names.append(device.device_name)
            else:
                fail += 1

        self.refresh_table()
        self._update_status_bar()

        if expired_names:
            self.notify(
                "Setup window expired — power-cycle to reconfigure: "
                + ", ".join(expired_names),
                severity="error",
            )
        other_fail = fail
        if ok == 0 and other_fail == 0 and expired > 0:
            return  # already notified above, nothing else to say
        if other_fail == 0 and ok > 0:
            self.notify(
                f"IP configuration complete — {ok} device(s) updated",
                severity="information",
            )
        elif ok > 0 or other_fail > 0:
            self.notify(
                f"Configuration finished: {ok} succeeded, {other_fail} failed",
                severity="warning",
            )

    # Setup menu actions
    def action_show_setup_menu(self) -> None:
        self.push_screen(
            SetupMenuScreen(self.site_data, self.app_config),
            self._handle_setup_menu
        )

    def _handle_setup_menu(self, result) -> None:
        if result and isinstance(result, dict):
            # Update site name
            old_name = self.site_data.name
            self.site_data.name = result['name']

            # Update network interface
            self.site_data.network_interface = result['network_interface']

            # Update deep check setting
            self.site_data.deep_check_enabled = result['deep_check_enabled']

            # Update scan frequency
            self.site_data.scan_frequency = result['frequency']

            # Update data folder
            new_folder = result.get('data_folder', 'data')
            if new_folder != self.app_config.data_folder:
                self.app_config.data_folder = new_folder
                self.app_config.ensure_data_folder()
                self.app_config.save()

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

        # Determine which devices to export (respecting current sort order)
        if options['scope'] == 'all':
            devices = []
            for group in self.site_data.groups:
                devices.extend(self._get_sorted_devices(group.devices))
        else:
            devices = []
            for group in self.site_data.groups:
                if group.name == options['scope']:
                    devices = self._get_sorted_devices(group.devices)
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

        # Get filename from options, resolve into data folder if not absolute
        base_filename = options.get('filename', 'export')
        export_base = Path(base_filename)
        if not export_base.is_absolute():
            self.app_config.ensure_data_folder()
            export_base = self.app_config.data_path / base_filename

        # Export to file with appropriate extension
        try:
            if options['format'] == 'json':
                filename = str(export_base) + ".json"
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
            else:
                import csv
                filename = str(export_base) + ".csv"
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
                    scheme = "https" if device.http_port == 443 else "http"
                    port = device.http_port if device.http_port not in (80, 443) else ""
                    port_str = f":{port}" if port else ""
                    url = f"{scheme}://{device.ip_address}{port_str}"
                    try:
                        webbrowser.open(url)
                        self.notify(f"Opening {url} in browser")
                    except Exception as e:
                        self.notify(f"Failed to open browser: {e}", severity="error")
            else:
                self.notify("Select a device to open in browser", severity="warning")
        else:
            self.notify("No row selected", severity="warning")

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to the system clipboard. Returns True on success."""
        import subprocess
        import platform
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
            elif system == "Darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=True)
            else:
                try:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
                except FileNotFoundError:
                    subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
            return True
        except Exception:
            return False

    def action_copy_cell(self) -> None:
        """Copy the value of the currently focused table cell to the clipboard."""
        from textual.coordinate import Coordinate
        table = self.query_one("#main-table", DataTable)
        row = table.cursor_row
        col = table.cursor_column
        if row is None or col is None:
            self.notify("No cell selected", severity="warning")
            return
        try:
            cell_value = table.get_cell_at(Coordinate(row, col))
        except Exception:
            self.notify("Could not read cell value", severity="warning")
            return

        # Strip rich markup — cell values may be Rich Text objects
        if hasattr(cell_value, "plain"):
            plain = cell_value.plain
        else:
            plain = str(cell_value)
        plain = plain.strip()

        if not plain:
            self.notify("Cell is empty", severity="warning")
            return

        if self._copy_to_clipboard(plain):
            self.notify(f"Copied: {plain}")
        else:
            self.notify(f"Clipboard unavailable. Value: {plain}", severity="warning")

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
