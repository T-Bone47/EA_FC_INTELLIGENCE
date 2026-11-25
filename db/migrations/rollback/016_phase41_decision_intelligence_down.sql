-- Rollback 016: Phase 41 Decision Intelligence tables
BEGIN;

DROP TABLE IF EXISTS public.phase41_decision_annotation;
DROP TABLE IF EXISTS public.phase41_training_scenario;
DROP TABLE IF EXISTS public.phase41_football_iq_profile;
DROP TABLE IF EXISTS public.phase41_decision_opportunity;

COMMIT;
