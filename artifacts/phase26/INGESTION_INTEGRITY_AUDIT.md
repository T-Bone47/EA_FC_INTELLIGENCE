# FC27 package integrity

The supplied card audit ZIP contains audit evidence. The raw bytes under data/fc27_research are the separate player-ratings snapshot and cannot validate the card package.

The card importer requires a maintainer-reviewed permission record and a hash-pinned permission document outside the package. It checks a private copy against approved file hashes, record counts, snapshot IDs and package version. The parser rejects missing raw files, duplicate identities, contradictory slugs and absent URLs on either side of duplicate records. Legacy CLI approval flags identify the operator. An approval record is still required. The source registry remains NOT_PERMITTED for futgg.

Migration 009 has uniqueness keys shared by snapshots. The importer serializes snapshot admission and refuses replacement or merging of a differently fingerprinted snapshot. For a validated replay it reconciles counts by snapshot before commit. An existing pre-Phase-26 snapshot with no approved hash is preserved and refused on replay. New card rows leave links unresolved until reviewed. Historical research rows are preserved.

Local regressions cover pre-DB refusal and package structure. The complete card package, approval record and disposable PostgreSQL were unavailable for an approved ingest, rollback or rerun.

## Approval record shape

The maintainer must enter source, scope, reviewer, applicable_terms, review_date,
expires, snapshot_id, permission_file, permission_sha256 and files in
data/approvals/fc27_card_identity.json. The scope is
FC27_CARD_IDENTITY_RESEARCH_ONLY. permission_file is relative to that directory.
The files object maps package-relative names to SHA-256 and CSV row counts.
The permission and approved inventory must come from a reviewed source outside
the package. A hash establishes which bytes were reviewed.
