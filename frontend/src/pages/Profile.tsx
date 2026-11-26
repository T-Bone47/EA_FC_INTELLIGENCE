import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { useAction, useApi } from '../lib/useApi'
import { PlayerIdentity } from '../components/PlayerIdentity'
import { ErrorBox, Field } from '../components/common'
import { StadiumField, StadiumSelect } from '../components/StadiumControls'
import { dateTime } from '../lib/format'
import { POSITIONS, TACTICS } from '../intelligence/Intelligence'
import type { RecommendationOptions, StatedFootballStyle, StatedSquadPreferences } from '../intelligence/types'

interface Me {
  id: string
  email: string
  display_name: string | null
  role: string
  preferred_game_version: string | null
  preferences: Record<string, unknown> | null
  created_at: string | null
  last_login_at: string | null
}

export default function Profile() {
  const { user, refreshUser, logout, versions, notify } = useSession()
  const nav = useNavigate()
  const { hash } = useLocation()
  const settings = useRef<HTMLDivElement>(null)
  useEffect(() => { if (hash === '#account-settings') settings.current?.scrollIntoView() }, [hash])
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [preferred, setPreferred] = useState(user?.preferred_game_version ?? '')
  const [favouritePosition, setFavouritePosition] = useState(
    String((user?.preferences as any)?.favourite_position ?? ''))

  const style = user?.preferences?.football_style as StatedFootballStyle | undefined
  const [stylePosition, setStylePosition] = useState(style?.position ?? '')
  const [styleTactic, setStyleTactic] = useState(style?.tactical_profile ?? '')
  const [cardPrefs,setCardPrefs] = useState<StatedSquadPreferences>((user?.preferences?.card_squad as StatedSquadPreferences) ?? {})
  const options = useApi<RecommendationOptions>('/api/v3/options')

  const save = useAction(async () => {
    const me = await api.patch<Me>('/api/auth/me', {
      display_name: displayName.trim() || null,
      preferred_game_version: preferred || null,
      preferences: { ...(user?.preferences ?? {}),
                     favourite_position: favouritePosition || null, card_squad:cardPrefs,
                     football_style: { position: stylePosition || null, tactical_profile: styleTactic || null } },
    })
    await refreshUser()
    notify('ok', 'Profile updated.')
    return me
  })

  return (
    <div className="stack profile-workspace">
      <div className="card profile-hero">
        <PlayerIdentity name={user?.display_name || user?.email || ''} />
        <div className="profile-hero-meta">
          <h1 className="mb0">Profile</h1>
          {user?.display_name && <strong>{user.display_name}</strong>}
          <div className="sub small profile-hero-email">{user?.email}</div>
        </div>
      </div>

      <div className="overview-detail">
      <div className="card" id="account-settings" ref={settings}>
        <h2>Account and tactical preferences</h2>
        <div className="col">
          <Field label="Display name">
            <input className="input" maxLength={80} value={displayName}
                   onChange={(e) => setDisplayName(e.target.value)} />
          </Field>
          <StadiumField label="Preferred game version"
                        hint="Used as the default when you open the app. Versions are never mixed.">
            <StadiumSelect aria-label="Preferred game version" value={preferred} onChange={setPreferred}>
              <option value="">— no preference —</option>
              {versions.map((v) => (
                <option key={v.code} value={v.code}>
                  {v.code}
                </option>
              ))}
            </StadiumSelect>
          </StadiumField>
          <Field label="Favourite position" hint="Stored as a free preference; the engine never infers facts from it.">
            <input className="input" maxLength={5} style={{ maxWidth: 120 }}
                   value={favouritePosition} placeholder="e.g. CM"
                   onChange={(e) => setFavouritePosition(e.target.value.toUpperCase())} />
          </Field>
          <fieldset className="col">
            <legend>Stated football preferences</legend>
            <StadiumField label="Preferred intelligence position">
              <StadiumSelect aria-label="Preferred intelligence position" value={stylePosition} onChange={setStylePosition}>
                <option value="">No preference</option>
                {POSITIONS.map(position => <option key={position}>{position}</option>)}
              </StadiumSelect>
            </StadiumField>
            <StadiumField label="Preferred tactical style">
              <StadiumSelect aria-label="Preferred tactical style" value={styleTactic} onChange={setStyleTactic}>
                <option value="">No preference</option>
                {TACTICS.map(tactic => <option key={tactic}>{tactic}</option>)}
              </StadiumSelect>
            </StadiumField>
          </fieldset>
          <fieldset className="col gap04"><legend>Card squad preferences</legend>
            <StadiumField label="Preferred squad formation">
              <StadiumSelect aria-label="Preferred squad formation" value={cardPrefs.formation??''} onChange={val=>setCardPrefs({...cardPrefs,formation:val||null,preferred_slot:null})}>
                <option value="">No preference</option>{Object.keys(options.data?.formations??{}).map(f=><option key={f}>{f}</option>)}
              </StadiumSelect>
            </StadiumField>
            <StadiumField label="Preferred formation slot">
              <StadiumSelect aria-label="Preferred formation slot" value={cardPrefs.preferred_slot??''} onChange={val=>setCardPrefs({...cardPrefs,preferred_slot:val||null})}>
                <option value="">No preference</option>{options.data?.formations[cardPrefs.formation??'']?.map(s=><option key={s.slot}>{s.slot}</option>)}
              </StadiumSelect>
            </StadiumField>
            <div className="field">
              <label htmlFor="pref-card-ps">Preferred card PlayStyle+</label>
              <input id="pref-card-ps" className="input" maxLength={60} value={cardPrefs.playstyle_plus??''} onChange={e=>setCardPrefs({...cardPrefs,playstyle_plus:e.target.value||null})} placeholder="e.g. Finesse Shot+" />
            </div>
            <StadiumField label="Default upgrade mode">
              <StadiumSelect aria-label="Default upgrade mode" value={cardPrefs.upgrade??''} onChange={val=>setCardPrefs({...cardPrefs,upgrade:val||null})}>
                <option value="">Optimize lineup</option><option value="one">One replacement</option><option value="two">Two replacements</option><option value="minimum">Minimum change</option>
              </StadiumSelect>
            </StadiumField>
            <label className="checkbox"><input type="checkbox" checked={cardPrefs.continuity??true} onChange={e=>setCardPrefs({...cardPrefs,continuity:e.target.checked})}/> Retain incumbents on equal fit</label>
          </fieldset>
          <ErrorBox error={save.error} />
          <div className="row">
            <button className="btn primary" disabled={save.pending} onClick={() => save.run()}>
              {save.pending ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>

      <div className="stack">
      <section className="card"><h2>Saved work</h2><div className="row">
        <Link className="btn ghost" to="/squads">Saved squads</Link><Link className="btn ghost" to="/saved">Saved players</Link>
        <Link className="btn ghost" to="/cards/squad-lab">Research scenarios</Link></div></section>
      <div className="card">
        <h2>Session and security</h2>
        <dl className="kv small">
          <dt>Role</dt><dd><span className="badge">{user?.role ?? 'user'}</span></dd>
          <dt>Member since</dt><dd>{dateTime((user as any)?.created_at)}</dd>
          <dt>Last login</dt><dd>{dateTime((user as any)?.last_login_at)}</dd>
        </dl>
        <div className="row mt2">
          <button className="btn ghost sm" onClick={async () => { await logout(false); nav('/') }}>
            Log out (this device)
          </button>
          <button className="btn ghost sm danger"
                  onClick={async () => {
                    if (!window.confirm('Revoke ALL active sessions for this account?')) return
                    await logout(true); nav('/')
                  }}>
            Log out everywhere
          </button>
        </div>
        <div className="tiny faint mt1">
          Sessions are protected with signed revocable tokens; sign out across all devices anytime above.
          Self-service password reset email is not enabled on this instance.
        </div>
      </div>

      <div className="card">
        <h2>Feedback and research</h2>
        <p className="muted">Record fit feedback on eligible recommendations. Research availability depends on this instance and the workspace opt-in.</p>
        <div className="row gap05 flex-wrap"><Link className="btn ghost sm" to="/intelligence">Intelligence Studio</Link><Link className="btn ghost sm" to="/cards/performance">Evidence Lab</Link></div>
      </div>
      </div>
      </div>
    </div>
  )
}
