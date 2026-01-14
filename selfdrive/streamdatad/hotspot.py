import dbus
import subprocess
import uuid
import os
from pathlib import Path

HOTSPOT_PREFIX = "KommuAssist_"
NM_BUS_NAME = 'org.freedesktop.NetworkManager'
NM_OBJECT_PATH = '/org/freedesktop/NetworkManager'
NM_IFACE = 'org.freedesktop.NetworkManager'
NM_SETTINGS_PATH = '/org/freedesktop/NetworkManager/Settings'
NM_SETTINGS_IFACE = 'org.freedesktop.NetworkManager.Settings'
NM_CONNECTION_IFACE = 'org.freedesktop.NetworkManager.Settings.Connection'
NM_DEVICE_IFACE = 'org.freedesktop.NetworkManager.Device'
NM_ACTIVE_CONN_IFACE = 'org.freedesktop.NetworkManager.Connection.Active'

def get_serial():
  try:
    with open("/proc/cpuinfo") as f:
      for line in f:
        if line.startswith("Serial"):
          return line.split(":")[1].strip()
  except FileNotFoundError:
    pass
  return "00000000"

def generate_virtual_mac(phys_mac):
  mac_bytes = [int(b, 16) for b in phys_mac.split(":")]
  mac_bytes[0] |= 0x02
  mac_bytes[-1] = (mac_bytes[-1] + 1) % 256
  return ":".join(f"{b:02x}" for b in mac_bytes)

class Hotspot:
  def __init__(self, phys_iface="wlan0", virt_iface="wlan1"):
    self.phys_iface = phys_iface
    self.virt_iface = virt_iface
    self.bus = dbus.SystemBus()
    self.nm = self.bus.get_object(NM_BUS_NAME, NM_OBJECT_PATH)
    self.settings = self.bus.get_object(NM_BUS_NAME, NM_SETTINGS_PATH)
    serial = get_serial()
    self.ssid, self.password = f"{HOTSPOT_PREFIX}{serial}", serial
    self.conn_path = self._get_hotspot_connection_path()

  def _prepare_interface(self):
    if not os.path.exists(f"/sys/class/net/{self.virt_iface}"):
      subprocess.run(["sudo", "iw", "dev", self.phys_iface, "interface", "add", self.virt_iface, "type", "__ap"], check=True)
      with open(f"/sys/class/net/{self.phys_iface}/address") as f:
        phys_mac = f.read().strip()
      virt_mac = generate_virtual_mac(phys_mac)
      subprocess.run(["sudo", "ip", "link", "set", self.virt_iface, "address", virt_mac], check=True)
    subprocess.run(["sudo", "ip", "link", "set", self.virt_iface, "up"], check=True)

  def _get_hotspot_connection_path(self):
    s_iface = dbus.Interface(self.settings, NM_SETTINGS_IFACE)
    for path in s_iface.ListConnections():
      conn = self.bus.get_object(NM_BUS_NAME, path)
      settings = dbus.Interface(conn, NM_CONNECTION_IFACE).GetSettings()
      if (ssid_val := settings.get('802-11-wireless', {}).get('ssid')) and ''.join(map(chr, ssid_val)) == self.ssid:
        return path
    return None

  def _create_hotspot_connection(self):
    c_settings = {
      'connection': {
        'type': '802-11-wireless',
        'uuid': str(uuid.uuid4()),
        'id': self.ssid,
        'interface-name': self.virt_iface,
        'autoconnect': False,
      },
      '802-11-wireless': {
        'ssid': dbus.ByteArray(self.ssid.encode()),
        'mode': 'ap',
      },
      '802-11-wireless-security': {
        'key-mgmt': 'wpa-psk',
        'psk': self.password,
      },
      'ipv4': {'method': 'shared'},
      'ipv6': {'method': 'ignore'},
    }
    self.conn_path = dbus.Interface(self.settings, NM_SETTINGS_IFACE).AddConnection(c_settings)

  def enable(self):
    self._prepare_interface()
    if not self.conn_path:
      self._create_hotspot_connection()
    nm_iface = dbus.Interface(self.nm, NM_IFACE)
    for dev_path in nm_iface.GetDevices():
      dev_obj = self.bus.get_object(NM_BUS_NAME, dev_path)
      if (iface := dbus.Interface(dev_obj, dbus.PROPERTIES_IFACE).Get(NM_DEVICE_IFACE, "Interface")) == self.virt_iface:
        nm_iface.ActivateConnection(self.conn_path, dev_path, "/")
        break

  def disable(self):
    nm_iface = dbus.Interface(self.nm, NM_IFACE)
    active_conns = dbus.Interface(self.nm, dbus.PROPERTIES_IFACE).Get(NM_IFACE, "ActiveConnections")
    for a_path in active_conns:
      ac_obj = self.bus.get_object(NM_BUS_NAME, a_path)
      ac_props = dbus.Interface(ac_obj, dbus.PROPERTIES_IFACE)
      if str(ac_props.Get(NM_ACTIVE_CONN_IFACE, "Connection")) == str(self.conn_path):
        nm_iface.DeactivateConnection(a_path)
        break
    for cmd in [
      ["sudo", "ip", "link", "set", self.virt_iface, "down"],
      ["sudo", "ip", "addr", "flush", "dev", self.virt_iface],
    ]:
      subprocess.run(cmd, check=False)
