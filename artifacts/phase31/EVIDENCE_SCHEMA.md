# Evidence contract v1

Migration 014 creates local research tables under `fc27_staging`. Each observation stores a research cohort version, the pinned FC27 source snapshot, exact source item ID, stable item UUID, evidence type, source registry key, submitter, consent, timestamp and typed JSON payload. The source item FK prevents dangling attachments. Base identification appears via the cohort record. The candidate ratings ID is a cross-reference and confirmed base ID remains null.

| Evidence category | Inputs and use |
| --- | --- |
| Official game mechanic / official card attribute | Approved source links, game version and publication/retrieval metadata. Manual rating spot-checks are separate from submitted match reports. |
| Community opinion / creator observation | Original HTTPS permalink, source author, claim topic, stance and reviewer-written paraphrase. Source families and copied text are grouped before agreement reporting. |
| Owner recorded / user submitted match | Optional patch and tactical context, match date, stable match key, minutes, platform, sample counts and anonymized confounders. Required provenance is the submitter’s attestation. |
| Controlled experiment | Same structured match fields plus explicit role, position, formation slot, protocol, session, setup, block, run order and source locator. Independent reviewer required for accepted controlled evidence. |
| Model prediction | Computed live through the existing V3.2 service and labelled by reference release. |
| Unverified claim | Contextual note with a citation and no weight in measured results. |

All reports start pending. The submitter can read private submissions and withdraw them. An administrator may approve or reject only records the submitter explicitly shared. The shared research read path includes accepted records only. The research gate also requires loopback and explicit opt-in. Raw evidence locators and context such as skill bracket or match key stay on authorized submission/review paths. No source URLs are fetched by the application.

A repeat with the same owner and identical data is idempotent. A conflicting report for the same match key rejects the whole batch. Across submitters, same-item match keys deduplicate. Conflicting values or context exclude that key from aggregation. Citation tracking normalizes tracking parameters and common video permalink shapes. The evaluator collapses source families and verbatim-equivalent notes, with conservative grouping for unverified origin. Semantic paraphrase copying still needs reviewer judgment.

Null fields remain null. The UI annotates exact patch, other patch and unknown patch evidence. An accepted note or report denotes local review, with no automatic claim of publisher accuracy, experiment validity or permission to republish.
