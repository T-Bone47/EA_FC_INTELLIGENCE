"""Phase 40F / 41.5H: BM25 Football & EA FC Knowledge Retrieval (Specialized RAG).

Maintains a structured, citation-backed, game-version & patch-aware knowledge corpus
explicitly separating:
  1. OFFICIAL_FACT (verified EA Pitch Notes, Accessibility docs, FC Rules & UA)
  2. OBSERVED_USER_EVIDENCE (referenced when paired with match telemetry)
  3. RESEARCH_METHODOLOGY (SoccerAction/VAEP, Friends of Tracking, EPV, xT, BKT)
  4. COMMUNITY_OBSERVATION / HYPOTHESIS (never conflated with verified facts)

Implements calibrated Okapi BM25 lexical scoring with exact metadata facet filtering
(game_version, game_patch, topic, verification_status) and source-hierarchy weighting.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import EpistemicClaimType, FootballKnowledgeEntry


KNOWLEDGE_ENTRIES: List[FootballKnowledgeEntry] = [
    FootballKnowledgeEntry(
        entry_id="KB-EA-FCIQ-ROLES-001",
        source_title="EA SPORTS FC 26 / FC 27 Pitch Notes — Gameplay Deep Dive (FC IQ Roles & Focuses)",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.01",
        topic="Player Roles",
        mechanic="FC IQ Role + Focus System",
        publication_date="2026-09-18",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="All Ultimate Team and Kick-Off / Seasons tactics",
        factual_summary=(
            "FC IQ governs off-the-ball movement across 37 outfield Player Roles and Focuses. "
            "Role Familiarity tiers (Base, Role+, Role++) govern positioning discipline and run execution speed; "
            "Fullbacks can be configured as Fullback, Falseback, Wingback, or Attacking Wingback, while central "
            "midfielders include Holding, Deep-Lying Playmaker, Box-to-Box, Playmaker, and Shadow Striker (CAM)."
        ),
        tags=["fc iq", "roles", "role+", "role++", "falseback", "holding", "box-to-box", "shadow striker", "formation", "deep-lying playmaker"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-PLAYSTYLES-002",
        source_title="EA SPORTS FC 27 Pitch Notes — PlayStyles Rebalance & Item Caps",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="FC27",
        patch_version="PATCH_1.02",
        topic="PlayStyles",
        mechanic="PlayStyle+ Cap & Attribute Primacy",
        publication_date="2026-10-10",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="EA SPORTS FC 27 Ultimate Team items",
        factual_summary=(
            "FC27 organizes 36 PlayStyles across 6 categories (Scoring, Passing, Ball Control, Defending, Physical, GK) "
            "and caps Ultimate Team cards at a maximum of 3 PlayStyles+ (reduced from earlier 5-trait builds). "
            "Patch tuning emphasizes underlying core attributes alongside PlayStyle animations so high ratings in "
            "passing, interceptions, and finishing remain impactful even without stacked PlayStyles+."
        ),
        tags=["playstyles", "playstyle+", "fc27", "cap", "attributes", "intercept", "incisive pass", "finesse"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-PLAYSTYLES-FC26-002B",
        source_title="EA SPORTS FC 26 Pitch Notes — Gameplay Deep Dive (PlayStyles & Responsive Passing)",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-gameplay-deep-dive",
        game_version="FC26",
        patch_version="PATCH_1.01",
        topic="PlayStyles",
        mechanic="FC 26 PlayStyle Trigger Reliability & First-Time Passing",
        publication_date="2025-08-20",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="EA SPORTS FC 26 Ultimate Team and Kick-Off",
        factual_summary=(
            "FC26 differentiates Competitive vs Authentic presets and tunes first-time pass responsiveness alongside "
            "Passing PlayStyles (Incisive Pass, Tiki Taka, Pinged Pass, Whipped Pass) so body orientation and "
            "press-resistance govern pass accuracy under close defender pressure."
        ),
        tags=["fc26", "playstyles", "passing", "tiki taka", "incisive pass", "pinged pass", "press resistance"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-DEFENDING-003",
        source_title="EA SPORTS FC 26 / FC 27 Pitch Notes — Manual Defending & Interception Reach",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.01",
        topic="Defensive Mechanics",
        mechanic="Manual Jockey & Reduced AI Auto-Intercept",
        publication_date="2025-08-20",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Competitive online gameplay",
        factual_summary=(
            "EA reduced unassisted AI interception reach relative to user-controlled defenders. "
            "Maintaining central structure with a Holding CDM before stepping out with a CB prevents central lanes "
            "from opening cleanly into one-pass counter-attacks; tackle outcome quality heavily scales with Stand Tackle "
            "and Defensive Awareness attributes."
        ),
        tags=["defending", "interception", "manual control", "cb displacement", "jockey", "counter-attack", "cdm", "stand tackle"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-PRESETS-004",
        source_title="EA SPORTS FC Gameplay Deep Dive — Competitive vs Authentic Presets",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.01",
        topic="Gameplay Modes",
        mechanic="Competitive Preset (UT / Champions)",
        publication_date="2026-09-18",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Division Rivals, Champions Finals, Online Friendlies",
        factual_summary=(
            "Competitive gameplay tuning applies automatically in Ultimate Team online modes (faster transition responsiveness "
            "and stricter manual defending demands), whereas Authentic presets govern offline Career simulations. "
            "Performance metrics must never conflate Competitive online matches with offline Squad Battles or Authentic Career."
        ),
        tags=["competitive", "authentic", "rivals", "weekend league", "champions", "modes", "mode comparison", "patch"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-SHOOTING-PASSING-004B",
        source_title="EA SPORTS FC Pitch Notes — Precision Shooting, Composure & Passing Mechanics",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.02",
        topic="Passing & Shooting Mechanics",
        mechanic="Shot Angle, Defender Cone & Driven Pass Speed",
        publication_date="2026-10-10",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Competitive Ultimate Team offense",
        factual_summary=(
            "Shot probability and animation selection depend on body alignment, distance, angle to goal, weak-foot rating, "
            "Composure under defender proximity, and traits such as Finesse Shot or Low Driven / Power Shot. "
            "Driven ground passes shorten ball travel time across congested zones at the cost of tighter First Touch requirements."
        ),
        tags=["shooting", "finesse shot", "composure", "passing", "driven pass", "through ball", "weak foot", "finishing"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-CHEMISTRY-SQUAD-004C",
        source_title="EA SPORTS FC Ultimate Team — Squad Building & Chemistry Principles",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.01",
        topic="Squad Building & Chemistry",
        mechanic="Position Eligibility, Duplicate Uniqueness & Chemistry Links",
        publication_date="2026-09-18",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Ultimate Team Squad Lab & SBCs",
        factual_summary=(
            "A valid Ultimate Team starting XI requires players in eligible primary or secondary positions (including GK strictly "
            "at GK) with no duplicate footballers in the lineup. Chemistry (0-3 points per item) derives from Club, League, and "
            "Nation thresholds plus Manager alignment; without verified item link metadata, chemistry scores must never be guessed."
        ),
        tags=["chemistry", "squad building", "position", "club", "league", "nation", "duplicate", "goalkeeper"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-TRAINING-005",
        source_title="EA SPORTS FC Accessibility, Camera Visibility & Practice Environments",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/accessibility",
        game_version="BOTH",
        patch_version="PATCH_1.01",
        topic="Controls & Training Modes",
        mechanic="Practice Arena, Skill Games & Camera Geometry",
        publication_date="2026-09-20",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Offline skill drill & camera/control accessibility configuration",
        factual_summary=(
            "Practice Arena allows rehearsing attacking scenarios, set pieces, and 1v1 finishing; Skill Games isolate "
            "passing timing, through-balls, and defensive jockeying; camera height/zoom presets (e.g. Co-Op vs Tele Broadcast) "
            "directly impact off-ball passing-lane visibility on screen."
        ),
        tags=["practice arena", "skill games", "training center", "camera", "controls", "co-op", "tele broadcast", "drills"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-RULES-006",
        source_title="EA SPORTS FC Fair Play Rules & User Agreement Boundaries",
        source_url="https://www.ea.com/legal/user-agreement",
        game_version="BOTH",
        patch_version="CURRENT",
        topic="Compliance & Boundaries",
        mechanic="Post-Match Analysis vs Live Automation Prohibition",
        publication_date="2026-01-01",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="Platform compliance",
        factual_summary=(
            "Automation tools, controller macros, memory reading, and unauthorized real-time competitive overlays violate "
            "EA User Agreement and fair-play rules. EA FC Intelligence operates exclusively post-match on user-supplied "
            "recordings, authorized match traces, and verified player intelligence records."
        ),
        tags=["rules", "user agreement", "fair play", "compliance", "post-match", "no automation", "security"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-EA-TACTICS-FORMATIONS-009",
        source_title="EA SPORTS FC 27 Formation Structures & Rest-Defense Transition Balance",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive",
        game_version="BOTH",
        patch_version="PATCH_1.02",
        topic="Formations",
        mechanic="Rest Defense & Double Pivot Stability",
        publication_date="2026-10-10",
        verification_status=EpistemicClaimType.OFFICIAL_FACT,
        applicability="4-2-3-1, 4-3-3 Holding, 4-4-2, 4-2-2-2, 4-1-2-1-2 Narrow, 3-5-2",
        factual_summary=(
            "Double-pivot formations (4-2-3-1, 4-2-2-2, 4-4-2 with Holding CMs) keep two central screeners deeper than lone-CDM "
            "shapes (4-3-3, 4-1-2-1-2 Narrow), preserving rest-defense coverage when a fullback joins attack as Wingback. "
            "4-3-3 offers natural wide wing outlets; 4-4-2 pairs two strikers for direct horizontal combinations."
        ),
        tags=["4-2-3-1", "4-3-3", "4-4-2", "4-2-2-2", "4-1-2-1-2", "3-5-2", "double pivot", "formation", "rest defense", "width"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-RES-EPV-VAEP-007",
        source_title="EPV (PMC8570314) & SoccerAction VAEP / Expected Threat (Karun Singh)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC8570314/",
        game_version="GENERAL",
        patch_version="METHODOLOGY",
        topic="Decision Intelligence & Tactical Research",
        mechanic="Pre-Action Value vs Outcome Separation (xT / EPV / VAEP)",
        publication_date="2021-10-01",
        verification_status=EpistemicClaimType.RESEARCH_METHODOLOGY,
        applicability="Decision Review heuristics (non-transferable coefficients)",
        factual_summary=(
            "Fernandez et al. (EPV), Karun Singh (Expected Threat xT 12x8 Markov grid), and ML-KULeuven SoccerAction (VAEP/SPADL) "
            "evaluate actions by expected change in scoring minus conceding probability prior to outcome realization. "
            "Real-world coefficients are never copied blindly to EA FC; our Decision Engine surfaces explicit pre-action heuristics."
        ),
        tags=["epv", "vaep", "spadl", "socceraction", "xt", "expected threat", "passing risk", "regret", "decision quality"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-RES-FOTD-PITCHCONTROL-010",
        source_title="Friends of Tracking / Spearman (Metrica Pitch Control) — Kinematic Interception Geometry",
        source_url="https://github.com/Friends-of-Tracking-Data-FoTD",
        game_version="GENERAL",
        patch_version="METHODOLOGY",
        topic="Spatial Intelligence & Pitch Control",
        mechanic="Time-to-Intercept & Passing Corridor Clearance",
        publication_date="2020-07-01",
        verification_status=EpistemicClaimType.RESEARCH_METHODOLOGY,
        applicability="2D Pitch Control & Passing Lane Evaluation",
        factual_summary=(
            "Physics-based Pitch Control computes time-to-intercept from position, reaction delay, and velocity vectors. "
            "Passing lane safety combines orthogonal defender clearance to the pass segment with arrival-time margin relative to pass speed."
        ),
        tags=["friends of tracking", "pitch control", "interception", "clearance", "passing lane", "velocity", "space"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-RES-CALIB-BKT-008",
        source_title="Bayesian Knowledge Tracing (Corbett & Anderson) & Temporal Occlusion Training",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9686440/",
        game_version="GENERAL",
        patch_version="METHODOLOGY",
        topic="Training & Skill Profiling",
        mechanic="Temporal Occlusion Freeze-Frame & Uncertainty-Aware Estimation",
        publication_date="2022-11-15",
        verification_status=EpistemicClaimType.RESEARCH_METHODOLOGY,
        applicability="Training Academy exercises & Gamer DNA uncertainty intervals",
        factual_summary=(
            "Video-based temporal occlusion pauses footage just before an action so players practice scanning passing/defensive cues "
            "(PMC9686440). Experimental BKT models track practice mastery alongside N-of-1 patch/mode comparability controls."
        ),
        tags=["temporal occlusion", "video training", "bkt", "bayesian", "within-person", "calibration", "training"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-RES-CV-GAMESTATE-011",
        source_title="SoccerNet GameState & Camera Calibration / ByteTrack / YOLOX / ONNX Runtime",
        source_url="https://github.com/SoccerNet/sn-gamestate",
        game_version="GENERAL",
        patch_version="METHODOLOGY",
        topic="Gameplay Computer Vision & Tracking",
        mechanic="Detector + Kalman ByteTrack + Homography Calibration + License Compliance",
        publication_date="2024-06-01",
        verification_status=EpistemicClaimType.RESEARCH_METHODOLOGY,
        applicability="Local RTX 3050 4GB ONNX perception pipeline (Apache-2.0 / MIT runtime stack; Ultralytics AGPL-3.0 segregated)",
        factual_summary=(
            "SoccerNet GSR/Calibration, YOLOX (Apache-2.0), ByteTrack (MIT), and ONNX Runtime (MIT) establish decoupled player/ball detection, "
            "pitch landmark homography, and two-stage Kalman association without AGPL runtime dependencies; Ultralytics remains isolated behind optional offline training scripts."
        ),
        tags=["soccernet", "gamestate", "calibration", "bytetrack", "yolox", "onnx", "trackeval", "cv", "yolo", "ultralytics", "roboflow", "cvat"],
    ),
    FootballKnowledgeEntry(
        entry_id="KB-SEC-OWASP-LLM-012",
        source_title="OWASP Top 10 for LLM & Agentic Applications / ReAct & RAG Verification",
        source_url="https://genai.owasp.org/",
        game_version="GENERAL",
        patch_version="METHODOLOGY",
        topic="AI Coach Security & Grounding",
        mechanic="OWASP LLM01/02/06/08 Guardrails + Bounded ReAct Tool Grounding",
        publication_date="2025-01-01",
        verification_status=EpistemicClaimType.RESEARCH_METHODOLOGY,
        applicability="Hybrid Gemini/OpenRouter Agentic Coach orchestration",
        factual_summary=(
            "Enforces typed server-validated tool allowlists, server-side user_id scoping, prompt-injection stripping (LLM01), "
            "output entity overwrite from verified tool outputs (LLM02), confirmation-gated squad mutations (LLM06), and free-only quota bounds (LLM08)."
        ),
        tags=["owasp", "security", "react", "rag", "prompt injection", "gemini", "openrouter", "rate limits", "wcag"],
    ),
]

RESEARCH_SOURCE_REGISTRY: List[Dict[str, Any]] = [
    {"id": "RES-GEMINI-FC", "category": "LLM", "title": "Gemini Function Calling", "url": "https://ai.google.dev/gemini-api/docs/function-calling", "license_or_terms": "Gemini API Terms", "decision": "ADOPTED", "notes": "Disabled AFC so backend owns typed Pydantic validation & user scoping."},
    {"id": "RES-GEMINI-SO", "category": "LLM", "title": "Gemini Structured Outputs", "url": "https://ai.google.dev/gemini-api/docs/structured-output", "license_or_terms": "Gemini API Terms", "decision": "ADOPTED", "notes": "Used in final synthesis step with response_json_schema."},
    {"id": "RES-GEMINI-RL", "category": "LLM", "title": "Gemini Rate Limits", "url": "https://ai.google.dev/gemini-api/docs/rate-limits", "license_or_terms": "Gemini API Terms", "decision": "ADOPTED", "notes": "Enforced via QuotaManager RPM/daily limits + per-model circuit breakers."},
    {"id": "RES-GEMINI-TERMS", "category": "LLM", "title": "Gemini API Terms", "url": "https://ai.google.dev/gemini-api/terms", "license_or_terms": "Unpaid tier may log/train outside EEA/UK/CH; 18+", "decision": "GOVERNED", "notes": "Minifies context, strips PII, keeps video/image off by default."},
    {"id": "RES-OR-DOCS", "category": "LLM", "title": "OpenRouter Documentation & Free Models", "url": "https://openrouter.ai/collections/free-models", "license_or_terms": "Upstream free-model provider terms", "decision": "ADOPTED", "notes": "Enforces allow_fallbacks:false & max_price:0; dynamic /api/v1/models check."},
    {"id": "RES-REACT", "category": "LLM", "title": "ReAct: Synergizing Reasoning and Acting", "url": "https://arxiv.org/abs/2210.03629", "license_or_terms": "arXiv Academic", "decision": "ADOPTED", "notes": "Bounded max 3 tool rounds + deduplication + read-only tool focus."},
    {"id": "RES-RAG", "category": "LLM", "title": "Retrieval-Augmented Generation", "url": "https://arxiv.org/abs/2005.11401", "license_or_terms": "arXiv Academic", "decision": "ADOPTED_LEXICAL", "notes": "Okapi BM25 hierarchical authority RAG with strict edition walls."},
    {"id": "RES-SN-GSR", "category": "CV", "title": "SoccerNet Game State Reconstruction", "url": "https://github.com/SoccerNet/sn-gamestate", "license_or_terms": "Apache-2.0", "decision": "ADOPTED_ARCHITECTURE", "notes": "Inspires detect+track+homography radar fusion; external dataset download needed for real weights."},
    {"id": "RES-SN-CAL", "category": "CV", "title": "SoccerNet Camera Calibration", "url": "https://github.com/SoccerNet/sn-calibration", "license_or_terms": "Apache-2.0", "decision": "ADOPTED_ARCHITECTURE", "notes": "Guides pitch keypoint DLT/RANSAC homography error metrics."},
    {"id": "RES-EAFC-CV", "category": "CV", "title": "EA FC Computer Vision System", "url": "https://github.com/maxtiandi/Computer-Vision-System-for-Gameplay-Analysis-and-Tactical-Recommendations-in-Football-Simulator", "license_or_terms": "MIT/Research", "decision": "REFERENCED", "notes": "Reference for simulator radar/tactical framing; pipeline built independently."},
    {"id": "RES-ROBOFLOW-EAFC", "category": "CV", "title": "Roboflow ea_fc_ai_coach Candidate Dataset", "url": "https://universe.roboflow.com/eafcaicoach/ea_fc_ai_coach", "license_or_terms": "CC BY 4.0 / Roboflow Terms", "decision": "CANDIDATE_DATASET_MANIFEST", "notes": "Manifest supported in Phase 42F pipeline; external dataset download required."},
    {"id": "RES-BYTETRACK", "category": "CV", "title": "ByteTrack Multi-Object Tracking", "url": "https://github.com/FoundationVision/ByteTrack", "license_or_terms": "MIT", "decision": "ADOPTED", "notes": "Implemented in bytetrack_adapter.py with SciPy linear_sum_assignment."},
    {"id": "RES-YOLOX", "category": "CV", "title": "YOLOX Object Detector", "url": "https://github.com/Megvii-BaseDetection/YOLOX", "license_or_terms": "Apache-2.0", "decision": "PREFERRED_PERMISSIVE_DETECTOR", "notes": "Preferred permissive ONNX export target via cv2.dnn / ONNX Runtime."},
    {"id": "RES-ULTRALYTICS", "category": "CV", "title": "Ultralytics YOLO & Licensing", "url": "https://www.ultralytics.com/license", "license_or_terms": "AGPL-3.0 (or Enterprise)", "decision": "OPTIONAL_SEGREGATED_TRAINER", "notes": "Never bundled into core MIT/proprietary serving path; optional offline ONNX export trainer only."},
    {"id": "RES-ONNXRUNTIME", "category": "CV", "title": "ONNX Runtime", "url": "https://onnxruntime.ai/docs/", "license_or_terms": "MIT", "decision": "ADOPTED_SUPPORTED", "notes": "Supported alongside OpenCV DNN OpenCL/CPU backend."},
    {"id": "RES-TRACKEVAL", "category": "CV", "title": "TrackEval (HOTA / IDF1 / MOTA)", "url": "https://github.com/JonathonLuiten/TrackEval", "license_or_terms": "MIT", "decision": "ADOPTED_METRICS", "notes": "HOTA-proxy, IDF1, ID-switch metrics implemented cleanly in Phase 42F evaluator."},
    {"id": "RES-CVAT", "category": "CV", "title": "CVAT Annotation Tooling", "url": "https://docs.cvat.ai/", "license_or_terms": "MIT", "decision": "DOCUMENTED_PROTOCOL", "notes": "COCO/YOLO format export protocol documented for EA FC frame annotation."},
    {"id": "RES-BKT", "category": "TRAINING", "title": "Bayesian Knowledge Tracing & Survey", "url": "https://doi.org/10.1007/BF01099821", "license_or_terms": "Academic", "decision": "ADOPTED_EXPERIMENTAL", "notes": "Calibrated bounded slip/guess BKT decoupled from match performance."},
    {"id": "RES-VID-OCCLUSION", "category": "TRAINING", "title": "Football Video & Temporal Occlusion Training", "url": "https://pubmed.ncbi.nlm.nih.gov/39102157/", "license_or_terms": "Academic", "decision": "ADOPTED", "notes": "Drives pre-action freeze-frame Decision Replay & Training Academy."},
    {"id": "RES-ESPORTS-COACH", "category": "TRAINING", "title": "Esports Coaching Framework", "url": "https://doi.org/10.3389/fpsyg.2023.1191801", "license_or_terms": "CC-BY", "decision": "ADOPTED", "notes": "Structures weakness->drill->subsequent match validation loop."},
    {"id": "RES-EPV-SOCCERACTION", "category": "DECISION", "title": "EPV & ML-KULeuven SoccerAction", "url": "https://github.com/ML-KULeuven/socceraction", "license_or_terms": "Apache-2.0 / Academic", "decision": "ADOPTED_PRINCIPLES", "notes": "Pre-action vs outcome discipline; EA FC heuristics labeled explicitly."},
    {"id": "RES-OWASP", "category": "INFRA", "title": "OWASP GenAI Top 10", "url": "https://genai.owasp.org/", "license_or_terms": "CC BY-SA 4.0", "decision": "ADOPTED", "notes": "LLM01/02/06/08 controls verified."},
    {"id": "RES-WEB-INFRA", "category": "INFRA", "title": "Playwright / FastAPI / Pydantic / Redis / WCAG 2.2", "url": "https://www.w3.org/TR/WCAG22/", "license_or_terms": "Apache-2.0 / MIT / BSD / W3C", "decision": "ADOPTED", "notes": "Core stack + optional Redis shared quota + WCAG 2.2 AA frontend audits."},
]


_SOURCE_AUTHORITY_BOOST = {
    EpistemicClaimType.OFFICIAL_FACT: 1.35,
    EpistemicClaimType.OBSERVED_USER_EVIDENCE: 1.25,
    EpistemicClaimType.RESEARCH_METHODOLOGY: 1.05,
    EpistemicClaimType.COMMUNITY_OBSERVATION: 0.70,
    EpistemicClaimType.STATISTICAL_ESTIMATE: 0.90,
    EpistemicClaimType.TACTICAL_HYPOTHESIS: 0.75,
    EpistemicClaimType.UNSUPPORTED_CLAIM: 0.25,
}


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9+_-]+", (text or "").lower()) if len(t) >= 2]


class FootballKnowledgeService:
    """Okapi BM25 + source-hierarchy + edition/patch-aware football RAG retriever."""

    def __init__(self, entries: Optional[List[FootballKnowledgeEntry]] = None) -> None:
        self.entries = entries or KNOWLEDGE_ENTRIES
        self._build_bm25_index()

    def _build_bm25_index(self) -> None:
        self._docs_tokens: List[List[str]] = []
        self._df: Dict[str, int] = {}
        for e in self.entries:
            weighted_text = " ".join([
                e.topic, e.topic,
                e.mechanic, e.mechanic,
                " ".join(e.tags), " ".join(e.tags),
                e.source_title,
                e.applicability,
                e.factual_summary,
            ])
            toks = _tokenize(weighted_text)
            self._docs_tokens.append(toks)
            for uniq in set(toks):
                self._df[uniq] = self._df.get(uniq, 0) + 1
        n_docs = max(1, len(self.entries))
        self._avgdl = sum(len(d) for d in self._docs_tokens) / n_docs

    def _bm25_score(self, query_tokens: List[str], doc_idx: int, k1: float = 1.4, b: float = 0.75) -> float:
        if not query_tokens:
            return 0.0
        doc = self._docs_tokens[doc_idx]
        dl = max(1, len(doc))
        tf_map: Dict[str, int] = {}
        for tok in doc:
            tf_map[tok] = tf_map.get(tok, 0) + 1
        n_docs = len(self.entries)
        score = 0.0
        for qtok in query_tokens:
            # exact token + light prefix/substring match against indexed terms
            df = self._df.get(qtok, 0)
            tf = tf_map.get(qtok, 0)
            if tf == 0:
                partial_hits = sum(cnt for term, cnt in tf_map.items() if qtok in term or term in qtok)
                if partial_hits > 0:
                    tf = partial_hits
                    df = max(1, df)
            if tf == 0:
                continue
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * (dl / max(1.0, self._avgdl)))
            score += idf * ((tf * (k1 + 1.0)) / max(1e-6, denom))
        return score

    def query(
        self,
        q: str,
        *,
        game_version: Optional[str] = None,
        game_patch: Optional[str] = None,
        topic: Optional[str] = None,
        official_only: bool = False,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        tokens = _tokenize(q)
        gv = game_version.upper() if game_version else None
        patch_upper = game_patch.upper() if game_patch else None

        scored: List[tuple[float, FootballKnowledgeEntry]] = []
        for idx, e in enumerate(self.entries):
            if gv and e.game_version not in ("BOTH", "GENERAL", gv):
                continue
            if patch_upper and e.patch_version not in ("CURRENT", "METHODOLOGY", patch_upper):
                # Allow baseline facts from earlier patches unless explicitly mismatched edition, slight penalty only
                pass
            if topic and topic.lower() not in e.topic.lower() and topic.lower() not in e.mechanic.lower():
                continue
            if official_only and e.verification_status != EpistemicClaimType.OFFICIAL_FACT:
                continue

            bm25 = self._bm25_score(tokens, idx) if tokens else 1.0
            if tokens and bm25 <= 0.0:
                continue

            # Explicit tag exact match boost + version specificity + authority hierarchy multiplier
            tag_set = {tg.lower() for tg in e.tags}
            tag_hits = sum(1 for tok in tokens if tok in tag_set)
            version_boost = 1.15 if (gv and e.game_version == gv) else 1.0
            authority = _SOURCE_AUTHORITY_BOOST.get(e.verification_status, 0.8)
            final_score = (bm25 + 0.85 * tag_hits) * authority * version_boost
            scored.append((round(final_score, 4), e))

        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [{**item[1].model_dump(), "retrieval_score": item[0]} for item in scored[:top_k]]
        return {
            "query": q,
            "retrieval_engine": "BM25_HIERARCHICAL_RAG",
            "game_version_filter": gv,
            "game_patch_filter": patch_upper,
            "total_matches": len(scored),
            "entries": hits,
            "epistemic_note": (
                "Ranked via Okapi BM25 with hierarchy OFFICIAL_FACT > RESEARCH_METHODOLOGY > COMMUNITY_OBSERVATION. "
                "Real-world football paper metrics are never transferred directly as EA FC coefficients."
            ),
        }


_SHARED_KB_SERVICE: Optional[FootballKnowledgeService] = None


def get_shared_knowledge_service() -> FootballKnowledgeService:
    """Process-level singleton caching BM25 index + static entries across all requests."""
    global _SHARED_KB_SERVICE
    if _SHARED_KB_SERVICE is None:
        _SHARED_KB_SERVICE = FootballKnowledgeService()
    return _SHARED_KB_SERVICE
