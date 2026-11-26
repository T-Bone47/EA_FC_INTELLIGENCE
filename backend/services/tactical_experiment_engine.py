"""Phase 43D: Tactical Experiment Engine (8 Supported Experiment Workflows).

Manages user-scoped tactical experiments comparing two immutable
TacticalConfigurationSnapshots (BASELINE_A vs VARIANT_B), enforcing edition & patch
checks, rejecting synthetic matches from causal arm totals, and supporting paired or
randomized ABBA match-level assignment designs.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from backend.domain.phase43_models import (
    DesignType,
    ExperimentMatchLinkCreate,
    ExperimentStatus,
    ExperimentType,
    TacticalExperimentCreate,
    TacticalExperimentRecord,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer


SUPPORTED_PRIMARY_METRICS: Dict[str, Dict[str, Any]] = {
    "conceded_transition_rate": {"higher_is_better": False, "numerator": "exposed_transitions", "denominator": "transition_opportunities"},
    "risky_central_pass_rate": {"higher_is_better": False, "numerator": "risky_central_passes", "denominator": "central_pass_opportunities"},
    "defensive_compactness": {"higher_is_better": True, "numerator": None, "denominator": None},
    "defensive_transition_management": {"higher_is_better": True, "numerator": None, "denominator": None},
    "central_progression": {"higher_is_better": True, "numerator": None, "denominator": None},
    "chance_creation": {"higher_is_better": True, "numerator": None, "denominator": None},
    "possession_share": {"higher_is_better": True, "numerator": None, "denominator": None},
    "pressing_intensity": {"higher_is_better": True, "numerator": None, "denominator": None},
}


class TacticalExperimentEngine:
    """Lifecycle and match-linking manager for all 8 Phase 43 experiment workflows."""

    def __init__(
        self,
        repo: Optional[Phase43Repository] = None,
        phase40_repo: Optional[Phase40Repository] = None,
    ) -> None:
        self.repo = repo or get_phase43_repository()
        self.p40_repo = phase40_repo or get_phase40_repository()

    def create_experiment(self, user_id: str, req: TacticalExperimentCreate) -> TacticalExperimentRecord:
        uid = str(user_id)
        snap_a = self.repo.get_snapshot(uid, req.baseline_snapshot_id)
        snap_b = self.repo.get_snapshot(uid, req.variant_snapshot_id)

        if snap_a.snapshot_id == snap_b.snapshot_id:
            raise ValueError("Baseline and Variant tactical snapshots must be distinct configurations.")
        if snap_a.game_version != req.game_version or snap_b.game_version != req.game_version:
            raise ValueError("Both tactical snapshots must match the experiment game_version (FC26/FC27 isolation).")
        if req.primary_metric not in SUPPORTED_PRIMARY_METRICS:
            raise ValueError(f"Unsupported primary_metric {req.primary_metric!r}; choose from {sorted(SUPPORTED_PRIMARY_METRICS)}")

        # Validate structural difference expected for specific experiment types
        if req.experiment_type == ExperimentType.FORMATION_COMPARISON and snap_a.formation == snap_b.formation:
            raise ValueError("FORMATION_COMPARISON requires two snapshots with different formations.")

        rec = TacticalExperimentRecord(
            user_id=uid,
            title=req.title.strip(),
            hypothesis=req.hypothesis.strip(),
            experiment_type=req.experiment_type,
            game_version=req.game_version,
            baseline_patch=req.baseline_patch,
            gameplay_mode=req.gameplay_mode,
            baseline_snapshot_id=snap_a.snapshot_id,
            variant_snapshot_id=snap_b.snapshot_id,
            primary_metric=req.primary_metric,
            secondary_metrics=list(req.secondary_metrics),
            target_min_matches_per_arm=req.target_min_matches_per_arm,
            assignment_design=req.assignment_design,
            protocol_version=1,
            design_type=req.design_type.value,
            minimum_meaningful_improvement=req.minimum_meaningful_improvement,
            planned_observations=max(req.planned_observations, req.target_min_matches_per_arm * 2),
            required_coverage_pct=req.required_coverage_pct,
            stopping_criteria=dict(req.stopping_criteria) or {
                "min_matches_per_arm": req.target_min_matches_per_arm,
                "stop_on_meaningful_posterior": 0.90,
                "max_matches_per_arm": max(10, req.target_min_matches_per_arm * 3),
            },
            confounder_controls=dict(req.confounder_controls) or {
                "lock_game_version": req.game_version,
                "lock_game_patch": req.baseline_patch,
                "lock_gameplay_mode": req.gameplay_mode,
            },
            random_seed=req.random_seed,
            status=ExperimentStatus.READY,
        )
        created = self.repo.create_experiment(rec)
        assignments = self._build_assignment_schedule(
            experiment_id=created.experiment_id,
            baseline_snapshot_id=snap_a.snapshot_id,
            variant_snapshot_id=snap_b.snapshot_id,
            design_type=req.design_type.value,
            target_per_arm=req.target_min_matches_per_arm,
            seed=req.random_seed,
        )
        saved_assigns = self.repo.save_experiment_assignments(uid, created.experiment_id, assignments)
        created.assignments = saved_assigns
        return created

    def update_status(
        self,
        user_id: str,
        experiment_id: str,
        target_status: ExperimentStatus,
        *,
        reason: Optional[str] = None,
    ) -> TacticalExperimentRecord:
        uid = str(user_id)
        exp = self.repo.get_experiment(uid, experiment_id)
        if exp.status == ExperimentStatus.ARCHIVED and target_status != ExperimentStatus.ARCHIVED:
            raise ValueError("Archived experiments cannot transition back to an active state.")
        return self.repo.update_experiment_status(uid, experiment_id, target_status, reason=reason)

    def _build_assignment_schedule(
        self,
        *,
        experiment_id: str,
        baseline_snapshot_id: str,
        variant_snapshot_id: str,
        design_type: str,
        target_per_arm: int,
        seed: int,
    ) -> List[Dict[str, Any]]:
        rng = random.Random(f"{experiment_id}:{seed}")
        schedule: List[Dict[str, Any]] = []
        seq = 0
        if design_type == DesignType.RANDOMIZED_BLOCKED.value:
            n_blocks = max(1, (target_per_arm + 1) // 2)
            for b in range(1, n_blocks + 1):
                block = ["BASELINE_A", "BASELINE_A", "VARIANT_B", "VARIANT_B"]
                rng.shuffle(block)
                for arm_label in block:
                    seq += 1
                    schedule.append(
                        {
                            "block_index": b,
                            "sequence_index": seq,
                            "assigned_arm": "A" if arm_label == "BASELINE_A" else "B",
                            "assigned_Arm_label": arm_label,
                            "assigned_snapshot_id": baseline_snapshot_id if arm_label == "BASELINE_A" else variant_snapshot_id,
                            "status": "PENDING",
                        }
                    )
        elif design_type == DesignType.DESCRIPTIVE_BEFORE_AFTER.value:
            for idx in range(target_per_arm):
                seq += 1
                schedule.append({"block_index": 1, "sequence_index": seq, "assigned_arm": "A", "assigned_snapshot_id": baseline_snapshot_id, "status": "PENDING"})
            for idx in range(target_per_arm):
                seq += 1
                schedule.append({"block_index": 2, "sequence_index": seq, "assigned_arm": "B", "assigned_snapshot_id": variant_snapshot_id, "status": "PENDING"})
        else:
            # CROSSOVER_ABBA or MATCHED_COMPARISON counterbalanced ABBA blocks
            n_blocks = max(1, (target_per_arm + 1) // 2)
            for b in range(1, n_blocks + 1):
                block = ["BASELINE_A", "VARIANT_B", "VARIANT_B", "BASELINE_A"] if b % 2 == 1 else ["VARIANT_B", "BASELINE_A", "BASELINE_A", "VARIANT_B"]
                for arm_label in block:
                    seq += 1
                    schedule.append(
                        {
                            "block_index": b,
                            "sequence_index": seq,
                            "assigned_arm": "A" if arm_label == "BASELINE_A" else "B",
                            "assigned_snapshot_id": baseline_snapshot_id if arm_label == "BASELINE_A" else variant_snapshot_id,
                            "status": "PENDING",
                        }
                    )
        return schedule

    def suggest_tactical_experiment(
        self,
        user_id: str,
        *,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.04",
        focus_weakness: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recommends a scientific N-of-1 trial based on observed mistakes, without modifying configs."""
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        matches = self.p40_repo.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=40)
        mistakes = RecurringMistakeAnalyzer().analyze(matches)
        top_w = focus_weakness or (mistakes[0].weakness_type if mistakes else "TRANSITION_EXPOSURE")
        snapshots = self.repo.list_snapshots(uid, game_version=gv, limit=10)

        metric = "conceded_transition_rate"
        exp_type = ExperimentType.DEFENSIVE_HEIGHT_PRESS_COMPARISON.value
        variant_goal = "Lower defensive line height by 8-12 points or move one CM to Holding (Defend) while holding XI constant."
        if "PASS" in top_w.upper() or "BUILD" in top_w.upper():
            metric = "central_progression"
            exp_type = ExperimentType.BUILD_UP_STYLE_COMPARISON.value
            variant_goal = "Test Balanced vs Short Passing build-up and add Deep-Lying Playmaker / Box-to-Box outlet triangles."
        elif "FORMATION" in top_w.upper():
            metric = "possession_share"
            exp_type = ExperimentType.FORMATION_COMPARISON.value
            variant_goal = "Compare current formation against a double-pivot shape (4-2-3-1) across 6 ABBA matches."

        return {
            "user_id": uid,
            "game_version": gv,
            "game_patch": game_patch,
            "detected_focus": top_w,
            "experiment_type": exp_type,
            "suggested_primary_metric": metric,
            "suggested_design": "CROSSOVER_ABBA",
            "target_min_matches_per_arm": 4,
            "minimum_meaningful_improvement": 0.05,
            "available_snapshot_ids": [s.snapshot_id for s in snapshots[:4]],
            "hypothesis": f"Applying tactical adjustment for {top_w} improves {metric} by >= 0.05 without trading away central chance creation.",
            "recommended_variant_change": variant_goal,
            "mutates_saved_config": False,
        }

    def preview_tactical_experiment(self, user_id: str, req: TacticalExperimentCreate) -> Dict[str, Any]:
        """Dry-run protocol validation and ABBA schedule preview — zero persistence or config mutation."""
        uid = str(user_id)
        snap_a = self.repo.get_snapshot(uid, req.baseline_snapshot_id)
        snap_b = self.repo.get_snapshot(uid, req.variant_snapshot_id)
        if snap_a.snapshot_id == snap_b.snapshot_id:
            raise ValueError("Baseline and Variant tactical snapshots must be distinct configurations.")
        if snap_a.game_version != req.game_version or snap_b.game_version != req.game_version:
            raise ValueError("Both tactical snapshots must match the experiment game_version.")
        if req.primary_metric not in SUPPORTED_PRIMARY_METRICS:
            raise ValueError(f"Unsupported primary_metric {req.primary_metric!r}")
        schedule = self._build_assignment_schedule(
            experiment_id="PREVIEW",
            baseline_snapshot_id=snap_a.snapshot_id,
            variant_snapshot_id=snap_b.snapshot_id,
            design_type=req.design_type.value,
            target_per_arm=req.target_min_matches_per_arm,
            seed=req.random_seed,
        )
        return {
            "preview_only": True,
            "mutates_saved_config": False,
            "title": req.title,
            "hypothesis": req.hypothesis,
            "experiment_type": req.experiment_type.value,
            "baseline_snapshot": {"snapshot_id": snap_a.snapshot_id, "formation": snap_a.formation, "label": snap_a.label},
            "variant_snapshot": {"snapshot_id": snap_b.snapshot_id, "formation": snap_b.formation, "label": snap_b.label},
            "design_type": req.design_type.value,
            "planned_observations": len(schedule),
            "schedule_preview": schedule,
        }

    def link_match(self, user_id: str, experiment_id: str, req: ExperimentMatchLinkCreate) -> Dict[str, Any]:
        uid = str(user_id)
        exp = self.repo.get_experiment(uid, experiment_id)
        match = self.p40_repo.get_match(uid, req.match_id)

        excluded_reason: Optional[str] = None
        if match.provenance == "SYNTHETIC_FIXTURE":
            excluded_reason = "SYNTHETIC_FIXTURE_EXCLUDED"
        elif match.game_version != exp.game_version:
            excluded_reason = f"GAME_VERSION_MISMATCH:{match.game_version}!={exp.game_version}"

        snap_id = req.snapshot_id or (
            exp.baseline_snapshot_id if req.arm.value == "BASELINE_A" else exp.variant_snapshot_id
        )
        # Validate snapshot ownership if supplied
        _ = self.repo.get_snapshot(uid, snap_id)

        return self.repo.link_match_to_experiment(
            uid,
            experiment_id,
            ExperimentMatchLinkCreate(
                match_id=req.match_id,
                arm=req.arm,
                snapshot_id=snap_id,
                opponent_archetype=req.opponent_archetype,
                match_order=req.match_order,
            ),
            game_version=match.game_version,
            game_patch=match.game_patch,
            gameplay_mode=match.gameplay_mode,
            excluded_reason=excluded_reason,
        )

    def get_recommended_schedule(self, experiment_id: str, rounds: int = 3) -> List[Dict[str, str]]:
        """Generates counterbalanced ABBA block schedule reducing patch/fatigue/order bias."""
        blocks = ["BASELINE_A", "VARIANT_B", "VARIANT_B", "BASELINE_A"]
        out: List[Dict[str, str]] = []
        for idx in range(max(1, min(6, rounds)) * 2):
            arm = blocks[idx % len(blocks)]
            out.append({"match_slot": idx + 1, "recommended_arm": arm, "experiment_id": experiment_id})
        return out
