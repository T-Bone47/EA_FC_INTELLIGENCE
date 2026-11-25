"""Multi-Source Computer Vision Perception Service (Phase 38 -> Phase 39 Real Pixel Extraction).

Implements three cooperating perception channels:
- Channel 1: Broadcast gameplay perception (HSV turf subtraction, foreground contours,
             optional ONNX YOLOX DNN inference, KMeans jersey clustering, small-object ball ROI).
- Channel 2: Minimap intelligence (radar ROI contour segmentation, team dot clustering).
- Channel 3: HUD and contextual intelligence (conservative banner/clock inspection without
             hallucinating unparsed team names or scores).

Synthetic fixture generator (`SyntheticFixtureDetector` / `HeuristicPerceptionDetector`)
is strictly isolated and labeled so synthetic fixtures are never misclassified as genuine video.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple
import numpy as np

from backend.domain.video_ingestion import (
    DetectedEntity,
    HUDContext,
    MinimapObservation,
    ObservationStatus,
)

log = logging.getLogger("eafc.multi_channel_perception")

DEFAULT_ONNX_PATH = Path(__file__).resolve().parents[1] / "models" / "fc_detector.onnx"


class DetectorBackend(Protocol):
    """Abstract interface for perception backends (PixelCV, ONNX, or SyntheticFixture)."""

    backend_name: str

    def detect_frame(
        self,
        rgb_array: np.ndarray,
        frame_index: int,
        timestamp_sec: float,
    ) -> Tuple[List[DetectedEntity], Optional[DetectedEntity], List[MinimapObservation], HUDContext]:
        ...


class PixelPerceptionExtractor:
    """Real pixel-based multi-channel CV extractor for decoded EA FC / football broadcast frames.

    Supports optional YOLOX ONNX model at `backend/models/fc_detector.onnx` (via OpenCV DNN
    OpenCL/CPU) when present; otherwise uses classical HSV turf subtraction + morphological
    connected components + KMeans jersey clustering. Explicitly reports `backend_name`.
    """

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        onnx_model_path: Optional[Path] = None,
    ):
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self._prev_ball_pos: Optional[Tuple[float, float, float]] = None
        self._team_centroids_rgb: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._onnx_net = None
        self.backend_name = "CV_CLASSICAL_HSV_CONTOUR"

        model_candidate = onnx_model_path or DEFAULT_ONNX_PATH
        if model_candidate.exists():
            try:
                import cv2
                net = cv2.dnn.readNetFromONNX(str(model_candidate))
                if cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL():
                    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
                self._onnx_net = net
                self.backend_name = f"ONNX_DNN ({model_candidate.name})"
            except Exception as e:
                log.warning("Could not load ONNX weights at %s: %s; using HSV contour detector", model_candidate, e)

    def extract_minimap_icons(self, rgb_array: np.ndarray) -> List[MinimapObservation]:
        """Channel 2: Extracts player and ball blips from the lower-center radar minimap."""
        h, w, _ = rgb_array.shape
        ymin, ymax = int(0.82 * h), int(0.98 * h)
        xmin, xmax = int(0.38 * w), int(0.62 * w)
        minimap_crop = rgb_array[ymin:ymax, xmin:xmax]

        ch, cw, _ = minimap_crop.shape
        observations: List[MinimapObservation] = []
        if ch < 12 or cw < 12:
            return observations

        r_chan = minimap_crop[:, :, 0].astype(np.int16)
        g_chan = minimap_crop[:, :, 1].astype(np.int16)
        b_chan = minimap_crop[:, :, 2].astype(np.int16)

        team1_mask = (r_chan > g_chan + 35) & (r_chan > b_chan + 35) & (r_chan > 90)
        team2_mask = ((b_chan > r_chan + 30) & (b_chan > 90)) | ((r_chan > 210) & (g_chan > 210) & (b_chan > 210))
        ball_mask = (r_chan > 190) & (g_chan > 190) & (b_chan < 120)

        try:
            import cv2
            use_cv = True
        except ImportError:
            use_cv = False

        for mask, team_label in [(team1_mask, "HOME"), (team2_mask, "AWAY"), (ball_mask, "BALL")]:
            if use_cv:
                u8 = (mask.astype(np.uint8)) * 255
                num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(u8, connectivity=8)
                for lbl in range(1, num_labels):
                    area = int(stats[lbl, cv2.CC_STAT_AREA])
                    # Radar dots occupy roughly 2..90 pixels depending on 720p/1080p scale
                    if not (2 <= area <= max(120, int(cw * ch * 0.015))):
                        continue
                    cx, cy = float(centroids[lbl][0]), float(centroids[lbl][1])
                    norm_x = max(0.0, min(1.0, cx / float(cw)))
                    norm_y = max(0.0, min(1.0, cy / float(ch)))
                    observations.append(MinimapObservation(
                        norm_xy=(round(norm_x, 3), round(norm_y, 3)),
                        pitch_xy_meters=(
                            round(norm_x * self.pitch_length, 2),
                            round((1.0 - norm_y) * self.pitch_width, 2),
                        ),
                        team=team_label,
                        confidence=0.80 if team_label != "BALL" else 0.85,
                    ))
            else:
                y_indices, x_indices = np.where(mask)
                visited = set()
                for py, px in zip(y_indices, x_indices):
                    cell = (int(py) // 6, int(px) // 6)
                    if cell in visited:
                        continue
                    visited.add(cell)
                    norm_x = px / float(cw)
                    norm_y = py / float(ch)
                    observations.append(MinimapObservation(
                        norm_xy=(round(norm_x, 3), round(norm_y, 3)),
                        pitch_xy_meters=(
                            round(norm_x * self.pitch_length, 2),
                            round((1.0 - norm_y) * self.pitch_width, 2),
                        ),
                        team=team_label,
                        confidence=0.72,
                    ))
        return observations

    def extract_hud_context(self, rgb_array: np.ndarray, timestamp_sec: float) -> HUDContext:
        """Channel 3: Checks top-left scoreboard HUD contrast honestly without hallucinating team names."""
        h, w, _ = rgb_array.shape
        tl = rgb_array[0 : int(0.12 * h), 0 : int(0.28 * w)]
        tl_gray = np.mean(tl, axis=2) if tl.size > 0 else np.zeros((1, 1))
        has_banner = bool(np.mean(tl_gray < 65) > 0.08 and np.mean(tl_gray > 195) > 0.005)
        mins = int(timestamp_sec) // 60
        secs = int(timestamp_sec) % 60
        return HUDContext(
            match_clock=f"{mins:02d}:{secs:02d}" if has_banner else None,
            home_score=None,
            away_score=None,
            home_team_abbr=None,
            away_team_abbr=None,
            active_player_name=None,
            playstyle_active=None,
        )

    def _cluster_teams_kmeans(self, jersey_rgbs: List[np.ndarray]) -> List[str]:
        """Separates player candidates into stable HOME/AWAY team clusters using torso colors."""
        n = len(jersey_rgbs)
        if n == 0:
            return []
        if n < 2:
            return ["HOME"] * n

        arr = np.vstack(jersey_rgbs).astype(np.float64)
        if np.ptp(arr, axis=0).max() < 12.0:
            return ["HOME"] * n

        try:
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=2, n_init=4, random_state=42)
            labels = km.fit_predict(arr)
            centers = km.cluster_centers_
        except Exception:
            lum = np.mean(arr, axis=1)
            med = float(np.median(lum))
            labels = (lum >= med).astype(int)
            c0 = arr[labels == 0].mean(axis=0) if np.any(labels == 0) else np.array([180.0, 40.0, 40.0])
            c1 = arr[labels == 1].mean(axis=0) if np.any(labels == 1) else np.array([40.0, 80.0, 200.0])
            centers = np.vstack([c0, c1])

        # Maintain consistent cluster->HOME/AWAY identity across frames
        if self._team_centroids_rgb is None:
            # Anchor HOME to brighter red/warm or higher luminance cluster deterministically
            if centers[0].sum() >= centers[1].sum():
                self._team_centroids_rgb = (centers[0], centers[1])
                mapping = {0: "HOME", 1: "AWAY"}
            else:
                self._team_centroids_rgb = (centers[1], centers[0])
                mapping = {1: "HOME", 0: "AWAY"}
        else:
            prev_h, prev_a = self._team_centroids_rgb
            cost_direct = np.linalg.norm(centers[0] - prev_h) + np.linalg.norm(centers[1] - prev_a)
            cost_swap = np.linalg.norm(centers[1] - prev_h) + np.linalg.norm(centers[0] - prev_a)
            if cost_direct <= cost_swap:
                mapping = {0: "HOME", 1: "AWAY"}
                self._team_centroids_rgb = (0.7 * prev_h + 0.3 * centers[0], 0.7 * prev_a + 0.3 * centers[1])
            else:
                mapping = {1: "HOME", 0: "AWAY"}
                self._team_centroids_rgb = (0.7 * prev_h + 0.3 * centers[1], 0.7 * prev_a + 0.3 * centers[0])

        return [mapping[int(lbl)] for lbl in labels]

    def _detect_with_onnx(
        self,
        rgb_array: np.ndarray,
        timestamp_sec: float,
    ) -> Optional[Tuple[List[DetectedEntity], Optional[DetectedEntity]]]:
        """Runs OpenCV DNN YOLOX-compatible ONNX inference when trained weights are present."""
        if self._onnx_net is None:
            return None
        try:
            import cv2

            h, w, _ = rgb_array.shape
            blob = cv2.dnn.blobFromImage(
                rgb_array,
                scalefactor=1.0 / 255.0,
                size=(640, 640),
                swapRB=False,
                crop=False,
            )
            self._onnx_net.setInput(blob)
            outputs = self._onnx_net.forward()
            preds = outputs[0] if isinstance(outputs, (list, tuple)) else outputs
            if preds.ndim == 3:
                preds = preds[0]
            if preds.ndim != 2 or preds.shape[1] < 6:
                return None

            boxes_xyxy: List[List[int]] = []
            confs: List[float] = []
            cls_ids: List[int] = []
            for row in preds:
                obj_conf = float(row[4])
                if obj_conf < 0.25:
                    continue
                cls_scores = row[5:]
                cid = int(np.argmax(cls_scores))
                score = obj_conf * float(cls_scores[cid])
                if score < 0.30:
                    continue
                cx_n = float(row[0]) / 640.0
                cy_n = float(row[1]) / 640.0
                bw_n = float(row[2]) / 640.0
                bh_n = float(row[3]) / 640.0
                x1 = int(max(0.0, cx_n - bw_n / 2.0) * w)
                y1 = int(max(0.0, cy_n - bh_n / 2.0) * h)
                bw_px = max(2, int(bw_n * w))
                bh_px = max(2, int(bh_n * h))
                boxes_xyxy.append([x1, y1, bw_px, bh_px])
                confs.append(score)
                cls_ids.append(cid)

            if not boxes_xyxy:
                return [], None

            keep_idxs = cv2.dnn.NMSBoxes(boxes_xyxy, confs, 0.30, 0.45)
            flat_idxs = [int(i) for i in np.array(keep_idxs).flatten()] if len(keep_idxs) > 0 else []

            player_boxes: List[Tuple[int, int, int, int, float, int]] = []
            jersey_colors: List[np.ndarray] = []
            ball_candidates: List[Tuple[int, int, int, int, float]] = []

            for idx in flat_idxs:
                bx, by, bw, bh = boxes_xyxy[idx]
                conf = confs[idx]
                cid = cls_ids[idx]
                if cid == 3:
                    ball_candidates.append((bx, by, bw, bh, conf))
                elif cid in (0, 1):
                    ty1 = min(h - 1, by + int(0.20 * bh))
                    ty2 = min(h, max(ty1 + 1, by + int(0.55 * bh)))
                    tx1 = min(w - 1, bx + int(0.15 * bw))
                    tx2 = min(w, max(tx1 + 1, bx + int(0.85 * bw)))
                    torso = np.median(rgb_array[ty1:ty2, tx1:tx2].reshape(-1, 3), axis=0)
                    player_boxes.append((bx, by, bw, bh, conf, cid))
                    jersey_colors.append(torso)

            teams = self._cluster_teams_kmeans(jersey_colors)
            players: List[DetectedEntity] = []
            for (bx, by, bw, bh, conf, cid), team in zip(player_boxes[:28], teams[:28]):
                players.append(
                    DetectedEntity(
                        entity_class="goalkeeper" if cid == 1 else "outfield_player",
                        team=team,
                        bbox_xywh=[round(bx / w, 4), round(by / h, 4), round(bw / w, 4), round(bh / h, 4)],
                        confidence=round(float(conf), 3),
                        observation_status=ObservationStatus.OBSERVED,
                    )
                )

            ball_entity: Optional[DetectedEntity] = None
            if ball_candidates:
                bx, by, bw, bh, conf = max(ball_candidates, key=lambda b: b[4])
                self._prev_ball_pos = ((bx + bw / 2.0) / w, (by + bh / 2.0) / h, timestamp_sec)
                ball_entity = DetectedEntity(
                    entity_class="ball",
                    team="BALL",
                    bbox_xywh=[round(bx / w, 4), round(by / h, 4), round(bw / w, 4), round(bh / h, 4)],
                    confidence=round(min(0.99, float(conf)), 3),
                    observation_status=ObservationStatus.OBSERVED,
                )
            return players, ball_entity
        except Exception as exc:
            log.warning("ONNX inference failed (%s); falling back to HSV contour detector", exc)
            return None

    def detect_broadcast_players_and_ball(
        self,
        rgb_array: np.ndarray,
        frame_index: int,
        timestamp_sec: float,
    ) -> Tuple[List[DetectedEntity], Optional[DetectedEntity]]:
        """Channel 1: Runs ONNX DNN if weights exist, else segments foreground players and ball on pitch turf."""
        onnx_out = self._detect_with_onnx(rgb_array, timestamp_sec)
        if onnx_out is not None:
            return onnx_out
        try:
            import cv2
        except ImportError as e:
            raise RuntimeError(f"OpenCV required for real pixel extraction: {e}") from e

        h, w, _ = rgb_array.shape
        hsv = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)

        # 1. Green turf segmentation
        turf = cv2.inRange(hsv, np.array([28, 35, 35]), np.array([92, 255, 255]))
        pitch_cov = float(np.mean(turf > 0))
        if pitch_cov < 0.15:
            return [], None

        close_k = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
        pitch_closed = cv2.morphologyEx(turf, cv2.MORPH_CLOSE, close_k)
        # Fill internal player/ball/line cutouts completely enclosed within the outer turf contour
        pitch_contours, _ = cv2.findContours(pitch_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pitch_region = np.zeros_like(turf)
        if pitch_contours:
            cv2.drawContours(pitch_region, pitch_contours, -1, 255, thickness=cv2.FILLED)
        else:
            pitch_region = pitch_closed

        # Foreground objects enclosed on turf (exclude bright pitch lines by vertical silhouette check later)
        fg_mask = cv2.bitwise_and(cv2.bitwise_not(turf), pitch_region)
        # Exclude HUD overlay regions (top-left scoreboard & bottom-center minimap)
        fg_mask[0 : int(0.13 * h), 0 : int(0.32 * w)] = 0
        fg_mask[int(0.81 * h) : h, int(0.35 * w) : int(0.65 * w)] = 0

        open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 5))
        fg_clean = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, open_k)

        contours, _ = cv2.findContours(fg_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        player_boxes: List[Tuple[int, int, int, int, float]] = []
        jersey_colors: List[np.ndarray] = []
        ball_candidates: List[Tuple[float, float, int, int, float]] = []

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw <= 2 or bh <= 2:
                continue
            area = cv2.contourArea(cnt)
            h_norm = bh / float(h)
            w_norm = bw / float(w)
            aspect = bw / float(bh)

            # Outfield player silhouette criteria in broadcast camera
            if 0.025 <= h_norm <= 0.24 and 0.008 <= w_norm <= 0.12 and 0.16 <= aspect <= 1.20:
                if area < max(20.0, bw * bh * 0.20):
                    continue
                # Sample torso pixels (20%..55% height) excluding remaining grass
                ty1 = by + int(0.20 * bh)
                ty2 = by + int(0.55 * bh)
                tx1 = bx + int(0.15 * bw)
                tx2 = bx + int(0.85 * bw)
                patch_rgb = rgb_array[ty1:ty2, tx1:tx2]
                patch_fg = fg_clean[ty1:ty2, tx1:tx2] > 0
                if np.any(patch_fg):
                    torso_rgb = np.median(patch_rgb[patch_fg], axis=0)
                else:
                    torso_rgb = np.median(patch_rgb.reshape(-1, 3), axis=0)
                fill_ratio = min(1.0, area / float(bw * bh))
                player_boxes.append((bx, by, bw, bh, 0.65 + 0.30 * fill_ratio))
                jersey_colors.append(torso_rgb)

            # Small bright round ball blob inside field
            elif 4 <= bw <= int(0.025 * w) and 4 <= bh <= int(0.032 * h) and 0.55 <= aspect <= 1.85:
                patch = rgb_array[by : by + bh, bx : bx + bw]
                mean_lum = float(np.mean(patch))
                if mean_lum >= 185.0:
                    cx = (bx + bw / 2.0) / float(w)
                    cy = (by + bh / 2.0) / float(h)
                    ball_candidates.append((cx, cy, bw, bh, mean_lum / 255.0))

        # Assign HOME/AWAY via KMeans jersey color clustering
        team_labels = self._cluster_teams_kmeans(jersey_colors)
        players: List[DetectedEntity] = []
        for (bx, by, bw, bh, conf), team in zip(player_boxes[:28], team_labels[:28]):
            players.append(DetectedEntity(
                entity_class="outfield_player",
                team=team,
                bbox_xywh=[
                    round(bx / float(w), 4),
                    round(by / float(h), 4),
                    round(bw / float(w), 4),
                    round(bh / float(h), 4),
                ],
                confidence=round(float(conf), 3),
                observation_status=ObservationStatus.OBSERVED,
            ))

        # Pick best physically plausible ball candidate
        ball_entity: Optional[DetectedEntity] = None
        if ball_candidates:
            ball_candidates.sort(key=lambda c: c[4], reverse=True)
            for cx, cy, bw, bh, score in ball_candidates:
                valid_vel = True
                if self._prev_ball_pos is not None:
                    px, py, pt = self._prev_ball_pos
                    dt = max(1e-3, timestamp_sec - pt)
                    dist_m = math.hypot((cx - px) * self.pitch_length, (cy - py) * self.pitch_width)
                    if (dist_m / dt) > 45.0:
                        valid_vel = False
                if valid_vel:
                    self._prev_ball_pos = (cx, cy, timestamp_sec)
                    ball_entity = DetectedEntity(
                        entity_class="ball",
                        team="BALL",
                        bbox_xywh=[
                            round(cx - (bw / (2.0 * w)), 4),
                            round(cy - (bh / (2.0 * h)), 4),
                            round(bw / float(w), 4),
                            round(bh / float(h), 4),
                        ],
                        confidence=round(min(0.95, score), 3),
                        observation_status=ObservationStatus.OBSERVED,
                    )
                    break

        return players, ball_entity

    def detect_frame(
        self,
        rgb_array: np.ndarray,
        frame_index: int,
        timestamp_sec: float,
    ) -> Tuple[List[DetectedEntity], Optional[DetectedEntity], List[MinimapObservation], HUDContext]:
        players, ball = self.detect_broadcast_players_and_ball(rgb_array, frame_index, timestamp_sec)
        minimap_obs = self.extract_minimap_icons(rgb_array)
        hud_ctx = self.extract_hud_context(rgb_array, timestamp_sec)
        return players, ball, minimap_obs, hud_ctx


class SyntheticFixtureDetector:
    """Explicit synthetic fixture detector ONLY for unit tests / un-decoded UI previews.
    Never sets ObservationStatus.OBSERVED when generating sine/cos player grids; uses
    ObservationStatus.INFERRED so synthetic points stay strictly separated from observed data.
    """

    backend_name = "SYNTHETIC_FIXTURE_GENERATOR"

    def __init__(self, pitch_length_m: float = 105.0, pitch_width_m: float = 68.0):
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self._pixel_helper = PixelPerceptionExtractor(pitch_length_m, pitch_width_m)

    def extract_minimap_icons(self, rgb_array: np.ndarray) -> List[MinimapObservation]:
        return self._pixel_helper.extract_minimap_icons(rgb_array)

    def extract_hud_context(self, rgb_array: np.ndarray, timestamp_sec: float) -> HUDContext:
        total_game_seconds = int(timestamp_sec * 6.5)
        return HUDContext(
            match_clock=f"{min(90, total_game_seconds // 60):02d}:{total_game_seconds % 60:02d}",
            home_score=None,
            away_score=None,
            home_team_abbr="SYNTH_H",
            away_team_abbr="SYNTH_A",
            active_player_name=None,
            playstyle_active=None,
        )

    def detect_broadcast_players_and_ball(
        self,
        rgb_array: np.ndarray,
        frame_index: int,
        timestamp_sec: float,
    ) -> Tuple[List[DetectedEntity], Optional[DetectedEntity]]:
        players: List[DetectedEntity] = []
        for i in range(20):
            col = i % 5
            row = i // 5
            x_norm = 0.15 + col * 0.16 + (0.02 * math.sin(frame_index * 0.1 + i))
            y_norm = 0.25 + row * 0.13 + (0.01 * math.cos(frame_index * 0.08 + i))
            team = "HOME" if (col % 2 == 0) else "AWAY"
            entity_class = "goalkeeper" if i in (0, 19) else "outfield_player"
            if i == 0:
                team = "HOME"
            elif i == 19:
                team = "AWAY"
            players.append(DetectedEntity(
                entity_class=entity_class,
                team=team,
                bbox_xywh=[round(x_norm, 4), round(y_norm, 4), 0.035, 0.085],
                confidence=0.92,
                observation_status=ObservationStatus.INFERRED,
            ))

        ball = DetectedEntity(
            entity_class="ball",
            team="BALL",
            bbox_xywh=[0.465, 0.57, 0.012, 0.016],
            confidence=0.88,
            observation_status=ObservationStatus.INFERRED,
        )
        return players, ball

    def detect_frame(
        self,
        rgb_array: np.ndarray,
        frame_index: int,
        timestamp_sec: float,
    ) -> Tuple[List[DetectedEntity], Optional[DetectedEntity], List[MinimapObservation], HUDContext]:
        players, ball = self.detect_broadcast_players_and_ball(rgb_array, frame_index, timestamp_sec)
        minimap_obs = self.extract_minimap_icons(rgb_array)
        hud_ctx = self.extract_hud_context(rgb_array, timestamp_sec)
        return players, ball, minimap_obs, hud_ctx


# Backward-compatible alias preserved strictly for legacy fixture unit tests
HeuristicPerceptionDetector = SyntheticFixtureDetector
