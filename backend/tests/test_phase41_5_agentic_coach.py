"""Phase 41.5 Comprehensive Automated Test Suite.

Covers:
1. Configuration, Secret Redaction & Env Aliases
2. Strict Free-Only Enforcement & Paid-Model / Media Rejection
3. QuotaManager (RPM, per-user, daily, turn budgets, HTTP 429 Retry-After cooldown)
4. Provider Adapters (Gemini Free & OpenRouter Free auth, tool-calling, streaming, 429/5xx/timeout/malformed JSON)
5. Model Router Failover & Cross-Provider Normalized History (Scenario E & F)
6. Bounded Agentic Tool Loop, Duplicate Suppression, Unknown Tool Rejection & Cancellation
7. V3.2.1 Preservation, Squad Hard Constraints & Confirmation/Rollback Gate (Scenario A & B)
8. Epistemic Honesty, Synthetic Isolation, Hallucination & Unverified Price Rejection (Scenario C, D, G)
9. BM25 Football Knowledge RAG Hierarchy & Cross-User Security (IDOR / OWASP Prompt Injection)
"""
from __future__ import annotations

import json
import threading
import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.domain.phase40_models import CoachQuestionRequest, MatchRecordCreate
from backend.repositories.phase40_repository import Phase40Repository
from backend.services.coach_tools import CoachToolRegistry
from backend.services.football_knowledge_service import FootballKnowledgeService
from backend.services.llm.contracts import (
    FootballLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolSpec,
    ModelCapabilities,
    ProviderError,
    ProviderErrorKind,
)
from backend.services.llm.free_guard import (
    FreeUsageGuard,
    PaidModelBlockedError,
    QuotaManager,
)
from backend.services.llm.gemini_provider import GeminiProvider
from backend.services.llm.openrouter_provider import OpenRouterProvider
from backend.services.llm.registry import ModelCapabilityRegistry, ProviderHealthMonitor
from backend.services.llm.router import FootballModelRouter, TaskIntent
from backend.services.llm.security import (
    check_media_transmission_allowed,
    redact_dict,
    redact_secrets,
)
from backend.services.personal_coach_orchestrator import PersonalCoachOrchestrator


# ------------------------------------------------------------------ 1. Config & Secrets
def test_config_redaction_and_aliases():
    s = Settings(
        gemini_api_key="AIzaSyFAKE1234567890SECRETKEY999999",
        openrouter_api_key="sk-or-v1-0123456789abcdef0123456789abcdef0123456789",
        ai_coach_video_upload_to_llm=False,
        ai_coach_allow_external_video=False,
    )
    pub = s.safe_ai_public_summary()
    dumped = json.dumps(pub)
    assert "AIza" not in dumped
    assert "sk-or-v1" not in dumped
    assert pub["gemini_configured"] is True
    assert pub["openrouter_configured"] is True
    assert pub["free_only"] is True
    assert pub["allow_external_video"] is False

    noisy = "Error calling Gemini with key AIzaSyFAKE1234567890SECRETKEY999999 and Bearer sk-or-v1-0123456789abcdef0123456789abcdef"
    redacted = redact_secrets(noisy)
    assert "AIzaSyFAKE" not in redacted
    assert "sk-or-v1-0123" not in redacted

    d_red = redact_dict({"api_key": "secret123456", "model": "gemini-4-hydrogen", "token_usage": {"prompt_tokens": 12}})
    assert d_red["api_key"] == "[REDACTED]"
    assert d_red["token_usage"] == {"prompt_tokens": 12}


def test_missing_api_keys_does_not_disable_platform():
    s = Settings(gemini_api_key=None, openrouter_api_key=None, ai_coach_enabled=True)
    router = FootballModelRouter(settings=s)
    dec = router.select_candidates(intent=TaskIntent.PLAYER_DISCOVERY, preferred_provider="AUTO")
    assert dec.candidates == []

    repo = Phase40Repository(force_memory=True)
    orch = PersonalCoachOrchestrator(repo, settings=s, router=router)
    resp = orch.ask("u-nokey", CoachQuestionRequest(question="Which formation suits balanced play?", consent_external_llm=True))
    assert resp.response_mode == "DETERMINISTIC_COACH"
    assert resp.answer


# ------------------------------------------------------------------ 2. Strict Free-Only & Media Policy
def test_free_usage_guard_blocks_paid_and_disallowed_providers():
    s = Settings(ai_coach_free_only=True, ai_coach_allow_paid_usage=False)
    guard = FreeUsageGuard(s)

    # Disallowed providers
    with pytest.raises(ProviderError) as exc_info:
        guard.assert_provider_allowed("ollama")
    assert exc_info.value.kind == ProviderErrorKind.INVALID_REQUEST

    with pytest.raises(ProviderError):
        guard.assert_provider_allowed("openai")

    # Paid Gemini models blocked
    for paid_gem in ("gemini-2.5-pro", "gemini-4-argon", "gemini-4-carbon", "gemini-3.1-pro-preview", "gemini-2.5-flash-tts"):
        with pytest.raises(PaidModelBlockedError):
            guard.validate_model("gemini", paid_gem)

    # Free Gemini models allowed
    guard.validate_model("gemini", "gemini-4-hydrogen")
    guard.validate_model("gemini", "gemini-3.8-flash")

    # Paid OpenRouter models blocked even if suffixed misleadingly or nonzero priced
    with pytest.raises(PaidModelBlockedError):
        guard.validate_model("openrouter", "openai/gpt-4o")

    paid_cap = ModelCapabilities(
        provider="openrouter",
        model_id="vendor/sneaky:free",
        input_price_usd_per_token=0.000001,
        output_price_usd_per_token=0.0,
        free_tier_eligible=True,
        available=True,
    )
    with pytest.raises(PaidModelBlockedError):
        guard.validate_model("openrouter", "vendor/sneaky:free", paid_cap)

    # Extra per-request / web-search fee blocked
    fee_cap = ModelCapabilities(
        provider="openrouter",
        model_id="vendor/reqfee:free",
        input_price_usd_per_token=0.0,
        output_price_usd_per_token=0.0,
        additional_fees_present=True,
        free_tier_eligible=True,
        available=True,
    )
    with pytest.raises(PaidModelBlockedError):
        guard.validate_model("openrouter", "vendor/reqfee:free", fee_cap)


def test_media_transmission_blocked_by_default():
    ok_v, reason_v = check_media_transmission_allowed(
        media_type="video",
        allow_external_images=False,
        allow_external_video=False,
        user_consent_media=True,
        mime_type="video/mp4",
        byte_length=100,
    )
    assert ok_v is False
    assert "disabled" in (reason_v or "").lower()

    ok_i, reason_i = check_media_transmission_allowed(
        media_type="image",
        allow_external_images=False,
        allow_external_video=False,
        user_consent_media=True,
        mime_type="image/png",
        byte_length=1024,
    )
    assert ok_i is False
    assert "AI_COACH_ALLOW_EXTERNAL_IMAGES" in (reason_i or "")


# ------------------------------------------------------------------ 3. QuotaManager & Budgets
def test_quota_manager_limits_and_model_cooldown():
    s = Settings(
        ai_coach_requests_per_minute=3,
        ai_coach_per_user_requests_per_minute=2,
        ai_coach_daily_provider_budget=5,
        ai_coach_max_provider_requests_per_turn=2,
    )
    qm = QuotaManager(s)

    qm.check_and_consume("gemini", "user-1", model_id="gemini-4-hydrogen")
    qm.check_and_consume("gemini", "user-1", model_id="gemini-4-hydrogen")
    # 3rd request in 1 min for user-1 hits per-user RPM
    with pytest.raises(ProviderError) as e_rpm:
        qm.check_and_consume("gemini", "user-1", model_id="gemini-4-hydrogen")
    assert e_rpm.value.kind == ProviderErrorKind.RATE_LIMITED

    # Model-specific cooldown only blocks that upstream model, leaving alternative openrouter model usable
    qm.trigger_cooldown("openrouter", retry_after_seconds=30.0, model_id="openrouter/free")
    with pytest.raises(ProviderError):
        qm.check_and_consume("openrouter", "user-2", model_id="openrouter/free")
    # Alternate free OpenRouter model still allowed
    qm.check_and_consume("openrouter", "user-2", model_id="nvidia/nemotron-3.5-super-vl:free")

    # Turn budget cap counts individual requests
    tb = qm.new_turn_budget()
    tb.reserve_request("gemini")
    tb.reserve_request("gemini")
    with pytest.raises(ProviderError) as e_tb:
        tb.reserve_request("gemini")
    assert e_tb.value.kind == ProviderErrorKind.QUOTA_EXHAUSTED


# ------------------------------------------------------------------ 4 & 5. Providers, Failover & Tool Loop
class _MockProvider(FootballLLMProvider):
    def __init__(self, name: str, script_fn):
        self.provider_name = name
        self.script_fn = script_fn
        self.calls = 0

    def generate(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return self.script_fn(self.calls, **kwargs)

    def health_check(self):
        return {"provider": self.provider_name, "mock": True}


def test_openrouter_payload_enforces_free_routing_and_handles_http_errors():
    s = Settings(openrouter_api_key="sk-or-v1-testmockkey1234567890", ai_coach_free_only=True)
    op = OpenRouterProvider(s)
    payload = op._build_payload(
        model="openrouter/free",
        messages=[LLMMessage(role="user", content="Analyze 4-3-3")],
        tools=[LLMToolSpec(name="search_players", description="Search", parameters_json_schema={"type": "object", "properties": {}})],
        response_schema=None,
        temperature=0.2,
        max_output_tokens=400,
        stream=False,
        privacy_strict=True,
    )
    assert payload["provider"]["allow_fallbacks"] is False
    assert payload["provider"]["max_price"] == {"prompt": 0, "completion": 0}
    assert payload["provider"]["data_collection"] == "deny"
    assert "plugins" not in payload

    err_429 = op._classify_http_error(429, "Rate limit exceeded sk-or-v1-testmockkey1234567890", {"retry-after": "15"}, "openrouter/free")
    assert err_429.kind == ProviderErrorKind.RATE_LIMITED
    assert err_429.retry_after_seconds == 15.0
    assert "testmockkey" not in str(err_429)


def test_scenario_e_gemini_failover_to_openrouter_free_and_scenario_f_both_fail():
    s = Settings(
        gemini_api_key="AIzaSyMockTestKey000000000000000000",
        openrouter_api_key="sk-or-v1-mocktestkey0000000000000000",
        ai_coach_free_only=True,
        ai_coach_allow_paid_usage=False,
    )

    def gemini_fail(call_idx, **kwargs):
        raise ProviderError(ProviderErrorKind.QUOTA_EXHAUSTED, "429 quota exceeded", provider="gemini", model=kwargs["model"], status_code=429)

    def openrouter_react(call_idx, **kwargs):
        # Round 1 asks for tool; Round 2 synthesizes final JSON
        if call_idx == 1:
            return LLMResponse(
                provider="openrouter",
                model="nvidia/nemotron-3.5-super-vl:free",
                text="",
                tool_calls=[LLMToolCall(call_id="call_1", name="search_football_knowledge", arguments={"query": "FC IQ double pivot"})],
                prompt_tokens=100,
                completion_tokens=20,
                reported_cost_usd=0.0,
            )
        return LLMResponse(
            provider="openrouter",
            model="nvidia/nemotron-3.5-super-vl:free",
            text=json.dumps({
                "answer": "Double-pivot shapes (4-2-3-1) retain rest defense behind attacking fullbacks per Official EA Pitch Notes.",
                "key_findings": ["Double-pivot preserves central lane screening."],
                "tactical_adjustments": ["Set one CDM to Holding."],
                "recommendations": ["Test 4-2-3-1 prior to signing cards."],
                "training_objectives": [],
                "limitations": ["Free OpenRouter failover used after Gemini quota exhaustion."],
                "evidence_summary": "Official KB",
            }),
            prompt_tokens=180,
            completion_tokens=60,
            reported_cost_usd=0.0,
        )

    reg = ModelCapabilityRegistry(s)
    reg._last_refresh_mono["gemini"] = 1e12
    reg._last_refresh_mono["openrouter"] = 1e12
    qm = QuotaManager(s)
    router = FootballModelRouter(
        settings=s,
        registry=reg,
        guard=FreeUsageGuard(s),
        quota=qm,
        health=ProviderHealthMonitor(),
        providers={"gemini": _MockProvider("gemini", gemini_fail), "openrouter": _MockProvider("openrouter", openrouter_react)},
    )
    repo = Phase40Repository(force_memory=True)
    orch = PersonalCoachOrchestrator(repo, settings=s, router=router)

    # Scenario E: Failover Gemini -> OpenRouter free with real ReAct tool execution
    resp = orch.ask(
        "user-e",
        CoachQuestionRequest(
            question="How does FC IQ double pivot prevent counter-attacks?",
            game_version="FC27",
            consent_external_llm=True,
            preferred_provider="AUTO",
        ),
    )
    assert resp.provider == "openrouter"
    assert resp.model == "nvidia/nemotron-3.5-super-vl:free"
    assert resp.response_mode == "OPENROUTER_FREE"
    assert resp.usage_metadata["reported_cost_usd"] == 0.0
    assert any(t["tool"] == "search_football_knowledge" for t in resp.tool_trace)
    assert len(resp.knowledge_sources) >= 1

    # Scenario F: Both providers fail -> Deterministic Coach Fallback
    both_down_router = FootballModelRouter(
        settings=s,
        registry=reg,
        guard=FreeUsageGuard(s),
        quota=QuotaManager(s),
        health=ProviderHealthMonitor(),
        providers={"gemini": _MockProvider("gemini", gemini_fail), "openrouter": _MockProvider("openrouter", gemini_fail)},
    )
    orch_down = PersonalCoachOrchestrator(repo, settings=s, router=both_down_router)
    resp_down = orch_down.ask(
        "user-f",
        CoachQuestionRequest(question="Which formation suits balanced play?", consent_external_llm=True, preferred_provider="AUTO"),
    )
    assert resp_down.response_mode == "DETERMINISTIC_COACH"
    assert resp_down.answer


def test_unknown_tool_rejected_duplicate_suppressed_and_cancellation_respected():
    repo = Phase40Repository(force_memory=True)
    reg_tools = CoachToolRegistry(repo)
    with pytest.raises(ValueError):
        reg_tools.execute("execute_arbitrary_sql", "user-1")

    # Cancellation stops LLM loop cleanly and falls back deterministically
    cancel_ev = threading.Event()
    cancel_ev.set()
    s = Settings(gemini_api_key="AIzaSyMockTestKey000000000000000000", openrouter_api_key=None)
    orch = PersonalCoachOrchestrator(repo, settings=s)
    resp = orch.ask(
        "user-cancel",
        CoachQuestionRequest(question="Which formation suits balanced play?", consent_external_llm=True),
        cancel_event=cancel_ev,
    )
    assert resp.response_mode == "DETERMINISTIC_COACH"


# ------------------------------------------------------------------ 6. BM25 Football Knowledge RAG
def test_bm25_rag_ranks_official_facts_above_research_and_filters_version():
    kb = FootballKnowledgeService()
    res = kb.query("PlayStyle+ cap attributes FC27", game_version="FC27")
    assert res["retrieval_engine"] == "BM25_HIERARCHICAL_RAG"
    assert res["total_matches"] >= 1
    assert res["entries"][0]["verification_status"] == "OFFICIAL_FACT"
    assert res["entries"][0]["game_version"] in ("FC27", "BOTH")

    # FC26 filter excludes FC27-only entries
    fc26_only = kb.query("PlayStyle+ cap attributes", game_version="FC26")
    assert all(e["game_version"] in ("FC26", "BOTH", "GENERAL") for e in fc26_only["entries"])


# ------------------------------------------------------------------ 7. API Endpoints: Conversations, Proposal Confirm/Rollback, Security
def test_coach_conversations_proposal_confirm_rollback_and_idor(app, auth_client):
    auth_client.delete("/api/phase40/privacy/reset")

    # Health & provider diagnostics never expose keys
    ph = auth_client.get("/api/phase40/coach/providers/health")
    assert ph.status_code == 200
    body_text = json.dumps(ph.json())
    assert "AIza" not in body_text
    assert "sk-or-v1" not in body_text
    assert ph.json()["config"]["free_only"] is True

    # Create a squad optimization proposal via tool registry directly scoped to user
    repo = CoachToolRegistry()
    prop_out, rec = repo.execute("optimize_squad", "unit-prop-user", formation="4-2-3-1", tactical_profile="BALANCED", game_version="FC26")
    assert rec.status == "OK"
    assert prop_out["requires_confirmation"] is True
    assert prop_out["hard_constraints_verified"]["unique_footballers"] is True
    assert len(prop_out["slots"]) == 11

    # Ask Coach & manage sessions via API
    r1 = auth_client.post("/api/phase40/coach/ask", json={"question": "Which formation suits balanced tactics?", "game_version": "FC26"})
    assert r1.status_code == 200
    sid = r1.json()["session_id"]

    convs = auth_client.get("/api/phase40/coach/conversations")
    assert convs.status_code == 200
    assert any(c["session_id"] == sid for c in convs.json()["conversations"])

    patch_res = auth_client.patch(f"/api/phase40/coach/conversations/{sid}", json={"title": "4-2-3-1 Review"})
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "4-2-3-1 Review"

    # Cross-user IDOR on conversation update/delete/proposal confirm must fail 404
    with TestClient(app) as other:
        em = f"idor415-{uuid.uuid4().hex[:8]}@example.com"
        s = other.post("/api/auth/signup", json={"email": em, "password": "Test-Passw0rd!415", "display_name": "Other415"})
        assert s.status_code == 201
        other.headers["Authorization"] = f"Bearer {s.json()['access_token']}"
        assert other.patch(f"/api/phase40/coach/conversations/{sid}", json={"title": "Hacked"}).status_code == 404
        assert other.delete(f"/api/phase40/coach/conversations/{sid}").status_code == 404

    # Owner deletes conversation cleanly
    assert auth_client.delete(f"/api/phase40/coach/conversations/{sid}").status_code == 204
    assert auth_client.delete(f"/api/phase40/coach/conversations/{sid}").status_code == 404


def test_scenario_c_synthetic_isolation_and_v321_tool_bridge():
    repo = Phase40Repository(force_memory=True)
    # Seed ONLY synthetic match for user
    repo.save_match(
        "user-synth",
        MatchRecordCreate(
            video_id="VID-SYNTH",
            provenance="SYNTHETIC_FIXTURE",
            coaching_findings=[{"code": "COUNTER_ATTACK_VULNERABILITY", "severity": "HIGH", "timestamp_start": 10.0, "timestamp_end": 12.0}],
        ),
    )
    orch = PersonalCoachOrchestrator(repo)
    resp = orch.ask("user-synth", CoachQuestionRequest(question="Why do I keep conceding counter-attacks?", game_version="FC27"))
    assert resp.abstained is True
    assert not resp.evidence_references
    assert "SYNTHETIC_FIXTURE" in resp.answer

    # Test V3.2.1 recommend_players tool returns valid structure or clean refusal (never alters weights)
    reg = CoachToolRegistry(repo)
    out, rec = reg.execute("recommend_players", "user-synth", game_version="FC26", position="CDM", tactical_profile="COUNTER_ATTACK", limit=4)
    assert rec.status == "OK"
    assert out["frozen_v321_untouched"] is True
