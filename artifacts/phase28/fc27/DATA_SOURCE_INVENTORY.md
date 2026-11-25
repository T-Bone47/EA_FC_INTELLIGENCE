# FC27 data source inventory

| File | CSV records | Fields | Use |
| --- | ---: | ---: | --- |
| archive (3).zip | 19,789 | 60 | Existing local FC27 player snapshot |
| EA_FC_ANALYSIS-main.zip | 19,789 | 60 | Equivalent player snapshot after date normalization |
| archive (4).zip | 10,762 | 71 | October item and base-ID staging observations |
| archive (5).zip | 9,962 | 55 | Card item staging observations with identity review |

The file manifest pins ZIP and CSV SHA-256 hashes, source keys, claimed dates, rights states and usage scope. Source A carries men's and women's divisions and 2,204 goalkeepers. No height or weight values are published in source A. Source B and C are preserved by independent source keys and never enrich the live player reference.

From the repository root with the four supplied input archives in one directory:

```sh
python scripts/stage_fc27_evidence.py /path/to/inputs --received 2026-11-23 --out /new/report/directory
```

For private PostgreSQL staging, apply tracked migrations with `scripts/setup_database.py`, use a disposable loopback database with `ENVIRONMENT=test`, and add `--stage`. A second run with a different report directory checks idempotence. On a clean staging schema, `--verify-rollback` exercises all writes and rolls back. The new schema has no public HTTP route.

For the existing FC27 player universe, use the pinned research archive specified by `data/fc27_research/MANIFEST.json` and the existing research source and ingestion scripts. Re-running ingestion enrolls the accepted rows in the exact research release. This record remains separate from all card staging.

To inspect the ledger and review queue from the local database:

```sql
SELECT snapshot_id, source_id, manifest
FROM fc27_staging.snapshot ORDER BY source_id;
SELECT snapshot_id, record_id, identity_review
FROM fc27_staging.observation
WHERE identity_review->>'status' IN ('CONFLICTED', 'AMBIGUOUS')
ORDER BY snapshot_id, source_row_number;
```
