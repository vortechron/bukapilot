"""
Driving model runner using RKNN (vision + policy). All inputs are cast to float16 before inference.
Requires: driving_vision.rknn, driving_policy.rknn in the model folder and rknnlite.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

try:
  from rknnlite.api import RKNNLite
except ImportError:
  RKNNLite = None  # type: ignore


def _to_fp16(x: np.ndarray) -> np.ndarray:
  """Cast to float16. For uint8 images we normalize to [0,1] then cast."""
  if x.dtype == np.uint8:
    return (x.astype(np.float32) / 255.0).astype(np.float16)
  return x.astype(np.float16)


class DrivingRKNNRunner:
  """Runs driving vision and policy models via RKNN. Inputs are cast to float16 before inference."""

  def __init__(self, model_dir: Path):
    self.model_dir = Path(model_dir)
    vision_meta_path = self.model_dir / "driving_vision_metadata.pkl"
    policy_meta_path = self.model_dir / "driving_policy_metadata.pkl"
    vision_rknn_path = self.model_dir / "driving_vision.rknn"
    policy_rknn_path = self.model_dir / "driving_policy.rknn"

    if not vision_rknn_path.exists() or not policy_rknn_path.exists():
      raise FileNotFoundError(
        f"RKNN models not found: need {vision_rknn_path.name} and {policy_rknn_path.name}"
      )
    if RKNNLite is None:
      raise ImportError("rknnlite is required for RKNN driving runner (pip install rknn-toolkit2-lite)")

    with open(vision_meta_path, "rb") as f:
      vision_meta = pickle.load(f)
    with open(policy_meta_path, "rb") as f:
      policy_meta = pickle.load(f)

    self.vision_input_shapes = vision_meta["input_shapes"]
    self.vision_output_slices = vision_meta["output_slices"]
    self.vision_output_shape = vision_meta["output_shapes"]["outputs"]
    self.vision_input_names = list(self.vision_input_shapes.keys())  # e.g. ['img', 'big_img']

    self.policy_input_shapes = policy_meta["input_shapes"]
    self.policy_output_slices = policy_meta["output_slices"]
    self.policy_output_shape = policy_meta["output_shapes"]["outputs"]
    self.policy_input_names = list(self.policy_input_shapes.keys())
    # Output sizes (flat)
    self.vision_output_size = int(np.prod(self.vision_output_shape))
    self.policy_output_size = int(np.prod(self.policy_output_shape))

    # Vision RKNN
    self._vision_rknn = RKNNLite(verbose=False)
    self._vision_rknn.load_rknn(str(vision_rknn_path))
    self._vision_rknn.init_runtime()
    n_vision_in = len(self.vision_input_names)
    self._vision_pass_through = [0] * n_vision_in
    self._vision_data_format = ["nchw"] * n_vision_in

    # Policy RKNN
    self._policy_rknn = RKNNLite(verbose=False)
    self._policy_rknn.load_rknn(str(policy_rknn_path))
    self._policy_rknn.init_runtime()
    n_policy_in = len(self.policy_input_names)
    self._policy_pass_through = [0] * n_policy_in
    self._policy_data_format = ["nchw"] * n_policy_in

  def run_vision(self, img: np.ndarray, big_img: np.ndarray) -> np.ndarray:
    """Run vision model. img and big_img are uint8; cast to float16 and run. Returns float32 (1, 1576)."""
    img_fp16 = _to_fp16(img.reshape(self.vision_input_shapes["img"]))
    big_img_fp16 = _to_fp16(big_img.reshape(self.vision_input_shapes["big_img"]))
    inputs = [img_fp16, big_img_fp16]
    outputs = self._vision_rknn.inference(
      inputs=inputs,
      data_type="float16",
      inputs_pass_through=self._vision_pass_through,
      data_format=self._vision_data_format,
    )
    assert len(outputs) == 1
    out = outputs[0]
    if out.dtype != np.float32:
      out = out.astype(np.float32)
    return out.reshape(self.vision_output_shape)

  def run_policy(
    self,
    desire_pulse: np.ndarray,
    traffic_convention: np.ndarray,
    features_buffer: np.ndarray,
  ) -> np.ndarray:
    """Run policy model. All inputs cast to float16. Returns float32 (1, 1000)."""
    dp = _to_fp16(desire_pulse.reshape(self.policy_input_shapes["desire_pulse"]))
    tc = _to_fp16(traffic_convention.reshape(self.policy_input_shapes["traffic_convention"]))
    fb = _to_fp16(features_buffer.reshape(self.policy_input_shapes["features_buffer"]))
    inputs = [dp, tc, fb]
    outputs = self._policy_rknn.inference(
      inputs=inputs,
      data_type="float16",
      inputs_pass_through=self._policy_pass_through,
      data_format=self._policy_data_format,
    )
    assert len(outputs) == 1
    out = outputs[0]
    if out.dtype != np.float32:
      out = out.astype(np.float32)
    return out.reshape(self.policy_output_shape)
