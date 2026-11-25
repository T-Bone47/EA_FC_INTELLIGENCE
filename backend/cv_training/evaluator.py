"""Detection, Small-Object Ball Recall, Tracking (IDF1/HOTA/IDSW), and Localization Evaluator."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import linear_sum_assignment


class BoxItem(BaseModel):
    class_name: str
    xyxy_norm: Tuple[float, float, float, float]
    confidence: float = 1.0
    track_id: Optional[str] = None
    pitch_xy_m: Optional[Tuple[float, float]] = None


class FrameGroundTruth(BaseModel):
    frame_index: int
    boxes: List[BoxItem] = Field(default_factory=list)


class FramePrediction(BaseModel):
    frame_index: int
    boxes: List[BoxItem] = Field(default_factory=list)


class ClassMetricSummary(BaseModel):
    class_name: str
    gt_count: int
    pred_count: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    ap50: float


class CVEvaluationReport(BaseModel):
    evaluation_scope: str
    frames_evaluated: int
    macro_precision: float
    macro_recall: float
    map50: float
    ball_recall: float
    ball_ap50: float
    player_ap50: float
    mota: float
    idf1: float
    hota: float
    id_switches: int
    pitch_localization_rmse_m: Optional[float] = None
    pitch_localization_median_m: Optional[float] = None
    per_class: List[ClassMetricSummary] = Field(default_factory=list)


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = max(1e-9, area_a + area_b - inter)
    return inter / union


def _voc_ap(rec: np.ndarray, prec: np.ndarray) -> float:
    if rec.size == 0:
        return 0.0
    mrec = np.concatenate(([0.0], rec, [1.0]))
    mpre = np.concatenate(([0.0], prec, [0.0]))
    for i in range(mpre.size - 1, 0, -1):
        mpre[i - 1] = np.maximum(mpre[i - 1], mpre[i])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def evaluate_detection_and_tracking(
    ground_truth: Sequence[FrameGroundTruth],
    predictions: Sequence[FramePrediction],
    *,
    iou_threshold: float = 0.50,
    ball_iou_threshold: float = 0.25,
    evaluation_scope: str = "LABELED_VALIDATION_SET",
) -> CVEvaluationReport:
    """Computes class-level AP50/precision/recall, separate ball metrics, IDF1, IDSW, HOTA, and pitch RMSE."""
    gt_by_frame = {g.frame_index: g for g in ground_truth}
    pred_by_frame = {p.frame_index: p for p in predictions}
    all_frames = sorted(set(gt_by_frame.keys()) | set(pred_by_frame.keys()))

    classes = sorted({b.class_name for g in ground_truth for b in g.boxes} | {b.class_name for p in predictions for b in p.boxes})
    if not classes:
        return CVEvaluationReport(
            evaluation_scope=evaluation_scope,
            frames_evaluated=len(all_frames),
            macro_precision=0.0,
            macro_recall=0.0,
            map50=0.0,
            ball_recall=0.0,
            ball_ap50=0.0,
            player_ap50=0.0,
            mota=0.0,
            idf1=0.0,
            hota=0.0,
            id_switches=0,
        )

    per_class_scores: Dict[str, List[Tuple[float, int]]] = {c: [] for c in classes}
    per_class_counts: Dict[str, Dict[str, int]] = {
        c: {"gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0} for c in classes
    }

    # Tracking bookkeeping
    total_gt_tracks = 0
    total_pred_tracks = 0
    id_pair_matches: Dict[Tuple[str, str], int] = {}
    last_gt_to_pred: Dict[str, str] = {}
    id_switches = 0
    det_tp_all = 0
    det_fp_all = 0
    det_fn_all = 0
    pitch_errors: List[float] = []

    for fidx in all_frames:
        g_boxes = gt_by_frame.get(fidx, FrameGroundTruth(frame_index=fidx)).boxes
        p_boxes = pred_by_frame.get(fidx, FramePrediction(frame_index=fidx)).boxes

        for cname in classes:
            gc = [b for b in g_boxes if b.class_name == cname]
            pc = sorted([b for b in p_boxes if b.class_name == cname], key=lambda x: x.confidence, reverse=True)
            thresh = ball_iou_threshold if cname == "ball" else iou_threshold

            per_class_counts[cname]["gt"] += len(gc)
            per_class_counts[cname]["pred"] += len(pc)

            matched_gt = set()
            if gc and pc:
                cost = np.ones((len(pc), len(gc)), dtype=np.float64)
                for pi, pb in enumerate(pc):
                    for gi, gb in enumerate(gc):
                        val = _iou(pb.xyxy_norm, gb.xyxy_norm)
                        cost[pi, gi] = 1.0 - val
                row_ind, col_ind = linear_sum_assignment(cost)
                pair_map = {int(r): int(c) for r, c in zip(row_ind, col_ind) if (1.0 - cost[r, c]) >= thresh}
            else:
                pair_map = {}

            for pi, pb in enumerate(pc):
                gi = pair_map.get(pi)
                if gi is not None and gi not in matched_gt:
                    matched_gt.add(gi)
                    gb = gc[gi]
                    per_class_counts[cname]["tp"] += 1
                    per_class_scores[cname].append((pb.confidence, 1))
                    if pb.pitch_xy_m and gb.pitch_xy_m:
                        err = math.hypot(pb.pitch_xy_m[0] - gb.pitch_xy_m[0], pb.pitch_xy_m[1] - gb.pitch_xy_m[1])
                        pitch_errors.append(err)
                else:
                    per_class_counts[cname]["fp"] += 1
                    per_class_scores[cname].append((pb.confidence, 0))
            per_class_counts[cname]["fn"] += max(0, len(gc) - len(matched_gt))

        # Track-level IDF1 & HOTA over tracked objects (players/goalkeepers)
        gt_tr = [b for b in g_boxes if b.track_id is not None]
        pr_tr = [b for b in p_boxes if b.track_id is not None]
        total_gt_tracks += len(gt_tr)
        total_pred_tracks += len(pr_tr)

        matched_this_frame = 0
        if gt_tr and pr_tr:
            cost = np.ones((len(gt_tr), len(pr_tr)), dtype=np.float64)
            for gi, gb in enumerate(gt_tr):
                for pi, pb in enumerate(pr_tr):
                    cost[gi, pi] = 1.0 - _iou(gb.xyxy_norm, pb.xyxy_norm)
            ri, ci = linear_sum_assignment(cost)
            for gi, pi in zip(ri, ci):
                if (1.0 - cost[gi, pi]) >= iou_threshold:
                    matched_this_frame += 1
                    gt_id = str(gt_tr[gi].track_id)
                    pr_id = str(pr_tr[pi].track_id)
                    id_pair_matches[(gt_id, pr_id)] = id_pair_matches.get((gt_id, pr_id), 0) + 1
                    if gt_id in last_gt_to_pred and last_gt_to_pred[gt_id] != pr_id:
                        id_switches += 1
                    last_gt_to_pred[gt_id] = pr_id

        det_tp_all += matched_this_frame
        det_fn_all += max(0, len(gt_tr) - matched_this_frame)
        det_fp_all += max(0, len(pr_tr) - matched_this_frame)

    class_summaries: List[ClassMetricSummary] = []
    for cname in classes:
        st = per_class_counts[cname]
        prec = st["tp"] / max(1, st["tp"] + st["fp"])
        rec = st["tp"] / max(1, st["gt"])
        scored = sorted(per_class_scores[cname], key=lambda x: x[0], reverse=True)
        if scored and st["gt"] > 0:
            tp_cum = np.cumsum([s[1] for s in scored], dtype=np.float64)
            fp_cum = np.cumsum([1 - s[1] for s in scored], dtype=np.float64)
            rec_curve = tp_cum / float(st["gt"])
            prec_curve = tp_cum / np.maximum(1e-9, tp_cum + fp_cum)
            ap = _voc_ap(rec_curve, prec_curve)
        else:
            ap = 0.0
        class_summaries.append(
            ClassMetricSummary(
                class_name=cname,
                gt_count=st["gt"],
                pred_count=st["pred"],
                tp=st["tp"],
                fp=st["fp"],
                fn=st["fn"],
                precision=round(prec, 4),
                recall=round(rec, 4),
                ap50=round(ap, 4),
            )
        )

    valid_classes = [c for c in class_summaries if c.gt_count > 0]
    macro_p = round(sum(c.precision for c in valid_classes) / max(1, len(valid_classes)), 4)
    macro_r = round(sum(c.recall for c in valid_classes) / max(1, len(valid_classes)), 4)
    map50 = round(sum(c.ap50 for c in valid_classes) / max(1, len(valid_classes)), 4)

    ball_sum = next((c for c in class_summaries if c.class_name == "ball"), None)
    player_sum = next((c for c in class_summaries if c.class_name in ("player", "outfield_player")), None)

    # Optimal bipartite ID assignment for IDF1 and AssA
    idtp = 0
    if id_pair_matches:
        gt_ids = sorted({g for g, _ in id_pair_matches})
        pr_ids = sorted({p for _, p in id_pair_matches})
        mat = np.zeros((len(gt_ids), len(pr_ids)), dtype=np.float64)
        for i, gid in enumerate(gt_ids):
            for j, pid in enumerate(pr_ids):
                mat[i, j] = float(id_pair_matches.get((gid, pid), 0))
        ri, ci = linear_sum_assignment(-mat)
        idtp = int(sum(mat[i, j] for i, j in zip(ri, ci)))

    idf1 = round((2.0 * idtp) / max(1, total_gt_tracks + total_pred_tracks), 4)
    mota = round(1.0 - ((det_fn_all + det_fp_all + id_switches) / max(1, total_gt_tracks)), 4)
    det_a = det_tp_all / max(1, det_tp_all + det_fp_all + det_fn_all)
    ass_a = idtp / max(1, det_tp_all)
    hota = round(math.sqrt(max(0.0, det_a * ass_a)), 4)

    rmse_m = round(math.sqrt(sum(e * e for e in pitch_errors) / len(pitch_errors)), 3) if pitch_errors else None
    med_m = round(float(np.median(pitch_errors)), 3) if pitch_errors else None

    return CVEvaluationReport(
        evaluation_scope=evaluation_scope,
        frames_evaluated=len(all_frames),
        macro_precision=macro_p,
        macro_recall=macro_r,
        map50=map50,
        ball_recall=ball_sum.recall if ball_sum else 0.0,
        ball_ap50=ball_sum.ap50 if ball_sum else 0.0,
        player_ap50=player_sum.ap50 if player_sum else 0.0,
        mota=mota,
        idf1=idf1,
        hota=hota,
        id_switches=id_switches,
        pitch_localization_rmse_m=rmse_m,
        pitch_localization_median_m=med_m,
        per_class=class_summaries,
    )
