# PHASE 40H: Unified Squad Lab Integration

**Backend Endpoint:** `POST /api/phase40/squad-intelligence/analyze` ([phase40_coach.py](../../backend/api/routes/phase40_coach.py))  
**Frontend Workspace:** `Personal Coach & Fit` tab inside [CardSquadLab.tsx](../../frontend/src/pages/CardSquadLab.tsx)

## 1. Personalized Squad Questions Answered
1. **How well does this XI suit my football?** Evaluates active XI alignment against observed Gamer DNA archetype (`PERSONALIZED` vs honest `STATIC_ONLY` fallback).
2. **Which roles complement my style?** Surfaces tailored FC IQ roles (`Holding`, `Box-to-Box`, `Playmaker`, `Defender`) mapped from style/proficiency balance.
3. **Which positions cause structural problems?** Links recurring gameplay mistakes (e.g., `EXPOSED_CENTRAL_CHANNEL`, `UNNECESSARY_CB_DISPLACEMENT`) directly to occupied squad slots and video clip references.
4. **What free / zero-coin improvements exist?** Prioritizes FC IQ instruction, width, depth, and formation fixes before card upgrades.
5. **Which budget-compatible upgrades address bottlenecks?** Queries canonical PG catalogue filtered for positional eligibility and duplicate footballer prevention (`duplicate_errors`).
6. **Counterfactual Squad Comparisons:** Compares formation/role switches (`0` coin cost) and single-slot upgrades with explicit uncertainty note (`"Tactical compatibility estimate; not a match win-rate guarantee"`).
