"""Leakage-free match-level dataset splitting for EA FC CV training and validation."""
from __future__ import annotations

import hashlib
from typing import Dict, List, Set, Tuple
from pydantic import BaseModel, Field

from backend.cv_training.manifest import LabeledFrameRecord


class MatchSplitResult(BaseModel):
    seed: int = 42
    train_matches: List[str] = Field(default_factory=list)
    val_matches: List[str] = Field(default_factory=list)
    test_matches: List[str] = Field(default_factory=list)
    train_frames: List[LabeledFrameRecord] = Field(default_factory=list)
    val_frames: List[LabeledFrameRecord] = Field(default_factory=list)
    test_frames: List[LabeledFrameRecord] = Field(default_factory=list)
    leakage_free_verified: bool = True
    camera_coverage: Dict[str, int] = Field(default_factory=dict)


def split_by_match_group(
    frames: List[LabeledFrameRecord],
    *,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> MatchSplitResult:
    """Splits labeled frames strictly at the `match_id` boundary to eliminate temporal leakage.

    Adjacent frames from the same broadcast clip always share grass lighting, kit colors,
    camera tilt, and crowd background. Frame-level random splits inflate mAP artificially
    and are prohibited here.
    """
    if not frames:
        return MatchSplitResult(seed=seed, leakage_free_verified=True)

    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-4:
        raise ValueError(f"Split ratios must sum to 1.0 (got {total_ratio:.4f}).")

    by_match: Dict[str, List[LabeledFrameRecord]] = {}
    cam_counts: Dict[str, int] = {}
    for fr in frames:
        by_match.setdefault(fr.match_id, []).append(fr)
        cam_counts[fr.camera_angle] = cam_counts.get(fr.camera_angle, 0) + 1

    # Deterministic seeded hash sort of match IDs
    def _sort_key(mid: str) -> Tuple[str, str]:
        digest = hashlib.sha256(f"{seed}:{mid}".encode("utf-8")).hexdigest()
        return digest, mid

    match_ids = sorted(by_match.keys(), key=_sort_key)
    n = len(match_ids)

    if n == 1:
        train_ids = match_ids
        val_ids: List[str] = []
        test_ids: List[str] = []
    elif n == 2:
        train_ids = [match_ids[0]]
        val_ids = [match_ids[1]]
        test_ids = []
    else:
        n_train = max(1, min(n - 2, round(n * train_ratio)))
        n_val = max(1, min(n - n_train - 1, round(n * val_ratio)))
        train_ids = match_ids[:n_train]
        val_ids = match_ids[n_train : n_train + n_val]
        test_ids = match_ids[n_train + n_val :]

    train_set: Set[str] = set(train_ids)
    val_set: Set[str] = set(val_ids)
    test_set: Set[str] = set(test_ids)
    if not (train_set.isdisjoint(val_set) and train_set.isdisjoint(test_set) and val_set.isdisjoint(test_set)):
        raise AssertionError("Match-level split overlap detected.")

    train_frames = [f for m in train_ids for f in sorted(by_match[m], key=lambda x: x.frame_index)]
    val_frames = [f for m in val_ids for f in sorted(by_match[m], key=lambda x: x.frame_index)]
    test_frames = [f for m in test_ids for f in sorted(by_match[m], key=lambda x: x.frame_index)]

    return MatchSplitResult(
        seed=seed,
        train_matches=train_ids,
        val_matches=val_ids,
        test_matches=test_ids,
        train_frames=train_frames,
        val_frames=val_frames,
        test_frames=test_frames,
        leakage_free_verified=True,
        camera_coverage=cam_counts,
    )
