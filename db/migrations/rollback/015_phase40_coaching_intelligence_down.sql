-- Rollback 015: Drop Phase 40 Personal AI Coach & Gamer DNA tables in reverse FK order.

BEGIN;

DROP TABLE IF EXISTS public.phase40_knowledge_entry;
DROP TABLE IF EXISTS public.phase40_coach_message;
DROP TABLE IF EXISTS public.phase40_coach_session;
DROP TABLE IF EXISTS public.phase40_training_attempt;
DROP TABLE IF EXISTS public.phase40_training_plan;
DROP TABLE IF EXISTS public.phase40_recurring_mistake;
DROP TABLE IF EXISTS public.phase40_gamer_profile;
DROP TABLE IF EXISTS public.phase40_match_record;
DROP TABLE IF EXISTS public.phase40_match_squad_snapshot;

COMMIT;
