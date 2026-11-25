BEGIN;
CREATE TABLE IF NOT EXISTS fc27_staging.card_squad (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    snapshot_id text NOT NULL REFERENCES fc27_staging.snapshot(snapshot_id),
    release_id text NOT NULL,
    name text NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
    receipt text NOT NULL CHECK(length(receipt)=64),
    plan jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id, release_id, receipt, name)
);
CREATE TABLE IF NOT EXISTS fc27_staging.card_feedback (
    user_id uuid NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    recommendation_id uuid NOT NULL,
    item_id uuid NOT NULL,
    snapshot_id text NOT NULL,
    source_item_id text NOT NULL,
    context jsonb NOT NULL,
    action text NOT NULL CHECK(action IN ('SELECTED','REJECTED','ALTERNATIVE_SELECTED','SAVED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id, recommendation_id, item_id),
    FOREIGN KEY(snapshot_id, source_item_id) REFERENCES fc27_staging.observation(snapshot_id,record_id)
);
COMMIT;
