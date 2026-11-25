# Architecture gaps at the Phase 27 checkpoint

| Boundary | Current path | Gap |
|---|---|---|
| Dataset release to reads | data_license_gate → API dependencies → PostgreSQL | A verified release could authorize other canonical same-version rows. Membership, observation and exact-row checks are required. |
| Formation to score | formations → demand_composition | V3 scoring supports slot emphasis but lacks a slot request path. |
| Recommendation to feedback | POST feedback → FeedbackRepository | Release scope and a server-recorded recommendation origin are needed before training. |
| Squad to V3 | SquadRepository → legacy context | V3 scoring and explanations must carry the slot context to evaluation and replacement. |
| Card to chemistry and value | isolated card/price/rule tables | Published data, legal scope and verified version/observation are unavailable. |
| Local evidence to certification | Windows DB/browser → evidence bundle | Hosted CI, complete browser checks, load and calibration decisions are pending. |
