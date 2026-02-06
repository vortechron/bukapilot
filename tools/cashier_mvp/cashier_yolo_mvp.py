#!/usr/bin/env python3
"""
Cashier MVP: grab camera frames from openpilot camerad (VisionIpc), run TinyGrad YOLOv8,
print detected COCO items.

Run on ka1 (openpilot must be running):
  cd /data/openpilot && PYTHONPATH=/data/openpilot:/data/openpilot/third_party/tinygrad python3 tools/cashier_mvp/cashier_yolo_mvp.py

Weights live in tools/cashier_mvp/weights/ (yolov8n.safetensors, coco.names).
"""
import sys
import time
from pathlib import Path
import numpy as np

# Ensure paths
OPENPILOT = "/data/openpilot"
TINYGRAD = "/data/openpilot/third_party/tinygrad"
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
for p in [OPENPILOT, TINYGRAD]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Minimal cv2 stub so yolov8 example can be imported (uses resize + copyMakeBorder)
try:
    import cv2
except ImportError:
    from PIL import Image
    class _cv2:
        INTER_LINEAR = 1
        BORDER_CONSTANT = 0
        @staticmethod
        def resize(img, size, interpolation=1):
            w, h = size[0], size[1]
            return np.array(Image.fromarray(img).resize((w, h), Image.BILINEAR))
        @staticmethod
        def copyMakeBorder(img, top, bottom, left, right, borderType, value=(114,114,114)):
            return np.pad(img, ((top,bottom),(left,right),(0,0)), mode="constant", constant_values=value)
    sys.modules["cv2"] = _cv2()

# Now we can import cereal and tinygrad
from cereal.visionipc import VisionIpcClient, VisionStreamType

# TinyGrad and YOLOv8 from submodule
sys.path.insert(0, TINYGRAD + "/examples")
import yolov8

# Constants
IMGSZ = 640
CONF_THRESH = 0.25
IOU_THRESH = 0.45
INFERENCE_INTERVAL_SEC = 1.0
YOLO_VARIANT = "n"


def yuv_to_rgb(y, u, v):
    ul = np.repeat(np.repeat(u, 2).reshape(u.shape[0], y.shape[1]), 2, axis=0).reshape(y.shape)
    vl = np.repeat(np.repeat(v, 2).reshape(v.shape[0], y.shape[1]), 2, axis=0).reshape(y.shape)
    yuv = np.dstack((y, ul, vl)).astype(np.int16)
    yuv[:, :, 1:] -= 128
    m = np.array([
        [1.0, 1.0, 1.0],
        [0.0, -0.39465, 2.03211],
        [1.13983, -0.58060, 0.0],
    ])
    return np.dot(yuv, m).clip(0, 255).astype(np.uint8)


def decode_frame(buf_data, width, height, stride, uv_offset):
    """Decode VisionIpc buffer (numpy array) to RGB. On ka1 recv() returns raw array."""
    y = np.array(buf_data[:uv_offset], dtype=np.uint8).reshape((-1, stride))[:height, :width]
    u = np.array(buf_data[uv_offset::2], dtype=np.uint8).reshape((-1, stride // 2))[:height // 2, :width // 2]
    v = np.array(buf_data[uv_offset + 1::2], dtype=np.uint8).reshape((-1, stride // 2))[:height // 2, :width // 2]
    return yuv_to_rgb(y, u, v)


def preprocess_rgb_for_yolo(rgb):
    """Resize RGB (H,W,3) to 640x640, normalize, return TinyGrad Tensor (1,3,640,640)."""
    from PIL import Image
    from tinygrad.tensor import Tensor
    img = Image.fromarray(rgb)
    img = img.resize((IMGSZ, IMGSZ), Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = arr[:, :, ::-1]  # RGB -> BGR as in yolov8 preprocess
    # HWC → NCHW: (1, 3, 640, 640)
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
    assert arr.shape == (1, 3, IMGSZ, IMGSZ), f"expected (1,3,{IMGSZ},{IMGSZ}), got {arr.shape}"
    return Tensor(arr)


def load_coco_names():
    path = WEIGHTS_DIR / "coco.names"
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    print("Cashier MVP: VisionIpc + YOLOv8. Openpilot/camerad must be running.")
    print("Loading YOLOv8n and weights from", WEIGHTS_DIR, "...")
    depth, width, ratio = yolov8.get_variant_multiples(YOLO_VARIANT)
    model = yolov8.YOLOv8(w=width, r=ratio, d=depth, num_classes=80)
    weights_path = TINYGRAD + "/weights/yolov8n.safetensors"
    import os
    if not os.path.exists(weights_path):
        weights_path = str(WEIGHTS_DIR / "yolov8n.safetensors")
    state_dict = yolov8.safe_load(weights_path)
    yolov8.load_state_dict(model, state_dict)
    class_labels = load_coco_names()
    print("Model loaded. Connecting to camerad (driver stream)...")

    frame_count = 0
    consecutive_none = 0
    while True:
        client = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_DRIVER, True)
        client.connect(True)
        print("Waiting for first frame from camerad...", flush=True)
        buf_data = None
        for _ in range(50):
            buf_data = client.recv(timeout_ms=200)
            if buf_data is not None and len(buf_data) > 0:
                break
            time.sleep(0.1)
        if client.width is None or client.height is None or buf_data is None or len(buf_data) == 0:
            print("No frames yet (is openpilot/camerad running?). Retrying in 3s...", flush=True)
            time.sleep(3)
            continue
        print("Connected. Frame size:", client.width, "x", client.height, flush=True)
        w, h = client.width, client.height
        stride = getattr(client, "stride", None) or w
        row_stride = stride if stride else w
        uv_offset = h * row_stride
        interrupted = False
        try:
            while True:
                try:
                    if buf_data is None or len(buf_data) == 0:
                        buf_data = client.recv(timeout_ms=500)
                        if buf_data is None or len(buf_data) == 0:
                            consecutive_none += 1
                            if consecutive_none % 20 == 1 and consecutive_none > 1:
                                print("Waiting for next frame...", flush=True)
                            time.sleep(0.2)
                            continue
                        consecutive_none = 0
                    else:
                        consecutive_none = 0
                    w, h = client.width, client.height
                    stride = getattr(client, "stride", None) or w
                    row_stride = stride if stride else w
                    uv_offset = h * row_stride
                    rgb = decode_frame(buf_data, w, h, row_stride, uv_offset)
                    inp = preprocess_rgb_for_yolo(rgb)
                    preds = model(inp)
                    all_preds = yolov8.postprocess(preds, inp, [rgb])
                    frame_count += 1
                    if not all_preds or len(all_preds[0]) == 0:
                        print("Frame %d: Detected: (none)" % frame_count, flush=True)
                    else:
                        pred = all_preds[0]
                        names = []
                        for row in pred:
                            if row[4] >= CONF_THRESH:
                                cid = int(row[5])
                                if 0 <= cid < len(class_labels):
                                    names.append(class_labels[cid])
                        print("Frame %d: Detected: %s" % (frame_count, ", ".join(names) if names else "(none)"), flush=True)
                    buf_data = None
                    time.sleep(INFERENCE_INTERVAL_SEC)
                except Exception as e:
                    print("Frame error (continuing):", e, flush=True)
                    buf_data = None
                    time.sleep(0.5)
        except KeyboardInterrupt:
            interrupted = True
            print("Stopped.", flush=True)
            break
        if interrupted:
            break
        print("Connection lost. Reconnecting in 3s...", flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
