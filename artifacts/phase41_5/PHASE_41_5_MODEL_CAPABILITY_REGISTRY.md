# Phase 41.5 Model Capability Registry & Live Discovery Audit

**Discovery Implementation:** [registry.py](../../backend/services/llm/registry.py) (`ModelCapabilityRegistry`)  
**Catalog Refresh Interval:** `AI_COACH_CATALOG_REFRESH_SECONDS = 1800` (30 minutes TTL cache; never re-downloads catalogs per user query).

---

## 1. Gemini API Verified Catalog Snapshot (Live `2026-11-25`)

Endpoint: `GET https://generativelanguage.googleapis.com/v1beta/models` (**HTTP 200**, 65 models listed).

| Model ID | Free-Tier Status | Context In / Out | Capabilities | Routing Status |
| :--- | :--- | :--- | :--- | :--- |
| `gemini-4-hydrogen` | Free-tier eligible | `1,048,576` / `65,536` | Text, image, tools, structured JSON, reasoning | **Configured Primary Default** (`GEMINI_MODEL`) |
| `gemini-3.8-flash` | Free-tier eligible | `1,048,576` / `65,536` | Text, image, tools, structured JSON, reasoning | **Secondary Fast Gemini Fallback** |
| `gemini-3.6-flash` | Free-tier eligible | `1,048,576` / `65,536` | Text, image, tools, structured JSON | Eligible Free Fallback |
| `gemma-4-26b-a4b-it`, `gemma-4-31b-it` | Free-tier eligible | `262,144` / `32,768` | Text, image, countTokens | Eligible (non-tool text tasks) |
| `gemini-4-argon`, `gemini-4-carbon`, `gemini-2.5-pro`, `gemini-3.1-pro-preview`, `*-tts`, `*-image` | Paid / Specialized quota | Varies | Paid Pro or Media Gen | **BLOCKED** by `FreeUsageGuard` under `AI_COACH_FREE_ONLY=true` |
| `gemini-2.5-flash` | Deprecated for new accounts (`404 NOT_FOUND` observed in live probe) | — | — | Automatically pruned by `registry.mark_unavailable()` |

---

## 2. OpenRouter Verified Free Catalog Snapshot (Live `2026-11-25`)

Endpoint: `GET https://openrouter.ai/api/v1/models` (**HTTP 200**, 472 total models; **14 zero-priced endpoints**).  
Account key check `GET https://openrouter.ai/api/v1/key` confirmed `is_free_tier: true`, `usage: 0`.

| OpenRouter Model ID | Context | Modalities | Tools | Structured Out | Prompt / Completion Price | Routing Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `openrouter/free` | `200,000` | `text`, `image` | Yes | Yes | `$0` / `$0` | **Default OpenRouter Router** |
| `nvidia/nemotron-3.5-super-vl:free` | `1,000,000` | `text`, `image`, `video` | Yes | Yes | `$0` / `$0` | Priority Multimodal / Tactical Model |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | `1,000,000` | `text` | Yes | Partial | `$0` / `$0` | Deep Reasoning Fallback |
| `nvidia/nemotron-3.5-lightning:free` | `1,000,000` | `text` | Yes | No | `$0` / `$0` | Low-Latency Fallback |
| `baidu/ernie-5.5-flash-preview:free` | `1,024,000` | `text` | Yes | Yes | `$0` / `$0` | Tool + Structured Output Fallback |
| `google/gemma-4-26b-a4b-it:free` | `262,144` | `text`, `image`, `video` | Yes | `response_format` | `$0` / `$0` | Multimodal / General Fallback |
| `google/gemma-4-31b-it:free` | `262,144` | `text`, `image`, `video` | Yes | `response_format` | `$0` / `$0` | Eligible Free Model |
| `inclusionai/ling-3.2-flash:free` | `1,048,576` | `text`, `image` | Yes | Yes | `$0` / `$0` | Eligible Free Model |
| `particle-ai/particle-1:free` | `1,048,576` | `text`, `image` | Yes | Yes | `$0` / `$0` | Eligible Free Model |
| `google/lyria-3-pro-preview`, `google/lyria-3-clip-preview` | `1,048,576` | `text`, `image` | **No** | `response_format` | `$0` / `$0` | Excluded from tool-calling chat (`supports_tools=False` & missing `:free` suffix) |
