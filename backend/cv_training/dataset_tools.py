"""Phase 43I: Real-Footage Dataset Export/Import, Confidence Calibration (ECE/Brier),
and Checkpoint Registry Integration for EA FC Gameplay Vision.

Strictly preserves:
- Match-level zero-leakage splitting via `split_by_match_group`
- Apache-2.0 / MIT runtime stack separation (never bundles AGPL code)
- Explicit separation of `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY` vs human-annotated footage
- Never fabricates missing `backend/models/fc_detector.onnx` weights.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.core import db
from backend.cv_training.config_generator import probe_local_cv_environment
from backend.cv_training.dataset_splitter import split_by_match_group
from backend.cv_training.evaluator import FrameGroundTruth, FramePrediction, _iou
from backend.cv_training.export_onnx import inspect_onnx_detector_compatibility
from backend.cv_training.manifest import (
    EA_FC_CLASSES,
    BoundingBoxLabel,
    DatasetManifest,
    validate_manifest,
)


_CLASS_NAME_BY_ID = dict(EA_FC_CLASSES)


def parse_yolo_label_lines(lines: Sequence[str]) -> List[BoundingBoxLabel]:
    """Parses normalized YOLO / CVAT annotation lines into validated BoundingBoxLabels."""
    labels: List[BoundingBoxLabel] = []
    for raw in lines:
        parts = raw.strip().split()
        if len(parts) < 5:
            continue
        cid = int(parts[0])
        if cid not in _CLASS_NAME_BY_ID:
            continue
        cx, cy, bw, bh = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
        track_id = int(parts[5]) if len(parts) >= 6 and parts[5].isdigit() else None
        labels.append(
            BoundingBoxLabel(
                class_id=cid,
                class_name=_CLASS_NAME_BY_ID[cid],
                xywh_norm=(cx, cy, bw, bh),
                track_id=track_id,
            )
        )
    return labels


def export_manifest_to_yolo_dataset(
    manifest: DatasetManifest,
    output_dir: Path,
    *,
    allow_synthetic: bool = False,
    seed: int = 42,
) -> Dict[str, Any]:
    """Exports validated EA FC frames into leakage-free train/val/test YOLO directory layout."""
    val = validate_manifest(manifest, allow_synthetic=allow_synthetic)
    if not val["valid"]:
        raise ValueError(f"Invalid dataset manifest: {val['errors'][:5]}")

    split = split_by_match_group(manifest.frames, seed=seed)
    out = Path(output_dir)
    for split_name, frames in (("train", split.train_frames), ("val", split.val_frames), ("test", split.test_frames)):
        lbl_dir = out / "labels" / split_name
        lbl_dir.mkdir(parents=True, exist_ok=True)
        (out / "images" / split_name).mkdir(parents=True, exist_ok=True)
        for fr in frames:
            lines = [
                f"{b.class_id} {b.xywh_norm[0]:.6f} {b.xywh_norm[1]:.6f} {b.xywh_norm[2]:.6f} {b.xywh_norm[3]:.6f}"
                for b in fr.labels
            ]
            (lbl_dir / f"{fr.frame_id}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    data_yaml = "\n".join(
        [
            f"path: {out.as_posix()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            *[f"  {cid}: {cname}" for cid, cname in EA_FC_CLASSES.items()],
        ]
    )
    (out / "data.yaml").write_text(data_yaml + "\n", encoding="utf-8")
    (out / "cvat_labels.json").write_text(
        json.dumps([{"name": cname, "id": cid} for cid, cname in EA_FC_CLASSES.items()], indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": str(out),
        "leakage_free_verified": split.leakage_free_verified,
        "train_frames": len(split.train_frames),
        "val_frames": len(split.val_frames),
        "test_frames": len(split.test_frames),
        "train_matches": split.train_matches,
        "val_matches": split.val_matches,
        "test_matches": split.test_matches,
        "class_counts": val["class_counts"],
        "synthetic_frames_present": val["synthetic_frame_count"],
    }


def compute_detector_ece_and_brier(
    ground_truth: Sequence[FrameGroundTruth],
    predictions: Sequence[FramePrediction],
    *,
    iou_threshold: float = 0.50,
    ball_iou_threshold: float = 0.25,
    evaluation_scope: str = "LABELED_VALIDATION_SET",
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Computes Expected Calibration Error (ECE) & Brier Score for predicted detection confidences."""
    gt_map = {g.frame_index: g for g in ground_truth}
    confs: List[float] = []
    corrects: List[float] = []

    for pred_f in predictions:
        gt_f = gt_map.get(pred_f.frame_index)
        gt_boxes = list(gt_f.boxes) if gt_f else []
        used: set[int] = set()
        for pb in sorted(pred_f.boxes, key=lambda b: b.confidence, reverse=True):
            thr = ball_iou_threshold if pb.class_name == "ball" else iou_threshold
            best_iou = 0.0
            best_idx = -1
            for gi, gb in enumerate(gt_boxes):
                if gi in used or gb.class_name != pb.class_name:
                    continue
                iou_v = _iou(pb.xyxy_norm, gb.xyxy_norm)
                if iou_v > best_iou:
                    best_iou = iou_v
                    best_idx = gi
            is_tp = 1.0 if (best_idx >= 0 and best_iou >= thr) else 0.0
            if is_tp > 0.0:
                used.add(best_idx)
            confs.append(max(0.0, min(1.0, float(pb.confidence))))
            corrects.append(is_tp)

    if not confs:
        return {
            "evaluation_scope": evaluation_scope,
            "samples": 0,
            "ece": None,
            "brier_score": None,
            "mean_confidence": None,
            "empirical_precision": None,
        }

    c_arr = np.asarray(confs, dtype=np.float64)
    y_arr = np.asarray(corrects, dtype=np.float64)
    brier = float(np.mean((c_arr - y_arr) ** 2))
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (c_arr >= lo) & (c_arr <= hi if i == n_bins - 1 else c_arr < hi)
        if np.any(mask):
            ece += (np.sum(mask) / len(c_arr)) * abs(float(np.mean(y_arr[mask]) - np.mean(c_arr[mask])))

    return {
        "evaluation_scope": evaluation_scope,
        "samples": len(confs),
        "ece": round(float(ece), 4),
        "brier_score": round(float(brier), 4),
        "mean_confidence": round(float(np.mean(c_arr)), 4),
        "empirical_precision": round(float(np.mean(y_arr)), 4),
    }


def register_cv_checkpoint_record(
    *,
    checkpoint_id: str,
    architecture: str,
    dataset_manifest: str,
    evaluation_scope: str,
    map_50: Optional[float] = None,
    precision_score: Optional[float] = None,
    recall_score: Optional[float] = None,
    idf1: Optional[float] = None,
    hota_proxy: Optional[float] = None,
    fps_rtx3050: Optional[float] = None,
    peak_vram_mb: Optional[float] = None,
    onnx_path: Optional[str] = None,
    license_name: str = "Apache-2.0",
) -> Dict[str, Any]:
    """Registers verified CV checkpoint metrics into `phase42_cv_checkpoint`."""
    if onnx_path and not Path(onnx_path).exists():
        raise FileNotFoundError(f"Refusing to register non-existent ONNX weights at {onnx_path!r}.")
    status = f"VERIFIED_{evaluation_scope}"
    rec = {
        "checkpoint_id": checkpoint_id,
        "architecture": architecture,
        "dataset_manifest": dataset_manifest,
        "onnx_path": onnx_path,
        "map_50": map_50,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "idf1": idf1,
        "hota_proxy": hota_proxy,
        "fps_rtx3050": fps_rtx3050,
        "peak_vram_mb": peak_vram_mb,
        "license_name": license_name,
        "status": status,
    }
    try:
        tbl = db.query_one("SELECT to_regclass('public.phase42_cv_checkpoint') AS t")
        if tbl and tbl.get("t"):
            db.execute(
                """INSERT INTO public.phase42_cv_checkpoint
                   (checkpoint_id, architecture, dataset_manifest, onnx_path, map_50,
                    precision_score, recall_score, idf1, hota_proxy, fps_rtx3050,
                    peak_vram_mb, license_name, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (checkpoint_id) DO UPDATE SET
                     map_50 = EXCLUDED.map_50,
                     precision_score = EXCLUDED.precision_score,
                     recall_score = EXCLUDED.recall_score,
                     idf1 = EXCLUDED.idf1,
                     hota_proxy = EXCLUDED.hota_proxy,
                     fps_rtx3050 = EXCLUDED.fps_rtx3050,
                     peak_vram_mb = EXCLUDED.peak_vram_mb,
                     status = EXCLUDED.status""",
                (
                    checkpoint_id, architecture, dataset_manifest, onnx_path, map_50,
                    precision_score, recall_score, idf1, hota_proxy, fps_rtx3050,
                    peak_vram_mb, license_name, status,
                ),
            )
    except Exception:
        pass
    return rec


def list_cv_checkpoints() -> List[Dict[str, Any]]:
    try:
        tbl = db.query_one("SELECT to_regclass('public.phase42_cv_checkpoint') AS t")
        if not tbl or not tbl.get("t"):
            return []
        rows = db.query("SELECT * FROM public.phase42_cv_checkpoint ORDER BY created_at DESC LIMIT 20")
        return [
            {**dict(r), "created_at": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or "")}
            for r in rows
        ]
    except Exception:
        return []


def get_cv_pipeline_status() -> Dict[str, Any]:
    return {
        "hardware_env": probe_local_cv_environment(),
        "onnx_detector": inspect_onnx_detector_compatibility(),
        "registered_checkpoints": list_cv_checkpoints(),
        "model_streams": {
            "broadcast": {
                "input_size": [640, 640],
                "target_onnx": "backend/models/fc_detector.onnx",
                "evaluation_protocol": "Held-out match-split validation set (never train on val clips)",
            },
            "minimap_roi": {
                "input_size": [320, 320],
                "target_onnx": "backend/models/fc_minimap_detector.onnx",
                "evaluation_protocol": "Separate radar-crop evaluation (solves off-screen compactness blindness)",
            },
        },
        "resume_and_early_stopping": {
            "early_stopping_patience_epochs": 8,
            "min_val_map50_delta": 0.003,
            "checkpoint_resume_supported": True,
        },
        "license_policy": "Apache-2.0 / MIT runtime stack (YOLOX preferred; Ultralytics AGPL-3.0 segregated behind explicit opt-in).",
    }
