# Cashier MVP – Run instructions (ka1)

## Location
Script and weights live inside openpilot: `tools/cashier_mvp/`
- Script: `tools/cashier_mvp/cashier_yolo_mvp.py`
- Weights: `tools/cashier_mvp/weights/yolov8n.safetensors`, `tools/cashier_mvp/weights/coco.names`

## Prerequisites
- Openpilot must be RUNNING on ka1 (so camerad is publishing frames).

## Run command
cd /data/openpilot && PYTHONPATH=/data/openpilot:/data/openpilot/third_party/tinygrad python3 tools/cashier_mvp/cashier_yolo_mvp.py

## If VisionIpc fails
Ensure openpilot (and thus camerad) is started first. If you see "could not open visionipc" or segfault, start openpilot and try again.
