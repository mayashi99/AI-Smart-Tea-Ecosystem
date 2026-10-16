import { useCallback, useEffect, useState } from 'react'

const emptyForm = { batch_id: '', event_type: 'Batch created', location: '', tea_grade: '', quantity_kg: '', note: '' }
const scannedBatchId = new URLSearchParams(window.location.search).get('batch')
const qrUrl = (batchId, download = false) => `/api/component04/digital-passports/qr?batch_id=${encodeURIComponent(batchId)}&base_url=${encodeURIComponent(window.location.origin)}&download=${download}`

export default function DigitalPassportPage() {
  const [ledger, setLedger] = useState({ passports: [], ledger_valid: true, ledger_records: 0 })
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [qrBatchId, setQrBatchId] = useState('')
  const refresh = useCallback(async () => {
    const response = await fetch('/api/component04/digital-passports')
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || 'Could not load passports')
    setLedger(payload)
  }, [])
  useEffect(() => { refresh().catch((err) => setError(err.message)) }, [refresh])

  async function addEvent(event) {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/component04/digital-passports/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, quantity_kg: Number(form.quantity_kg), note: form.note || null }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not add traceability event')
      setForm({ ...emptyForm, batch_id: form.batch_id })
      setQrBatchId(form.batch_id)
      await refresh()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <main className="dashboard">
      <header className="dashboard-header"><div><p className="eyebrow">Component 04 · Traceability</p><h1>Tea Digital Passport</h1><p className="subtle">Create a batch record and append traceability events across processing and shipment.</p></div><div className="model-chip"><span>Ledger integrity</span><strong>{ledger.ledger_valid ? 'Verified' : 'Integrity issue'}</strong><span>{ledger.ledger_records} records</span></div></header>
      {!ledger.ledger_valid && <section className="panel advisor-error" role="alert">Hash chain verification failed at record {ledger.broken_record}.</section>}
      <section className="panel advisor-form-panel"><form className="advisor-form" onSubmit={addEvent}>
        <div className="advisor-input-row"><label><span>Batch ID</span><input required minLength={3} maxLength={80} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} placeholder="e.g. LK-TEA-2026-001" /></label><label><span>Traceability event</span><select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })}>{['Batch created', 'Collected', 'Processed', 'Quality checked', 'Packed', 'Exported', 'Received'].map((item) => <option key={item}>{item}</option>)}</select></label></div>
        <div className="advisor-input-row"><label><span>Location</span><input required minLength={2} maxLength={120} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Estate, factory, port" /></label><label><span>Tea grade / product</span><input required maxLength={80} value={form.tea_grade} onChange={(e) => setForm({ ...form, tea_grade: e.target.value })} placeholder="e.g. OP1" /></label><label><span>Quantity (kg)</span><input required type="number" min="0.01" step="0.01" value={form.quantity_kg} onChange={(e) => setForm({ ...form, quantity_kg: e.target.value })} /></label></div>
        <label><span>Event note (do not enter personal or confidential data)</span><textarea rows={2} maxLength={500} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
        <button className="advisor-submit" disabled={busy || !ledger.ledger_valid}>{busy ? 'Adding record…' : 'Add signed-hash event to ledger'}</button>
      </form><p className="advisor-note">This local prototype uses a SHA-256 hash-linked append-only ledger, not a public or distributed blockchain network. Production traceability needs access controls and a shared ledger deployment.</p></section>
      {error && <section className="empty-state advisor-error" role="alert">{error}</section>}
      <section className="passport-list"><h2>{scannedBatchId ? `Batch passport: ${scannedBatchId}` : 'Batch passports'}</h2>{ledger.passports.length === 0 ? <article className="panel"><p>No batches recorded yet. Add the first event to create a passport.</p></article> : (scannedBatchId ? ledger.passports.filter((item) => item.batch_id === scannedBatchId) : ledger.passports).map((passport) => <article className="panel passport-card" key={passport.batch_id}><div className="passport-title"><div><p className="eyebrow">Batch passport</p><h3>{passport.batch_id}</h3></div><span className="citation-chip">{passport.events.length} events · {passport.latest_event}</span></div><div className="passport-events">{passport.events.map((item) => <div className="passport-event" key={item.record_hash}><strong>{item.event_type}</strong><span>{item.location} · {item.tea_grade} · {Number(item.quantity_kg).toLocaleString()} kg</span><small>{new Date(item.timestamp).toLocaleString()} · hash {item.record_hash.slice(0, 16)}…</small></div>)}</div><a className="passport-qr-download" href={qrUrl(passport.batch_id, true)} download={`tea-passport-${passport.batch_id}.png`}>Download passport QR</a>{qrBatchId === passport.batch_id && <div className="passport-qr-preview"><img src={qrUrl(passport.batch_id)} alt={`QR code linking to batch passport ${passport.batch_id}`} /><p>Scan to open this batch passport.</p></div>}</article>)}{scannedBatchId && !ledger.passports.some((item) => item.batch_id === scannedBatchId) && <article className="panel"><p>Passport for batch {scannedBatchId} was not found in this ledger.</p></article>}</section>
    </main>
  )
}
