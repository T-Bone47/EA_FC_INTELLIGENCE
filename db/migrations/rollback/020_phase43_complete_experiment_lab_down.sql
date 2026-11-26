-- Reversible rollback for Migration 020: Phase 43 Complete Tactical Experimentation Lab

DROP TABLE IF EXISTS phase43_recommendation_feedback;
DROP TABLE IF EXISTS phase43_replacement_experiment;
DROP TABLE IF EXISTS phase43_formation_fit_observation;
DROP TABLE IF EXISTS phase43_experiment_analysis;
DROP TABLE IF EXISTS phase43_experiment_observation;
DROP TABLE IF EXISTS phase43_experiment_assignment;
DROP TABLE IF EXISTS phase43_experiment_protocol_version;

ALTER TABLE phase43_experiment
    DROP COLUMN IF EXISTS protocol_version,
    DROP COLUMN IF EXISTS design_type,
    DROP COLUMN IF EXISTS minimum_meaningful_improvement,
    DROP COLUMN IF EXISTS planned_observations,
    DROP COLUMN IF EXISTS required_coverage_pct,
    DROP COLUMN IF EXISTS stopping_criteria_json,
    DROP COLUMN IF EXISTS confounders_json,
    DROP COLUMN IF EXISTS random_seed,
    DROP COLUMN IF EXISTS completed_at,
    DROP COLUMN IF EXISTS cancelled_at;

UPDATE phase43_experiment
SET status = CASE
    WHEN status IN ('READY', 'COLLECTING_EVIDENCE') THEN 'ACTIVE'
    WHEN status IN ('READY_FOR_ANALYSIS', 'INSUFFICIENT_EVIDENCE') THEN 'INCONCLUSIVE'
    WHEN status = 'CANCELLED' THEN 'ARCHIVED'
    ELSE status
END;

ALTER TABLE phase43_experiment
    DROP CONSTRAINT IF EXISTS phase43_experiment_status_check;

ALTER TABLE phase43_experiment
    ADD CONSTRAINT phase43_experiment_status_check CHECK (
        status IN ('DRAFT', 'ACTIVE', 'COMPLETED', 'INCONCLUSIVE', 'PAUSED', 'ARCHIVED')
    );

ALTER TABLE phase43_tactical_snapshot
    DROP COLUMN IF EXISTS mid_match_changes_json,
    DROP COLUMN IF EXISTS notes;
