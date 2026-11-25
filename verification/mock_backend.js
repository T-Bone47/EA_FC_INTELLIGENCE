const http = require('http');

const mockSynergy = {
  formation: '4-3-3',
  tactical_profile: 'HIGH_PRESS',
  experimental_tactical_alignment: {
    alignment_index_pct: 75.9,
    status: 'MODERATE_ALIGNMENT',
    status_convention: 'Explicit model convention: HIGH (>=82.0%), MODERATE (72.0-81.9%), PARTIAL (60.0-71.9%), DISSONANCE (<60.0%).',
    mean_suitability: 0.8255,
    suitability_dispersion: 0.0430,
    friction_penalty: 0.0500,
    active_friction_count: 2,
    scored_slots_count: 10,
    total_slots_count: 11,
    unscored_slots: ['GK']
  },
  channels: {
    LEFT_FLANK: {
      name: 'Left Flank Unit',
      slots: ['LB', 'LCM', 'LW'],
      scored_count: 3,
      unscored_slots: [],
      mean_suitability: 0.8643,
      status: 'HIGH_CONTROL',
      contributing_items: [
        { slot: 'LB', player_name: 'Nuno Mendes', score: 0.8686 },
        { slot: 'LCM', player_name: 'Alexia Putellas', score: 0.8841 },
        { slot: 'LW', player_name: 'Vinícius Jr.', score: 0.8402 }
      ]
    },
    CENTRAL_SPINE: {
      name: 'Central Spine Unit',
      slots: ['GK', 'LCB', 'RCB', 'CDM', 'ST'],
      scored_count: 4,
      unscored_slots: ['GK'],
      mean_suitability: 0.8015,
      status: 'SOLID_PIVOT',
      contributing_items: [
        { slot: 'GK', player_name: 'Thibaut Courtois', score: null },
        { slot: 'LCB', player_name: 'Virgil van Dijk', score: 0.8124 },
        { slot: 'RCB', player_name: 'Gabriel Magalhães', score: 0.7686 },
        { slot: 'CDM', player_name: 'Rodrigo (Rodri)', score: 0.7932 },
        { slot: 'ST', player_name: 'Kylian Mbappé', score: 0.8319 }
      ]
    },
    RIGHT_FLANK: {
      name: 'Right Flank Unit',
      slots: ['RB', 'RCM', 'RW'],
      scored_count: 3,
      unscored_slots: [],
      mean_suitability: 0.8327,
      status: 'EXPLOSIVE_TRANSITION',
      contributing_items: [
        { slot: 'RB', player_name: 'Achraf Hakimi', score: 0.8210 },
        { slot: 'RCM', player_name: 'Aitana Bonmatí', score: 0.8490 },
        { slot: 'RW', player_name: 'Caroline Graham Hansen', score: 0.8281 }
      ]
    }
  },
  tactical_friction_alerts: [
    {
      rule_id: 'RULE-HP-FWD-DEF',
      rule_version: '1.0.0',
      slot: 'LW',
      position: 'LW',
      card_item_id: 'bb2ac9ee-59fe-59ff-ae8c-2592936aab60',
      card_name: 'Vinícius José de Oliveira Júnior',
      tactical_context: 'HIGH_PRESS',
      evaluated_capability: 'High-turnover defensive disruption',
      attribute_name: 'defending',
      attribute_value: 31,
      threshold: 40,
      evidence_classification: 'EMPIRICALLY_SUPPORTED',
      friction_penalty: 0.025,
      explanation: 'Forward defending attribute (31) is below 40, significantly reducing turnover winning rates in opponent third.',
      recommended_action: 'Deploy a pressing forward specialist or transition team tactical profile to COUNTER_ATTACK.',
      empirical_reference: 'Phase 33 Experiment 001: Dembélé (55 Def) produced +2.0 tackles/90 vs Mbappé (29 Def).'
    },
    {
      rule_id: 'RULE-HP-FWD-DEF',
      rule_version: '1.0.0',
      slot: 'ST',
      position: 'ST',
      card_item_id: '97aaac8f-1616-50a0-afea-fd8aeff337ce',
      card_name: 'Kylian Mbappé',
      tactical_context: 'HIGH_PRESS',
      evaluated_capability: 'High-turnover defensive disruption',
      attribute_name: 'defending',
      attribute_value: 29,
      threshold: 40,
      evidence_classification: 'EMPIRICALLY_SUPPORTED',
      friction_penalty: 0.025,
      explanation: 'Forward defending attribute (29) is below 40, significantly reducing turnover winning rates in opponent third.',
      recommended_action: 'Deploy a pressing forward specialist (e.g. Dembélé) or transition team tactical profile to COUNTER_ATTACK.',
      empirical_reference: 'Phase 33 Experiment 001: Dembélé (55 Def) produced +2.0 tackles/90 and +2.0 interceptions/90 vs Mbappé (29 Def).'
    }
  ]
};

const mockLineup = {
  filled: 11,
  scored: 10,
  total_fit: 8.2546,
  mean_coverage_scored: 0.95,
  footballer_uniqueness_verified: true,
  weakest_scored_slots: ['RCB', 'CDM', 'RB'],
  attribute_contributions: { pace: 34, shooting: 28, passing: 42, dribbling: 38, defending: 35, physicality: 30 },
  observed_playstyles: { 'Quick Step+': 2, 'Finesse Shot': 3, 'Incisive Pass+': 1 },
  unknown_playstyle_lists: 0,
  observed_outfield_attributes: {
    pace: { mean: 86.4, published: 10 },
    shooting: { mean: 81.2, published: 10 },
    passing: { mean: 83.7, published: 10 },
    dribbling: { mean: 85.1, published: 10 },
    defending: { mean: 68.3, published: 10 },
    physicality: { mean: 76.9, published: 10 }
  },
  attribute_suitability: [
    { attribute: 'passing', mean: 0.852, scored_slots: 10 },
    { attribute: 'dribbling', mean: 0.841, scored_slots: 10 }
  ],
  slots: [
    { slot: 'GK', item: { entity_id: 'gk-1', name: 'Thibaut Courtois', rarity: 'Gold Rare', source_item_id: 'COURTOIS-01' }, score: null, status: 'LOCKED_UNSCORED', reason: 'Insufficient goalkeeper item evidence' },
    { slot: 'LB', item: { entity_id: 'lb-1', name: 'Nuno Alexandre Tavares Mendes', rarity: 'Gold Rare', source_item_id: 'MENDES-01' }, score: 0.8686, status: 'SCORED', reason: null },
    { slot: 'LCB', item: { entity_id: 'cb-1', name: 'Virgil van Dijk', rarity: 'Gold Rare', source_item_id: 'VANDIJK-01' }, score: 0.8124, status: 'SCORED', reason: null },
    { slot: 'RCB', item: { entity_id: 'cb-2', name: 'Gabriel dos S. Magalhães', rarity: 'Gold Rare', source_item_id: 'GABRIEL-01' }, score: 0.7686, status: 'SCORED', reason: null },
    { slot: 'RB', item: { entity_id: 'rb-1', name: 'Achraf Hakimi', rarity: 'Gold Rare', source_item_id: 'HAKIMI-01' }, score: 0.8210, status: 'SCORED', reason: null },
    { slot: 'LCM', item: { entity_id: 'cm-1', name: 'Alexia Putellas Segura', rarity: 'Gold Rare', source_item_id: 'PUTELLAS-01' }, score: 0.8841, status: 'SCORED', reason: null },
    { slot: 'CDM', item: { entity_id: 'cdm-1', name: 'Rodrigo Hernández Cascante', rarity: 'Gold Rare', source_item_id: 'RODRI-01' }, score: 0.7932, status: 'SCORED', reason: null },
    { slot: 'RCM', item: { entity_id: 'cm-2', name: 'Aitana Bonmatí Conca', rarity: 'Gold Rare', source_item_id: 'BONMATI-01' }, score: 0.8490, status: 'SCORED', reason: null },
    { slot: 'LW', item: { entity_id: 'lw-1', name: 'Vinícius José de Oliveira Júnior', rarity: 'Gold Rare', source_item_id: 'VINI-01' }, score: 0.8402, status: 'SCORED', reason: null },
    { slot: 'ST', item: { entity_id: 'st-1', name: 'Kylian Mbappé', rarity: 'Gold Rare', source_item_id: 'MBAPPE-01' }, score: 0.8319, status: 'SCORED', reason: null },
    { slot: 'RW', item: { entity_id: 'rw-1', name: 'Caroline Graham Hansen', rarity: 'Gold Rare', source_item_id: 'HANSEN-01' }, score: 0.8281, status: 'SCORED', reason: null }
  ]
};

const mockEvalResult = {
  release_id: 'fc27-card-items-local-r1',
  model_version: '3.2.1',
  config_version: 'v3.2',
  solver_status: 'EXACT_OPTIMAL',
  pool_size: 16,
  admissible_items: 16,
  scope: 'SELECTED_RESEARCH_ITEMS',
  research_only: true,
  price: null,
  chemistry: null,
  current: mockLineup,
  optimized: mockLineup,
  tactical_synergy: {
    current: mockSynergy,
    optimized: mockSynergy
  },
  matrix: [],
  nondominated_generated_profiles: [],
  unavailable_profiles: {},
  upgrade_status: 'NO_IMPROVING_SOLUTION',
  upgrade_gain: null,
  upgrades: [],
  receipt: 'digest-phase34b-audit-certified-001'
};

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = req.url;
  console.log(`[Mock Backend] ${req.method} ${url}`);

  if (url.includes('/api/meta/game-versions')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify([{ code: 'FC27', name: 'EA SPORTS FC 27', active: true }]));
  } else if (url.includes('/api/v3/options')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      formations: {
        '4-3-3': [
          { slot: 'GK', position: 'GK', side: 'CENTER', duty: 'GOALKEEPER' },
          { slot: 'LB', position: 'LB', side: 'LEFT', duty: 'DEFENSE' },
          { slot: 'LCB', position: 'CB', side: 'LEFT', duty: 'DEFENSE' },
          { slot: 'RCB', position: 'CB', side: 'RIGHT', duty: 'DEFENSE' },
          { slot: 'RB', position: 'RB', side: 'RIGHT', duty: 'DEFENSE' },
          { slot: 'LCM', position: 'CM', side: 'LEFT', duty: 'MIDFIELD' },
          { slot: 'CDM', position: 'CDM', side: 'CENTER', duty: 'MIDFIELD' },
          { slot: 'RCM', position: 'CM', side: 'RIGHT', duty: 'MIDFIELD' },
          { slot: 'LW', position: 'LW', side: 'LEFT', duty: 'ATTACK' },
          { slot: 'ST', position: 'ST', side: 'CENTER', duty: 'ATTACK' },
          { slot: 'RW', position: 'RW', side: 'RIGHT', duty: 'ATTACK' }
        ]
      }
    }));
  } else if (url.includes('/api/meta/availability')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      database_status: 'CONNECTED',
      environment: 'local',
      versions: {
        FC27: {
          ut_card: {
            research: {
              status: 'RESEARCH_RELEASE_AVAILABLE',
              goalkeeper_reference_ready: true,
              record_count: 100
            }
          }
        }
      }
    }));
  } else if (url.includes('/api/auth/me')) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: 'Unauthenticated' }));
  } else if (url.includes('/api/research/videos')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify([
      {
        video_id: 'VID-001',
        source_url: 'https://www.youtube.com/watch?v=ivshwl8WrJA',
        platform: 'YOUTUBE',
        title: 'FC27 Full Game — PSG vs Real Madrid',
        creator_name: 'Krasi',
        publication_date: '2026-09-28',
        game_version: 'FC27',
        game_patch: 'PATCH_1.01',
        video_type: 'FULL_MATCH',
        duration_seconds: 1240,
        rights_status: 'PUBLIC_EMBED_ONLY',
        evidence_tier: 'TIER_B',
        exact_card_status: 'UNRESOLVED_STANDARD_CLUB',
        review_status: 'REGISTERED'
      },
      {
        video_id: 'VID-003',
        source_url: 'https://www.youtube.com/watch?v=ZmpMLe7wwjs',
        platform: 'YOUTUBE',
        title: 'FC27 Ultimate Team Gameplay & First Impressions',
        creator_name: 'Malfxction',
        publication_date: '2026-09-30',
        game_version: 'FC27',
        game_patch: 'PATCH_1.01',
        video_type: 'EDITED_MATCH',
        duration_seconds: 940,
        rights_status: 'PUBLIC_EMBED_ONLY',
        evidence_tier: 'TIER_B',
        exact_card_status: 'CONFIRMED_UT_CARDS',
        review_status: 'REGISTERED'
      },
      {
        video_id: 'VID-004',
        source_url: 'https://www.youtube.com/watch?v=wWCrfSFlMmI',
        platform: 'YOUTUBE',
        title: 'FC27 Future Stars Thompson — RB Gameplay Review',
        creator_name: '48hrss',
        publication_date: '2026-10-12',
        game_version: 'FC27',
        game_patch: 'PATCH_1.02',
        video_type: 'CARD_REVIEW',
        duration_seconds: 780,
        rights_status: 'PUBLIC_EMBED_ONLY',
        evidence_tier: 'TIER_C',
        exact_card_status: 'EXACT_CARD_VERIFIED_THOMPSON_88',
        review_status: 'REGISTERED'
      },
      {
        video_id: 'VID-012',
        source_url: 'local://datasets/controlled_experiments/EXP_ST_PRESS_001_MATCH_A.mp4',
        platform: 'LOCAL_STORAGE',
        title: 'Controlled Experiment Trial 01 — Dembélé High Press vs AI Legend',
        creator_name: 'Project Engineering Team',
        publication_date: '2026-11-20',
        game_version: 'FC27',
        game_patch: 'PATCH_1.04',
        video_type: 'CONTROLLED_COMPARISON',
        duration_seconds: 720,
        rights_status: 'PROJECT_OWNED',
        evidence_tier: 'TIER_A',
        exact_card_status: 'EXACT_CARDS_CONTROLLED_STUDY',
        review_status: 'ACCEPTED_FOR_CV'
      },
      {
        video_id: 'VID-013',
        source_url: 'local://datasets/controlled_experiments/EXP_ST_PRESS_001_MATCH_B.mp4',
        platform: 'LOCAL_STORAGE',
        title: 'Controlled Experiment Trial 02 — Mbappé High Press vs AI Legend',
        creator_name: 'Project Engineering Team',
        publication_date: '2026-11-20',
        game_version: 'FC27',
        game_patch: 'PATCH_1.04',
        video_type: 'CONTROLLED_COMPARISON',
        duration_seconds: 720,
        rights_status: 'PROJECT_OWNED',
        evidence_tier: 'TIER_A',
        exact_card_status: 'EXACT_CARDS_CONTROLLED_STUDY',
        review_status: 'ACCEPTED_FOR_CV'
      }
    ]));
  } else if (url.includes('/api/research/prediction-challenges')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify([
      {
        challenge_id: 'PRED-CHALLENGE-001',
        hypothesis_code: 'HYP-RULE-HP-FWD-DEF',
        title: 'High Press Forward Defending Disruption',
        description: 'Evaluates whether Dembélé (55 Def) produces higher turnovers/90 than Mbappé (29 Def) in High Press.',
        v321_prediction_summary: 'RULE-HP-FWD-DEF imposes -0.025 friction penalty on forwards with Defending < 40 in High Press.',
        expected_direction: 'Dembélé turnover winning rate exceeds Mbappé by >= +1.5/90',
        candidate_card_a_name: 'Ousmane Dembélé (86)',
        candidate_card_b_name: 'Kylian Mbappé (91)',
        tactical_profile: 'HIGH_PRESS',
        evaluation_metric: 'turnovers_forced_per_90',
        status: 'EMPIRICALLY_CONFIRMED',
        observed_delta: 2.5,
        p_value: 0.018,
        conclusion: 'Confirmed: Dembélé achieved 4.8 turnovers/90 vs 2.3 for Mbappé (Delta = +2.5/90, p = 0.018).'
      }
    ]));
  } else if (url.includes('/api/research/fc27/performance/items/')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      card: {
        card_item_id: '97aaac8f-1616-50a0-afea-fd8aeff337ce',
        source_item_id: 'MBAPPE-01',
        name: 'Kylian Mbappé',
        rank: 1,
        cohort: 'TOP_100',
        overall: 91,
        primary_position: 'ST',
        positions: ['ST', 'LW'],
        identity_status: 'CONFIRMED',
        reviewed_match_count: 0,
        reviewed_note_count: 0,
        attributes: { pace: 97, shooting: 90, passing: 80, dribbling: 92, defending: 36, physicality: 78 },
        snapshot_date: '2026-09-20',
        base_player_id: 'player-mbappe',
        candidate_base_player_id: 'player-mbappe',
        playstyles: { base: ['Rapid', 'Quick Step'], plus: ['Trickster+'] },
        editorial_role_fit: 'Poacher'
      },
      official_ratings_reference: {
        source_url: 'https://www.ea.com/games/ea-sports-fc',
        accessed_on: '2026-09-20',
        rating: '91',
        primary_position: 'ST'
      },
      reviewed_evidence: [],
      compatible_match_count: 0,
      disputes: [],
      opinion_groups: [],
      discovery_queries: []
    }));
  } else if (url.includes('/api/research/fc27/performance')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      manifest: { version: 'fc27-perf-001', top_100: 2, position_control: 2 },
      cards: [
        {
          card_item_id: '97aaac8f-1616-50a0-afea-fd8aeff337ce',
          source_item_id: 'MBAPPE-01',
          name: 'Kylian Mbappé',
          rank: 1,
          cohort: 'TOP_100',
          overall: 91,
          primary_position: 'ST',
          positions: ['ST', 'LW'],
          identity_status: 'CONFIRMED',
          reviewed_match_count: 0,
          reviewed_note_count: 0
        },
        {
          card_item_id: 'dembele-55def-item-01',
          source_item_id: 'DEMBELE-01',
          name: 'Ousmane Dembélé',
          rank: 2,
          cohort: 'TOP_100',
          overall: 86,
          primary_position: 'ST',
          positions: ['ST', 'RW', 'LW'],
          identity_status: 'CONFIRMED',
          reviewed_match_count: 0,
          reviewed_note_count: 0
        }
      ],
      sources: [
        {
          source_key: 'EA_OFFICIAL_FC27_LAUNCH',
          title: 'EA SPORTS FC 27 Official Database Release',
          observation_type: 'CATALOG_RATINGS',
          source_url: 'https://www.ea.com/games/ea-sports-fc',
          access: 'PUBLIC',
          disposition: 'ARCHIVED'
        }
      ],
      formations: {
        '4-3-3': [
          { slot: 'ST', position: 'ST' },
          { slot: 'LW', position: 'LW' },
          { slot: 'RW', position: 'RW' }
        ]
      }
    }));
  } else if (url.includes('/api/research/fc27/cards/squad/preview') || url.includes('/api/research/fc27/cards/squad-lab/evaluate')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(mockEvalResult));
  } else if (url.includes('/api/research/fc27/cards')) {
    const cardItems = mockLineup.slots.map(s => s.item).filter(Boolean);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ items: cardItems, total: cardItems.length }));
  } else {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify([]));
  }
});

server.listen(8000, '127.0.0.1', () => {
  console.log('Mock Backend listening on http://127.0.0.1:8000');
});
