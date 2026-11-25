# PHASE 20 SOURCE FORENSICS

Full machine-readable data: `artifacts/phase20/source_registry.json` (7 sources).

## What changed since the original data-forensics session

Three items were re-verified or newly investigated this session, with fresh evidence (dates below), rather than carried forward from memory:

### 1. FUTBIN — re-verified, evidence strengthened
Prior finding: ToS prohibits data mining/scraping without written permission.
**New this session**: direct fetch of `futbin.com/tos` (dated Feb 24, 2026) also contains an explicit, separate clause: *"No business use allowed without permission. You must not use any of the materials on our Website for business purposes without obtaining a license."* This is a second, independent basis for RED, distinct from the anti-scraping clause. **Classification unchanged: RED. Confidence: HIGH → HIGH (strengthened).**

### 2. FutDB (futdb.app) — downgraded from YELLOW to UNKNOWN
Prior finding: the most promising candidate, classified YELLOW pending legal review, based on it having a documented, metered API.
**New this session**: fetched `futdb.app` directly. **There is no terms-of-service, license, or legal-usage page anywhere on the site** — no `/terms`, `/tos`, `/license`, or `/privacy` link on the homepage. The site is pricing/marketing copy only ("Free to use for everyone", tiered pricing by request volume). A commercial API with no published legal terms cannot be responsibly classified YELLOW ("some use permitted, pending review") — there is no document describing what is permitted. **Classification changed: YELLOW → UNKNOWN. Since UNKNOWN behaves as RED for production per this phase's own rule, this is a downgrade, not an upgrade, on closer inspection.**

### 3. FUT-DB.com — new source discovered, distinct from FutDB.app
While searching for FutDB's terms, found a second, differently-hyphenated service, `fut-db.com` (T&C hosted at `futdb.digitalsable.com/terms`, operated by an individual, Nikita Loges), which is easily confused with `futdb.app` under casual research. Its terms explicitly permit use "by individuals and companies" — more permissive language than FUTBIN/FUT.GG — but the terms are standard SaaS payment/termination/GDPR terms, **not an IP or data license**: they say nothing about storage, derivative-data creation, or redistribution rights. "You may use our API" is not "you may store, derive from, and serve this data in your own product." **Classification: UNKNOWN**, pending a direct written clarification of those specific rights.

### 4. FUTWIZ — attempted resolution, remains genuinely unresolved
Two independent search attempts (this session and the prior data-forensics session) did not locate FUTWIZ's actual terms-of-service text. **Classification: UNKNOWN** (honestly reported as unresolved, not guessed). Per the mandate's own rule, this behaves as RED for production.

### Unchanged, carried forward with high confidence
- **EA FC Community API**: verified directly from EA's own Pitch Notes (checked prior session, not expected to change within days); partner programme closed to new applicants, scope is user account data not the card universe. RED/BLOCKED.
- **FUT.GG**: verified prior session (ToS bars "any robot, spider, scraper, crawler... for any purpose"); not re-fetched this session since the wording found was unambiguous and unlikely to have changed materially in days. RED.
- **EA Ratings website**: player-level only, no FUT card data at any legal status regardless of terms.

## Net effect on the acquisition question

No source improved to GREEN or a confirmed-actionable YELLOW this session. If anything, closer inspection **removed** the one candidate previously carrying the most optimism (FutDB), because "has a metered API and a pricing page" turned out not to mean "has published legal terms." This is reported plainly rather than smoothed over.
