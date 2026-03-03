# Cython wrapper for DrivingRKNNModel (C++ RKNN driving runner)
# Use when USE_RKNN=1; inputs are cast to float16 in C++.

# distutils: language = c++
# cython: c_string_encoding=ascii

import numpy as np
cimport numpy as np
from libcpp.string cimport string

from .driving_rknnmodel cimport DrivingRKNNModel

cdef class DrivingRKNNRunnerCpp:
    """Runs driving vision + policy via C++ RKNN. Inputs converted to float16 in C++."""
    cdef DrivingRKNNModel* _model
    cdef float[:] _vision_out
    cdef float[:] _policy_out

    def __cinit__(self, str vision_path, str policy_path):
        # Allocate output buffers (vision 1576, policy 1000)
        cdef float[::1] v_out = np.zeros(1576, dtype=np.float32)
        cdef float[::1] p_out = np.zeros(1000, dtype=np.float32)
        self._vision_out = v_out
        self._policy_out = p_out
        self._model = new DrivingRKNNModel(
            vision_path.encode('utf-8'),
            policy_path.encode('utf-8'),
            &v_out[0],
            &p_out[0],
        )

    def __dealloc__(self):
        if self._model is not NULL:
            del self._model
            self._model = NULL

    def run_vision(self, np.ndarray img, np.ndarray big_img):
        """img, big_img: uint8 numpy arrays (1,12,128,256) or flat."""
        cdef unsigned char[::1] img_flat = np.ascontiguousarray(img).reshape(-1).astype(np.uint8)
        cdef unsigned char[::1] big_flat = np.ascontiguousarray(big_img).reshape(-1).astype(np.uint8)
        self._model.run_vision(&img_flat[0], &big_flat[0])
        return np.asarray(self._vision_out).copy()

    def run_policy(self, np.ndarray desire_pulse, np.ndarray traffic_convention, np.ndarray features_buffer):
        """All float32 numpy arrays."""
        cdef float[::1] dp = np.ascontiguousarray(desire_pulse, dtype=np.float32).reshape(-1)
        cdef float[::1] tc = np.ascontiguousarray(traffic_convention, dtype=np.float32).reshape(-1)
        cdef float[::1] fb = np.ascontiguousarray(features_buffer, dtype=np.float32).reshape(-1)
        self._model.run_policy(&dp[0], &tc[0], &fb[0])
        return np.asarray(self._policy_out).copy()

    def get_vision_run_us(self):
        return self._model.get_vision_run_us()

    def get_policy_run_us(self):
        return self._model.get_policy_run_us()
