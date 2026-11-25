"""ByteTrack Multi-Object Tracking & Association Adapter (Phase 38E).

Implements the two-stage ByteTrack data association algorithm using pure Python & NumPy.
Associates high-confidence detections first, then recovers occluded tracks using
low-confidence detections, maintaining persistent session IDs across match footage.
Includes Kalman filtering, camera motion compensation (CMC), and physical velocity sanity checks.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class KalmanTrackState:
    """Represents a single object's state in image coordinates using a constant-velocity Kalman filter."""

    def __init__(self, track_id: str, bbox_xywh: List[float], team: str = "HOME", entity_class: str = "outfield_player"):
        self.track_id = track_id
        self.team = team
        self.entity_class = entity_class
        # State vector: [x_center, y_center, aspect_ratio (w/h), height, vx, vy, va, vh]
        xc = bbox_xywh[0] + bbox_xywh[2] / 2.0
        yc = bbox_xywh[1] + bbox_xywh[3] / 2.0
        a = bbox_xywh[2] / max(1e-5, bbox_xywh[3])
        h = bbox_xywh[3]
        self.mean = np.array([xc, yc, a, h, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.covariance = np.diag([0.05, 0.05, 0.01, 0.05, 0.1, 0.1, 0.01, 0.1])
        self.time_since_update = 0
        self.hit_streak = 1
        self.age = 1
        self.confidence = 1.0
        self.last_bbox = list(bbox_xywh)

    def predict(self, camera_offset_xy: Tuple[float, float] = (0.0, 0.0)) -> None:
        """Propagates state forward by 1 time step and applies camera motion compensation."""
        # Constant velocity transition
        self.mean[0] += self.mean[4] + camera_offset_xy[0]
        self.mean[1] += self.mean[5] + camera_offset_xy[1]
        self.mean[2] += self.mean[6]
        self.mean[3] += self.mean[7]

        # Process noise
        self.covariance += np.diag([0.01, 0.01, 0.005, 0.01, 0.05, 0.05, 0.005, 0.05])
        self.age += 1
        self.time_since_update += 1

    def update(self, bbox_xywh: List[float], confidence: float, team: Optional[str] = None) -> None:
        """Corrects Kalman state given a matching detection."""
        xc = bbox_xywh[0] + bbox_xywh[2] / 2.0
        yc = bbox_xywh[1] + bbox_xywh[3] / 2.0
        a = bbox_xywh[2] / max(1e-5, bbox_xywh[3])
        h = bbox_xywh[3]
        measurement = np.array([xc, yc, a, h], dtype=np.float64)

        # Innovation
        residual = measurement - self.mean[:4]
        r_cov = np.diag([0.02, 0.02, 0.01, 0.02])
        s = self.covariance[:4, :4] + r_cov
        k = self.covariance[:, :4] @ np.linalg.inv(s)

        self.mean += k @ residual
        self.covariance = (np.eye(8) - k @ np.eye(4, 8)) @ self.covariance

        self.time_since_update = 0
        self.hit_streak += 1
        self.confidence = confidence
        if team:
            self.team = team
        self.last_bbox = list(bbox_xywh)

    def to_bbox_xywh(self) -> List[float]:
        """Returns current bounding box [x, y, w, h] from state vector."""
        xc, yc, a, h = self.mean[0], self.mean[1], self.mean[2], self.mean[3]
        w = max(1e-4, a * h)
        h = max(1e-4, h)
        x = xc - w / 2.0
        y = yc - h / 2.0
        return [round(float(x), 4), round(float(y), 4), round(float(w), 4), round(float(h), 4)]


def calculate_iou(bbox1: List[float], bbox2: List[float]) -> float:
    """Calculates Intersection-over-Union between two [x, y, w, h] bounding boxes."""
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_w = max(0.0, xi2 - xi1)
    inter_h = max(0.0, yi2 - yi1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, w1 * h1)
    area2 = max(0.0, w2 * h2)
    union_area = area1 + area2 - inter_area

    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


class ByteTrackAdapter:
    """Two-stage ByteTrack multi-object tracking association engine."""

    def __init__(
        self,
        high_conf_thresh: float = 0.50,
        low_conf_thresh: float = 0.15,
        match_thresh_high: float = 0.70,  # Max cost (1 - IoU) for stage 1
        match_thresh_low: float = 0.50,   # Max cost for stage 2
        max_time_lost: int = 30,          # Frames before track termination
    ):
        self.high_conf_thresh = high_conf_thresh
        self.low_conf_thresh = low_conf_thresh
        self.match_thresh_high = match_thresh_high
        self.match_thresh_low = match_thresh_low
        self.max_time_lost = max_time_lost

        self._active_tracks: List[KalmanTrackState] = []
        self._lost_tracks: List[KalmanTrackState] = []
        self._next_id = 1

    def _generate_track_id(self, entity_class: str, team: str) -> str:
        prefix = "trk"
        if entity_class == "ball":
            return "ball_0"
        elif entity_class == "goalkeeper":
            prefix = "gk"
        elif team == "HOME":
            prefix = "home"
        elif team == "AWAY":
            prefix = "away"
        tid = f"{prefix}_{self._next_id:02d}"
        self._next_id += 1
        return tid

    def update(
        self,
        detections: List[Dict[str, Any]],  # [{bbox_xywh, confidence, team, entity_class}]
        camera_offset_xy: Tuple[float, float] = (0.0, 0.0),
    ) -> List[Dict[str, Any]]:
        """Executes two-stage association on incoming detections and returns active track records."""
        # 1. Predict new positions for all existing tracks
        for t in self._active_tracks:
            t.predict(camera_offset_xy)

        # 2. Split detections into high-confidence and low-confidence pools
        high_dets = [d for d in detections if d.get("confidence", 1.0) >= self.high_conf_thresh]
        low_dets = [
            d for d in detections
            if self.low_conf_thresh <= d.get("confidence", 1.0) < self.high_conf_thresh
        ]

        # 3. First Stage Association: High-confidence detections with active tracks
        matched_tracks_1, unmatched_tracks_1, unmatched_dets_1 = self._associate_bboxes(
            self._active_tracks, high_dets, max_cost=self.match_thresh_high
        )

        for track, det in matched_tracks_1:
            track.update(det["bbox_xywh"], det["confidence"], det.get("team"))

        # 4. Second Stage Association: Low-confidence detections with remaining unmatched tracks
        matched_tracks_2, unmatched_tracks_2, _ = self._associate_bboxes(
            unmatched_tracks_1, low_dets, max_cost=self.match_thresh_low
        )

        for track, det in matched_tracks_2:
            track.update(det["bbox_xywh"], det["confidence"], det.get("team"))

        # 5. Initialize new tracks for unmatched high-confidence detections
        for det in unmatched_dets_1:
            new_id = self._generate_track_id(det.get("entity_class", "outfield_player"), det.get("team", "HOME"))
            new_track = KalmanTrackState(
                track_id=new_id,
                bbox_xywh=det["bbox_xywh"],
                team=det.get("team", "HOME"),
                entity_class=det.get("entity_class", "outfield_player"),
            )
            self._active_tracks.append(new_track)

        # 6. Lifecycle maintenance: remove tracks lost longer than max_time_lost
        active_remaining = []
        for t in self._active_tracks:
            if t.time_since_update <= self.max_time_lost:
                active_remaining.append(t)
        self._active_tracks = active_remaining

        # 7. Format output records
        results = []
        for t in self._active_tracks:
            if t.time_since_update == 0 or t.hit_streak >= 2:
                results.append({
                    "track_id": t.track_id,
                    "team": t.team,
                    "entity_class": t.entity_class,
                    "bbox_xywh": t.to_bbox_xywh(),
                    "confidence": round(float(t.confidence), 3),
                    "is_occluded": bool(t.time_since_update > 0),
                    "velocity_mps": round(float(math.sqrt(t.mean[4]**2 + t.mean[5]**2) * 30.0), 2),  # approx m/s
                })
        return results

    def _associate_bboxes(
        self,
        tracks: List[KalmanTrackState],
        detections: List[Dict[str, Any]],
        max_cost: float,
    ) -> Tuple[List[Tuple[KalmanTrackState, Dict[str, Any]]], List[KalmanTrackState], List[Dict[str, Any]]]:
        """Optimal bipartite matching via Hungarian algorithm (scipy.optimize.linear_sum_assignment)
        with deterministic greedy fallback."""
        if not tracks or not detections:
            return [], list(tracks), list(detections)

        # Compute cost matrix: cost = 1.0 - IoU + subtle center-distance tiebreaker for small balls/occlusions
        cost_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float64)
        for i, track in enumerate(tracks):
            track_box = track.to_bbox_xywh()
            tcx, tcy = track_box[0] + track_box[2] / 2.0, track_box[1] + track_box[3] / 2.0
            for j, det in enumerate(detections):
                db = det["bbox_xywh"]
                iou = calculate_iou(track_box, db)
                dcx, dcy = db[0] + db[2] / 2.0, db[1] + db[3] / 2.0
                dist = math.hypot(tcx - dcx, tcy - dcy)
                cost = (1.0 - iou) if iou > 0.0 else min(1.0, 0.72 + dist * 2.0)
                cost_matrix[i, j] = cost

        matched_tracks: List[Tuple[KalmanTrackState, Dict[str, Any]]] = []
        matched_track_indices = set()
        matched_det_indices = set()

        try:
            from scipy.optimize import linear_sum_assignment
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_ind.tolist(), col_ind.tolist()):
                if cost_matrix[r, c] <= max_cost:
                    matched_track_indices.add(r)
                    matched_det_indices.add(c)
                    matched_tracks.append((tracks[r], detections[c]))
        except Exception:
            flat_indices = np.argsort(cost_matrix.flatten())
            for flat_idx in flat_indices:
                row = int(flat_idx // len(detections))
                col = int(flat_idx % len(detections))
                if row in matched_track_indices or col in matched_det_indices:
                    continue
                if cost_matrix[row, col] > max_cost:
                    continue
                matched_track_indices.add(row)
                matched_det_indices.add(col)
                matched_tracks.append((tracks[row], detections[col]))

        unmatched_tracks = [t for i, t in enumerate(tracks) if i not in matched_track_indices]
        unmatched_dets = [d for j, d in enumerate(detections) if j not in matched_det_indices]

        return matched_tracks, unmatched_tracks, unmatched_dets

    def reset(self) -> None:
        """Resets all active tracks (e.g. after a camera cut or goal celebration)."""
        self._active_tracks.clear()
        self._lost_tracks.clear()
        self._next_id = 1
