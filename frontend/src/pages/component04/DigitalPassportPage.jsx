import { useState } from 'react'
import Icon from '../../components/Icon'
import { Card, ErrorState, Link, LoadingState, PageHeader, StatCard } from '../../components/ui'
import { useLocation } from '../../lib/router'
import { useSettings } from '../../lib/settings'
import { endpoints, postJSON, useApi } from '../../services/api'

const emptyForm = { batch_id: '', event_type: 'Batch created', location: '', tea_grade: '', quantity_kg: '', note: '' }
const eventTypes = ['Batch created', 'Collected', 'Processed', 'Quality checked', 'Packed', 'Exported', 'Received']
const [currentHost] = window.location.hostname.split('.')
const isPrivateHost = (host) => host === 'localhost' || host === '127.0.0.1' || host === '::1' || /^10\./.test(host) || /^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host)
const configuredSiteUrl = (import.meta.env.VITE_PUBLIC_SITE_URL || '').replace(/\/$/, '')
const activeOrigin = isPrivateHost(window.location.hostname) && /^\d+\.\d+\.\d+\.\d+$/.test(currentHost) ? `${window.location.protocol}//${currentHost}:5173` : window.location.origin
const emptyLedger = { passports: [], ledger_valid: true, ledger_records: 0 }

export default function DigitalPassportPage() {
  const settings = useSettings()
  const { query } = useLocation()
  const scannedBatchId = query.get('batch')
  const { data, error: loadError, loading, reload } = useApi(endpoints.passports)
  const ledger = data || emptyLedger
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [qrBatchId, setQrBatchId] = useState('')
  const [search, setSearch] = useState('')
  const [siteUrl, setSiteUrl] = useState(settings.passportSiteUrl || configuredSiteUrl || activeOrigin)

  async function addEvent(event) {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      await postJSON(endpoints.passportEvents, { ...form, quantity_kg: Number(form.quantity_kg), note: form.note || null }, 'Could not add traceability event')
      setForm({ ...emptyForm, batch_id: form.batch_id })
      setQrBatchId(form.batch_id)
      reload()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const visible = (scannedBatchId ? ledger.passports.filter((item) => item.batch_id === scannedBatchId) : ledger.passports)
    .filter((item) => !search || item.batch_id.toLowerCase().includes(search.toLowerCase()))
  const totalKg = ledger.passports.reduce((total, passport) => total + Number(passport.events.at(-1)?.quantity_kg || 0), 0)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Component 04 · Traceability"
        title="Tea Digital Passport"
        description="Create a batch record and append traceability events across processing and shipment. Each batch gets a scannable QR passport."
        note="Local prototype: a SHA-256 hash-linked append-only ledger, not a public or distributed blockchain network."
      />

      {!ledger.ledger_valid && <ErrorState message={`Hash chain verification failed at record ${ledger.broken_record}.`} />}

      <section className="stat-grid" aria-label="Ledger summary">
        <StatCard icon="shield" tone={ledger.ledger_valid ? 'green' : 'red'} label="Ledger integrity" value={!data ? '…' : ledger.ledger_valid ? 'Verified' : 'Integrity issue'} hint={`${ledger.ledger_records} records`} />
        <StatCard icon="package" tone="teal" label="Batch passports" value={ledger.passports.length} />
        <StatCard icon="refresh" tone="blue" label="Traceability events" value={ledger.passports.reduce((total, item) => total + item.events.length, 0)} />
        <StatCard icon="leaf" tone="amber" label="Latest recorded quantity" value={`${totalKg.toLocaleString()} kg`} hint="Sum of each batch's latest event" />
      </section>

      <Card number="1" title="Record a traceability event" description="Add the first event to create a passport, or append to an existing batch ID.">
        <label className="field passport-site-url"><span>Site address for QR scans</span><input type="url" required value={siteUrl} onChange={(event) => setSiteUrl(event.target.value)} placeholder="https://your-tea-site.example" /></label>
        <p className="field-hint">For another phone on this Wi-Fi, use your computer’s LAN address (for example http://192.168.1.20:5173). Outside your network, add the deployed public site address. You can save a default in <Link to="/settings">Settings</Link>.</p>
        <form className="form-grid" onSubmit={addEvent}>
          <div className="form-row">
            <label className="field"><span>Batch ID</span><input required minLength={3} maxLength={80} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} placeholder="e.g. LK-TEA-2026-001" list="known-batches" /><datalist id="known-batches">{ledger.passports.map((item) => <option key={item.batch_id} value={item.batch_id} />)}</datalist></label>
            <label className="field"><span>Traceability event</span><select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })}>{eventTypes.map((item) => <option key={item}>{item}</option>)}</select></label>
          </div>
          <div className="form-row is-three">
            <label className="field"><span>Location</span><input required minLength={2} maxLength={120} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Estate, factory, port" /></label>
            <label className="field"><span>Tea grade / product</span><input required maxLength={80} value={form.tea_grade} onChange={(e) => setForm({ ...form, tea_grade: e.target.value })} placeholder="e.g. OP1" /></label>
            <label className="field"><span>Quantity (kg)</span><input required type="number" min="0.01" step="0.01" value={form.quantity_kg} onChange={(e) => setForm({ ...form, quantity_kg: e.target.value })} /></label>
          </div>
          <label className="field"><span>Event note (do not enter personal or confidential data)</span><textarea rows={2} maxLength={500} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
          <button className="btn btn-primary" disabled={busy || !ledger.ledger_valid}><Icon name="shield" size={17} />{busy ? 'Adding record…' : 'Add signed-hash event to ledger'}</button>
        </form>
        <p className="field-hint">Production traceability needs access controls and a shared ledger deployment.</p>
      </Card>

      {error && <ErrorState message={error} />}
      {loadError && <ErrorState message={loadError} onRetry={reload} />}

      <Card
        number="2"
        title={scannedBatchId ? `Batch passport: ${scannedBatchId}` : 'Batch passports'}
        description={scannedBatchId ? 'Opened from a passport QR code.' : 'Every event is chained to the previous record hash.'}
        actions={scannedBatchId ? <Link className="btn btn-ghost btn-sm" to="/digital-passport">Show all batches</Link> : <input className="search-input" type="search" placeholder="Search batch ID…" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search batch ID" />}
      >
        {!data && loading ? <LoadingState compact label="Loading passports…" /> : ledger.passports.length === 0 ? <p className="field-hint">No batches recorded yet. Add the first event to create a passport.</p> : (
          <div className="passport-list">
            {visible.map((passport) => {
              const passportQrUrl = (download = false) => `${endpoints.passports}/qr?batch_id=${encodeURIComponent(passport.batch_id)}&base_url=${encodeURIComponent(siteUrl)}&download=${download}`
              return (
                <article className="passport-card" key={passport.batch_id}>
                  <div className="passport-title">
                    <div><p className="eyebrow">Batch passport</p><h3>{passport.batch_id}</h3></div>
                    <span className="chip">{passport.events.length} events · {passport.latest_event}</span>
                  </div>
                  <ol className="passport-events">
                    {passport.events.map((item) => (
                      <li className="passport-event" key={item.record_hash}>
                        <strong>{item.event_type}</strong>
                        <span>{item.location} · {item.tea_grade} · {Number(item.quantity_kg).toLocaleString()} kg</span>
                        {item.note && <span className="passport-note">{item.note}</span>}
                        <small>{new Date(item.timestamp).toLocaleString()} · hash {item.record_hash.slice(0, 16)}…</small>
                      </li>
                    ))}
                  </ol>
                  <div className="button-row">
                    <a className="btn btn-primary btn-sm" href={passportQrUrl(true)} download={`tea-passport-${passport.batch_id}.png`}><Icon name="download" size={15} />Download passport QR</a>
                    <button className="btn btn-secondary btn-sm" type="button" onClick={() => setQrBatchId(qrBatchId === passport.batch_id ? '' : passport.batch_id)}>{qrBatchId === passport.batch_id ? 'Hide QR' : 'Show QR'}</button>
                    <button className="btn btn-ghost btn-sm" type="button" onClick={() => { setForm({ ...emptyForm, batch_id: passport.batch_id }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Add event</button>
                  </div>
                  {qrBatchId === passport.batch_id && <div className="passport-qr-preview"><img src={passportQrUrl()} alt={`QR code linking to batch passport ${passport.batch_id}`} onError={(event) => { event.currentTarget.replaceWith(Object.assign(document.createElement('strong'), { className: 'qr-error', textContent: 'QR service unavailable — install backend dependencies (pip install -r requirements.txt).' })) }} /><p>Scan to open {siteUrl}/digital-passport?batch={passport.batch_id}</p></div>}
                </article>
              )
            })}
            {visible.length === 0 && !scannedBatchId && <p className="field-hint">No batch matches “{search}”.</p>}
            {scannedBatchId && !ledger.passports.some((item) => item.batch_id === scannedBatchId) && <p className="field-hint">Passport for batch {scannedBatchId} was not found in this ledger.</p>}
          </div>
        )}
      </Card>
    </div>
  )
}
