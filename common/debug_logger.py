"""Lightweight buffered JSONL logger for real-time control debugging.

Designed for resource-constrained devices (KA2 dongle). Features:
- Rate-throttled (default 10 Hz) to avoid spamming from 50 Hz loops
- Buffered writes (default 50 entries) — one disk I/O per ~5 seconds
- Auto-rotating file with size cap — never fills disk
- All public methods are exception-safe — logger never crashes the caller

Usage:
  from openpilot.common.debug_logger import DebugLogger

  dbg = DebugLogger("long_ctrl")
  dbg.log({"vEgo": 27.8, "accel": 0.5, "source": "lead0"})
"""
import json
import os
import time

_DEFAULT_DIR = "/tmp"
_DEFAULT_MAX_MB = 5
_DEFAULT_MAX_BACKUPS = 1
_DEFAULT_BUFFER_SIZE = 50
_DEFAULT_RATE_HZ = 10


class DebugLogger:
  def __init__(self, name, path=_DEFAULT_DIR, max_file_mb=_DEFAULT_MAX_MB,
               max_backups=_DEFAULT_MAX_BACKUPS, buffer_size=_DEFAULT_BUFFER_SIZE,
               rate_hz=_DEFAULT_RATE_HZ):
    self._name = name
    self._file_path = os.path.join(path, f"bp_debug_{name}.jsonl")
    self._max_bytes = max_file_mb * 1_000_000
    self._max_backups = max_backups
    self._buffer_size = buffer_size
    self._min_interval = 1.0 / rate_hz if rate_hz > 0 else 0.0

    self._buffer = []
    self._last_log_t = 0.0
    self._fh = None

  def log(self, data):
    """Append a data dict if rate allows. Flushes buffer when full."""
    try:
      now = time.monotonic()
      if now - self._last_log_t < self._min_interval:
        return
      self._last_log_t = now

      entry = {"_t": round(time.time(), 3), "_m": round(now, 4), "_s": self._name}
      entry.update(data)
      self._buffer.append(json.dumps(entry, default=_safe_float))

      if len(self._buffer) >= self._buffer_size:
        self.flush()
    except Exception:
      pass

  def flush(self):
    """Write buffered entries to disk in one call."""
    try:
      if not self._buffer:
        return
      self._ensure_open()
      self._maybe_rotate()
      self._fh.write("\n".join(self._buffer) + "\n")
      self._fh.flush()
      self._buffer.clear()
    except Exception:
      self._buffer.clear()  # drop data rather than OOM

  def close(self):
    """Flush remaining buffer and close file handle."""
    try:
      self.flush()
      if self._fh is not None:
        self._fh.close()
        self._fh = None
    except Exception:
      pass

  def _ensure_open(self):
    if self._fh is None or self._fh.closed:
      self._fh = open(self._file_path, "a")

  def _maybe_rotate(self):
    try:
      if not os.path.exists(self._file_path):
        return
      if os.path.getsize(self._file_path) < self._max_bytes:
        return
      # Close current handle
      if self._fh is not None:
        self._fh.close()
        self._fh = None
      # Rotate backups
      for i in range(self._max_backups, 0, -1):
        src = self._file_path if i == 1 else f"{self._file_path}.{i - 1}"
        dst = f"{self._file_path}.{i}"
        if os.path.exists(dst):
          os.remove(dst)
        if os.path.exists(src):
          os.rename(src, dst)
      # Open fresh file
      self._fh = open(self._file_path, "a")
    except Exception:
      pass


def _safe_float(obj):
  """JSON serializer fallback for numpy types."""
  try:
    return float(obj)
  except (TypeError, ValueError):
    return str(obj)
