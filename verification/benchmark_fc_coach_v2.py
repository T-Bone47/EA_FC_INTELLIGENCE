"""Phase 42 Live Provider, Latency/TTFT, Context-Envelope & Privacy Benchmark (FC_COACH_BENCH_V2).

Loads API credentials securely from backend settings / `.env` without printing secrets.
Isolates per-provider benchmark accounts so Gemini, OpenRouter Free, and Deterministic
modes never trip shared per-user RPM quotas against each other.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.config import get_settings


BENCH_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "BENCH-CTX-SCOUT",
        "route_name": "PLAYER_DISCOVERY",
        "question": "Recommend 2 defensive midfielders for FC27 under Balanced tactics and explain key traits.",
        "context_envelope": {"route_name": "PLAYER_DISCOVERY", "game_version": "FC27", "active_filters": {"position": "CDM"}},
    },
    {
        "case_id": "BENCH-DNA-WEAKNESS",
        "route_name": "GAMER_DNA",
        "question": "Summarize my Gamer DNA archetype and whether my sample size supports firm conclusions.",
        "context_envelope": {"route_name": "GAMER_DNA", "game_version": "FC27"},
    },
    {
        "case_id": "BENCH-FCIQ-KB",
        "route_name": "GENERAL",
        "question": "Explain the difference between Holding and Deep-Lying Playmaker in FC IQ with citations.",
        "context_envelope": {"route_name": "GENERAL", "game_version": "FC27"},
    },
]


def _setup_client(app, suffix: str) -> TestClient:
    c = TestClient(app)
    email = f"phase42_bench_{suffix}@example.com"
    r = c.post("/api/auth/signup", json={"email": email, "password": "Password123!", "display_name": f"Bench_{suffix}"})
    if r.status_code == 409:
        r = c.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    tok = r.json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {tok}"})
    c.post(
        "/api/phase40/matches",
        json={
            "video_id": f"VID-BENCH-{suffix}",
            "game_version": "FC27",
            "game_patch": "PATCH_1.04",
            "formation": "4-2-3-1",
            "provenance": "REAL_VIDEO_DECODED",
            "observation_quality": "HIGH",
            "tracking_coverage_pct": 89.0,
            "duration_seconds": 360.0,
            "feature_metrics": {"defensive_compactness": 0.72, "central_progression": 0.65, "transition_opportunities": 8, "exposed_transitions": 3},
            "coaching_findings": [{"diagnostic_code": "EXPOSED_CENTRAL_CHANNEL", "severity": "HIGH", "summary": "Central pivot stepped too high on turnover."}],
        },
    )
    return c


def run_benchmark() -> Dict[str, Any]:
    settings = get_settings()
    app = create_app()

    modes: List[str] = ["DETERMINISTIC"]
    if settings.gemini_api_key:
        modes.append("GEMINI")
    if settings.openrouter_api_key:
        modes.append("OPENROUTER_FREE")

    results: Dict[str, Any] = {
        "benchmark_version": "FC_COACH_BENCH_V2",
        "configured_free_providers": {
            "gemini_configured": bool(settings.gemini_api_key),
            "gemini_model": settings.gemini_model,
            "openrouter_configured": bool(settings.openrouter_api_key),
            "openrouter_model": settings.openrouter_model,
        },
        "runs": [],
        "privacy_redaction_gate_check": {},
    }

    for mode in modes:
        client = _setup_client(app, f"{mode.lower()}_{int(time.time())}")
        for case in BENCH_CASES:
            t0 = time.perf_counter()
            resp = client.post(
                "/api/phase40/coach/ask",
                json={
                    "question": case["question"],
                    "game_version": "FC27",
                    "context_envelope": case["context_envelope"],
                    "consent_external_llm": mode != "DETERMINISTIC",
                    "preferred_provider": mode,
                },
            )
            wall_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            data = resp.json() if resp.status_code == 200 else {"error_status": resp.status_code}
            results["runs"].append({
                "requested_mode": mode,
                "case_id": case["case_id"],
                "http_status": resp.status_code,
                "actual_provider": data.get("provider"),
                "actual_model": data.get("model"),
                "response_mode": data.get("response_mode"),
                "fallback_used": data.get("fallback_used"),
                "wall_ms": wall_ms,
                "backend_latency_ms": data.get("latency_ms"),
                "ttft_ms": data.get("ttft_ms"),
                "tools_sent_count": data.get("tools_sent_count"),
                "tool_calls_executed": len(data.get("tool_trace") or []),
                "answer_chars": len(data.get("answer") or ""),
                "player_cards_count": len(data.get("player_cards") or []),
                "provider_notes": data.get("provider_notes", []),
            })

    priv_client = _setup_client(app, f"priv_{int(time.time())}")
    blocked_r = priv_client.post(
        "/api/phase40/coach/ask",
        json={
            "question": "Check my squad image",
            "game_version": "FC27",
            "preferred_provider": "DETERMINISTIC",
            "image_b64": "ZmFrZQ==",
            "image_mime": "image/png",
            "user_consent_media": True,
            "redaction_confirmed": False,
        },
    )
    allowed_r = priv_client.post(
        "/api/phase40/coach/ask",
        json={
            "question": "Check my redacted squad image",
            "game_version": "FC27",
            "preferred_provider": "DETERMINISTIC",
            "screenshot_use_case": "FORMATION_SCREENSHOT",
            "image_b64": "ZmFrZQ==",
            "image_mime": "image/png",
            "user_consent_media": True,
            "redaction_confirmed": True,
        },
    )
    results["privacy_redaction_gate_check"] = {
        "unconfirmed_blocked_notices": blocked_r.json().get("security_notices", []),
        "confirmed_candidate_notes": allowed_r.json().get("multimodal_candidate_notes", []),
    }
    return results


if __name__ == "__main__":
    out_path = Path("artifacts/phase42/live_provider_eval_raw.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = run_benchmark()
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(summary['runs'])} benchmark runs)")
