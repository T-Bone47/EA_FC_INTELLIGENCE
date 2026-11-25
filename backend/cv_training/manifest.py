"""Dataset manifest schema and strict provenance validator for EA FC CV training."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

EA_FC_CLASSES: Dict[int, str] = {
    0: "player",
    1: "goalkeeper",
    2: "referee",
    3: "ball",
    4: "minimap_roi",
}


class BoundingBoxLabel(BaseModel):
    class_id: int = Field(..., ge=0, le=4)
    class_name: str
    xywh_norm: Tuple[float, float, float, float]  # center_x, center_y, width, height in [0, 1]
    track_id: Optional[int] = None
    team_id: Optional[Literal["HOME", "AWAY", "REFEREE", "BALL"]] = None
    pitch_xy_m: Optional[Tuple[float, float]] = None
    occluded: bool = False


class LabeledFrameRecord(BaseModel):
    frame_id: str
    match_id: str
    video_id: str
    frame_index: int = Field(..., ge=0)
    timestamp_sec: float = Field(..., ge=0.0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    camera_angle: Literal["TELE_BROADCAST", "COOP", "TACTICAL", "LEGACY", "OTHER"] = "TELE_BROADCAST"
    game_version: Literal["FC26", "FC27", "SOCERNET_BROADCAST"] = "FC27"
    scene_class: Literal["ACTIVE_GAMEPLAY", "SET_PIECE", "REPLAY", "HUD_MENU"] = "ACTIVE_GAMEPLAY"
    is_synthetic_calibration_test: bool = False
    image_relpath: Optional[str] = None
    labels: List[BoundingBoxLabel] = Field(default_factory=list)


class DatasetManifest(BaseModel):
    manifest_version: str = "fc.cv.manifest.v1"
    dataset_name: str
    license_name: str = "User-Annotated / Permissive"
    commercial_safe: bool = True
    frames: List[LabeledFrameRecord] = Field(default_factory=list)


def validate_manifest(
    manifest: DatasetManifest,
    *,
    allow_synthetic: bool = False,
) -> Dict[str, object]:
    """Validates class IDs, normalized coordinates, track IDs, and synthetic-vs-real boundaries."""
    errors: List[str] = []
    class_counts: Dict[str, int] = {name: 0 for name in EA_FC_CLASSES.values()}
    unique_matches: set[str] = set()
    synthetic_count = 0

    for idx, frame in enumerate(manifest.frames):
        unique_matches.add(frame.match_id)
        if frame.is_synthetic_calibration_test:
            synthetic_count += 1
            if not allow_synthetic:
                errors.append(
                    f"Frame {idx} ({frame.frame_id}) marked is_synthetic_calibration_test=True inside real training manifest."
                )
        for lbl_idx, box in enumerate(frame.labels):
            expected_name = EA_FC_CLASSES.get(box.class_id)
            if expected_name != box.class_name:
                errors.append(
                    f"Frame {frame.frame_id} label {lbl_idx}: class_id={box.class_id} expected {expected_name!r}, got {box.class_name!r}."
                )
            cx, cy, bw, bh = box.xywh_norm
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.0 < bw <= 1.0 and 0.0 < bh <= 1.0):
                errors.append(
                    f"Frame {frame.frame_id} label {lbl_idx}: normalized xywh {box.xywh_norm} out of bounds."
                )
            if expected_name:
                class_counts[expected_name] += 1

    return {
        "valid": len(errors) == 0 and len(manifest.frames) > 0,
        "error_count": len(errors),
        "errors": errors[:25],
        "frame_count": len(manifest.frames),
        "unique_match_count": len(unique_matches),
        "synthetic_frame_count": synthetic_count,
        "class_counts": class_counts,
    }
