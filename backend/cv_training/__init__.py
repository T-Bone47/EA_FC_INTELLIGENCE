"""Phase 42F Domain Computer Vision Training, Evaluation, and ONNX Export Harness.

Provides dataset manifest validation, match-level leakage-free splitting,
commercial-safe (YOLOX Apache-2.0) vs opt-in (Ultralytics AGPL-3.0) config generation,
Hungarian matching & HOTA/IDF1/AP50/localization evaluation, ONNX export/verification,
and local hardware + PyAV/OpenCL/ONNX DNN benchmarking without fabricating missing weights.
"""
from __future__ import annotations

from backend.cv_training.config_generator import (
    TrainingRecipeSpec,
    build_training_recipe,
    probe_local_cv_environment,
)
from backend.cv_training.dataset_splitter import MatchSplitResult, split_by_match_group
from backend.cv_training.evaluator import (
    CVEvaluationReport,
    FrameGroundTruth,
    FramePrediction,
    evaluate_detection_and_tracking,
)
from backend.cv_training.manifest import (
    EA_FC_CLASSES,
    BoundingBoxLabel,
    DatasetManifest,
    LabeledFrameRecord,
    validate_manifest,
)

__all__ = [
    "BoundingBoxLabel",
    "CVEvaluationReport",
    "DatasetManifest",
    "EA_FC_CLASSES",
    "FrameGroundTruth",
    "FramePrediction",
    "LabeledFrameRecord",
    "MatchSplitResult",
    "TrainingRecipeSpec",
    "build_training_recipe",
    "evaluate_detection_and_tracking",
    "probe_local_cv_environment",
    "split_by_match_group",
    "validate_manifest",
]
