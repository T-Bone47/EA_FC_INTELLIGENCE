# Recommendation refresh and performance

| Capability | Observed design |
|---|---|
| Recommendation, comparison, what-if | ON_DEMAND HTTP requests. The React UI renders response values. |
| On-screen refresh | ON_DEMAND. New database data only reaches the screen after a new request. |
| Reference distribution | STATIC_SNAPSHOT loaded by version and cached per process. Reference publication requires versioned rollout. |
| Candidate cache | ON_DEMAND watermarks and 120-second TTL. Migration 010 increments a shared generation as changed inputs commit. |
| Live stream, periodic polling or background refresh | NOT_IMPLEMENTED. |

Before Phase 26 the watermark followed only the parent player table. An attribute, affiliation or PlayStyle write could leave a worker serving an older candidate pool. With migration 010 each recommender checks the committed generation per load. The staged DB test covers rollback and cache miss across two repository instances on the next load. A DB service was unavailable, so commit-to-API-to-render delay, restart, recovery and database load are unmeasured.

Offline FC26 scoring and explanation timings are in PERFORMANCE_RESULTS.json. The previous 786 KB raw and 145 KB compressed CM response is historical. Payload budgets, gateway limits and a latency target require live measurements and an owner decision. Gzip and the existing exclusion contract remain in effect.
