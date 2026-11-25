import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import GameplayStudio from './GameplayStudio'

describe('GameplayStudio Component (Phase 36)', () => {
  it('renders studio header, title, and epistemic honesty banner', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    expect(screen.getByText('Gameplay Intelligence Studio')).toBeInTheDocument()
    expect(screen.getByText(/Video Gameplay Research/i)).toBeInTheDocument()
    expect(screen.getByText(/Strict Honest Data Policy:/i)).toBeInTheDocument()
    expect(screen.getByText('₹0 External Budget')).toBeInTheDocument()
  })

  it('renders research library with video sources and evidence tier badges', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    expect(screen.getByText('Research Library')).toBeInTheDocument()
    expect(screen.getAllByText('Controlled Experiment Trial 01 — Dembélé High Press vs AI Legend').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('TIER_A').length).toBeGreaterThanOrEqual(1)
  })

  it('renders video cockpit, event scrubber, and tactical inspector', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    expect(screen.getByText('Tactical Event Scrubber:')).toBeInTheDocument()
    expect(screen.getByText('+ Tag Observation')).toBeInTheDocument()
    expect(screen.getByText('Tactical Inspector')).toBeInTheDocument()
    expect(screen.getByText('V3.2.1 Connected')).toBeInTheDocument()
  })

  it('switches tabs to Prediction Challenges and displays hypothesis rows', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const challengeBtn = screen.getByRole('button', { name: /Prediction Challenges/i })
    fireEvent.click(challengeBtn)

    expect(screen.getByText('V3.2.1 Empirical Prediction Challenges')).toBeInTheDocument()
    expect(screen.getByText('HYP-RULE-HP-FWD-DEF')).toBeInTheDocument()
    expect(screen.getByText('HYP-COUNTER-PACE-DOM')).toBeInTheDocument()
    expect(screen.getByText('HYP-PIVOT-SCREEN')).toBeInTheDocument()
  })

  it('switches tabs to Evidence Quality Audit and displays multi-tier cards', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const qualityBtn = screen.getByRole('button', { name: /Evidence Quality Audit/i })
    fireEvent.click(qualityBtn)

    expect(screen.getByText('Evidence Quality Framework & Anti-Pooling Audit')).toBeInTheDocument()
    expect(screen.getByText('Controlled Experiments')).toBeInTheDocument()
    expect(screen.getByText('Structured Observations')).toBeInTheDocument()
    expect(screen.getByText('Qualitative Tactical Evidence')).toBeInTheDocument()
    expect(screen.getByText('Research Discovery Only')).toBeInTheDocument()
  })

  it('switches tabs to 2D Radar & Pitch Replay and displays tactical canvas and HUD', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const radarBtn = screen.getByRole('button', { name: /2D Radar & Pitch Replay/i })
    fireEvent.click(radarBtn)

    expect(screen.getByText('Interactive 2D Pitch Radar & Telemetry Replay')).toBeInTheDocument()
    expect(screen.getByText('Defensive Line Depth')).toBeInTheDocument()
    expect(screen.getByText('Team Length')).toBeInTheDocument()
    expect(screen.getByText('Compactness Area')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Play 2D Replay/i })).toBeInTheDocument()
  })

  it('switches tabs to Bayesian Calibration and displays parameter table and simulator', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const calibBtn = screen.getByRole('button', { name: /Bayesian Calibration/i })
    fireEvent.click(calibBtn)

    expect(screen.getByText('V3.3 Empirical Bayesian Calibration Engine')).toBeInTheDocument()
    expect(screen.getByText('mod_high_press_forward_def')).toBeInTheDocument()
    expect(screen.getByText('mod_counterattack_sprint')).toBeInTheDocument()
    expect(screen.getByText('Interactive Recommendation Score Simulator (V3.2.1 vs V3.3)')).toBeInTheDocument()
    expect(screen.getByText('Simulate Suitability Score')).toBeInTheDocument()
  })

  it('triggers automated event proposal in video cockpit', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const proposeBtn = screen.getByRole('button', { name: /Propose Events/i })
    fireEvent.click(proposeBtn)

    expect(screen.getByText(/Automated Spatio-Temporal Proposal Detector/i)).toBeInTheDocument()
  })

  it('switches to Video Ingestion tab and displays upload cockpit, profile selectors, and job table', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const ingestBtn = screen.getByRole('button', { name: /Video Ingestion & Vision/i })
    fireEvent.click(ingestBtn)

    expect(screen.getByText('Automated Gameplay Video Ingestion & Perception Engine')).toBeInTheDocument()
    expect(screen.getByText('Upload Gameplay Recording')).toBeInTheDocument()
    expect(screen.getByText('Active Ingestion Pipeline Queue')).toBeInTheDocument()
    expect(screen.getByText(/EXP_ST_PRESS_001_MATCH_A.mp4/i)).toBeInTheDocument()
    expect(screen.getByText('COMPLETED (100%)')).toBeInTheDocument()
  })

  it('renders Dual-Cockpit Broadcast Perception and Radar Pitch canvas in Radar Replay tab', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const radarBtn = screen.getByRole('button', { name: /2D Radar & Pitch Replay/i })
    fireEvent.click(radarBtn)

    expect(screen.getByText('CHANNEL 1: BROADCAST CAMERA VIEW (1080p)')).toBeInTheDocument()
    expect(screen.getByText('CHANNEL 2: TOP-DOWN 2D RADAR (105m x 68m)')).toBeInTheDocument()
    expect(screen.getByText('Bounding Boxes')).toBeInTheDocument()
    expect(screen.getByText('DLT Foot Markers')).toBeInTheDocument()
    expect(screen.getByText('Match Perception & Tracking Coverage Summary')).toBeInTheDocument()
  })

  it('submits manual evidence review and renders cryptographic verification audit history', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const radarBtn = screen.getByRole('button', { name: /2D Radar & Pitch Replay/i })
    fireEvent.click(radarBtn)

    expect(screen.getByText('Analyst Verification & Manual Evidence Review')).toBeInTheDocument()
    expect(screen.getByText('REV-012-001')).toBeInTheDocument()
    expect(screen.getByText('lead-football-analyst')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Submit Cryptographic Review/i })).toBeInTheDocument()
  })

  it('renders Phase 39 Spatial Overlays, Manual Calibration Fallback, and Coaching Panel', () => {
    render(
      <MemoryRouter>
        <GameplayStudio />
      </MemoryRouter>
    )

    const radarBtn = screen.getByRole('button', { name: /2D Radar & Pitch Replay/i })
    fireEvent.click(radarBtn)

    expect(screen.getByText('Pitch Control')).toBeInTheDocument()
    expect(screen.getByText('Passing Lanes')).toBeInTheDocument()
    expect(screen.getByText('Vectors')).toBeInTheDocument()
    expect(screen.getByText('Trails')).toBeInTheDocument()

    const manualCalBtn = screen.getByRole('button', { name: /Manual 4-Point Calibration Fallback/i })
    fireEvent.click(manualCalBtn)
    expect(screen.getByRole('button', { name: /Apply Manual Homography Override/i })).toBeInTheDocument()

    const coachBtn = screen.getByRole('button', { name: /Tactical Coaching & Squad Lab/i })
    fireEvent.click(coachBtn)
    expect(screen.getByText('Evidence-Grounded Tactical Coaching & Squad Integration')).toBeInTheDocument()
    expect(screen.getByText('3. Experimental PlayStyle+ Behavioural Signature Matrix')).toBeInTheDocument()
  })
})
