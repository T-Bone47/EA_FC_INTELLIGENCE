# Outreach package — FUT-DB.com

- **Project**: EA FC Player Intelligence — contextual FC26 card recommendation
- **Intended use**: read FC26 card attributes, PlayStyles, Roles, positions, club/league/nation, and (if permitted) prices; normalize into our canonical card model; compute demand-weighted contextual scores; serve ranked recommendations to end users
- **Fields required**: card_id, player_id, game_version, card_version, card_type, overall, positions, attributes, PlayStyles, PlayStyle+, Roles, club, league, nation; price is optional
- **Expected request volume**: full-catalogue sync initially (estimated low thousands of cards), then incremental updates on a daily-or-slower cadence — not high-frequency polling
- **Storage**: normalized records in our own PostgreSQL database, retained per whatever retention limit you require
- **Derived-data use**: demand-weighted contextual capability scores; no raw-field redisplay beyond what's needed to label a recommendation
- **User-facing display**: card name, position, attributes, PlayStyles, Roles, card type/version — the same information a card's own in-game screen shows
- **Commercial status**: consumer product, monetization model not yet finalized (free or freemium)
- **Attribution plan**: open to your preferred form — footer credit, per-card "data via FUT-DB.com" label, or another format you specify
- **Retention/deletion policy**: will delete stored data and disable derived features within 30 days of any termination notice, or per your required timeline
- **Technical architecture**: source adapter → raw observation → validation → normalization → canonical card → field-level provenance → conflict detection → publication gate (all already built and tested against synthetic fixtures; see `backend/services/card_publication_gate.py`)
- **Specific open question**: your Terms Section 7 prohibits reproduction/distribution/modification of your content without permission. We do not need to redistribute your raw dataset — only serve derived recommendation scores. Does Section 7 extend to that, or is a separate clarification needed?

Rights questionnaire attached: `FC26_DATA_PROVIDER_RIGHTS_QUESTIONNAIRE.md`
