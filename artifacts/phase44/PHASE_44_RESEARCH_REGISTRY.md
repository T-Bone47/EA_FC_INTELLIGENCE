# Phase 44 Research Registry & Methodological Adoption Log

All external academic, open-source, statistical, optimization, and EA SPORTS FC Pro esports references are registered cleanly in `RESEARCH_SOURCE_REGISTRY` (`backend/services/football_knowledge_service.py`) and queryable via `GET /api/phase40/research-registry` and BM25 RAG (`GET /api/phase40/knowledge`).

## Groups Added / Extended for Phase 44
- **Group A — Playing-Style Identification:**
  - PMC10443261 Systematic Review (`RES-STYLE-REV-PMC`) -> `ADOPTED_FEATURE_PRINCIPLES`
  - SAGE 2025 Team Sports Style Identification (`RES-STYLE-REV-SAGE`) -> `ADOPTED_METHODOLOGY`
  - Swartz Individual Playing Styles (`RES-SWARTZ-STYLE`) -> `ADOPTED_SIMILARITY_PRINCIPLES`
  - JQAS 2025 Topic Modeling (`RES-STYLE-TOPIC`) -> `ADOPTED_CONCEPTS`
- **Group B — Tactical Structure & Contextual Behaviour:**
  - Frontiers 2024 Tactical Formation Principles (`RES-FORM-PRINCIPLES`) -> `ADOPTED`
  - SAGE 2026 Same Formation, Different Styles (`RES-SAME-FORM-STYLES`) -> `ADOPTED`
  - Plus existing `RES-EPV-PAPER`, `RES-EPV-SOCCERACTION`, `RES-FOT-TRACKING` (`real-world coefficients never transferred into EA FC`).
- **Group C — Machine Learning & Similarity Models:**
  - Scikit-learn Clustering, Neighbors, Decomposition (PCA), GMM & GroupKFold (`RES-SKLEARN-STYLE`) -> `ADOPTED`
  - SciPy Spatial Distances & Wasserstein Distance (`RES-SCIPY-DIST`) -> `ADOPTED`
  - UMAP & metric-learn (`RES-UMAP-HDBSCAN-NOTE`) -> `REFERENCED_NOT_INSTALLED` (UMAP never treated as proof of cluster validity; `umap`, `hdbscan`, `metric_learn` verified absent locally).
- **Group D — Official Esports Reference Governance:**
  - EA SPORTS FC Pro & Official FC Pro 26/27 Rules (`RES-EA-FCPRO`) -> `METADATA_AND_GOVERNANCE_ONLY`
  - `@EASPORTSFCPro` & Google YouTube API Developer Policies (`RES-YT-POLICIES`) -> `STRICT_COMPLIANCE_BLOCK` (public stream visibility does NOT grant extraction, training, or redistribution rights).
