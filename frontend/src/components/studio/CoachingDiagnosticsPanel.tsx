import { Link } from 'react-router-dom'

export interface CoachingDiagnosticItem {
  diagnostic_id: string
  video_id: string
  code: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string
  category: string
  what_happened: string
  why_it_potentially_happened: string
  timestamp_start: number
  timestamp_end: number
  supporting_timestamps: number[]
  tactical_visualization: Record<string, any>
  confidence_level: 'HIGH' | 'MODERATE' | 'LOW' | string
  confidence_score: number
  alternative_decisions: string[]
  actionable_advice: string
  provenance: string
  evidence_caveats?: string[]
}

export interface PlayStyleReportItem {
  playstyle_name: string
  epistemic_state: 'EXPLICIT_HUD_OBSERVED' | 'BEHAVIOUR_CONSISTENT' | 'UNKNOWN_ACTIVATION' | string
  activation_claim_permitted: boolean
  observed_signature_count: number
  best_evidence_timestamps: number[]
  measured_metrics: Record<string, any>
  explanation: string
  provenance: string
}

export interface SquadCoachingPlanData {
  video_id: string
  game_version: string
  provenance: string
  status: string
  attributions: {
    diagnostic_code: string
    primary_cause: string
    secondary_causes: string[]
    tactical_first_prescription: string
    tactical_instruction_changes: string[]
    formation_adjustment?: string | null
    purchase_recommended: boolean
    provenance_gated: boolean
  }[]
  tactical_priority_summary: string[]
  capability_profiles: {
    target_position: string
    priority_attributes: Record<string, number>
    recommended_playstyles: string[]
    rationale: string
    intelligence_route: string
    discovery_route: string
    squad_lab_route: string
  }[]
  frozen_v321_untouched: boolean
}

interface Props {
  provenance: string
  diagnostics: CoachingDiagnosticItem[]
  playstyles: PlayStyleReportItem[]
  squadPlan: SquadCoachingPlanData | null
  onJumpToTimestamp: (timestampSec: number) => void
}

export function CoachingDiagnosticsPanel({
  provenance,
  diagnostics,
  playstyles,
  squadPlan,
  onJumpToTimestamp,
}: Props) {
  const isSynthetic = provenance === 'SYNTHETIC_FIXTURE'

  return (
    <section className="studio-panel" aria-label="Tactical Coaching and PlayStyle Intelligence">
      <div className="row space-between align-center flex-wrap gap05 mb03">
        <div>
          <h2 className="studio-panel-title">
            <span>Evidence-Grounded Tactical Coaching & Squad Integration</span>
            <span className={`badge sm ${isSynthetic ? 'warning' : 'lime'} font-mono`}>
              {provenance}
            </span>
          </h2>
          <p className="tiny text-secondary mb0">
            Causal match mistake diagnostics, conservative PlayStyle+ behavioural checks, and non-purchase-first Squad Lab prescriptions.
            Frozen V3.2.1 scoring weights remain unmodified.
          </p>
        </div>
        <span className="badge sm outline cyan font-mono">V3.2.1 Frozen Parity Active</span>
      </div>

      {isSynthetic && (
        <div className="callout warning tiny mb03">
          <strong>Synthetic Fixture Gate Active:</strong> Current source uses illustrative{' '}
          <code>SYNTHETIC_FIXTURE</code> telemetry. Squad capability upgrade recommendations are withheld
          until a real MP4/WebM match clip or imported tracking trace is analyzed.
        </div>
      )}

      {/* 1. Tactical Coaching Diagnostics */}
      <div className="mb04">
        <h3 className="section-title mb02">
          1. Match Tactical Mistake Diagnostics ({diagnostics.length})
        </h3>
        {diagnostics.length === 0 ? (
          <div className="p1 text-muted tiny" style={{ background: 'rgba(13,23,34,0.6)', borderRadius: 8 }}>
            No sustained tactical errors detected across current calibrated frames (or insufficient active gameplay footage).
          </div>
        ) : (
          <div className="stack gap05">
            {diagnostics.map((d) => (
              <article key={d.diagnostic_id} className="coaching-diag-card">
                <div className="row space-between align-center flex-wrap gap05 mb01">
                  <div className="row align-center gap05 flex-wrap">
                    <span
                      className={`badge sm ${
                        d.severity === 'HIGH' ? 'danger' : d.severity === 'MEDIUM' ? 'warning' : 'cyan'
                      }`}
                    >
                      {d.severity}
                    </span>
                    <strong className="text-white">{d.code.replace(/_/g, ' ')}</strong>
                    <span className="badge sm outline">{d.category}</span>
                  </div>
                  <div className="row align-center gap05">
                    <span className="badge sm font-mono">
                      Confidence: {d.confidence_level} ({(d.confidence_score * 100).toFixed(0)}%)
                    </span>
                    <button
                      type="button"
                      className="timestamp-jump-btn"
                      onClick={() => onJumpToTimestamp(d.timestamp_start)}
                    >
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style={{ marginRight: '0.3rem', verticalAlign: '-1px' }}>
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      {d.timestamp_start.toFixed(1)}s – {d.timestamp_end.toFixed(1)}s
                    </button>
                  </div>
                </div>

                <div className="grid-2col gap05 tiny mt02">
                  <div>
                    <div className="text-muted strong">What happened</div>
                    <div className="text-white">{d.what_happened}</div>
                    <div className="text-muted strong mt02">Why it potentially happened</div>
                    <div className="text-secondary">{d.why_it_potentially_happened}</div>
                  </div>
                  <div>
                    <div className="text-lime strong">Actionable Advice</div>
                    <div className="text-white">{d.actionable_advice}</div>
                    {d.alternative_decisions.length > 0 && (
                      <>
                        <div className="text-cyan strong mt02">Alternative Decisions</div>
                        <ul className="m0 pl1 text-secondary">
                          {d.alternative_decisions.map((alt, idx) => (
                            <li key={idx}>{alt}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                </div>

                {d.evidence_caveats && d.evidence_caveats.length > 0 && (
                  <div className="tiny text-muted mt02 font-mono">
                    Caveat: {d.evidence_caveats.join(' · ')}
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      {/* 2. Squad Lab Causal Attribution & Capability Profiles */}
      {squadPlan && (
        <div className="mb04">
          <h3 className="section-title mb02">
            2. Root-Cause Attribution & Squad Lab Integration (Tactics First)
          </h3>

          {squadPlan.tactical_priority_summary.length > 0 && (
            <div className="coaching-priority-box mb03">
              <strong className="text-lime">Top Non-Purchase Coaching Actions:</strong>
              <ul className="m0 pl1 tiny text-white mt01">
                {squadPlan.tactical_priority_summary.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {squadPlan.attributions.length > 0 && (
            <div className="audit-log-table-wrapper mb03">
              <table className="audit-log-table">
                <thead>
                  <tr>
                    <th>Diagnostic</th>
                    <th>Primary Root Cause</th>
                    <th>Tactical / Role Adjustment</th>
                    <th>Formation</th>
                  </tr>
                </thead>
                <tbody>
                  {squadPlan.attributions.map((attr, i) => (
                    <tr key={`${attr.diagnostic_code}-${i}`}>
                      <td className="font-mono text-cyan">{attr.diagnostic_code}</td>
                      <td><span className="badge sm outline lime">{attr.primary_cause}</span></td>
                      <td className="tiny text-white">
                        <div>{attr.tactical_first_prescription}</div>
                        {attr.tactical_instruction_changes.length > 0 && (
                          <div className="text-muted mt01">
                            Instructions: {attr.tactical_instruction_changes.join(' | ')}
                          </div>
                        )}
                      </td>
                      <td className="tiny">{attr.formation_adjustment ?? 'Keep Current'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {squadPlan.capability_profiles.length > 0 && (
            <div className="grid-2col gap05">
              {squadPlan.capability_profiles.map((prof, idx) => (
                <div key={idx} className="metric-box">
                  <div className="row space-between align-center">
                    <strong className="text-lime">Role Profile: {prof.target_position}</strong>
                    <span className="badge tiny outline">Optional Secondary Check</span>
                  </div>
                  <p className="tiny text-secondary mb01">{prof.rationale}</p>
                  <div className="row gap05 flex-wrap tiny font-mono mb02">
                    {Object.entries(prof.priority_attributes).map(([attr, val]) => (
                      <span key={attr} className="badge tiny cyan">{attr}: {val}+</span>
                    ))}
                    {prof.recommended_playstyles.map((ps) => (
                      <span key={ps} className="badge tiny outline">{ps}</span>
                    ))}
                  </div>
                  <div className="row gap05 flex-wrap">
                    <Link className="btn ghost sm" to={prof.intelligence_route}>
                      Evaluate in Intelligence
                    </Link>
                    <Link className="btn ghost sm" to={prof.discovery_route}>
                      Scout {prof.target_position}
                    </Link>
                    <Link className="btn ghost sm text-lime" to={prof.squad_lab_route}>
                      Open Squad Lab
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 3. PlayStyle+ Behavioural Signatures */}
      <div>
        <div className="row space-between align-center flex-wrap gap05 mb02">
          <h3 className="section-title mb0">
            3. Experimental PlayStyle+ Behavioural Signature Matrix
          </h3>
          <span className="tiny text-muted">
            Distinguishes explicit HUD icons from consistent movement kinematics
          </span>
        </div>
        <div className="audit-log-table-wrapper">
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>PlayStyle+</th>
                <th>Epistemic Classification</th>
                <th>Windows</th>
                <th>Evidence Notes (No Unverified Activation Claims)</th>
              </tr>
            </thead>
            <tbody>
              {playstyles.map((ps) => (
                <tr key={ps.playstyle_name}>
                  <td><strong className="text-white">{ps.playstyle_name}</strong></td>
                  <td>
                    <span
                      className={`badge sm ${
                        ps.epistemic_state === 'EXPLICIT_HUD_OBSERVED'
                          ? 'lime'
                          : ps.epistemic_state === 'BEHAVIOUR_CONSISTENT'
                          ? 'cyan'
                          : 'outline'
                      }`}
                    >
                      {ps.epistemic_state}
                    </span>
                  </td>
                  <td className="font-mono text-secondary">
                    {ps.observed_signature_count > 0 ? (
                      <button
                        type="button"
                        className="timestamp-jump-btn"
                        onClick={() => onJumpToTimestamp(ps.best_evidence_timestamps[0] ?? 0)}
                      >
                        {ps.observed_signature_count}× ({(ps.best_evidence_timestamps[0] ?? 0).toFixed(1)}s)
                      </button>
                    ) : (
                      '0'
                    )}
                  </td>
                  <td className="tiny text-secondary">{ps.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
