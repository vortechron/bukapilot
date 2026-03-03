#!/usr/bin/env python3
"""
Stream replay UI frames over WebRTC.

This reuses the same core inputs as tools/replay/ui.py:
  - VisionIPC road camera frames
  - modelV2 / radarState overlays
  - liveCalibration for projection

Signaling is handled by a tiny aiohttp server.
Open http://<host>:8083 in a browser and click connect.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web

import cereal.messaging as messaging
from msgq.visionipc import VisionIpcClient, VisionStreamType
from openpilot.common.transformations.camera import DEVICE_CAMERAS
from openpilot.tools.replay.lib.ui_helpers import UP, Calibration, get_blank_lid_overlay, maybe_update_radar_points, plot_lead, plot_model

try:
  from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
  from av import VideoFrame
except Exception as e:  # pragma: no cover
  raise ImportError(
    "ui_webrtc.py requires aiortc + av. Install with: pip install aiortc av"
  ) from e


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8083
VIEWER_FILE = Path(__file__).with_name("ui_webrtc_viewer.html")


@dataclass
class LatestFrame:
  frame: np.ndarray | None = None
  lock: threading.Lock = field(default_factory=threading.Lock)


class ReplayUIRenderer(threading.Thread):
  def __init__(self, addr: str):
    super().__init__(daemon=True)
    self.addr = addr
    self.latest = LatestFrame()
    self.running = True

  def stop(self) -> None:
    self.running = False

  @staticmethod
  def decode_nv12(data: bytes, width: int, height: int, stride: int) -> np.ndarray:
    imgff = np.frombuffer(data, dtype=np.uint8).reshape((len(data) // stride, stride))
    return cv2.cvtColor(imgff[: height * 3 // 2, : width], cv2.COLOR_YUV2RGB_NV12)

  def run(self) -> None:
    sm = messaging.SubMaster(
      ["modelV2", "radarState", "liveCalibration", "liveTracks", "roadCameraState"],
      addr=self.addr,
    )
    vipc = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_ROAD, True)
    calibration = None
    num_px = 0
    calib_scale = 1.0
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    lid_overlay_blank = get_blank_lid_overlay(UP)

    while self.running:
      if not vipc.is_connected():
        vipc.connect(True)

      yuv = vipc.recv()
      if yuv is None or not yuv.data.any():
        time.sleep(0.01)
        continue

      sm.update(0)
      rgb = self.decode_nv12(yuv.data, vipc.width, vipc.height, vipc.stride)
      camera = DEVICE_CAMERAS[("tici", str(sm["roadCameraState"].sensor))]
      bb_scale = camera.fcam.width / 640.0
      calib_scale = camera.fcam.width / 640.0
      zoom_matrix = np.asarray([[bb_scale, 0.0, 0.0], [0.0, bb_scale, 0.0], [0.0, 0.0, 1.0]])
      cv2.warpAffine(rgb, zoom_matrix[:2], (img.shape[1], img.shape[0]), dst=img, flags=cv2.WARP_INVERSE_MAP)
      num_px = vipc.width * vipc.height

      lid_overlay = lid_overlay_blank.copy()
      top_down = (UP, lid_overlay)
      if sm.recv_frame["modelV2"]:
        plot_model(sm["modelV2"], img, calibration, top_down)
      if sm.recv_frame["radarState"]:
        plot_lead(sm["radarState"], top_down)
      maybe_update_radar_points(sm["liveTracks"].points, top_down[1])

      if sm.updated["liveCalibration"] and num_px:
        rpy_calib = np.asarray(sm["liveCalibration"].rpyCalib)
        calibration = Calibration(num_px, rpy_calib, camera.fcam.intrinsics, calib_scale)

      with self.latest.lock:
        self.latest.frame = img.copy()


class ReplayUIVideoTrack(MediaStreamTrack):
  kind = "video"

  def __init__(self, renderer: ReplayUIRenderer):
    super().__init__()
    self.renderer = renderer

  async def recv(self) -> VideoFrame:
    pts, time_base = await self.next_timestamp()
    frame = None
    with self.renderer.latest.lock:
      if self.renderer.latest.frame is not None:
        frame = self.renderer.latest.frame.copy()
    if frame is None:
      frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    vf = VideoFrame.from_ndarray(frame, format="rgb24")
    vf.pts = pts
    vf.time_base = time_base
    return vf


class ReplayUIWebRTCServer:
  def __init__(self, ip_addr: str):
    self.renderer = ReplayUIRenderer(ip_addr)
    self.pcs: set[RTCPeerConnection] = set()
    self.log = logging.getLogger("ui_webrtc")

  async def index(self, _: web.Request) -> web.Response:
    content = VIEWER_FILE.read_text(encoding="utf-8")
    return web.Response(text=content, content_type="text/html")

  async def offer(self, request: web.Request) -> web.Response:
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    self.pcs.add(pc)
    self.log.info("Peer connected (%d active)", len(self.pcs))

    @pc.on("connectionstatechange")
    async def _on_state_change() -> None:
      if pc.connectionState in ("failed", "closed", "disconnected"):
        await pc.close()
        self.pcs.discard(pc)
        self.log.info("Peer removed (%d active)", len(self.pcs))

    pc.addTrack(ReplayUIVideoTrack(self.renderer))
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

  async def on_shutdown(self, _: web.Application) -> None:
    self.renderer.stop()
    await asyncio.gather(*[pc.close() for pc in list(self.pcs)], return_exceptions=True)
    self.pcs.clear()

  def run(self) -> None:
    self.renderer.start()
    app = web.Application()
    app.router.add_get("/", self.index)
    app.router.add_post("/offer", self.offer)
    app.on_shutdown.append(self.on_shutdown)
    web.run_app(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


def main() -> None:
  parser = argparse.ArgumentParser(description="Stream replay UI over WebRTC")
  parser.add_argument("ip_address", nargs="?", default="127.0.0.1", help="Address where replay is publishing services")
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO)
  if args.ip_address != "127.0.0.1":
    os.environ["ZMQ"] = "1"
    messaging.reset_context()

  ReplayUIWebRTCServer(args.ip_address).run()


if __name__ == "__main__":
  main()
