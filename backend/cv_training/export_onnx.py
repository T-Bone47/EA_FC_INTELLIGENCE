"""ONNX Verification & Deployment Helper for EA FC Gameplay Detector.

Validates ONNX detector graphs against OpenCV DNN (OpenCL GPU / CPU) without overwriting
production weight paths with untrained placeholder weights.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def inspect_onnx_detector_compatibility(onnx_path: Optional[Path] = None) -> Dict[str, Any]:
    """Checks whether `backend/models/fc_detector.onnx` exists and passes OpenCV DNN load + forward pass."""
    target = onnx_path or (Path(__file__).resolve().parents[1] / "models" / "fc_detector.onnx")
    meta_path = target.with_suffix(".meta.json")
    metadata: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

    if not target.exists():
        return {
            "weights_present": False,
            "onnx_path": str(target),
            "status": "NO_TRAINED_WEIGHTS_PRESENT",
            "active_runtime_fallback": "CV_CLASSICAL_HSV_CONTOUR",
            "metadata": metadata,
        }

    try:
        import cv2
        t0 = time.perf_counter()
        net = cv2.dnn.readNetFromONNX(str(target))
        target_dev = "CPU"
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            if cv2.ocl.useOpenCL():
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
                target_dev = "OPENCL_GPU"
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        blob = cv2.dnn.blobFromImage(dummy, scalefactor=1.0 / 255.0, size=(640, 640), swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "weights_present": True,
            "onnx_path": str(target),
            "status": "VERIFIED_OPENCV_DNN",
            "target_device": target_dev,
            "output_shape": list(out.shape) if hasattr(out, "shape") else None,
            "smoke_latency_ms": round(elapsed_ms, 2),
            "metadata": metadata,
        }
    except Exception as exc:
        return {
            "weights_present": True,
            "onnx_path": str(target),
            "status": "ONNX_LOAD_FAILED",
            "error": str(exc),
            "metadata": metadata,
        }
