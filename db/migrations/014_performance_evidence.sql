BEGIN;
CREATE TABLE IF NOT EXISTS fc27_staging.performance_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    snapshot_id text NOT NULL,
    source_item_id text NOT NULL,
    cohort_version text NOT NULL,
    card_item_id uuid NOT NULL,
    schema_version integer NOT NULL CHECK(schema_version=1),
    fingerprint text NOT NULL CHECK(length(fingerprint)=64),
    evidence_kind text NOT NULL CHECK(evidence_kind IN (
        'OFFICIAL_GAME_MECHANIC','OFFICIAL_CARD_ATTRIBUTE','COMMUNITY_OPINION','CREATOR_OBSERVATION',
        'OWNER_RECORDED_MATCH','USER_SUBMITTED_MATCH','CONTROLLED_EXPERIMENT','MODEL_PREDICTION','UNVERIFIED_CLAIM')),
    source_key text NOT NULL,
    payload jsonb NOT NULL,
    share_for_research boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,cohort_version,fingerprint),
    FOREIGN KEY(snapshot_id,source_item_id) REFERENCES fc27_staging.observation(snapshot_id,record_id)
);
CREATE INDEX IF NOT EXISTS performance_evidence_cohort_card ON fc27_staging.performance_evidence(cohort_version,card_item_id);
CREATE TABLE IF NOT EXISTS fc27_staging.performance_evidence_review (
    evidence_id uuid PRIMARY KEY REFERENCES fc27_staging.performance_evidence(id) ON DELETE CASCADE,
    reviewer_id uuid REFERENCES public.user_profile(id) ON DELETE SET NULL,
    disposition text NOT NULL CHECK(disposition IN ('ACCEPTED','REJECTED','WITHDRAWN')),
    reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 500),
    reviewed_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
