import { useState } from 'react'
import Icon from '../components/Icon'
import { Card, PageHeader, StatusPill } from '../components/ui'
import { clearLastEri, defaultSettings, markets, resetSettings, saveSettings, teaTypes, useLastEri, useSettings } from '../lib/settings'
import { endpoints, invalidate } from '../services/api'

const services = [
  ['Auction price model', endpoints.trainOutput],
  ['Export demand model', endpoints.exportDemand],
  ['Combined price model', endpoints.combinedAuctionPrice],
  ['Zone intelligence', endpoints.zoneIntelligence],
  ['Digital passport ledger', endpoints.passportVerify],
]

export default function SettingsPage() {
  const settings = useSettings()
  const lastEri = useLastEri()
  const [form, setForm] = useState(settings)
  const [message, setMessage] = useState('')
  const [checks, setChecks] = useState({})
  const [checking, setChecking] = useState(false)
  const dirty = JSON.stringify(form) !== JSON.stringify(settings)
  const update = (key) => (event) => setForm({ ...form, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value })

  function save(event) {
    event.preventDefault()
    saveSettings({ ...form, defaultCapacity: Number(form.defaultCapacity) || defaultSettings.defaultCapacity, passportSiteUrl: form.passportSiteUrl.trim().replace(/\/$/, '') })
    setMessage('Settings saved.')
  }

  function reset() {
    resetSettings()
    setForm(defaultSettings)
    setMessage('Settings restored to defaults.')
  }

  async function runChecks() {
    setChecking(true)
    const results = await Promise.all(services.map(async ([name, url]) => {
      const started = performance.now()
      try {
        const response = await fetch(url)
        const payload = await response.json().catch(() => ({}))
        const detail = response.ok ? (payload.valid === false ? 'Hash chain integrity issue' : 'Available') : payload.detail || `HTTP ${response.status}`
        return [name, { ok: response.ok && payload.valid !== false, detail, ms: Math.round(performance.now() - started) }]
      } catch (error) {
        return [name, { ok: false, detail: error.message, ms: Math.round(performance.now() - started) }]
      }
    }))
    setChecks(Object.fromEntries(results))
    setChecking(false)
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Platform · Settings" title="Settings" description="Manage your profile, planning defaults and platform data. Preferences are stored in this browser." />

      <form className="settings-grid" onSubmit={save}>
        <Card icon="user" title="Account" description="Your identity and role are managed by the administrator.">
          <p className="field-hint">Account profile and permissions are supplied by secure Google sign-in. Contact an administrator if your assigned role is incorrect.</p>
        </Card>

        <Card icon="settings" title="Planning defaults" description="Pre-filled in Export Readiness and Trade Insights.">
          <div className="form-grid">
            <div className="form-row">
              <label className="field"><span>Default destination market</span><select value={form.defaultMarket} onChange={update('defaultMarket')}><option value="">None</option>{markets.map(([name, flag]) => <option key={name} value={name}>{flag} {name}</option>)}</select></label>
              <label className="field"><span>Default tea type</span><select value={form.defaultTeaType} onChange={update('defaultTeaType')}>{teaTypes.map((tea) => <option key={tea}>{tea}</option>)}</select></label>
            </div>
            <label className="field"><span>Default monthly capacity (tonnes)</span><div className="input-suffix"><input type="number" min="0.1" step="0.1" required value={form.defaultCapacity} onChange={update('defaultCapacity')} /><span>tonnes</span></div></label>
            <label className="field"><span>Passport QR site address (optional)</span><input type="url" value={form.passportSiteUrl} onChange={update('passportSiteUrl')} placeholder="https://your-tea-site.example" /></label>
            <label className="toggle"><input type="checkbox" checked={form.notifications} onChange={update('notifications')} /><span className="toggle-track" aria-hidden="true" /><span>Show notifications in the top bar</span></label>
            <label className="toggle"><input type="checkbox" checked={form.animatedBackground} onChange={update('animatedBackground')} /><span className="toggle-track" aria-hidden="true" /><span>Animated tea-leaf background</span></label>
          </div>
        </Card>

        <div className="settings-actions">
          <button type="submit" className="btn btn-primary" disabled={!dirty}><Icon name="check" size={17} />Save settings</button>
          <button type="button" className="btn btn-secondary" onClick={reset}>Restore defaults</button>
          {message && <span className="muted-line" role="status">{message}</span>}
        </div>
      </form>

      <div className="grid-2">
        <Card icon="refresh" title="System status" description="Check that each backend model output and service is reachable." actions={<button type="button" className="btn btn-secondary btn-sm" onClick={runChecks} disabled={checking}><Icon name="refresh" size={15} />{checking ? 'Checking…' : 'Run check'}</button>}>
          <ul className="status-list">
            {services.map(([name, url]) => {
              const result = checks[name]
              return (
                <li key={name}>
                  <div><strong>{name}</strong><small>{url}</small></div>
                  {result ? <span className="status-detail"><small>{result.detail} · {result.ms} ms</small><StatusPill ok={result.ok}>{result.ok ? 'Online' : 'Issue'}</StatusPill></span> : <span className="status-pill">Not checked</span>}
                </li>
              )
            })}
          </ul>
        </Card>

        <Card icon="doc" title="Data on this device" description="Cached API responses and saved assessments.">
          <ul className="status-list">
            <li>
              <div><strong>Cached model outputs</strong><small>Clear after retraining models so pages fetch fresh results.</small></div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => { invalidate(); setMessage('Cached data cleared. Pages will reload fresh results.') }}>Clear cache</button>
            </li>
            <li>
              <div><strong>Saved ERI assessment</strong><small>{lastEri ? `${lastEri.score}/100 · ${lastEri.destination_country} · ${new Date(lastEri.saved_at).toLocaleString()}` : 'None saved'}</small></div>
              <button type="button" className="btn btn-ghost btn-sm" disabled={!lastEri} onClick={() => { clearLastEri(); setMessage('Saved ERI assessment removed.') }}>Remove</button>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
