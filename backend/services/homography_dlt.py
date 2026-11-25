"""Direct Linear Transformation (DLT) & RANSAC Pitch Homography Service (Phase 38F).

Computes planar projective transformations from screen pixel coordinates (u, v)
to canonical metric pitch coordinates (X, Y) in [0, 105]m x [0, 68]m.
Implements pure NumPy DLT with SVD decomposition, RANSAC inlier filtering,
ground-contact point projection, and confidence state gates.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.domain.video_ingestion import HomographyResult, PitchCalibrationState, PitchLandmark


class PitchHomographyEstimator:
    """Estimates homography matrix H mapping image pixels to metric pitch space."""

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        inlier_threshold_m: float = 2.5,
        ransac_iterations: int = 500,
    ):
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self.inlier_threshold_m = inlier_threshold_m
        self.ransac_iterations = ransac_iterations

    def compute_dlt_homography(
        self,
        src_points: np.ndarray,  # Shape (N, 2) in image pixels (u, v)
        dst_points: np.ndarray,  # Shape (N, 2) in pitch meters (X, Y)
    ) -> Optional[np.ndarray]:
        """Computes 3x3 homography matrix using Direct Linear Transformation (DLT) via SVD.
        
        Requires N >= 4 point correspondences.
        """
        n = src_points.shape[0]
        if n < 4:
            return None

        # Construct 2N x 9 matrix A
        a = np.zeros((2 * n, 9), dtype=np.float64)
        for i in range(n):
            u, v = src_points[i, 0], src_points[i, 1]
            x, y = dst_points[i, 0], dst_points[i, 1]

            a[2 * i] = [-u, -v, -1.0, 0.0, 0.0, 0.0, u * x, v * x, x]
            a[2 * i + 1] = [0.0, 0.0, 0.0, -u, -v, -1.0, u * y, v * y, y]

        # Solve via SVD: Ah = 0
        try:
            _, _, vh = np.linalg.svd(a)
            h = vh[-1].reshape((3, 3))
            if abs(h[2, 2]) > 1e-8:
                h = h / h[2, 2]
            return h
        except np.linalg.LinAlgError:
            return None

    def estimate_homography_ransac(
        self,
        src_points: np.ndarray,
        dst_points: np.ndarray,
        random_seed: int = 42,
    ) -> HomographyResult:
        """Estimates robust homography using RANSAC inlier maximization."""
        n = src_points.shape[0]
        if n < 4:
            return HomographyResult(
                matrix_3x3=[],
                inliers_count=0,
                reprojection_error_m=999.0,
                state=PitchCalibrationState.REJECTED,
            )

        rng = np.random.RandomState(random_seed)
        best_h: Optional[np.ndarray] = None
        best_inliers: List[int] = []
        best_error: float = float("inf")

        for _ in range(self.ransac_iterations):
            # Sample 4 random points
            idx = rng.choice(n, 4, replace=False)
            h_candidate = self.compute_dlt_homography(src_points[idx], dst_points[idx])
            if h_candidate is None:
                continue

            # Project all points
            proj = self.project_points(h_candidate, src_points)
            if proj is None:
                continue

            # Calculate Euclidean distance in meters
            errors = np.linalg.norm(proj - dst_points, axis=1)
            inliers = np.where(errors <= self.inlier_threshold_m)[0].tolist()

            if len(inliers) > len(best_inliers):
                best_inliers = inliers
                best_h = h_candidate
                best_error = float(np.mean(errors[inliers])) if inliers else float("inf")
                if len(best_inliers) == n and best_error < 0.25:
                    break

        # Refine homography over all inliers
        if len(best_inliers) >= 4 and best_h is not None:
            refined_h = self.compute_dlt_homography(src_points[best_inliers], dst_points[best_inliers])
            if refined_h is not None:
                proj = self.project_points(refined_h, src_points[best_inliers])
                if proj is not None:
                    final_error = float(np.mean(np.linalg.norm(proj - dst_points[best_inliers], axis=1)))
                    best_h = refined_h
                    best_error = round(final_error, 2)

        if best_h is None or len(best_inliers) < 4:
            return HomographyResult(
                matrix_3x3=[],
                inliers_count=len(best_inliers),
                reprojection_error_m=round(best_error, 2),
                state=PitchCalibrationState.REJECTED,
            )

        # Classify state
        if best_error < 2.0 and len(best_inliers) >= 6:
            state = PitchCalibrationState.GOOD
        elif best_error <= 4.0:
            state = PitchCalibrationState.COARSE
        else:
            state = PitchCalibrationState.REJECTED

        return HomographyResult(
            matrix_3x3=[[round(float(v), 6) for v in row] for row in best_h],
            inliers_count=len(best_inliers),
            reprojection_error_m=round(best_error, 2),
            state=state,
        )

    def project_points(self, h_matrix: np.ndarray, points: np.ndarray) -> Optional[np.ndarray]:
        """Projects image points (N, 2) to pitch points (N, 2) using homography H."""
        n = points.shape[0]
        if n == 0:
            return np.empty((0, 2), dtype=np.float64)

        # Convert to homogeneous coordinates (3, N)
        homogeneous = np.vstack([points.T, np.ones(n)])
        projected = h_matrix @ homogeneous

        # Check for division by zero / negative scale
        scales = projected[2, :]
        if np.any(np.abs(scales) < 1e-8):
            return None

        x = projected[0, :] / scales
        y = projected[1, :] / scales
        return np.column_stack([x, y])

    def project_ground_contact(
        self,
        h_matrix: List[List[float]],
        bbox_xywh_norm: List[float],
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
    ) -> Tuple[Optional[float], Optional[float], PitchCalibrationState]:
        """Projects player bounding box bottom-center (ground contact) to pitch metric coordinates.
        
        Returns (pitch_x_meters, pitch_y_meters, calibration_state).
        """
        if not h_matrix or len(h_matrix) != 3:
            return None, None, PitchCalibrationState.REJECTED

        h_arr = np.array(h_matrix, dtype=np.float64)
        x_norm, y_norm, w_norm, h_norm = bbox_xywh_norm[0], bbox_xywh_norm[1], bbox_xywh_norm[2], bbox_xywh_norm[3]

        # Ground contact: bottom-center of bounding box
        contact_u = (x_norm + w_norm / 2.0) * frame_width
        contact_v = (y_norm + h_norm) * frame_height

        point = np.array([[contact_u, contact_v]], dtype=np.float64)
        proj = self.project_points(h_arr, point)
        if proj is None:
            return None, None, PitchCalibrationState.REJECTED

        px, py = float(proj[0, 0]), float(proj[0, 1])

        # Bounds validation
        if -5.0 <= px <= self.pitch_length + 5.0 and -5.0 <= py <= self.pitch_width + 5.0:
            clamped_x = max(0.0, min(self.pitch_length, px))
            clamped_y = max(0.0, min(self.pitch_width, py))
            return round(clamped_x, 2), round(clamped_y, 2), PitchCalibrationState.GOOD

        return None, None, PitchCalibrationState.REJECTED

    def calibrate_manual_points(
        self,
        correspondences: List[PitchLandmark],
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
    ) -> HomographyResult:
        """Computes explicit DLT + RANSAC homography from user-pinned manual landmarks."""
        if len(correspondences) < 4:
            return HomographyResult(
                matrix_3x3=[],
                inliers_count=0,
                reprojection_error_m=999.0,
                state=PitchCalibrationState.REJECTED,
            )
        src_pts = np.array([
            [c.pixel_xy[0] * frame_width if c.pixel_xy[0] <= 1.0 else c.pixel_xy[0],
             c.pixel_xy[1] * frame_height if c.pixel_xy[1] <= 1.0 else c.pixel_xy[1]]
            for c in correspondences
        ], dtype=np.float64)
        dst_pts = np.array([
            [c.pitch_xy_meters[0], c.pitch_xy_meters[1]] for c in correspondences
        ], dtype=np.float64)
        return self.estimate_homography_ransac(src_pts, dst_pts)

    def calibrate_from_frame(self, rgb_array: np.ndarray) -> Tuple[HomographyResult, List[PitchLandmark]]:
        """Extracts white pitch lines inside the green turf mask using OpenCV HoughLinesP,
        computes line intersections, and runs RANSAC DLT calibration.
        Returns REJECTED cleanly if too few non-collinear field lines are visible."""
        try:
            import cv2
        except ImportError:
            return HomographyResult(state=PitchCalibrationState.REJECTED, reprojection_error_m=999.0), []

        h, w, _ = rgb_array.shape
        hsv = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)

        # Turf mask + white field line extraction
        turf = cv2.inRange(hsv, np.array([28, 35, 35]), np.array([90, 255, 255]))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        turf_region = cv2.morphologyEx(turf, cv2.MORPH_CLOSE, kernel)

        white_lines = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 75, 255]))
        masked_lines = cv2.bitwise_and(white_lines, turf_region)
        edges = cv2.Canny(masked_lines, 50, 150)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180.0,
            threshold=max(40, int(w * 0.04)),
            minLineLength=max(45, int(w * 0.07)),
            maxLineGap=25,
        )
        if lines is None or len(lines) < 3:
            return HomographyResult(
                matrix_3x3=[], inliers_count=0, reprojection_error_m=999.0, state=PitchCalibrationState.REJECTED
            ), []

        horiz_lines = []
        vert_lines = []
        for l in np.asarray(lines).reshape(-1, 4):
            x1, y1, x2, y2 = float(l[0]), float(l[1]), float(l[2]), float(l[3])
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length < 1e-3:
                continue
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle <= 14.0 or angle >= 166.0:
                horiz_lines.append((x1, y1, x2, y2, (y1 + y2) / 2.0))
            elif 35.0 <= angle <= 145.0:
                vert_lines.append((x1, y1, x2, y2, (x1 + x2) / 2.0))

        # Need >= 2 distinct horizontal touchlines/box horizontals AND >= 2 vertical/angled pitch lines
        if len(horiz_lines) < 2 or len(vert_lines) < 2:
            return HomographyResult(
                matrix_3x3=[], inliers_count=0, reprojection_error_m=999.0, state=PitchCalibrationState.REJECTED
            ), []

        # Pick top-most & bottom-most horizontals + left-most & right-most verticals to anchor trapezoid
        horiz_lines.sort(key=lambda item: item[4])
        top_h = horiz_lines[0][:4]
        bot_h = horiz_lines[-1][:4]
        if abs(horiz_lines[-1][4] - horiz_lines[0][4]) < h * 0.18:
            return HomographyResult(
                matrix_3x3=[], inliers_count=0, reprojection_error_m=999.0, state=PitchCalibrationState.REJECTED
            ), []

        vert_lines.sort(key=lambda item: item[4])
        # Exclude duplicate clusters closer than 12% frame width
        distinct_verts = [vert_lines[0]]
        for v in vert_lines[1:]:
            if abs(v[4] - distinct_verts[-1][4]) >= w * 0.12:
                distinct_verts.append(v)

        if len(distinct_verts) < 2:
            return HomographyResult(
                matrix_3x3=[], inliers_count=0, reprojection_error_m=999.0, state=PitchCalibrationState.REJECTED
            ), []

        def _intersect(l1: Tuple[float, float, float, float], l2: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
            x1, y1, x2, y2 = l1
            x3, y3, x4, y4 = l2
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(denom) < 1e-5:
                return None
            px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
            py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
            if -0.25 * w <= px <= 1.25 * w and -0.25 * h <= py <= 1.25 * h:
                return px, py
            return None

        src_pts = []
        dst_pts = []
        landmarks: List[PitchLandmark] = []
        selected_verts = [distinct_verts[0][:4], distinct_verts[-1][:4]]
        if len(distinct_verts) >= 3:
            mid_idx = len(distinct_verts) // 2
            selected_verts = [distinct_verts[0][:4], distinct_verts[mid_idx][:4], distinct_verts[-1][:4]]
            pitch_xs = [16.5, 52.5, 88.5]
        else:
            # Map left/right vertical frustum lines proportionally into visible pitch span
            u_left = distinct_verts[0][4] / max(1.0, float(w))
            u_right = distinct_verts[-1][4] / max(1.0, float(w))
            pitch_xs = [round(u_left * self.pitch_length, 1), round(u_right * self.pitch_length, 1)]

        for x_world, v_line in zip(pitch_xs, selected_verts):
            for tag, y_world, h_line in [("FAR", self.pitch_width, top_h), ("NEAR", 0.0, bot_h)]:
                pt = _intersect(h_line, v_line)
                if pt is not None:
                    src_pts.append([pt[0], pt[1]])
                    dst_pts.append([x_world, y_world])
                    landmarks.append(PitchLandmark(
                        name=f"{tag}_X{x_world}",
                        pixel_xy=(round(pt[0], 1), round(pt[1], 1)),
                        pitch_xy_meters=(x_world, y_world),
                        confidence=0.78 if len(selected_verts) >= 3 else 0.62,
                    ))

        if len(src_pts) < 4:
            return HomographyResult(
                matrix_3x3=[], inliers_count=0, reprojection_error_m=999.0, state=PitchCalibrationState.REJECTED
            ), []

        res = self.estimate_homography_ransac(np.array(src_pts, dtype=np.float64), np.array(dst_pts, dtype=np.float64))
        # Two-line frustum heuristic without full penalty-arc anchor caps at COARSE unless >= 6 landmarks
        if len(src_pts) < 6 and res.state == PitchCalibrationState.GOOD:
            res.state = PitchCalibrationState.COARSE
        return res, landmarks

    def estimate_camera_motion_lk(
        self,
        prev_rgb: np.ndarray,
        curr_rgb: np.ndarray,
    ) -> Tuple[float, float]:
        """Estimates normalized frame-to-frame camera pan (dx_norm, dy_norm) via Lucas-Kanade optical flow."""
        try:
            import cv2
        except ImportError:
            return 0.0, 0.0

        h, w, _ = curr_rgb.shape
        # Subsample 480p for fast (<2ms) background pan computation
        scale_w, scale_h = 480, max(240, int(h * (480 / max(1, w))))
        prev_g = cv2.cvtColor(cv2.resize(prev_rgb, (scale_w, scale_h)), cv2.COLOR_RGB2GRAY)
        curr_g = cv2.cvtColor(cv2.resize(curr_rgb, (scale_w, scale_h)), cv2.COLOR_RGB2GRAY)

        pts = cv2.goodFeaturesToTrack(prev_g, maxCorners=80, qualityLevel=0.02, minDistance=18)
        if pts is None or len(pts) < 8:
            return 0.0, 0.0

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_g, curr_g, pts, None, winSize=(15, 15), maxLevel=2)
        if next_pts is None or status is None:
            return 0.0, 0.0

        mask = status.reshape(-1) == 1
        good_old = pts.reshape(-1, 2)[mask]
        good_new = next_pts.reshape(-1, 2)[mask]
        if len(good_old) < 4:
            return 0.0, 0.0

        deltas = good_new - good_old
        dx_norm = float(np.median(deltas[:, 0])) / float(scale_w)
        dy_norm = float(np.median(deltas[:, 1])) / float(scale_h)
        return round(dx_norm, 5), round(dy_norm, 5)
