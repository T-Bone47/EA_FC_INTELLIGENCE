# Defensive API review

Reviewed the changed boundaries against the [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).

| Area | Evidence and residual risk |
|---|---|
| Object authorization | V3 now refuses non-null squad context at validation. Legacy V2 routes are disabled in production-like environments. The existing squad repository scopes lookup to authenticated owner. |
| Validation and disclosure | V3 uses strict Pydantic schemas. Generic server failures return a generic message and request ID. SPA fallback is constrained to its build directory. Route-level runtime evidence is pending. |
| Source isolation | Reference resolution checks the exact registered version and data approval on every request. Engine input checks reject wrong scopes and synthetic or otherwise inadmissible candidates. FC27 research cards remain quarantined. |
| Resource use | The API applies a per-worker shared default rate limit. Recommendation and what-if cost, exclusion response size, proxy identity and multiworker behavior remain unverified. |
| Other API surfaces | Player lookup, card lookup, auth, and squad endpoints need a complete deployment-level exposure and authorization review. The recommendation licence fix alone is not certification for those routes. |
