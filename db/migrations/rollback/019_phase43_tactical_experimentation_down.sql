-- Rollback 019: Phase 43 Personal Tactical Experimentation Lab schema
BEGIN;

DROP TABLE IF EXISTS public.phase43_personal_meta;
DROP TABLE IF EXISTS public.phase43_experiment_match_link;
DROP TABLE IF EXISTS public.phase43_experiment;
DROP TABLE IF EXISTS public.phase43_tactical_fingerprint;
DROP TABLE IF EXISTS public.phase43_tactical_snapshot;

ALTER TABLE public.phase40_match_record
    DROP COLUMN IF EXISTS tactical_snapshot_id;

COMMIT;
