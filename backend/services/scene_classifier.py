"""Gameplay Scene Understanding and Frame Classification Service (Phase 38C).

Classifies video frames into 12 distinct scene categories to ensure replay footage,
pause menus, and goal celebrations never pollute active match metrics.
Detects camera cuts and triggers tracking state reconciliation.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.domain.video_ingestion import SceneClass, SceneClassificationResult


class SceneClassifier:
    """Classifies video frames and detects cuts using pixel heuristics, color histograms, and HUD presence."""

    def __init__(self, cut_distance_threshold: float = 0.65):
        self.cut_distance_threshold = cut_distance_threshold
        self._prev_histogram: Optional[np.ndarray] = None

    def compute_color_histogram(self, rgb_array: np.ndarray, bins: int = 16) -> np.ndarray:
        """Computes a normalized 3D RGB color histogram (stride-subsampled for realtime speed)."""
        if rgb_array.ndim != 3 or rgb_array.shape[2] != 3:
            raise ValueError("Expected 3D RGB array with shape (H, W, 3)")
        
        sampled = rgb_array[::4, ::4, :] if (rgb_array.shape[0] >= 32 and rgb_array.shape[1] >= 32) else rgb_array
        pixels = sampled.reshape(-1, 3)
        hist, _ = np.histogramdd(pixels, bins=(bins, bins, bins), range=((0, 256), (0, 256), (0, 256)))
        hist = hist.astype(np.float32)
        total = hist.sum()
        if total > 0:
            hist /= total
        return hist.flatten()

    def compute_bhattacharyya_distance(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Measures statistical distance between two color histograms. Returns [0.0, 1.0]."""
        # Bhattacharyya coefficient
        bc = np.sum(np.sqrt(np.clip(hist1 * hist2, 0.0, 1.0)))
        # Distance: sqrt(1 - BC)
        return float(np.sqrt(max(0.0, 1.0 - bc)))

    def calculate_pitch_pixel_coverage(self, rgb_array: np.ndarray) -> float:
        """Estimates the fraction of pixels displaying football pitch grass.
        
        Green grass criteria in RGB space:
        - G > R + 15
        - G > B + 15
        - G in [45, 220] (not too dark shadow, not pure white)
        """
        sampled = rgb_array[::2, ::2, :] if (rgb_array.shape[0] >= 16 and rgb_array.shape[1] >= 16) else rgb_array
        r = sampled[:, :, 0].astype(np.int16)
        g = sampled[:, :, 1].astype(np.int16)
        b = sampled[:, :, 2].astype(np.int16)

        is_green = (g > r + 15) & (g > b + 15) & (g >= 45) & (g <= 220)
        return float(np.mean(is_green))

    def detect_hud_presence(self, rgb_array: np.ndarray) -> Tuple[bool, bool]:
        """Detects presence of top-left scoreboard HUD and bottom-center minimap.
        
        Returns (scoreboard_visible, minimap_visible).
        """
        h, w, _ = rgb_array.shape

        # 1. Top-left scoreboard region: [y: 0 to 0.12*h, x: 0 to 0.25*w]
        top_left = rgb_array[0 : int(0.12 * h), 0 : int(0.25 * w)]
        # Scoreboard has high contrast dark banner with bright white text
        tl_gray = np.mean(top_left, axis=2)
        has_dark_banner = np.mean(tl_gray < 50) > 0.10
        has_bright_text = np.mean(tl_gray > 200) > 0.008
        scoreboard_visible = bool(has_dark_banner and has_bright_text)

        # 2. Bottom-center minimap region: [y: 0.85*h to 0.98*h, x: 0.40*w to 0.60*w]
        bottom_center = rgb_array[int(0.85 * h) : int(0.98 * h), int(0.40 * w) : int(0.60 * w)]
        bc_gray = np.mean(bottom_center, axis=2)
        # Minimap outline has circular/oval contrast with distinct edge variance
        minimap_std = float(np.std(bc_gray))
        minimap_visible = bool(minimap_std > 15.0)

        return scoreboard_visible, minimap_visible

    def detect_menu_characteristics(
        self, rgb_array: np.ndarray, pitch_coverage: float = 0.0
    ) -> Optional[SceneClass]:
        """Checks for pause menu or tactical team management screen."""
        h, w, _ = rgb_array.shape
        # Menu screens have dark background and large rectangular card structures
        gray = np.mean(rgb_array, axis=2)
        overall_darkness = np.mean(gray < 40)
        center_region = gray[int(0.2 * h) : int(0.8 * h), int(0.2 * w) : int(0.8 * w)]
        center_std = float(np.std(center_region))

        # Tactical menu has multiple high-contrast cards and squad layout
        if overall_darkness > 0.40:
            if center_std > 50.0:
                return SceneClass.TACTICAL_MENU
            return SceneClass.PAUSE_MENU

        # Loading screen is almost completely uniform and lacks grass pitch coverage
        if pitch_coverage < 0.15 and center_std < 8.0:
            return SceneClass.LOADING_SCREEN

        return None

    def classify_frame(
        self,
        rgb_array: np.ndarray,
        video_id: str = "vid_eval",
        frame_index: int = 0,
        timestamp_sec: float = 0.0,
    ) -> SceneClassificationResult:
        """Classifies a single frame into one of 12 distinct scene categories."""
        # 1. Compute histogram and check for camera cut
        hist = self.compute_color_histogram(rgb_array)
        is_camera_cut = False
        if self._prev_histogram is not None:
            dist = self.compute_bhattacharyya_distance(self._prev_histogram, hist)
            if dist > self.cut_distance_threshold:
                is_camera_cut = True
        self._prev_histogram = hist

        # 2. Pitch grass pixel coverage
        pitch_coverage = self.calculate_pitch_pixel_coverage(rgb_array)

        # 3. HUD and minimap detection
        scoreboard_visible, minimap_visible = self.detect_hud_presence(rgb_array)

        # 4. Check for menu states first (passing pitch_coverage)
        menu_scene = self.detect_menu_characteristics(rgb_array, pitch_coverage=pitch_coverage)
        if menu_scene:
            return SceneClassificationResult(
                video_id=video_id,
                frame_index=frame_index,
                timestamp_sec=timestamp_sec,
                scene_class=menu_scene,
                confidence=0.92,
                is_camera_cut=is_camera_cut,
                pitch_pixel_coverage=pitch_coverage,
                hud_visible=scoreboard_visible,
                minimap_visible=minimap_visible,
            )

        # 5. Active gameplay vs replay evaluation
        if pitch_coverage >= 0.35:
            if scoreboard_visible and minimap_visible:
                return SceneClassificationResult(
                    video_id=video_id,
                    frame_index=frame_index,
                    timestamp_sec=timestamp_sec,
                    scene_class=SceneClass.ACTIVE_GAMEPLAY,
                    confidence=0.95,
                    is_camera_cut=is_camera_cut,
                    pitch_pixel_coverage=pitch_coverage,
                    hud_visible=True,
                    minimap_visible=True,
                )
            elif not scoreboard_visible and not minimap_visible:
                # High pitch grass but no HUD indicates goal replay or broadcast cutaway
                return SceneClassificationResult(
                    video_id=video_id,
                    frame_index=frame_index,
                    timestamp_sec=timestamp_sec,
                    scene_class=SceneClass.GOAL_REPLAY,
                    confidence=0.88,
                    is_camera_cut=is_camera_cut,
                    pitch_pixel_coverage=pitch_coverage,
                    hud_visible=False,
                    minimap_visible=False,
                )
            else:
                # Partial HUD visible - e.g. set piece preparation or cinematic replay
                return SceneClassificationResult(
                    video_id=video_id,
                    frame_index=frame_index,
                    timestamp_sec=timestamp_sec,
                    scene_class=SceneClass.SET_PIECE,
                    confidence=0.80,
                    is_camera_cut=is_camera_cut,
                    pitch_pixel_coverage=pitch_coverage,
                    hud_visible=scoreboard_visible,
                    minimap_visible=minimap_visible,
                )

        # 6. Low pitch coverage (< 35%)
        if pitch_coverage < 0.15:
            # Very low pitch coverage - close up celebration or crowd/stadium cutaway
            return SceneClassificationResult(
                video_id=video_id,
                frame_index=frame_index,
                timestamp_sec=timestamp_sec,
                scene_class=SceneClass.CELEBRATION,
                confidence=0.85,
                is_camera_cut=is_camera_cut,
                pitch_pixel_coverage=pitch_coverage,
                hud_visible=scoreboard_visible,
                minimap_visible=minimap_visible,
            )

        return SceneClassificationResult(
            video_id=video_id,
            frame_index=frame_index,
            timestamp_sec=timestamp_sec,
            scene_class=SceneClass.UNKNOWN,
            confidence=0.50,
            is_camera_cut=is_camera_cut,
            pitch_pixel_coverage=pitch_coverage,
            hud_visible=scoreboard_visible,
            minimap_visible=minimap_visible,
        )

    def reset(self) -> None:
        """Resets temporal tracking state."""
        self._prev_histogram = None
